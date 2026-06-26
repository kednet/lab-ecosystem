#!/usr/bin/env python3
"""
fetch_vk_posts.py — парсер постов VK через VK API.

Использование:
  python fetch_vk_posts.py --group pulabru --depth 200
  python fetch_vk_posts.py --group 237295798 --depth 500

Переменные окружения:
  VK_ACCESS_TOKEN  — токен доступа VK API
  VK_VERIFY_SSL    — false для корпоративного MITM (по умолчанию true)

Источник токена:
  1. Сам скрипт (--token)
  2. Переменная окружения VK_ACCESS_TOKEN
  3. C:\\Users\\kfigh\\publisher_skill\\.env (резерв)
  4. C:\\Users\\kfigh\\wish_librarian\\.env (резерв)

Выход: data/competitors/<group>/posts.json
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

# Force UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

# Подавляем предупреждения SSL для корпоративного MITM (если VK_VERIFY_SSL=false)
try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except ImportError:
    pass

import requests
from dotenv import load_dotenv

# Пути
SKILL_DIR = Path(__file__).parent.parent
DATA_DIR = SKILL_DIR / "data"
COMPETITORS_DIR = DATA_DIR / "competitors"

# Резервные пути к .env (для токенов других скилов)
ENV_FALLBACKS = [
    Path("C:/Users/kfigh/publisher_skill/.env"),
    Path("C:/Users/kfigh/wish_librarian/.env"),
    Path("C:/Users/kfigh/seo-advisor-skill/.env"),
    Path("C:/Users/kfigh/expert-reviews-hub/.env"),
    SKILL_DIR / ".env",  # Свой .env (если есть)
]


def load_env() -> Dict[str, str]:
    """Загрузить переменные окружения из .env файлов (с приоритетом своего)."""
    # Свой .env — первый
    for env_path in ENV_FALLBACKS:
        if env_path.exists():
            load_dotenv(env_path, override=False)  # override=False: не перезаписываем уже установленные
    return {k: v for k, v in os.environ.items() if v}


def resolve_group_id(group: str) -> int:
    """
    Разрешить ID группы. Может быть:
    - числовой ID (237295798)
    - короткое имя (pulabru, club237295798)
    """
    # Убираем возможные префиксы
    g = group.strip()
    if g.startswith("https://vk.com/"):
        g = g[len("https://vk.com/"):]
    if g.startswith("vk.com/"):
        g = g[len("vk.com/"):]
    if g.startswith("club"):
        g = g[4:]
    if g.startswith("public"):
        g = g[6:]

    # Если это число — возвращаем как int
    if g.lstrip("-").isdigit():
        return int(g)

    # Иначе — резолвим через API
    token = os.environ.get("VK_ACCESS_TOKEN", "")
    if not token:
        raise ValueError(f"Не удалось резолвить '{group}' в числовой ID без VK_ACCESS_TOKEN")

    api_version = "5.131"
    resp = requests.get(
        "https://api.vk.com/method/utils.resolveScreenName",
        params={
            "screen_name": g,
            "access_token": token,
            "v": api_version,
        },
        verify=os.environ.get("VK_VERIFY_SSL", "true").lower() != "false",
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    if "error" in data:
        raise ValueError(f"VK API error: {data['error']}")

    resolved = data.get("response", {})
    if not resolved or resolved.get("type") != "group":
        raise ValueError(f"Не удалось резолвить '{group}' как группу: {resolved}")

    return int(resolved["object_id"])


def vk_api_call(method: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Универсальный вызов VK API."""
    token = os.environ.get("VK_ACCESS_TOKEN", "")
    if not token:
        raise ValueError(
            "VK_ACCESS_TOKEN не найден. Установите переменную окружения "
            "или добавьте в .env (см. ENV_FALLBACKS в скрипте)."
        )

    api_version = "5.131"
    params = {
        **params,
        "access_token": token,
        "v": api_version,
    }

    verify_ssl = os.environ.get("VK_VERIFY_SSL", "true").lower() != "false"

    try:
        resp = requests.get(
            f"https://api.vk.com/method/{method}",
            params=params,
            verify=verify_ssl,
            timeout=30,
        )
        resp.raise_for_status()
    except requests.exceptions.SSLError as e:
        if verify_ssl:
            raise RuntimeError(
                f"SSL ошибка. Если корпоративный MITM — установите VK_VERIFY_SSL=false. "
                f"Оригинал: {e}"
            )
        raise

    data = resp.json()

    if "error" in data:
        err = data["error"]
        raise RuntimeError(f"VK API error: {err.get('error_code')} {err.get('error_msg')}")

    return data.get("response", {})


