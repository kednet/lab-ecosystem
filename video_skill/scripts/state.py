"""
state.py — идемпотентность Video Creator Skill v1.0.

Отличия от publisher_skill/scripts/state.py (2026-06-17):
- Путь: state/<profile>/<slug>.json (а не state/<slug>.json)
- Поле `profile: str` (рядом с slug)
- Расширенный набор статусов под 4 фазы

state/<profile>/<slug>.json:
{
  "slug": "5-oshibok-karty-zhelaniy",
  "profile": "lab",
  "status": "draft | script_ready | fetched | rendered | mixed | exported | published | failed",
  "title": "...",
  "created_at": "...",
  "script_at": "...", "script_path": "...",
  "fetched_at": null, "rendered_at": null, "mixed_at": null,
  "exported_at": null, "exported_path": null,
  "deployed_at": null, "live_url": null,
  "channels_posted": {"tg": null, "vk": null, "email": null, "ok": null, "zen": null},
  "channels_failed": [],
  "error": null
}

Конвенция вызова из CLI: slug передаётся в формате "<profile>/<slug>"
(см. video.py: state show lab/5-oshibok-karty-zhelaniy)
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Корень скила
SKILL_ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = SKILL_ROOT / "state"

# UTF-8 fix for Windows
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


def parse_slug_id(slug_id: str) -> tuple[str, str]:
    """'lab/5-oshibok' → ('lab', '5-oshibok'). Без '/' — ('_default', slug)."""
    if "/" in slug_id:
        profile, slug = slug_id.split("/", 1)
        return profile.strip(), slug.strip()
    return "_default", slug_id.strip()


def _state_path(profile: str, slug: str) -> Path:
    return STATE_DIR / profile / f"{slug}.json"


def load(slug_id: str) -> dict:
    """Загрузить state. slug_id: 'profile/slug' или 'slug' (default profile)."""
    profile, slug = parse_slug_id(slug_id)
    p = _state_path(profile, slug)
    if not p.exists():
        return _empty(profile, slug)
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[state] WARN: {p} повреждён: {e}. Создаю новый.", file=sys.stderr)
        return _empty(profile, slug)


def save(slug_id: str, data: dict) -> None:
    """Сохранить state."""
    profile, slug = parse_slug_id(slug_id)
    p = _state_path(profile, slug)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def update(slug_id: str, **kwargs) -> dict:
    """Обновить поля state (merge) и сохранить."""
    data = load(slug_id)
    data.update(kwargs)
    save(slug_id, data)
    return data


def mark_channel_posted(slug_id: str, channel: str) -> dict:
    """Пометить канал как отправленный."""
    data = load(slug_id)
    posted = data.get("channels_posted") or {}
    posted[channel] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    data["channels_posted"] = posted
    save(slug_id, data)
    return data


def mark_channel_failed(slug_id: str, channel: str, error: str) -> dict:
    """Добавить канал в failed."""
    data = load(slug_id)
    failed = data.get("channels_failed") or []
    failed.append({"channel": channel, "error": error, "at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")})
    data["channels_failed"] = failed
    data["status"] = "failed"
    data["error"] = error
    save(slug_id, data)
    return data


def reset(slug_id: str) -> dict:
    """Полный сброс state (для --force)."""
    profile, slug = parse_slug_id(slug_id)
    data = _empty(profile, slug)
    save(slug_id, data)
    return data


def is_published(slug_id: str) -> bool:
    return load(slug_id).get("status") == "published"


def channel_pending(slug_id: str, channel: str) -> bool:
    """Канал ещё не отправлен?"""
    data = load(slug_id)
    posted = data.get("channels_posted") or {}
    return posted.get(channel) is None


def list_all(profile: str | None = None) -> list[dict]:
    """Список всех state-файлов. Опционально фильтр по профилю."""
    if profile:
        d = STATE_DIR / profile
    else:
        d = STATE_DIR
    if not d.exists():
        return []
    out = []
    for p in sorted(d.glob("**/*.json")):
        try:
            with open(p, "r", encoding="utf-8") as f:
                out.append(json.load(f))
        except Exception:
            pass
    return out


def _empty(profile: str, slug: str) -> dict:
    return {
        "slug": slug,
        "profile": profile,
        "status": None,
        "title": None,
        "created_at": None,
        "script_at": None,
        "script_path": None,
        "fetched_at": None,
        "rendered_at": None,
        "mixed_at": None,
        "exported_at": None,
        "exported_path": None,
        "deployed_at": None,
        "live_url": None,
        "channels_posted": {"tg": None, "vk": None, "email": None, "ok": None, "zen": None},
        "channels_failed": [],
        "error": None,
    }


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Video Skill state manager")
    sub = p.add_subparsers(dest="cmd")

    show = sub.add_parser("show", help="Показать state")
    show.add_argument("slug_id", help="profile/slug или просто slug")

    list_p = sub.add_parser("list", help="Список всех state-файлов")
    list_p.add_argument("--profile", help="Фильтр по профилю")

    reset_p = sub.add_parser("reset", help="Сбросить state")
    reset_p.add_argument("slug_id")
    reset_p.add_argument("--force", action="store_true")

    mark = sub.add_parser("mark", help="Пометить канал")
    mark.add_argument("slug_id")
    mark.add_argument("channel", choices=["tg", "vk", "email", "ok", "zen"])
    mark.add_argument("status_str", choices=["posted", "failed"])
    mark.add_argument("--error", default="")

    args = p.parse_args()
    if args.cmd == "show":
        print(json.dumps(load(args.slug_id), ensure_ascii=False, indent=2))
    elif args.cmd == "list":
        for s in list_all(args.profile):
            print(f"{s.get('profile','?')}/{s.get('slug','?')}  →  {s.get('status','?')}")
    elif args.cmd == "reset":
        if not args.force:
            ans = input(f"Сбросить {args.slug_id}? (yes/no): ")
            if ans != "yes":
                print("Отменено.")
                sys.exit(0)
        reset(args.slug_id)
        print(f"Reset {args.slug_id}.")
    elif args.cmd == "mark":
        if args.status_str == "posted":
            mark_channel_posted(args.slug_id, args.channel)
        else:
            mark_channel_failed(args.slug_id, args.channel, args.error)
        print(f"{args.slug_id}.{args.channel} = {args.status_str}")
    else:
        p.print_help()
