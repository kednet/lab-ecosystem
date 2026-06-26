"""
state.py — идемпотентность Publisher.

state/<slug>.json:
{
  "slug": "transerfing-realnosti",
  "status": "rendering | deploying | announcing | published | failed",
  "rendered_at": "...",
  "deployed_at": "...",
  "published_at": "...",
  "live_url": "...",
  "page_path": "...",
  "data_path": "...",
  "artifacts_dir": "...",
  "seo_path": "...",
  "preview_path": "...",
  "channels_posted": {"tg": null, "vk": null, "email": null},
  "channels_failed": [],
  "error": null
}
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Корень скила
SKILL_ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = SKILL_ROOT / "state"

# UTF-8 fix for Windows
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


def _state_path(slug: str) -> Path:
    return STATE_DIR / f"{slug}.json"


def load(slug: str) -> dict:
    """Загрузить state. Если нет — вернуть пустую заготовку."""
    p = _state_path(slug)
    if not p.exists():
        return _empty(slug)
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[state] WARN: {p} повреждён: {e}. Создаю новый.", file=sys.stderr)
        return _empty(slug)


def save(slug: str, data: dict) -> None:
    """Сохранить state."""
    p = _state_path(slug)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def update(slug: str, **kwargs) -> dict:
    """Обновить поля state (merge) и сохранить."""
    data = load(slug)
    data.update(kwargs)
    save(slug, data)
    return data


def mark_channel_posted(slug: str, channel: str) -> dict:
    """Пометить канал как отправленный."""
    data = load(slug)
    posted = data.get("channels_posted") or {}
    posted[channel] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    data["channels_posted"] = posted
    save(slug, data)
    return data


def mark_channel_failed(slug: str, channel: str, error: str) -> dict:
    """Добавить канал в failed."""
    data = load(slug)
    failed = data.get("channels_failed") or []
    failed.append({"channel": channel, "error": error, "at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")})
    data["channels_failed"] = failed
    data["status"] = "failed"
    data["error"] = error
    save(slug, data)
    return data


def reset(slug: str) -> dict:
    """Полный сброс state (для --force)."""
    data = _empty(slug)
    save(slug, data)
    return data


def is_published(slug: str) -> bool:
    return load(slug).get("status") == "published"


def channel_pending(slug: str, channel: str) -> bool:
    """Канал ещё не отправлен?"""
    data = load(slug)
    posted = data.get("channels_posted") or {}
    return posted.get(channel) is None


def _empty(slug: str) -> dict:
    return {
        "slug": slug,
        "status": None,
        "rendered_at": None,
        "deployed_at": None,
        "published_at": None,
        "live_url": None,
        "page_path": None,
        "data_path": None,
        "artifacts_dir": None,
        "seo_path": None,
        "preview_path": None,
        "channels_posted": {"tg": None, "vk": None, "email": None},
        "channels_failed": [],
        "error": None,
    }


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Publisher state manager")
    sub = p.add_subparsers(dest="cmd")

    show = sub.add_parser("show", help="Показать state")
    show.add_argument("slug")

    reset_p = sub.add_parser("reset", help="Сбросить state")
    reset_p.add_argument("slug")
    reset_p.add_argument("--force", action="store_true")

    mark = sub.add_parser("mark", help="Пометить канал")
    mark.add_argument("slug")
    mark.add_argument("channel", choices=["tg", "vk", "email"])
    mark.add_argument("status", choices=["posted", "failed"])
    mark.add_argument("--error", default="")

    update = sub.add_parser("update", help="Обновить произвольные поля state")
    update.add_argument("slug")
    update.add_argument("fields", nargs="+", help="Поля в формате key=value (например: status=published live_url=https://...)")

    clean = sub.add_parser("clean", help="Очистить channels_failed (когда ошибка ложная)")
    clean.add_argument("slug")

    args = p.parse_args()
    if args.cmd == "show":
        print(json.dumps(load(args.slug), ensure_ascii=False, indent=2))
    elif args.cmd == "reset":
        if not args.force:
            ans = input(f"Сбросить {args.slug}? (yes/no): ")
            if ans != "yes":
                print("Отменено.")
                sys.exit(0)
        reset(args.slug)
        print(f"Reset {args.slug}.")
    elif args.cmd == "mark":
        if args.status == "posted":
            mark_channel_posted(args.slug, args.channel)
        else:
            mark_channel_failed(args.slug, args.channel, args.error)
        print(f"{args.slug}.{args.channel} = {args.status}")
    elif args.cmd == "update":
        kwargs = {}
        for f in args.fields:
            if "=" in f:
                k, v = f.split("=", 1)
                # Попробуем распарсить JSON-значения
                try:
                    kwargs[k] = json.loads(v)
                except Exception:
                    kwargs[k] = v
        # NB: update() — функция в этом модуле, не argparse
        from state import update as _update_fn  # type: ignore  # noqa: F401
        # Если не сработало (мы и есть state.py) — используем прямую запись
        d = load(args.slug)
        d.update(kwargs)
        save(args.slug, d)
        print(f"Updated {args.slug}: {list(kwargs.keys())}")
    elif args.cmd == "clean":
        d = load(args.slug)
        d["channels_failed"] = []
        d["error"] = None
        save(args.slug, d)
        print(f"Cleaned {args.slug}.channels_failed")
    else:
        p.print_help()
