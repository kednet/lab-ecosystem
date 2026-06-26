"""
cmd_profile.py — подкоманда `video.py profile` (NEW v1.0).

Использование:
    python scripts/video.py profile list
    python scripts/video.py profile show <name>
    python scripts/video.py profile validate <name>

Читает data/profiles/<name>.yaml.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import yaml

from _image_common import PROFILES_DIR  # type: ignore  # noqa: E402


# UTF-8 fix
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


def list_profiles() -> list[str]:
    """Список имён профилей = имена .yaml файлов без расширения."""
    if not PROFILES_DIR.exists():
        return []
    return sorted(p.stem for p in PROFILES_DIR.glob("*.yaml"))


def profile_path_for(name: str) -> Path:
    return PROFILES_DIR / f"{name}.yaml"


def load_profile(name: str) -> dict:
    """Загрузить YAML-профиль. Бросает FileNotFoundError если нет."""
    p = profile_path_for(name)
    if not p.exists():
        raise FileNotFoundError(f"Профиль '{name}' не найден ({p})")
    with open(p, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Профиль '{name}' не dict (тип={type(data).__name__})")
    return data


def show_profile(name: str) -> dict:
    """Загрузить и вернуть профиль. CLI: печатает как JSON."""
    import json
    return load_profile(name)


def validate_profile(name: str) -> list[str]:
    """Проверить обязательные поля. Возвращает список ошибок (пустой = OK)."""
    errors: list[str] = []
    try:
        data = load_profile(name)
    except Exception as e:
        return [str(e)]

    # name
    if not data.get("name"):
        errors.append("name пустой (должен = stem файла)")
    elif data["name"] != name:
        errors.append(f"name='{data['name']}' не совпадает с именем файла '{name}'")

    # display_name
    if not data.get("display_name"):
        errors.append("display_name пустой")

    # defaults
    defaults = data.get("defaults") or {}
    for k in ("format", "style", "mood"):
        if not defaults.get(k):
            errors.append(f"defaults.{k} пустой")

    # branding
    branding = data.get("branding") or {}
    if not branding.get("watermark"):
        errors.append("branding.watermark пустой")
    if not branding.get("accent_color"):
        errors.append("branding.accent_color пустой")
    palette = branding.get("palette") or {}
    if not palette.get("primary"):
        errors.append("branding.palette.primary пустой")

    # hashtags_base
    if not data.get("hashtags_base"):
        errors.append("hashtags_base пустой")

    # negative_prompts (image-skill specific)
    if not data.get("negative_prompts"):
        errors.append("negative_prompts пустой")

    # prompt_styles (image-skill specific)
    if not data.get("prompt_styles"):
        errors.append("prompt_styles пустой")

    # prompt_moods (image-skill specific)
    if not data.get("prompt_moods"):
        errors.append("prompt_moods пустой")

    # cta_profiles (Phase 3, опц.) — не валидируем жёстко
    cta_profiles = data.get("cta_profiles") or {}
    # if not cta_profiles:
    #     errors.append("cta_profiles пустой (опц. для Phase 3)")

    # output.state_subdir
    output = data.get("output") or {}
    if not output.get("state_subdir"):
        errors.append("output.state_subdir пустой")

    return errors


def run(args) -> int:
    """CLI entry: вызывается из video.py:profile подкоманды."""
    action = getattr(args, "profile_action", None)
    name = getattr(args, "name", None)

    if action == "list" or (not action and not name):
        names = list_profiles()
        print(f"📁 {len(names)} профилей в {PROFILES_DIR}:")
        for n in names:
            try:
                d = load_profile(n)
                desc = d.get("description", "")[:60]
                print(f"  • {n:10} — {d.get('display_name', '?'):30} — {desc}...")
            except Exception as e:
                print(f"  • {n:10} — ERROR: {e}")
        return 0

    if action == "show":
        if not name:
            print("❌ show: укажите имя профиля", file=sys.stderr)
            return 2
        import json
        try:
            data = show_profile(name)
        except Exception as e:
            print(f"❌ {e}", file=sys.stderr)
            return 1
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    if action == "validate":
        if not name:
            print("❌ validate: укажите имя профиля", file=sys.stderr)
            return 2
        errs = validate_profile(name)
        if errs:
            print(f"❌ Профиль '{name}': {len(errs)} ошибок:")
            for e in errs:
                print(f"  - {e}")
            return 1
        else:
            print(f"✅ Профиль '{name}': OK (все обязательные поля заполнены)")
            return 0

    print(f"❌ Неизвестное действие: {action}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Video Skill profile manager")
    sub = p.add_subparsers(dest="profile_action")

    p_list = sub.add_parser("list", help="Список профилей")
    p_show = sub.add_parser("show", help="Показать профиль")
    p_show.add_argument("name")
    p_val = sub.add_parser("validate", help="Валидировать профиль")
    p_val.add_argument("name")

    args = p.parse_args()
    sys.exit(run(args))
