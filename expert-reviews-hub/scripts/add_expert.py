"""
add_expert.py
=============

Минимальный сборщик черновика карточки эксперта для /experts/ wizard.

Вход (через CLI):
  python scripts/add_expert.py "Марк Розин"                # name-режим
  python scripts/add_expert.py "https://www.youtube.com/watch?v=..."   # YT-режим
  python scripts/add_expert.py "..." --dry-run             # только показать план

Что делает:
  1. Определяет режим (name vs YouTube).
  2. Slug через _slugify (импорт из lab_site/python-service/loaders/experts.py).
  3. WebSearch (вызывается Claude Code, не здесь) → top-3 источников.
  4. WebFetch первого источника → bio/photo/socials.
  5. YouTube: yt_search_videos + transcript + YandexGPT → 1 цитата.
  6. Генерирует experts/{slug}.md по шаблону templates/expert-card.md.
  7. Валидирует через load_expert.

Не делает:
  ❌ Не выдумывает факты (если WebSearch ничего не дал — пустые поля).
  ❌ Не ищет 50 регалий (только базовый скелет).
  ❌ Не пишет в lab_site — это делает deploy_experts.py.

Подводные камни:
  - Корп. MITM → ssl._create_unverified_context() для всего внешнего HTTPS.
  - WL фабрика LLM опциональна — без неё пропускаем AI-суммаризацию.
  - youtube_transcript_api опциональна — без неё берём только метаданные видео.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import ssl
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# ── UTF-8 fix for Windows ─────────────────────────────────
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


# ── Корень skill ──────────────────────────────────────────
SKILL_ROOT = Path(__file__).resolve().parent.parent
EXPERTS_DIR = SKILL_ROOT / "experts"
TEMPLATE_PATH = SKILL_ROOT / "templates" / "expert-card.md"
ENV_PATH = SKILL_ROOT / ".env"


# ── Загрузка .env (простое чтение KEY=VALUE) ──────────────
def load_env() -> dict:
    env = {}
    if not ENV_PATH.exists():
        return env
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


ENV = load_env()
YOUTUBE_API_KEY = ENV.get("YOUTUBE_API_KEY", "")
YANDEX_API_KEY = ENV.get("YANDEX_API_KEY", "")
YANDEX_FOLDER_ID = ENV.get("YANDEX_FOLDER_ID", "")
AI_PROVIDER = ENV.get("AI_PROVIDER", "yandex")


# ── Импорт _slugify и load_expert из lab_site ──────────────
def _import_lab_site_helpers():
    """Импортирует _slugify и load_expert из lab_site/python-service.
    Бросает ImportError если lab_site не найден.
    """
    candidates = [
        SKILL_ROOT.parent / "lab_site" / "python-service",
        Path(r"C:\Users\kfigh\lab_site\python-service"),
    ]
    for p in candidates:
        if p.exists():
            sys.path.insert(0, str(p))
            try:
                from loaders.experts import _slugify, load_expert  # type: ignore
                return _slugify, load_expert
            except ImportError as e:
                print(f"⚠️ Не удалось импортировать из {p}: {e}", file=sys.stderr)
                continue
    raise ImportError(
        "Не найден lab_site/python-service/loaders/experts.py. "
        "Ожидается в C:\\Users\\kfigh\\lab_site\\python-service\\loaders\\"
    )


_slugify, _load_expert = _import_lab_site_helpers()


# ── Утилиты ───────────────────────────────────────────────
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def is_youtube_url(s: str) -> bool:
    return bool(re.match(r"^https?://(www\.|m\.)?(youtube\.com|youtu\.be)/", s.strip()))


def detect_mode(input_str: str) -> str:
    return "youtube" if is_youtube_url(input_str) else "name"


# ── YouTube: вытащить ID ─────────────────────────────────
def parse_youtube_url(url: str) -> dict:
    """Возвращает {'mode': 'video'|'channel', 'id': '...'} или бросает ValueError."""
    url = url.strip()
    # youtu.be/VIDEO_ID
    m = re.match(r"^https?://youtu\.be/([\w-]+)", url)
    if m:
        return {"mode": "video", "id": m.group(1)}
    # youtube.com/watch?v=VIDEO_ID
    parsed = urllib.parse.urlparse(url)
    qs = urllib.parse.parse_qs(parsed.query)
    if "v" in qs:
        return {"mode": "video", "id": qs["v"][0]}
    # youtube.com/@HANDLE
    m = re.match(r"^/@([\w.-]+)", parsed.path)
    if m:
        return {"mode": "channel_handle", "handle": m.group(1)}
    # youtube.com/channel/ID
    m = re.match(r"^/channel/([\w-]+)", parsed.path)
    if m:
        return {"mode": "channel", "id": m.group(1)}
    # youtube.com/c/HANDLE или /user/HANDLE
    m = re.match(r"^/(c|user)/([\w.-]+)", parsed.path)
    if m:
        return {"mode": "channel_handle", "handle": m.group(2)}
    raise ValueError(f"Не удалось распарсить YouTube-ссылку: {url}")


# ── YouTube API (как в parse_youtube.py) ─────────────────
def _yt_get(path: str, params: dict) -> dict:
    """Прямой GET к YouTube Data API v3. Без google-api-python-client.
    Паттерн из parse_youtube.py:157-175.
    """
    if not YOUTUBE_API_KEY:
        raise RuntimeError("YOUTUBE_API_KEY не задан в .env (expert-reviews-hub/.env)")

    params = {**params, "key": YOUTUBE_API_KEY}
    qs = urllib.parse.urlencode(params)
    url = f"https://www.googleapis.com/youtube/v3/{path}?{qs}"

    req = urllib.request.Request(url)
    ctx = ssl._create_unverified_context()  # обход корп. MITM
    with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
        return json.loads(resp.read().decode("utf-8"))


def yt_get_video(video_id: str) -> dict | None:
    """Получить метаданные одного видео."""
    data = _yt_get("videos", {"part": "snippet,statistics,contentDetails", "id": video_id})
    items = data.get("items", [])
    return items[0] if items else None


def yt_get_channel(channel_id: str) -> dict | None:
    """Получить метаданные канала по ID."""
    data = _yt_get("channels", {"part": "snippet,statistics", "id": channel_id})
    items = data.get("items", [])
    return items[0] if items else None


def yt_get_channel_by_handle(handle: str) -> dict | None:
    """Получить канал по @handle (нужен дляHandle)."""
    data = _yt_get("channels", {"part": "snippet,statistics", "forHandle": handle})
    items = data.get("items", [])
    return items[0] if items else None


def yt_search_videos(query: str, max_results: int = 5) -> list:
    """Поиск видео."""
    data = _yt_get("search", {
        "part": "id",
        "q": query,
        "type": "video",
        "maxResults": min(max_results, 10),
        "relevanceLanguage": "ru",
        "videoDuration": "medium",
        "order": "relevance",
    })
    video_ids = [item["id"]["videoId"] for item in data.get("items", [])]
    if not video_ids:
        return []
    videos_data = _yt_get("videos", {"part": "snippet,statistics,contentDetails", "id": ",".join(video_ids)})
    return videos_data.get("items", [])


def yt_get_transcript(video_id: str) -> list:
    """Получить транскрипт видео. Возвращает [] если недоступно."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        api = YouTubeTranscriptApi()
        snippets = api.fetch(video_id, languages=["ru", "en"])
        return [{"text": s.text, "start": s.start, "duration": s.duration} for s in snippets]
    except Exception as e:
        print(f"  ℹ Транскрипт {video_id} недоступен: {e}", file=sys.stderr)
        return []


