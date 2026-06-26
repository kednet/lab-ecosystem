#!/usr/bin/env python3
"""
suggest_crawler.py — краулер языка ЦА через Яндекс.Suggest (НЕ Вордстат, но ближе к живому
языку: что люди реально дописывают в поисковую строку, а не абстрактную частотность).

Использование:
  python suggest_crawler.py --seed "чего хочет женщина" --depth 2
  python suggest_crawler.py --seed "как загадать желание" --depth 3 --max 200
  python suggest_crawler.py --seeds-file sources/ca-queries.md --depth 2

Вход:  --seed "фраза"  или  --seeds-file path/to/file.md (по одной фразе на строку)
       --depth N (1-3): сколько раз «докручиваем» подсказки (depth=1 = только seed-уровень)
       --max M: макс. число уникальных фраз на выходе (защита от взрыва)

Процесс:
  1. Запрос к https://suggest.yandex.ru/suggest-ya.cgi?part=<seed>&uil=ru&v=4
  2. Берём top-10 подсказок (это «что ищут рядом с моим запросом»)
  3. Если depth > 1 — рекурсивно идём по каждой подсказке (на 2 уровне — сужаем тему)
  4. Сбор уникальных фраз + счётчик «встречаемости» (=сколько раз фразу увидели в разных ветках)
  5. Фильтр мусора (короткие, цифры, навигационные)
  6. Классификация через LLM: боль / вопрос / желание / тема-для-поста
  7. Сохранение

Выход:
  data/audience/suggest-<seed-slug>.{json,md}
  (опц.) обновление pain-language-bank.md — агрегатор фраз

Статус: v0.2 — рабочий. Без LLM (--offline) — без классификации, только сырой краул-вывод.
"""
import argparse
import json
import re
import sys
import time
import urllib.parse
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Set

# Force UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

# Corporate MITM: SSL verify off, urllib3 disable_warnings
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    import requests
except ImportError:
    print("[error] requests не установлен. pip install requests", file=sys.stderr)
    sys.exit(1)

SKILL_DIR = Path(__file__).parent.parent
DATA_DIR = SKILL_DIR / "data"
AUDIENCE_DIR = DATA_DIR / "audience"

# Подгружаем .env из соседних скилов (там могут быть прокси-настройки)
for env_path in [
    SKILL_DIR / ".env",
    SKILL_DIR.parent / "publisher_skill" / ".env",
    SKILL_DIR.parent / "wish_librarian" / ".env",
]:
    if env_path.exists():
        try:
            for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                if "=" in line and not line.strip().startswith("#"):
                    k, _, v = line.partition("=")
                    k, v = k.strip(), v.strip().strip("'\"")
                    if k and v and k not in os.environ if (os := __import__("os")) else True:
                        pass
        except Exception:
            pass

# === Загрузка .env проще ===
def _load_env():
    import os
    for p in [
        SKILL_DIR / ".env",
        SKILL_DIR.parent / "publisher_skill" / ".env",
        SKILL_DIR.parent / "wish_librarian" / ".env",
        SKILL_DIR.parent / "expert-reviews-hub" / ".env",
        SKILL_DIR.parent / "seo-advisor-skill" / ".env",
    ]:
        if p.exists():
            for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                k, v = k.strip(), v.strip().strip("'\"")
                if k and k not in os.environ:
                    os.environ[k] = v

_load_env()

# Прокси: пробуем SOCKS5 только если корпоративный (см. memory/corporate-mitm-proxy.md).
# НЕ переопределяем socket.socket глобально — это ломает прямой доступ, если SOCKS недоступен.
PROXIES = {}
try:
    import socket, socks  # type: ignore
    # Проверяем что SOCKS реально отвечает, иначе не используем
    s = socks.socksocket()
    s.settimeout(2)
    s.connect(("127.0.0.1", 10808))
    s.close()
    PROXIES = {"http": "socks5h://127.0.0.1:10808", "https": "socks5h://127.0.0.1:10808"}
    print("[proxy] SOCKS5 127.0.0.1:10808 активен")
except Exception:
    PROXIES = {}
    print("[proxy] SOCKS недоступен, прямой доступ")

SUGGEST_URL = "https://suggest.yandex.ru/suggest-ya.cgi"

# Мусор: цифры без контекста, навигационные, короткие, порно
JUNK_PATTERNS = [
    re.compile(r"^\d+$"),                           # только цифры
    re.compile(r"^[\W_]+$", re.UNICODE),            # только знаки
    re.compile(r"скачать|торрент|порно|секс в|эротика|видео", re.IGNORECASE),
    re.compile(r"\.com|\.ru|\.org|www\.", re.IGNORECASE),
    re.compile(r"^вк |^вконтакте|^ютуб|^tiktok|^инстаграм", re.IGNORECASE),
    re.compile(r"^купить|^цена|^стоимость|^заказать", re.IGNORECASE),
    # Мусор про фильм «Чего хотят женщины» (2006, Мэл Гибсон) и стихи
    re.compile(r"фильм|акт[её]ры|смотреть онлайн|в хорошем качестве", re.IGNORECASE),
    re.compile(r"песня|стих|валерий с[её]мин|синатра|мэл гибсон|автор слов", re.IGNORECASE),
    re.compile(r"^фильм \d{4}|^что хотят женщины$", re.IGNORECASE),
    re.compile(r" бесплатно|озвучка|дублированн|субтитр", re.IGNORECASE),
    # Празднично-бытовой мусор
    re.compile(r"на 8 марта|открытка|поздравлен|подарок на", re.IGNORECASE),
    # Песенно-кинематографическое
    re.compile(r"текст песни|клип|минусовка|аккорды", re.IGNORECASE),
]