def fetch_posts(group_id: int, depth: int = 200) -> List[Dict[str, Any]]:
    """
    Тянет посты со стены сообщества.

    Возвращает список словарей с полями:
      - id, date, text, views, likes, reposts, comments
      - attachments (если есть)
      - is_pinned
    """
    all_posts = []
    offset = 0
    batch_size = 100  # VK API лимит за один запрос

    while len(all_posts) < depth:
        count = min(batch_size, depth - len(all_posts))
        print(f"[fetch] group={group_id} offset={offset} count={count}")

        response = vk_api_call("wall.get", {
            "owner_id": -group_id,  # минус = сообщество
            "count": count,
            "offset": offset,
            "filter": "owner",  # только от имени сообщества
            "extended": 0,
        })

        items = response.get("items", [])
        if not items:
            print(f"[fetch] Постов больше нет. Всего получено: {len(all_posts)}")
            break

        all_posts.extend(items)
        offset += len(items)

        # Rate limit
        time.sleep(0.4)  # ~3 req/sec, как в publisher_skill

        # Если получили меньше, чем просили — больше нет
        if len(items) < count:
            print(f"[fetch] Получено {len(items)} < {count}. Стоп.")
            break

    return all_posts[:depth]


def normalize_post(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Привести пост к нашему формату."""
    return {
        "id": raw.get("id"),
        "date": datetime.fromtimestamp(raw.get("date", 0)).isoformat() if raw.get("date") else None,
        "text": raw.get("text", ""),
        "views": raw.get("views", {}).get("count", 0) if isinstance(raw.get("views"), dict) else raw.get("views", 0),
        "likes": raw.get("likes", {}).get("count", 0) if isinstance(raw.get("likes"), dict) else raw.get("likes", 0),
        "reposts": raw.get("reposts", {}).get("count", 0) if isinstance(raw.get("reposts"), dict) else raw.get("reposts", 0),
        "comments": raw.get("comments", {}).get("count", 0) if isinstance(raw.get("comments"), dict) else raw.get("comments", 0),
        "is_pinned": bool(raw.get("is_pinned", 0)),
        "attachments_count": len(raw.get("attachments", [])),
        "has_photo": any(a.get("type") == "photo" for a in raw.get("attachments", [])),
        "has_video": any(a.get("type") == "video" for a in raw.get("attachments", [])),
        "has_link": any(a.get("type") == "link" for a in raw.get("attachments", [])),
        "post_type": raw.get("post_type", "post"),
    }


def save_posts(group: str, group_id: int, posts: List[Dict[str, Any]], output: Path) -> None:
    """Сохранить посты в JSON."""
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": "1.0",
        "group": group,
        "group_id": group_id,
        "fetched": datetime.now().isoformat(),
        "count": len(posts),
        "posts": posts,
    }
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[save] {len(posts)} постов → {output}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Парсер постов VK через VK API")
    parser.add_argument("--group", type=str, required=True,
                        help="ID группы, короткое имя (pulabru), или URL (https://vk.com/pulabru)")
    parser.add_argument("--depth", type=int, default=200,
                        help="Сколько постов тянуть (default: 200)")
    parser.add_argument("--output", type=str, default=None,
                        help="Куда сохранить (default: data/competitors/<group>/posts.json)")

    args = parser.parse_args()

    # Загружаем .env
    load_env()

    # Резолвим ID
    print(f"[resolve] '{args.group}' → ID...")
    try:
        group_id = resolve_group_id(args.group)
        print(f"[resolve] → {group_id}")
    except Exception as e:
        print(f"[error] {e}", file=sys.stderr)
        return 1

    # Куда сохранять
    if args.output:
        output = Path(args.output)
    else:
        # Используем короткое имя для папки (или ID, если было числом)
        folder = args.group.lstrip("-")
        if folder.startswith("https://vk.com/"):
            folder = folder[len("https://vk.com/"):]
        output = COMPETITORS_DIR / folder / "posts.json"

    # Тянем
    print(f"[fetch] depth={args.depth}")
    try:
        raw_posts = fetch_posts(group_id, args.depth)
    except Exception as e:
        print(f"[error] {e}", file=sys.stderr)
        return 1

    if not raw_posts:
        print(f"[info] Постов не получено. Файл {output} не создан.")
        return 0

    # Нормализуем
    posts = [normalize_post(p) for p in raw_posts]
    print(f"[normalize] {len(posts)} постов")

    # Сохраняем
    folder_name = output.parent.name
    save_posts(folder_name, group_id, posts, output)

    # Краткая статистика
    total_views = sum(p.get("views", 0) for p in posts)
    total_likes = sum(p.get("likes", 0) for p in posts)
    total_comments = sum(p.get("comments", 0) for p in posts)
    total_reposts = sum(p.get("reposts", 0) for p in posts)
    avg_er = ((total_likes + total_comments + total_reposts) / total_views * 100) if total_views > 0 else 0

    print(f"\n[stats] Сводка:")
    print(f"  Постов: {len(posts)}")
    print(f"  Просмотров: {total_views:,}")
    print(f"  Лайков: {total_likes:,}")
    print(f"  Комментов: {total_comments:,}")
    print(f"  Репостов: {total_reposts:,}")
    print(f"  Средний ER: {avg_er:.2f}%")

    return 0


if __name__ == "__main__":
    sys.exit(main())