def transcript_to_text(snippets: list, max_chars: int = 6000) -> str:
    lines, total = [], 0
    for s in snippets:
        ts = int(s["start"])
        m, sec = divmod(ts, 60)
        text = s["text"].replace("\n", " ").strip()
        line = f"[{m}:{sec:02d}] {text}"
        if total + len(line) > max_chars:
            lines.append(f"...[truncated at {total} chars]...")
            break
        lines.append(line)
        total += len(line)
    return "\n".join(lines)


# ── YandexGPT ─────────────────────────────────────────────
def _direct_yandexgpt(system: str, user: str) -> str:
    """Прямой вызов YandexGPT."""
    if not YANDEX_API_KEY or not YANDEX_FOLDER_ID:
        raise RuntimeError("YANDEX_API_KEY/YANDEX_FOLDER_ID не заданы в .env")
    url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
    payload = {
        "modelUri": f"gpt://{YANDEX_FOLDER_ID}/yandexgpt/latest",
        "completionOptions": {"stream": False, "temperature": 0.2, "maxTokens": 600},
        "messages": [{"role": "system", "text": system}, {"role": "user", "text": user}],
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Api-Key {YANDEX_API_KEY}"},
    )
    ctx = ssl._create_unverified_context()
    with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
        body = json.loads(resp.read().decode("utf-8"))
        return body["result"]["alternatives"][0]["message"]["text"]


