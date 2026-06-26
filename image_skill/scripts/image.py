"""
image.py — orchestrator для image_skill Phase 1.

Sub-команды:
- generate <format> <source_text>  — сгенерировать PNG через YandexART
- profile list|show|validate [name] — управление профилями
- state show|list|reset <slug_id>   — state идемпотентность
- validate <slug_id>                 — валидация PNG + state
- auto <slug_id>                     — STUB (Phase 2: upscale + text overlay)
- publish <slug_id>                  — STUB (Phase 3: publisher_skill integration)

Стиль argparse: скопирован из video_skill/scripts/video.py.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Пути к scripts/ для импорта
SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from _image_common import default_profile_name  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="image",
        description="Image Skill — генерация картинок для соцсетей через YandexART",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    # === generate ===
    gen = sub.add_parser("generate", help="Сгенерировать картинку")
    gen.add_argument("format", help="Формат: vk_post | vk_story | pinterest | wb | og")
    gen.add_argument("source_text", help="Текст запроса")
    gen.add_argument("--profile", default=default_profile_name())
    gen.add_argument("--style", default=None)
    gen.add_argument("--mood", default=None)
    gen.add_argument("--seed", type=int, default=None)
    gen.add_argument("--force", action="store_true", help="Перегенерировать")
    gen.add_argument("--dry-run", action="store_true", help="Показать что будет сделано")

    # === profile ===
    prof = sub.add_parser("profile", help="Управление профилями")
    prof_sub = prof.add_subparsers(dest="profile_cmd", required=True)
    list_p = prof_sub.add_parser("list", help="Список профилей")
    list_p.set_defaults(profile_action="list")
    show = prof_sub.add_parser("show", help="Показать профиль")
    show.add_argument("name")
    show.set_defaults(profile_action="show")
    val = prof_sub.add_parser("validate", help="Валидировать профиль")
    val.add_argument("name")
    val.set_defaults(profile_action="validate")

    # === state ===
    st = sub.add_parser("state", help="Управление state")
    st_sub = st.add_subparsers(dest="state_cmd", required=True)
    st_show = st_sub.add_parser("show", help="Показать state")
    st_show.add_argument("slug_id")
    st_list = st_sub.add_parser("list", help="Список state-файлов")
    st_list.add_argument("--profile", default=None)
    st_reset = st_sub.add_parser("reset", help="Сбросить state")
    st_reset.add_argument("slug_id")
    st_reset.add_argument("--force", action="store_true")

    # === validate ===
    val2 = sub.add_parser("validate", help="Валидировать картинку + state")
    val2.add_argument("slug_id")

    # === auto (Phase 2) ===
    auto = sub.add_parser("auto", help="Phase 2: upscale + text overlay + watermark")
    auto.add_argument("slug_id")
    auto.add_argument("--profile", default=default_profile_name())
    auto.add_argument("--to", default=None, help="Custom target WxH (default из format.target_size)")
    auto.add_argument("--no-text", action="store_true", help="Пропустить text overlay")
    auto.add_argument("--no-watermark", action="store_true", help="Пропустить watermark")
    auto.add_argument("--force", action="store_true", help="Перезаписать существующий upscaled")

    # === publish (Phase 3) ===
    pub = sub.add_parser("publish", help="Phase 3: storage upload + post_channels.py (vk/tg/ok/zen)")
    pub.add_argument("slug_id")
    pub.add_argument("--profile", default=default_profile_name())
    pub.add_argument("--channels", default="vk", help="Каналы через запятую: vk,tg,ok,zen")
    pub.add_argument("--live-url", default="", help="URL статьи/страницы (если есть)")
    pub.add_argument("--storage", default="", help="Storage provider: auto|r2|yandex (default: STORAGE_PROVIDER env или auto)")
    pub.add_argument("--dry-run", action="store_true", help="Превью без публикации")
    pub.add_argument("--force", action="store_true", help="Перезаписать существующий published")

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.cmd == "generate":
        from cmd_generate import run as run_generate
        return run_generate(args)

    if args.cmd == "profile":
        from cmd_profile import run as run_profile
        return run_profile(args)

    if args.cmd == "state":
        # Inline (как в video_skill)
        import json
        from state import load as state_load, list_all, reset as state_reset
        if args.state_cmd == "show":
            print(json.dumps(state_load(args.slug_id), ensure_ascii=False, indent=2))
            return 0
        if args.state_cmd == "list":
            for s in list_all(args.profile):
                print(f"{s.get('profile','?')}/{s.get('slug','?')}  →  {s.get('status','?')}  ({s.get('format','?')})")
            return 0
        if args.state_cmd == "reset":
            if not args.force:
                ans = input(f"Сбросить {args.slug_id}? (yes/no): ")
                if ans != "yes":
                    print("Отменено.")
                    return 0
            state_reset(args.slug_id)
            print(f"Reset {args.slug_id}.")
            return 0

    if args.cmd == "validate":
        from validate_image import run as run_validate
        return run_validate(args)

    if args.cmd == "auto":
        from cmd_auto import run as run_auto
        return run_auto(args)

    if args.cmd == "publish":
        from cmd_publish import run as run_publish
        return run_publish(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
