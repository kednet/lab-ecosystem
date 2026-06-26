"""
video.py — единый orchestrator Video Creator Skill v1.0.

Использование:
    python scripts/video.py script <platform> <goal> <tone> <duration> <source> [opts]
    python scripts/video.py profile list|show|validate [name]
    python scripts/video.py state show|list|reset [slug_id]
    python scripts/video.py validate <path-to-md>
    python scripts/video.py auto ...    # Phase 2 stub
    python scripts/video.py manual ...  # Phase 3 stub
    python scripts/video.py publish ... # Phase 4 stub

Стиль argparse — по идиоме publisher_skill/scripts/post_channels.py.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# UTF-8 fix
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="video",
        description="Video Creator Skill v1.0 — универсальный, 5 профилей, 3 режима, 4 фазы",
        epilog="Подкоманды: script / profile / state / validate / auto / manual / publish",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    # === script ===
    s_script = sub.add_parser("script", help="C-режим: сгенерировать сценарий (Phase 1)")
    s_script.add_argument("platform", help="tiktok | youtube | vk | telegram | reels")
    s_script.add_argument("goal", help="engagement | subscribe | traffic | contest")
    s_script.add_argument("tone", help="soulful | bold | inspiring | educational | playful | neutral | calm | confident | warm | energetic")
    s_script.add_argument("duration", type=int, help="Длительность в секундах (15/30/45/60/90)")
    s_script.add_argument("source", help="Тема/идея/цитата для сценария")
    s_script.add_argument("--profile", help="Имя профиля (lab/wl/coach/experts/market). Default из PROFILE_DEFAULT env")
    s_script.add_argument("--voice", help="Override голоса Yandex (alena/jane/filipp/ermil/marina/madirus/zahar)")
    s_script.add_argument("--speed", type=float, help="Override TTS speed (0.1-3.0)")
    s_script.add_argument("--music-mood", help="Override music mood (ambient/uplifting/...)")
    s_script.add_argument("--cta", help="Override CTA-текста")
    s_script.add_argument("--from-file", help="Прочитать source из файла (тема/цитата/заметка)")
    s_script.add_argument("--out", help="Куда сохранить .md (default: tmp/scripts/<profile>/<slug>.md)")
    s_script.add_argument("--dry-run", action="store_true", help="Только показать промпт, не генерировать")
    s_script.add_argument("--force", action="store_true", help="Перезаписать существующий сценарий")

    # === profile ===
    s_profile = sub.add_parser("profile", help="Управление профилями (Phase 1)")
    profile_sub = s_profile.add_subparsers(dest="profile_action", required=False)
    profile_sub.add_parser("list", help="Список профилей")
    p_show = profile_sub.add_parser("show", help="Показать профиль")
    p_show.add_argument("name")
    p_val = profile_sub.add_parser("validate", help="Валидировать профиль")
    p_val.add_argument("name")

    # === state ===
    s_state = sub.add_parser("state", help="Управление state (идемпотентность)")
    state_sub = s_state.add_subparsers(dest="state_action", required=True)
    p_show_st = state_sub.add_parser("show", help="Показать state")
    p_show_st.add_argument("slug_id", help="profile/slug или просто slug")
    p_list_st = state_sub.add_parser("list", help="Список всех state-файлов")
    p_list_st.add_argument("--profile", help="Фильтр по профилю")
    p_reset_st = state_sub.add_parser("reset", help="Сбросить state")
    p_reset_st.add_argument("slug_id")
    p_reset_st.add_argument("--force", action="store_true")

    # === validate ===
    s_val = sub.add_parser("validate", help="Валидировать .md сценарий")
    s_val.add_argument("path", help="Путь к .md файлу")
    s_val.add_argument("--duration", type=int, help="Ожидаемая длительность (если не в frontmatter)")

    # === auto/manual/publish (стабы) ===
    s_auto = sub.add_parser("auto", help="A-режим: auto-сборка mp4 (Phase 2 STUB)")
    s_auto.add_argument("--from-script", help="Slug сценария для авто-сборки")
    s_auto.add_argument("--profile", help="Имя профиля")
    s_manual = sub.add_parser("manual", help="B-режим: нарезка видео (Phase 3 STUB)")
    s_manual.add_argument("--from-file", help="Локальный видео-файл")
    s_manual.add_argument("--from-url", help="URL для yt-dlp")
    s_manual.add_argument("--timestamps", help="Диапазоны через запятую, формат H:MM:SS-H:MM:SS")
    s_manual.add_argument("--profile", help="Имя профиля")
    s_pub = sub.add_parser("publish", help="Публикация (Phase 4 STUB)")
    s_pub.add_argument("slug_id")
    s_pub.add_argument("--channels", default="vk,tg,ok,zen", help="Каналы публикации")
    s_pub.add_argument("--profile", help="Имя профиля для адаптации текстов")
    s_pub.add_argument("--dry-run", action="store_true")

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    # Lazy imports — чтобы не грузить всё подряд
    if args.cmd == "script":
        from cmd_script import run as run_script
        return run_script(args)
    elif args.cmd == "profile":
        from cmd_profile import run as run_profile
        return run_profile(args)
    elif args.cmd == "state":
        from state import load, list_all, reset as state_reset
        if args.state_action == "show":
            import json
            print(json.dumps(load(args.slug_id), ensure_ascii=False, indent=2))
            return 0
        elif args.state_action == "list":
            for s in list_all(args.profile):
                print(f"{s.get('profile','?')}/{s.get('slug','?')}  →  {s.get('status','?')}  ({s.get('title','')[:40]})")
            return 0
        elif args.state_action == "reset":
            if not args.force:
                ans = input(f"Сбросить {args.slug_id}? (yes/no): ")
                if ans != "yes":
                    print("Отменено.")
                    return 0
            state_reset(args.slug_id)
            print(f"Reset {args.slug_id}.")
            return 0
    elif args.cmd == "validate":
        from validate_script import validate_script
        from pathlib import Path
        errs = validate_script(Path(args.path), args.duration)
        if errs:
            print(f"❌ {len(errs)} ошибок:")
            for e in errs:
                print(f"  - {e}")
            return 1
        else:
            print("✅ OK: сценарий валиден")
            return 0
    elif args.cmd == "auto":
        from cmd_auto import run as run_auto
        return run_auto(args)
    elif args.cmd == "manual":
        from cmd_manual import run as run_manual
        return run_manual(args)
    elif args.cmd == "publish":
        from cmd_publish import run as run_pub
        return run_pub(args)

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