def extract_quote_with_llm(name: str, transcript_text: str) -> dict | None:
    """Через YandexGPT вытащить 1 цитату из транскрипта.
    Возвращает {quote, context, year} или None если не получилось.
    """
    if not transcript_text:
        return None
    system = (
        "Ты — редактор карточек экспертов для сайта саморазвития. "
        "Из транскрипта видео выбери ОДНУ яркую цитату эксперта (1-2 предложения, до 200 слов), "
        "которая лучше всего раскрывает его/её подход. "
        "Верни ТОЛЬКО валидный JSON без markdown-обёрток:\n"
        '{"quote": "...", "context": "название видео или лекция или интервью", "year": 2024}'
    )
    user = f"Эксперт: {name}\n\nТранскрипт:\n{transcript_text}"

    # Пытаемся через WL-фабрику, fallback на прямой YandexGPT
    raw = None
    try:
        sys.path.insert(0, str(SKILL_ROOT.parent / "wish_librarian"))
        from agent.ai.factory import get_llm_client  # type: ignore
        client = get_llm_client(provider=AI_PROVIDER)
        response = client.generate(system=system, user=user, max_tokens=600, temperature=0.2)
        raw = response.text if hasattr(response, "text") else str(response)
    except Exception as e:
        print(f"  ℹ WL фабрика недоступна ({e}), прямой YandexGPT", file=sys.stderr)
        try:
            raw = _direct_yandexgpt(system, user)
        except Exception as e2:
            print(f"  ⚠️ Прямой YandexGPT тоже не сработал: {e2}", file=sys.stderr)
            return None

    if not raw:
        return None

    # Парсим JSON (могут быть ```json ... ```)
    raw_clean = raw.strip()
    if raw_clean.startswith("```"):
        raw_clean = re.sub(r"^```(?:json)?\s*\n?", "", raw_clean)
        raw_clean = re.sub(r"\n?```\s*$", "", raw_clean)

    try:
        data = json.loads(raw_clean)
        if isinstance(data, dict) and "quote" in data:
            return {
                "quote": str(data.get("quote", "")).strip(),
                "context": str(data.get("context", "")).strip(),
                "year": data.get("year"),
            }
    except Exception as e:
        print(f"  ⚠️ Не удалось распарсить JSON от LLM: {e}", file=sys.stderr)
        print(f"     raw: {raw[:200]}", file=sys.stderr)

    return None


# ── Парсинг bio со страницы (минимальный regex) ───────────
SOCIAL_PATTERNS = {
    "vk": re.compile(r"https?://vk\.com/[\w.-]+"),
    "telegram": re.compile(r"https?://t\.me/[\w.-]+"),
    "youtube": re.compile(r"https?://(www\.)?youtube\.com/[\w./@-]+"),
    "linkedin": re.compile(r"https?://(www\.)?linkedin\.com/in/[\w.-]+"),
}


def extract_socials(html: str) -> dict[str, str]:
    """Вытащить первую ссылку каждой соцсети из HTML/текста."""
    result = {}
    for platform, pattern in SOCIAL_PATTERNS.items():
        m = pattern.search(html)
        if m:
            result[platform] = m.group(0)
    return result


