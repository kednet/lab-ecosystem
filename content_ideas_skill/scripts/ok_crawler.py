#!/usr/bin/env python3
"""
ok_crawler.py — парсер тематических лент Одноклассников через ATOM-фиды.

Использование:
  python ok_crawler.py --topic hobby --max 50
  python ok_crawler.py --topic hobby --all
  python ok_crawler.py --group 51819176984790  # требует OK_ACCESS_TOKEN (API)

Источники:
  1. ATOM-фиды тематических разделов (https://ok.ru/atom-feed/<topic>) — без авторизации
     Доступны: hobby, возможно другие
  2. Конкретная группа по ID — через OK API (нужен токен с scope GROUP_CONTENT)
     Документация: https://apiok.ru/

Выход:
  data/competitors/ok/<topic>-<date>.json
  data/competitors/ok/<topic>-<date>.md

Статус: v0.2 — ATOM-фид работает. OK API для конкретных групп — stub.
"""
import argparse
import json
import re
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

# Force UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

import urllib3
urllib3.disable_warnings()
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    import requests
except ImportError:
    print("[error] requests не установлен. pip install requests")
    sys.exit(1)

# Корпоративный прокси (см. memory/corporate-mitm-proxy.md)
def _load_env():
    import os
    for p in [
        Path(__file__).parent.parent / ".env",
        Path(__file__).parent.parent.parent / "publisher_skill" / ".env",
        Path(__file__).parent.parent.parent / "wish_librarian" / ".env",
        Path(__file__).parent.parent.parent / "expert-reviews-hub" / ".env",
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

# Прокси: SOCKS5 только если реально доступен
PROXIES = {}
try:
    import socket, socks
    s = socks.socksocket()
    s.settimeout(2)
    s.connect(("127.0.0.1", 10808))
    s.close()
    PROXIES = {"http": "socks5h://127.0.0.1:10808", "https": "socks5h://127.0.0.1:10808"}
    print("[proxy] SOCKS5 активен")
except Exception:
    PROXIES = {}
    print("[proxy] SOCKS недоступен, прямой доступ")

SKILL_DIR = Path(__file__).parent.parent
DATA_DIR = SKILL_DIR / "data"
COMPETITORS_DIR = DATA_DIR / "competitors" / "ok"
COMPETITORS_DIR.mkdir(parents=True, exist_ok=True)

# Каталог известных рабочих ATOM-фидов ОК
KNOWN_FEEDS = {
    "hobby": "https://ok.ru/atom-feed/hobby",
    # Другие разделы закрыты (404). Расширяется по мере обнаружения.
}

# Мусор-фильтр
JUNK_RE = re.compile(
    r"купить|заказать|реклама|акция|скидка|распродажа|"
    r"смотреть онлайн|фильм \d{4}|"
    r"порно|эротика|18\+|"
    r"\.ru|\.com|www\.",
    re.IGNORECASE,
)


def fetch_atom(url: str, timeout: int = 10) -> Dict[str, Any]:
    """GET ATOM-фид → dict {feed: {...}, entries: [{title, link, summary, author, published}]}"""
    try:
        r = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            timeout=timeout, verify=False, proxies=PROXIES or None,
        )
        r.raise_for_status()
        # ATOM XML namespaces
        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "dc": "http://purl.org/dc/elements/1.1/",
        }
        root = ET.fromstring(r.content)

        def _txt(elem_path: str) -> str:
            el = root.find(elem_path, ns)
            return (el.text or "").strip() if el is not None else ""

        feed = {
            "title": _txt("atom:title"),
            "subtitle": _txt("atom:subtitle"),
            "updated": _txt("atom:updated"),
        }
        entries = []
        for e in root.findall("atom:entry", ns):
            link = ""
            group_id = topic_id = None
            link_el = e.find("atom:link[@rel='alternate']", ns)
            if link_el is not None:
                link = link_el.get("href", "")
                m = re.search(r"/group/(\d+)/topic/(\d+)", link)
                if m:
                    group_id, topic_id = m.group(1), m.group(2)

            def _entry_txt(name: str) -> str:
                el = e.find(name, ns)
                return (el.text or "").strip() if el is not None else ""

            entries.append({
                "title": _entry_txt("atom:title"),
                "link": link,
                "summary": _entry_txt("atom:summary"),
                "author": _entry_txt("atom:author/atom:name"),
                "published": _entry_txt("atom:published"),
                "updated": _entry_txt("atom:updated"),
                "group_id": group_id,
                "topic_id": topic_id,
            })
        return {"feed": feed, "entries": entries}
    except Exception as e:
        print(f"  [error] {url}: {e}", file=sys.stderr)
        return {"feed": {}, "entries": []}


