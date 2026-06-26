"""
state.py — идемпотентность Image Skill v0.1.

Основано на video_skill/scripts/state.py (2026-06-17), адаптировано под image:
- Путь: state/<profile>/<slug>.json
- Поле `profile: str`
- Расширенный набор статусов под фазы:
  draft → prompt_ready → generated → saved → (Phase 2: upscaled) → (Phase 3: published) | failed

state/<profile>/<slug>.json:
{
  "slug": "5-oshibok-karty-zhelaniy",
  "profile": "lab",
  "status": "draft | prompt_ready | generated | saved | upscaled | published | failed",
  "title": "...",
  "format": "vk_post",
  "style": "watercolor",
  "mood": "soft",
  "aspect": "1:1",
  "width_ratio": 8,
  "height_ratio": 8,
  "seed": 271828,
  "prompt_text": "...",
  "image_path": "tmp/images/lab/5-oshibok-vk_post.png",
  "image_size_kb": 73,
  "image_mime": "image/png",
  "created_at": "...",
  "prompt_at": null, "prompt_text": null,
  "generated_at": null, "image_path": null, "image_size_kb": null,
  "upscaled_at": null, "upscaled_path": null,
  "published_at": null,
  "error": null
}

Конвенция вызова из CLI: slug передаётся в формате "<profile>/<slug>"
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
    """'lab/5-oshibok' → ('lab', '5-oshibok'). Без '/' → ('_default', slug)."""
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


def reset(slug_id: str) -> dict:
    """Полный сброс state (для --force)."""
    profile, slug = parse_slug_id(slug_id)
    data = _empty(profile, slug)
    save(slug_id, data)
    return data


def is_saved(slug_id: str) -> bool:
    """Картинка уже сгенерирована и сохранена?"""
    return load(slug_id).get("status") == "saved"


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
        "format": None,
        "style": None,
        "mood": None,
        "aspect": None,
        "width_ratio": None,
        "height_ratio": None,
        "seed": None,
        "prompt_text": None,
        "image_path": None,
        "image_size_kb": None,
        "image_mime": None,
        "created_at": None,
        "prompt_at": None,
        "generated_at": None,
        "upscaled_at": None,
        "upscaled_path": None,
        "published_at": None,
        "error": None,
    }


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Image Skill state manager")
    sub = p.add_subparsers(dest="cmd")

    show = sub.add_parser("show", help="Показать state")
    show.add_argument("slug_id", help="profile/slug или просто slug")

    list_p = sub.add_parser("list", help="Список всех state-файлов")
    list_p.add_argument("--profile", help="Фильтр по профилю")

    reset_p = sub.add_parser("reset", help="Сбросить state")
    reset_p.add_argument("slug_id")
    reset_p.add_argument("--force", action="store_true")

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
    else:
        p.print_help()