def is_junk(phrase: str) -> bool:
    if len(phrase) < 4 or len(phrase) > 80:
        return True
    return any(p.search(phrase) for p in JUNK_PATTERNS)


def slugify(s: str) -> str:
    """Транслит для имени файла: 'чего хочет женщина' -> 'chego-hochet-zhenschina'"""
    translit = {
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
        "ж": "zh", "з": "z", "и": "i", "й": "i", "к": "k", "л": "l", "м": "m",
        "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
        "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
        "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    }
    out = []
    for ch in s.lower():
        out.append(translit.get(ch, ch))
    s = "".join(out)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:40]
    return s or "seed"


def fetch_suggest(query: str, timeout: int = 8) -> List[str]:
    """GET suggest.yandex.ru → JSON с подсказками."""
    try:
        r = requests.get(
            SUGGEST_URL,
            params={"part": query, "uil": "ru", "v": "4"},
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            timeout=timeout,
            verify=False,
            proxies=PROXIES or None,
        )
        r.raise_for_status()
        data = r.json()
        # Формат: ["query", ["sugg1", "sugg2", ...], {...metadata...}]
        if isinstance(data, list) and len(data) >= 2 and isinstance(data[1], list):
            return [s for s in data[1] if isinstance(s, str)]
    except Exception as e:
        print(f"  [warn] suggest fail для '{query[:50]}': {e}", file=sys.stderr)
    return []


def crawl(seeds: List[str], depth: int = 2, max_phrases: int = 200, delay: float = 0.3) -> Dict[str, int]:
    """
    Рекурсивный обход suggest-API.
    Возвращает: {фраза: сколько_раз_встретилась_в_разных_ветках}
    """
    counter: Counter = Counter()
    seen: Set[str] = set()
    queue: List[tuple] = [(s, 0) for s in seeds]

    while queue and len(counter) < max_phrases:
        query, level = queue.pop(0)
        if level > depth:
            continue
        if query in seen:
            continue
        seen.add(query)

        suggestions = fetch_suggest(query)
        time.sleep(delay)

        for sugg in suggestions:
            sugg_clean = sugg.strip()
            if is_junk(sugg_clean):
                continue
            if sugg_clean.lower() == query.lower():
                continue
            counter[sugg_clean] += 1
            # Идём глубже: берём первые 5 подсказок следующего уровня
            if level < depth and len(counter) < max_phrases:
                queue.append((sugg_clean, level + 1))

    return dict(counter.most_common(max_phrases))


def classify_with_llm(phrases: List[str]) -> Dict[str, List[str]]:
    """Классифицирует фразы через LLMClient: боль / вопрос / желание / тема-для-поста."""
    try:
        sys.path.insert(0, str(Path(__file__).parent / "lib"))
        from llm_client import LLMClient
        client = LLMClient()

        # Сгруппируем пачками по 30, чтобы не уйти в токены
        all_classified: Dict[str, List[str]] = {"боль": [], "вопрос": [], "желание": [], "тема-для-поста": []}
        for i in range(0, len(phrases), 30):
            batch = phrases[i:i + 30]
            prompt = f"""Классифицируй поисковые фразы ЦА Лаборатории желаний (психологическое сообщество для женщин 25-45).

Верни JSON-объект с 4 списками:
{{
  "боль": ["фразы, где звучит проблема или страдание"],
  "вопрос": ["фразы в форме вопроса или поиска совета"],
  "желание": ["фразы, где звучит мечта или хочу"],
  "тема-для-поста": ["нейтральные темы, на которые можно сделать пост ЛЖ"]
}}

Фразы:
{chr(10).join(f'- {p}' for p in batch)}

Одна фраза может попасть в 1-2 категории. Верни ТОЛЬКО JSON без пояснений."""

            try:
                resp = client.generate(prompt, max_tokens=2000, temperature=0.3)
                # Вытаскиваем JSON из ответа
                resp = resp.strip()
                if "```" in resp:
                    resp = re.sub(r"```\w*\n?", "", resp).strip()
                parsed = json.loads(resp)
                for k in all_classified:
                    vals = parsed.get(k, [])
                    if isinstance(vals, list):
                        all_classified[k].extend(vals)
            except Exception as e:
                print(f"  [warn] LLM classify batch {i}: {e}", file=sys.stderr)
        return all_classified
    except ImportError:
        return {}


