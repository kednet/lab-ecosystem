#!/usr/bin/env python3
"""
trending_topics.py — сезонные тренды + инфоповоды.

Парсит:
  - sources/seasonal-calendar.md (формальные праздники РФ, темы, углы, анти-маркеры)
  - sources/trends-watchlist.md (методология типов трендов — даты не парсит, это ручной процесс)

Опционально LLM-обогащение: для каждой сезонной темы в горизонте генерирует
N идей (по разным рубрикам) в тоне ЛЖ и сохраняет в ideas-bank.json.

Использование:
  # Что в горизонте 30 дней (по дефолту)
  python trending_topics.py --source seasonal
  python trending_topics.py --source seasonal --horizon 14d

  # Конкретный месяц (планирование контента)
  python trending_topics.py --source seasonal --month 2026-10
  python trending_topics.py --source seasonal --month 2026-12 --generate-ideas --count 2

  # Все источники (сезонка + тренды-шаблоны)
  python trending_topics.py --source all --horizon 30d

  # Без LLM (только парсинг markdown)
  python trending_topics.py --source seasonal --offline

Выход:
  data/trending/seasonal-<period>.json   — детальный JSON
  data/trending/seasonal-<period>.md     — markdown-сводка
  (опц.) data/ideas-bank.json            — добавляются идеи через LLM при --generate-ideas

Статус: v0.2 — реальный парсинг seasonal-calendar.md + опц. LLM-обогащение.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

# Force UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

# Добавляем scripts/lib в sys.path для импорта llm_client
sys.path.insert(0, str(Path(__file__).parent / "lib"))

SKILL_DIR = Path(__file__).parent.parent
SOURCES_DIR = SKILL_DIR / "sources"
DATA_DIR = SKILL_DIR / "data"
TRENDING_DIR = DATA_DIR / "trending"
IDEAS_BANK = DATA_DIR / "ideas-bank.json"

SEASONAL_FILE = SOURCES_DIR / "seasonal-calendar.md"
TRENDS_FILE = SOURCES_DIR / "trends-watchlist.md"

MONTHS_RU = {
    "январь": 1, "января": 1, "февраль": 2, "февраля": 2, "март": 3, "марта": 3,
    "апрель": 4, "апреля": 4, "май": 5, "мая": 5, "июнь": 6, "июня": 6,
    "июль": 7, "июля": 7, "август": 8, "августа": 8, "сентябрь": 9, "сентября": 9,
    "октябрь": 10, "октября": 10, "ноябрь": 11, "ноября": 11, "декабрь": 12, "декабря": 12,
}


# ==== Парсинг seasonal-calendar.md ====

# Паттерн: "**1–8 января** — Новый год + каникулы"
# Или:    "**14 января** — Старый Новый год"
DATE_RE = re.compile(
    r"\*\*(?P<date>[\d–\-\sа-я]+)\s+(?P<month>[а-я]+)\*\*\s*[—–-]\s*(?P<title>.+?)(?=\n|$)",
    re.IGNORECASE,
)
# Паттерн: "- **Темы:** рефлексия, итоги года, ..."
LIST_RE = re.compile(r"^[-*]\s*\*\*(?P<key>[^*]+):\*\*\s*(?P<value>.+?)$", re.IGNORECASE)
# Паттерн: "  - Темы: ..."  (вложенный)
NESTED_LIST_RE = re.compile(r"^\s+[-*]\s*(?P<value>.+?)$")
SKIP_MARKERS = (
    "не трогаем",
    "не трогать",
    "пропускаем",
    "осторожно",
    "использовать с осторожностью",
)


def _parse_date_range(date_str: str, month: int, year: int) -> Tuple[datetime, datetime]:
    """Парсит "1–8" / "1-8" / "8" / "конец" / "начало" → (start, end)."""
    date_str = date_str.strip().lower()
    # Диапазон
    m = re.match(r"(\d+)\s*[–\-]\s*(\d+)", date_str)
    if m:
        d_start = int(m.group(1))
        d_end = int(m.group(2))
    else:
        m = re.match(r"(\d+)", date_str)
        if m:
            d_start = d_end = int(m.group(1))
        elif "конец" in date_str:
            d_start, d_end = 24, 31
        elif "начало" in date_str:
            d_start, d_end = 1, 10
        elif "перед" in date_str or "канун" in date_str:
            d_start, d_end = 28, 31
        else:
            d_start, d_end = 1, 28  # fallback

    # Защита от переполнения месяца
    from calendar import monthrange
    _, max_day = monthrange(year, month)
    d_start = min(max(d_start, 1), max_day)
    d_end = min(max(d_end, d_start), max_day)
    return (
        datetime(year, month, d_start),
        datetime(year, month, d_end),
    )


def _slug_anchor(date_range: Tuple[datetime, datetime], title: str) -> str:
    """Якорь для ссылки из markdown (#январь → '1-8-января-новый-год')."""
    months_genitive = {
        1: "января", 2: "февраля", 3: "марта", 4: "апреля", 5: "мая", 6: "июня",
        7: "июля", 8: "августа", 9: "сентября", 10: "октября", 11: "ноября", 12: "декабря",
    }
    d = date_range[0]
    slug = re.sub(r"[^\w\s-]", "", title.lower())
    slug = re.sub(r"\s+", "-", slug)[:40]
    return f"{d.day}-{months_genitive[d.month]}-{slug}"


def parse_seasonal_calendar(year: int = None) -> List[Dict[str, Any]]:
    """Распарсить seasonal-calendar.md → список тем."""
    if not SEASONAL_FILE.exists():
        print(f"[error] {SEASONAL_FILE} не найден")
        return []
    year = year or datetime.now().year
    text = SEASONAL_FILE.read_text(encoding="utf-8")
    lines = text.split("\n")

    topics: List[Dict[str, Any]] = []
    current_month: Optional[int] = None
    current_topic: Optional[Dict[str, Any]] = None

    for line in lines:
        # Заголовок месяца: "### Январь"
        m = re.match(r"^###\s+([А-Яа-я]+)\s*$", line)
        if m:
            month_name = m.group(1).strip().lower()
            current_month = MONTHS_RU.get(month_name)
            continue

        # Секция месяца: "## Дни психологического здоровья / терапии" — пропускаем,
        # т.к. это мета-категории без конкретных дат
        if line.startswith("## "):
            # Сохраняем последнюю текущую тему перед сбросом (если файл заканчивается
            # не на новой теме, а на секции — а иначе она потеряется)
            if current_topic:
                topics.append(current_topic)
            current_month = None
            current_topic = None
            continue

        if current_month is None:
            continue

        # Новая дата/праздник
        m = DATE_RE.search(line)
        if m:
            # Сохраняем предыдущий
            if current_topic:
                topics.append(current_topic)
            date_str = m.group("date").strip()
            month_name = m.group("month").strip().lower()
            title = m.group("title").strip()
            month_num = MONTHS_RU.get(month_name, current_month)
            try:
                date_range = _parse_date_range(date_str, month_num, year)
            except (ValueError, OverflowError):
                continue
            current_topic = {
                "title": title,
                "date_range": date_range,
                "month": month_num,
                "month_name": month_name,
                "date_str": f"{date_str} {month_name}",
                "themes": [],
                "lj_angle": "",
                "skip": False,
                "skip_reasons": [],
                "anchor": _slug_anchor(date_range, title),
            }
            continue

        # Поля темы (themes, lj_angle, antipattern) — следующие строки
        if current_topic is None:
            continue

        # Анти-маркеры
        lower_line = line.lower()
        for marker in SKIP_MARKERS:
            if marker in lower_line:
                current_topic["skip"] = True
                current_topic["skip_reasons"].append(line.strip())

        # Bullet-формат
        m = LIST_RE.match(line)
        if m:
            key = m.group("key").strip().lower()
            value = m.group("value").strip()
            if "темы" in key or "тема" in key:
                current_topic["themes"].append(value)
            elif "угол" in key or "лж" in key:
                current_topic["lj_angle"] = value
            continue

        # Вложенный bullet "- Темы: ..." (формат с одним тире, не **Темы:**)
        m = NESTED_LIST_RE.match(line)
        if m and not current_topic["lj_angle"]:
            value = m.group("value").strip()
            # Виды: "Темы: ...", "Угол: ...", "Угол ЛЖ: ..."
            vm = re.match(r"^(\*\*)?(Темы?|Угол(?:\s+ЛЖ)?|Тема)(?:\*\*)?:\s*(.+)$", value, re.IGNORECASE)
            if vm:
                key = vm.group(2).strip().lower()
                payload = vm.group(3).strip()
                if "угол" in key:
                    current_topic["lj_angle"] = payload
                else:
                    current_topic["themes"].append(payload)
            else:
                # Иначе — это просто тема (для формата "- Темы: ..." где value = "Темы: семья ...")
                if ":" in value:
                    # Похоже на "Ключ: значение", обработать
                    pass
                else:
                    # Просто текст — добавить в themes
                    current_topic["themes"].append(value)

    if current_topic:
        topics.append(current_topic)

    # Дополнительно: гарантируем сохранение последней темы (если файл закончился на новой теме)
    return topics


def parse_trends_templates() -> List[Dict[str, Any]]:
    """Распарсить trends-watchlist.md → шаблоны трендов (без дат, для ручной работы)."""
    if not TRENDS_FILE.exists():
        return []
    text = TRENDS_FILE.read_text(encoding="utf-8")
    templates: List[Dict[str, Any]] = []

    # Паттерн: "### 1. Выход новой книги / статьи"
    section_re = re.compile(
        r"^###\s+\d+\.\s+(?P<name>[^/]+?)(?:\s*/\s*(?P<extra>.+?))?$",
        re.MULTILINE,
    )
    for m in section_re.finditer(text):
        name = m.group("name").strip()
        extra = (m.group("extra") or "").strip()
        templates.append({
            "type": name,
            "example": extra,
            "checklist": [
                "Релевантно ЦА (женщины 25-45, психология желаний)?",
                "Не противоречит тону (не «успешный успех», не эзотерика)?",
                "Можем дать уникальный угол?",
                "Не политика / не религия / не «взрывоопасное»?",
                "Пост будет актуален минимум неделю?",
            ],
        })
    return templates


# ==== Фильтрация по горизонту ====

def filter_by_horizon(
    topics: List[Dict[str, Any]],
    horizon_days: int,
    reference_date: datetime = None,
) -> List[Dict[str, Any]]:
    """Оставить только темы в горизонте N дней от reference_date (default: сегодня)."""
    ref = reference_date or datetime.now()
    end_date = ref + timedelta(days=horizon_days)

    filtered = []
    for t in topics:
        start, end = t["date_range"]
        # Тема попадает в горизонт, если start в [ref, ref+horizon]
        # или end пересекается с [ref, ref+horizon]
        if start <= end_date and end >= ref:
            # Дней до начала
            days_until = (start - ref).days
            t = dict(t)
            t["days_until"] = days_until
            t["in_horizon"] = True
            filtered.append(t)
    return filtered


def filter_by_month(
    topics: List[Dict[str, Any]],
    year: int,
    month: int,
) -> List[Dict[str, Any]]:
    """Оставить темы в конкретном месяце."""
    filtered = []
    for t in topics:
        if t["month"] == month:
            t = dict(t)
            start, _ = t["date_range"]
            t["days_until"] = (start - datetime.now()).days
            t["in_horizon"] = True
            filtered.append(t)
    return filtered


# ==== LLM-обогащение: генерация идей из сезонной темы ====

def build_trend_prompt(topic: Dict[str, Any], target: str, count: int) -> str:
    """Промпт: превратить сезонную тему в N идей постов."""
    themes = "; ".join(topic.get("themes", [])) or "(темы не указаны)"
    angle = topic.get("lj_angle") or ""
    return f"""Сгенерируй РОВНО {count} идей постов для Лаборатории желаний (психологическое сообщество для женщин 25-45) на базе сезонной темы.

СЕЗОННАЯ ТЕМА: {topic['title']} ({topic['date_str']})
ТЕМЫ (из календаря): {themes}
УГОЛ ЛЖ: {angle if angle else '(придумай сама — наш тон, без эзотерики, без "успешного успеха")'}

ПЛОЩАДКА: {target}

Верни ТОЛЬКО валидный JSON-массив объектов:
[
  {{
    "title": "5-12 слов, цепляет, не кликбейт",
    "hook": "1-2 предложения, первая фраза поста",
    "key_idea": "1-2 предложения, О ЧЁМ пост",
    "rubric": "ОДНА из: разбор-цитаты, детектор, история, провокация, практика, миф-vs-правда, подборка",
    "structure_hint": "AIDA | PAS | storytelling | list | howto",
    "cta": "1-2 фразы. Вопрос, мягкое действие",
    "target_metric": "комменты | репосты | сохранения | переходы",
    "priority": "high | medium | low",
    "reasoning": "1 предложение, почему сработает (на какую боль ЦА)",
    "notes": "что НЕ писать"
  }}
]

ВАЖНО:
- Идеи должны быть ПРИВЯЗАНЫ к сезону, но НЕ предсказуемые (не «8 марта = поздравляю»)
- Учитывай наш угол: «а что ты на самом деле хочешь, когда все ждут валентинок?»
- Минимум 2 разных рубрики в выдаче
- Без эзотерики, без «узнайте», без «попробуйте»
"""


def generate_ideas_from_topic(
    topic: Dict[str, Any],
    client: Any,
    target: str,
    count: int,
) -> List[Dict[str, Any]]:
    """Сгенерировать идеи из сезонной темы через LLM."""
    prompt = build_trend_prompt(topic, target, count)
    try:
        response = client.generate(
            prompt,
            system="Ты контент-стратег Лаборатории желаний. Возвращаешь ТОЛЬКО JSON.",
            max_tokens=2500,
            temperature=0.7,
        )
    except Exception as e:
        print(f"  [warn] LLM ошибка для '{topic['title']}': {e}")
        return []

    parsed = _parse_llm_response(response)
    if not isinstance(parsed, list):
        return []
    return parsed


def _parse_llm_response(text: str) -> Any:
    """Парсер JSON из LLM-ответа (аналог extract_themes)."""
    if not text:
        return None
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```\s*$", "", t)
    t = t.strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass

    def find_balanced(s: str, open_ch: str, close_ch: str) -> Optional[str]:
        start = s.find(open_ch)
        if start == -1:
            return None
        depth = 0
        for i in range(start, len(s)):
            if s[i] == open_ch:
                depth += 1
            elif s[i] == close_ch:
                depth -= 1
                if depth == 0:
                    return s[start:i + 1]
        return None

    for open_ch, close_ch in [("[", "]"), ("{", "}")]:
        candidate = find_balanced(t, open_ch, close_ch)
        if candidate is None:
            continue
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None


def make_idea_id() -> str:
    import random
    return f"idea-{datetime.now().strftime('%Y-%m-%d')}-{random.randint(100000, 999999)}"


def build_idea_card(
    raw: Dict[str, Any],
    topic: Dict[str, Any],
    target: str,
    provider: str,
    model: str,
) -> Dict[str, Any]:
    """Превратить LLM-ответ в карточку ideas-bank.json."""
    title = (raw.get("title") or "").strip()
    if not title:
        return None
    hook = (raw.get("hook") or "").strip()
    rubric = raw.get("rubric") or "разбор-цитаты"
    import hashlib
    fp_raw = f"{title}|{rubric}|{hook[:50]}"
    fingerprint = hashlib.sha256(fp_raw.encode("utf-8")).hexdigest()[:16]
    return {
        "id": make_idea_id(),
        "created": datetime.now().isoformat(),
        "version": "1.0",
        "target": target,
        "rubric": rubric,
        "priority": raw.get("priority", "medium"),
        "title": title,
        "hook": hook,
        "key_idea": (raw.get("key_idea") or "").strip(),
        "structure_hint": raw.get("structure_hint", "storytelling"),
        "source": {
            "type": "seasonal",
            "ref": f"{topic['date_str']} — {topic['title']}",
            "reason": f"Сгенерировано из сезонной темы '{topic['title']}' (LLM {provider}/{model})",
        },
        "audience": "ca-zhelanii",
        "tone": "B3",
        "cta": (raw.get("cta") or "").strip(),
        "target_metric": raw.get("target_metric", "комменты"),
        "reasoning": (raw.get("reasoning") or "").strip(),
        "notes": (raw.get("notes") or "").strip(),
        "llm_provider": provider,
        "llm_model": model,
        "fingerprint": fingerprint,
    }


def save_ideas_to_bank(new_ideas: List[Dict[str, Any]]) -> int:
    """Сохранить новые идеи в ideas-bank.json (с дедупом по fingerprint)."""
    if not new_ideas:
        return 0
    if IDEAS_BANK.exists():
        bank = json.loads(IDEAS_BANK.read_text(encoding="utf-8"))
    else:
        bank = {"version": "1.0", "updated": None, "ideas": []}

    existing_fps = {i.get("fingerprint") for i in bank.get("ideas", [])}
    added = 0
    for idea in new_ideas:
        if idea["fingerprint"] in existing_fps:
            continue
        bank["ideas"].append(idea)
        added += 1
    bank["updated"] = datetime.now().isoformat()
    IDEAS_BANK.parent.mkdir(parents=True, exist_ok=True)
    IDEAS_BANK.write_text(
        json.dumps(bank, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return added


# ==== Сохранение / рендер ====

def save_trending(source: str, period: str, items: List[Dict[str, Any]], meta: Dict[str, Any]) -> Dict[str, Path]:
    """Сохранить JSON + Markdown."""
    TRENDING_DIR.mkdir(parents=True, exist_ok=True)
    paths: Dict[str, Path] = {}

    json_path = TRENDING_DIR / f"{source}-{period}.json"
    payload = {
        "version": "1.0",
        "source": source,
        "period": period,
        "fetched": datetime.now().isoformat(),
        "meta": meta,
        "count": len(items),
        "items": items,
    }
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    paths["json"] = json_path
    print(f"[save] → {json_path}")

    md_path = TRENDING_DIR / f"{source}-{period}.md"
    md_path.write_text(render_markdown(source, period, items, meta), encoding="utf-8")
    paths["md"] = md_path
    print(f"[save] → {md_path}")
    return paths


def render_markdown(source: str, period: str, items: List[Dict[str, Any]], meta: Dict[str, Any]) -> str:
    """Markdown-отчёт. Поддерживает 2 формата: seasonal (с датами) и trends (шаблоны)."""
    lines = [
        f"# {source.capitalize()}: {period}",
        "",
        f"**Дата:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**Горизонт:** {meta.get('horizon_days') or '—'}",
        f"**Тем в горизонте:** {len(items)}",
        "",
        "---",
        "",
    ]

    for t in items:
        # === Шаблоны трендов (без дат) ===
        if "type" in t and "checklist" in t:
            lines.append(f"## {t['type']}")
            if t.get("example"):
                lines.append(f"**Пример:** {t['example']}")
                lines.append("")
            lines.append("**Чек-лист адаптации:**")
            for item in t["checklist"]:
                lines.append(f"- [ ] {item}")
            lines.append("")
            lines.append("---")
            lines.append("")
            continue

        # === Сезонные темы (с датами) ===
        skip_badge = " ⛔" if t.get("skip") else ""
        days = t.get("days_until")
        days_str = f"+{days}д" if days is not None and days >= 0 else f"{days}д" if days is not None else ""
        lines.append(f"## {t['title']}{skip_badge}")
        lines.append(f"**Дата:** {t.get('date_str', '—')} ({days_str}) · **anchor:** `#{t.get('anchor', '')}`")
        lines.append("")
        if t.get("themes"):
            lines.append("**Темы:**")
            for th in t["themes"][:5]:
                lines.append(f"- {th}")
            lines.append("")
        if t.get("lj_angle"):
            lines.append(f"**Угол ЛЖ:** {t['lj_angle']}")
            lines.append("")
        if t.get("skip_reasons"):
            lines.append("**⛔ Skip reasons:**")
            for r in t["skip_reasons"]:
                lines.append(f"- {r}")
            lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


# ==== main ====

def main() -> int:
    parser = argparse.ArgumentParser(description="Сезонные тренды + инфоповоды")
    parser.add_argument("--source", type=str, default="seasonal",
                        choices=["seasonal", "trends", "all"],
                        help="Источник (default: seasonal)")
    parser.add_argument("--horizon", type=str, default="30d",
                        help="Горизонт в днях (например, 7d, 30d, 90d) — default: 30d")
    parser.add_argument("--month", type=str, default=None,
                        help="Конкретный месяц: YYYY-MM (например, 2026-10)")
    parser.add_argument("--year", type=int, default=None,
                        help="Год для парсинга (default: текущий)")
    parser.add_argument("--target", type=str, default="vk",
                        choices=["vk", "blog", "telegram"],
                        help="Площадка для --generate-ideas (default: vk)")
    parser.add_argument("--count", type=int, default=3,
                        help="Сколько идей генерировать на каждую тему при --generate-ideas (default: 3)")
    parser.add_argument("--include-skipped", action="store_true",
                        help="Не фильтровать ⛔-темы (НЕ трогаем / осторожно)")
    parser.add_argument("--generate-ideas", action="store_true",
                        help="Сгенерировать идеи в ideas-bank.json через LLM")
    parser.add_argument("--offline", action="store_true",
                        help="Без LLM (только парсинг markdown)")
    parser.add_argument("--output", type=str, default=None,
                        help="Доп. путь для JSON-результата")

    args = parser.parse_args()

    year = args.year or datetime.now().year

    # 1. Парсим seasonal-calendar.md
    print(f"[parse] {SEASONAL_FILE}")
    all_topics = parse_seasonal_calendar(year=year)
    print(f"[parse] Найдено {len(all_topics)} тем за {year} год")

    # 2. Фильтрация
    if args.month:
        m = re.match(r"(\d{4})-(\d{1,2})", args.month)
        if not m:
            print(f"[error] --month должен быть YYYY-MM, дано: {args.month}")
            return 1
        y_, m_ = int(m.group(1)), int(m.group(2))
        items = filter_by_month(all_topics, y_, m_)
        period = f"{y_}-{m_:02d}"
        meta = {"horizon_days": None, "year": y_, "month": m_}
    else:
        horizon_days = int(args.horizon.replace("d", ""))
        items = filter_by_horizon(all_topics, horizon_days)
        period = f"{horizon_days}d"
        meta = {"horizon_days": horizon_days, "year": year}

    # 3. Skip-фильтр
    if not args.include_skipped:
        before = len(items)
        items = [t for t in items if not t.get("skip")]
        skipped = before - len(items)
        if skipped:
            print(f"[filter] Отфильтровано {skipped} ⛔-тем (используйте --include-skipped чтобы увидеть)")

    # 4. Сортировка по дате
    items.sort(key=lambda t: t["date_range"][0])

    # 5. Сохранение
    if args.source in ("seasonal", "all"):
        paths = save_trending("seasonal", period, items, meta)
        if args.output:
            import shutil
            out_path = Path(args.output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(paths["json"], out_path)
            print(f"[copy] → {out_path}")

    # 6. Парсим trends-watchlist.md (шаблоны, без дат)
    if args.source in ("trends", "all"):
        templates = parse_trends_templates()
        print(f"[trends] Шаблонов трендов: {len(templates)}")
        if templates:
            save_trending("trends-templates", "all", templates, {"count": len(templates)})

    # 7. --generate-ideas (опц., LLM)
    if args.generate_ideas and items and not args.offline:
        try:
            from llm_client import LLMClient
            client = LLMClient()
            if not client.is_available():
                print(f"[warn] LLM недоступен (provider={client.provider}), пропускаю генерацию идей")
            else:
                print(f"[llm] Генерирую идеи через {client.provider}/{client.model}...")
                all_new_ideas: List[Dict[str, Any]] = []
                total = len(items)
                for i, topic in enumerate(items, 1):
                    print(f"  [{i}/{total}] {topic['title']} ({topic['date_str']})")
                    raw_ideas = generate_ideas_from_topic(topic, client, args.target, args.count)
                    for raw in raw_ideas:
                        card = build_idea_card(raw, topic, args.target, client.provider, client.model)
                        if card:
                            all_new_ideas.append(card)
                added = save_ideas_to_bank(all_new_ideas)
                print(f"[save] Добавлено {added} новых идей в {IDEAS_BANK}")
        except Exception as e:
            print(f"[warn] LLM-блок: {e}")

    # Сводка
    print()
    print("=" * 60)
    print(f"Готово. {args.source}: {len(items)} тем в горизонте '{period}'")
    if items:
        next_t = items[0]
        print(f"  Ближайшая: {next_t['title']} ({next_t['date_str']}, {next_t.get('days_until', 0):+d} дней)")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