def extract_email(html: str) -> str:
    """Вытащить первый публичный email (mailto: или text)."""
    m = re.search(r'mailto:([\w.+-]+@[\w.-]+\.\w+)', html)
    if m:
        return m.group(1)
    m = re.search(r'([\w.+-]+@[\w.-]+\.\w+)', html)
    if m:
        return m.group(1)
    return ""


def fetch_page(url: str, timeout: int = 20) -> str:
    """Загрузить HTML страницы. Обход корп. MITM."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
        },
    )
    ctx = ssl._create_unverified_context()
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        raw = resp.read()
        # Пытаемся определить кодировку
        charset = "utf-8"
        m = re.search(rb'charset=["\']?([\w-]+)', raw[:1024])
        if m:
            try:
                charset = m.group(1).decode("ascii")
            except Exception:
                pass
        return raw.decode(charset, errors="replace")


# ── Генерация MD-черновика ────────────────────────────────
def build_expert_md(
    *,
    slug: str,
    name: str,
    job_title: str,
    description: str,
    image_url: str,
    url: str,
    email: str,
    same_as: list[str],
    knows_about: list[str],
    quote: str | None,
    quote_context: str,
    quote_year: int | None,
    tags: list[str],
) -> str:
    """Сгенерировать experts/{slug}.md по шаблону templates/expert-card.md."""

    # Schema.org JSON-LD
    schema = {
        "@context": "https://schema.org",
        "@type": "Person",
        "name": name,
        "jobTitle": job_title or "Эксперт",
        "url": url or "",
        "image": image_url or "",
        "email": email or "",
        "sameAs": same_as,
        "knowsAbout": knows_about,
    }
    schema = {k: v for k, v in schema.items() if v not in ("", [], None)}

    # Теги в frontmatter (список, НЕ inline)
    tags_yaml = "[" + ", ".join(f'"{t}"' for t in tags) + "]" if tags else "[]"

    # Цитата
    quote_block = ""
    if quote:
        year_part = f", {quote_year}" if quote_year else ""
        quote_block = f"> «{quote}»\n> — {quote_context or 'источник не указан'}{year_part}\n"

    # Медиа-блок (все найденные соцсети)
    media_lines = []
    for url_x in same_as:
        if "vk.com" in url_x:
            media_lines.append(f"- [ВКонтакте]({url_x})")
        elif "t.me" in url_x:
            media_lines.append(f"- [Telegram]({url_x})")
        elif "youtube.com" in url_x or "youtu.be" in url_x:
            media_lines.append(f"- [YouTube]({url_x})")
        elif "linkedin.com" in url_x:
            media_lines.append(f"- [LinkedIn]({url_x})")
        else:
            media_lines.append(f"- [{url_x}]({url_x})")
    media_block = "\n".join(media_lines) if media_lines else "- _нет данных — добавь вручную_"

    # SameAs для schema (как JSON-массив в одну строку)
    same_as_json = json.dumps(same_as, ensure_ascii=False)
    knows_about_json = json.dumps(knows_about, ensure_ascii=False)

    md = f"""---
slug: {slug}
type: expert
status: draft
generated_at: {now_iso()}
name: "{name}"
tags: {tags_yaml}
score: 0
---

# {name}

**{job_title or 'Эксперт'}**

> {description or '_краткое описание — добавь вручную_'}

![{name}]({image_url or ''})

## 📋 Основное

| Поле | Значение |
|------|----------|
| **ФИО** | {name} |
| **Должность / главная роль** | {job_title or '_заполни вручную_'} |
| **Сфера** | {', '.join(knows_about) if knows_about else '_заполни вручную_'} |
| **Специализация** | {', '.join(knows_about) if knows_about else '_заполни вручную_'} |
| **Сайт** | [{url or '_не указан_'}]({url or '#'}) |
| **Email** | {email or '_не указан_'} |

## 🎓 Образование и регалии

- _добавь вручную через `/experts edit {slug}`_

## 🎙️ Медиа

{media_block}

## 💬 Цитаты