def render_md(seed: str, phrases: Dict[str, int], classified: Dict[str, List[str]] = None) -> str:
    md = [f"# Suggest-краул: {seed}", ""]
    md.append(f"**Дата:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    md.append(f"**Уникальных фраз:** {len(phrases)}")
    md.append("")
    md.append("## Топ-30 фраз (по частотности встреч в дереве)")
    md.append("")
    for phrase, cnt in list(phrases.items())[:30]:
        md.append(f"- `{phrase}` ×{cnt}")
    if classified:
        md.append("")
        md.append("## Классификация LLM")
        for cat, items in classified.items():
            if items:
                md.append(f"### {cat} ({len(items)})")
                for p in items[:20]:
                    md.append(f"- {p}")
                md.append("")
    return "\n".join(md)


def update_pain_bank(phrases: Dict[str, int], source_seed: str):
    """Дописывает топ-фразы в audience-mining/pain-language-bank.md (если файл есть)."""
    bank_path = AUDIENCE_DIR / "pain-language-bank.md"
    if not bank_path.parent.exists():
        return
    # Создаём файл-агрегатор, если нет
    if not bank_path.exists():
        bank_path.write_text(
            "# Pain-language bank — агрегатор фраз ЦА\n\n"
            "Формируется из: mine_audience_pains.py, suggest_crawler.py.\n\n---\n\n",
            encoding="utf-8",
        )
    top = list(phrases.items())[:20]
    if not top:
        return
    block = [
        "",
        f"## Добавлено {datetime.now().strftime('%Y-%m-%d')} из suggest: `{source_seed}`",
        "",
    ]
    for phrase, cnt in top:
        block.append(f"- `{phrase}` ×{cnt}")
    block.append("")
    with bank_path.open("a", encoding="utf-8") as f:
        f.write("\n".join(block))
    print(f"[bank] +{len(top)} фраз в pain-language-bank.md")


def main() -> int:
    parser = argparse.ArgumentParser(description="Suggest-краулер языка ЦА через Яндекс.Suggest")
    parser.add_argument("--seed", type=str, help="Один seed-запрос (например, 'чего хочет женщина')")
    parser.add_argument("--seeds-file", type=str, help="Файл с seed-запросами (по одному на строку)")
    parser.add_argument("--depth", type=int, default=2, help="Глубина рекурсии (1-3)")
    parser.add_argument("--max", type=int, default=200, help="Макс. уникальных фраз")
    parser.add_argument("--offline", action="store_true", help="Не вызывать LLM-классификацию")
    parser.add_argument("--no-update-bank", action="store_true", help="Не обновлять pain-language-bank.md")
    args = parser.parse_args()

    seeds: List[str] = []
    if args.seed:
        seeds.append(args.seed.strip())
    if args.seeds_file:
        p = Path(args.seeds_file)
        if not p.exists():
            print(f"[error] {p} не найден")
            return 1
        seeds.extend([line.strip() for line in p.read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")])
    if not seeds:
        print("[error] нужен --seed или --seeds-file")
        return 1

    print(f"[crawl] {len(seeds)} seed(s), depth={args.depth}, max={args.max}")
    for s in seeds:
        print(f"  - {s}")

    # Тест connectivity
    test = fetch_suggest("тест")
    if not test:
        print("[error] suggest endpoint не отвечает. Проверь сеть/VPN.")
        return 1
    print(f"[ok] suggest endpoint работает ({len(test)} подсказок на 'тест')")

    # Краул
    phrases = crawl(seeds, depth=args.depth, max_phrases=args.max)
    print(f"[crawl] собрано {len(phrases)} уникальных фраз")

    # Классификация
    classified = {}
    if not args.offline:
        print("[llm] классифицирую фразы...")
        classified = classify_with_llm(list(phrases.keys())[:50])
        for k, v in classified.items():
            if v:
                print(f"  {k}: {len(v)} фраз")

    # Сохранение
    AUDIENCE_DIR.mkdir(parents=True, exist_ok=True)
    out_slug = slugify(seeds[0])
    json_path = AUDIENCE_DIR / f"suggest-{out_slug}.json"
    md_path = AUDIENCE_DIR / f"suggest-{out_slug}.md"

    json_path.write_text(
        json.dumps(
            {
                "seeds": seeds,
                "depth": args.depth,
                "fetched": datetime.now().isoformat(),
                "count": len(phrases),
                "phrases": [{"text": p, "weight": w} for p, w in phrases.items()],
                "classified": classified,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    md_path.write_text(render_md(seeds[0], phrases, classified), encoding="utf-8")
    print(f"[save] → {json_path}")
    print(f"[save] → {md_path}")

    if not args.no_update_bank:
        update_pain_bank(phrases, seeds[0])

    # Топ-10
    print("\n[top-10]")
    for p, c in list(phrases.items())[:10]:
        print(f"  {c:3d}× {p}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