def is_junk(entry: Dict[str, Any]) -> bool:
    text = f"{entry.get('title','')} {entry.get('summary','')}"
    return bool(JUNK_RE.search(text)) or len(text) < 30


def render_md(feed_title: str, entries: List[Dict[str, Any]]) -> str:
    md = [
        f"# OK: {feed_title}",
        "",
        f"**Дата:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**Постов:** {len(entries)}",
        "",
    ]
    for i, e in enumerate(entries, 1):
        title = e.get("title", "").replace("\n", " ").strip()
        summary = e.get("summary", "").replace("\n", " ").strip()[:200]
        author = e.get("author", "")
        published = e.get("published", "")[:10]
        link = e.get("link", "")
        md.append(f"## {i}. {title}")
        md.append(f"**{author}** · {published}")
        if summary:
            md.append(f"\n> {summary}…\n")
        md.append(f"[→ пост]({link})")
        md.append("")
    return "\n".join(md)


def main() -> int:
    parser = argparse.ArgumentParser(description="Парсер тематических лент ОК")
    parser.add_argument("--topic", type=str, help="Тема (hobby, ...)")
    parser.add_argument("--all", action="store_true", help="Все известные темы")
    parser.add_argument("--max", type=int, default=50, help="Макс. постов на тему")
    parser.add_argument("--group", type=str, help="ID группы для API-парсинга (нужен OK_ACCESS_TOKEN)")
    parser.add_argument("--depth", type=int, default=1, help="Сколько страниц фида пройти (по 50)")
    args = parser.parse_args()

    if not (args.topic or args.all or args.group):
        print("[error] укажите --topic, --all или --group")
        print(f"        Доступные темы: {list(KNOWN_FEEDS.keys())}")
        return 1

    timestamp = datetime.now().strftime("%Y-%m-%d")

    if args.all or args.topic:
        topics = list(KNOWN_FEEDS.keys()) if args.all else [args.topic]
        if args.topic and args.topic not in KNOWN_FEEDS:
            print(f"[warn] тема '{args.topic}' не в каталоге, пробую напрямую...")
            topics = [args.topic]
        for topic in topics:
            url = KNOWN_FEEDS.get(topic, f"https://ok.ru/atom-feed/{topic}")
            print(f"[fetch] {topic}: {url}")
            all_entries = []
            for page in range(1, args.depth + 1):
                page_url = url if page == 1 else f"{url}?page={page}"
                data = fetch_atom(page_url)
                entries = data.get("entries", [])
                if not entries:
                    break
                all_entries.extend(entries)
                time.sleep(0.5)
            if not all_entries:
                print(f"  [warn] {topic}: пусто")
                continue
            # Фильтр мусора
            clean = [e for e in all_entries if not is_junk(e)][:args.max]
            print(f"  [ok] {len(clean)}/{len(all_entries)} постов (мусор отфильтрован)")
            # Сохранение
            slug = re.sub(r"[^a-z0-9]+", "-", topic.lower())[:30]
            json_path = COMPETITORS_DIR / f"ok-{slug}-{timestamp}.json"
            md_path = COMPETITORS_DIR / f"ok-{slug}-{timestamp}.md"
            json_path.write_text(
                json.dumps({
                    "topic": topic, "url": url, "fetched": datetime.now().isoformat(),
                    "feed_meta": data.get("feed", {}),
                    "count": len(clean),
                    "entries": clean,
                }, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            md_path.write_text(render_md(data.get("feed", {}).get("title", topic), clean), encoding="utf-8")
            print(f"  [save] → {json_path.name}")
            print(f"  [save] → {md_path.name}")
            # Топ-5
            print(f"\n  [top-5 заголовков]")
            for e in clean[:5]:
                print(f"    - {e['title'][:80]}")
            print()

    if args.group:
        print(f"[api] группа {args.group} — требует OK_ACCESS_TOKEN (пока stub)")
        print("  Чтобы парсить конкретную группу через API:")
        print("  1. Зарегистрируй приложение на https://apiok.ru/")
        print("  2. Получи токен с scope GROUP_CONTENT")
        print("  3. Положи в .env: OK_ACCESS_TOKEN=...")
        print("  4. Используй API: https://apiok.ru/wiki/groups/getGroupInfo")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