{quote_block if quote_block else '> _добавь цитату вручную через `/experts edit {slug}`_'}

## 🔗 Связь с Лабораторией желаний

- **Книги в библиотеке WL:** _проверь через grep `C:\\Users\\kfigh\\wish_librarian\\output\\*\\summary.md`_
- **Совместные мероприятия:** _нет_

## Schema.org

```json
{json.dumps(schema, ensure_ascii=False, indent=2)}
```

## Источники

- WebSearch + WebFetch → {url or 'нет оф. сайта'}
- YouTube → {(same_as[0] if same_as else 'нет')}
"""
    return md


# ── Основной пайплайн ─────────────────────────────────────
def collect_name_mode(name: str) -> dict:
    """Name-режим: WebSearch → WebFetch → 1 цитата с YouTube.
    WebSearch/WebFetch делает Claude Code через tools.
    Здесь — только подготовка данных, которые вернёт Claude Code.
    """
    print(f"📝 Name-режим: ищу эксперта «{name}»", file=sys.stderr)
    print(f"  ⚠️ Этот скрипт не делает WebSearch/WebFetch сам.", file=sys.stderr)
    print(f"     Запусти его через Claude Code: /experts add \"{name}\"", file=sys.stderr)
    print(f"     Claude Code сделает WebSearch/WebFetch/YouTube и подставит данные.", file=sys.stderr)
    return {
        "name": name,
        "job_title": "",
        "description": "",
        "image_url": "",
        "url": "",
        "email": "",
        "same_as": [],
        "knows_about": [],
        "quote": None,
        "quote_context": "",
        "quote_year": None,
        "tags": [],
    }


def collect_youtube_mode(url: str) -> dict:
    """YT-режим: парсим URL → получаем метаданные канала/видео → 1 цитата."""
    print(f"📺 YouTube-режим: {url}", file=sys.stderr)

    if not YOUTUBE_API_KEY:
        print("  ⚠️ YOUTUBE_API_KEY не задан в .env — не могу получить метаданные.", file=sys.stderr)
        return {
            "name": "Unknown",
            "job_title": "",
            "description": "",
            "image_url": "",
            "url": url,
            "email": "",
            "same_as": [url],
            "knows_about": [],
            "quote": None,
            "quote_context": "",
            "quote_year": None,
            "tags": [],
        }

    info = parse_youtube_url(url)
    print(f"  Режим: {info}", file=sys.stderr)

    name = ""
    description = ""
    image_url = ""
    channel_url = url

    if info["mode"] == "video":
        video = yt_get_video(info["id"])
        if not video:
            print("  ⚠️ Видео не найдено", file=sys.stderr)
        else:
            snippet = video.get("snippet", {})
            name = snippet.get("channelTitle", "")
            description = snippet.get("description", "")[:300]
            channel_id = snippet.get("channelId")
            if channel_id:
                channel = yt_get_channel(channel_id)
                if channel:
                    c_snippet = channel.get("snippet", {})
                    name = c_snippet.get("title", name)
                    image_url = c_snippet.get("thumbnails", {}).get("high", {}).get("url", "")
                    channel_url = f"https://www.youtube.com/channel/{channel_id}"

            # Транскрипт → 1 цитата
            transcript = yt_get_transcript(info["id"])
            if transcript:
                text = transcript_to_text(transcript, max_chars=6000)
                quote_data = extract_quote_with_llm(name, text)
            else:
                quote_data = None
    else:
        # Channel (по ID или handle)
        channel = None
        if info["mode"] == "channel":
            channel = yt_get_channel(info["id"])
        elif info["mode"] == "channel_handle":
            channel = yt_get_channel_by_handle(info["handle"])

        if channel:
            c_snippet = channel.get("snippet", {})
            name = c_snippet.get("title", "")
            description = c_snippet.get("description", "")[:300]
            image_url = c_snippet.get("thumbnails", {}).get("high", {}).get("url", "")
            channel_id = channel.get("id")
            channel_url = f"https://www.youtube.com/channel/{channel_id}"
        quote_data = None

    return {
        "name": name or "Unknown",
        "job_title": "Автор YouTube-канала",
        "description": description or "",
        "image_url": image_url or "",
        "url": channel_url,
        "email": "",
        "same_as": [channel_url] if channel_url else [url],
        "knows_about": [],
        "quote": quote_data["quote"] if quote_data else None,
        "quote_context": quote_data["context"] if quote_data else "",
        "quote_year": quote_data["year"] if quote_data else None,
        "tags": ["youtube", "блогер"],
    }


# ── CLI ───────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser(
        description="add_expert.py — собрать мини-черновик карточки эксперта для /experts/ wizard"
    )
    p.add_argument("input", help='Имя эксперта или YouTube-ссылка (например, "Марк Розин" или "https://youtube.com/...")')
    p.add_argument("--dry-run", action="store_true", help="Только показать план, ничего не писать")
    p.add_argument("--overwrite", action="store_true", help="Перезаписать существующий draft")
    p.add_argument("--data-json", help="Готовые данные в JSON (имя, цитата, соцсети). Для использования из Claude Code.")

    args = p.parse_args()

    mode = detect_mode(args.input)
    print(f"🔍 Режим: {mode}")
    print(f"   Вход: {args.input}")

    # Если данные переданы напрямую через --data-json (от Claude Code)
    if args.data_json:
        data = json.loads(args.data_json)
    elif mode == "name":
        data = collect_name_mode(args.input)
    else:
        data = collect_youtube_mode(args.input)

    slug = _slugify(data["name"]) if data.get("name") else _slugify(args.input)
    print(f"   Slug: {slug}")

    out_path = EXPERTS_DIR / f"{slug}.md"
    if out_path.exists():
        print(f"  ⚠️ Файл уже существует: {out_path}")
        if not args.overwrite:
            print("     Используй --overwrite или /experts edit")
            sys.exit(1)

    md = build_expert_md(slug=slug, **data)

    if args.dry_run:
        print("\n" + "=" * 60)
        print("DRY-RUN: ничего не пишем")
        print(f"  План: создать {out_path} ({len(md)} символов, {md.count(chr(10))} строк)")
        print(f"  Slug: {slug}")
        print(f"  Status: draft")
        print("=" * 60)
        print("\nПервые 30 строк черновика:")
        print("-" * 60)
        print("\n".join(md.splitlines()[:30]))
        return

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md, encoding="utf-8")
    print(f"\n✅ Создан черновик: {out_path}")
    print(f"   Размер: {len(md)} символов, {md.count(chr(10))} строк")

    # Валидация через парсер lab_site
    print("\n🔍 Валидация через load_expert...")
    try:
        card = _load_expert(slug)
        if card is None:
            print("  ⚠️ Парсер не смог прочитать файл")
        else:
            print(f"  ✅ name: {card.name}")
            print(f"  {'✅' if card.jobTitle else '⚠️ '} jobTitle: {card.jobTitle or '(пусто)'}")
            print(f"  {'✅' if card.description else '⚠️ '} description: {(card.description or '')[:60] or '(пусто)'}")
            print(f"  {'✅' if card.image else '⚠️ '} image: {(card.image or '')[:60] or '(будет fallback-аватар)'}")
            print(f"  {'✅' if card.tags else '⚠️ '} tags: {card.tags or '(пусто)'}")
            print(f"  ✅ quotes: {len(card.quotes)} шт")
            print(f"  {'✅' if card.sameAs else '⚠️ '} sameAs: {len(card.sameAs)} ссылок")
            print(f"  ✅ schema_jsonld @type: {card.schema_jsonld.get('@type', '(нет)')}")
    except Exception as e:
        print(f"  ⚠️ Ошибка валидации: {e}")

    print("\n📋 Следующие шаги:")
    print(f"  1. Открой {out_path} и проверь что нашлось")
    print(f"  2. Скажи «правь <секция>» — поправлю точечно")
    print(f"  3. Скажи «готово» — переведу в status: published")
    print(f"  4. Скажи «деплой» — залью на https://app.pulab.ru/experts/")


if __name__ == "__main__":
    main()
