"""
_image_common.py — общие утилиты Image Skill v0.1.

Содержит:
- load_env() — ручной парсер .env (без python-dotenv), по идиоме publisher_skill
- now_iso() — UTC timestamp в формате ISO-Z
- mitm_bypass_ssl() — context для HTTPS с отключенной верификацией (corporate proxy)
- SKILL_ROOT / PROFILES_DIR / DATA_DIR / TMP_DIR / FORMATS_PATH — пути
- load_formats() / get_format() — работа с registry форматов
"""
from __future__ import annotations

import os
import ssl
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# === Пути ===
SKILL_ROOT: Path = Path(__file__).resolve().parent.parent
DATA_DIR: Path = SKILL_ROOT / "data"
PROFILES_DIR: Path = DATA_DIR / "profiles"
FORMATS_PATH: Path = DATA_DIR / "formats.yaml"
TMP_DIR: Path = SKILL_ROOT / "tmp"
IMAGES_DIR: Path = TMP_DIR / "images"
LOGS_DIR: Path = SKILL_ROOT / "logs"
STATE_DIR: Path = SKILL_ROOT / "state"

# Создаём runtime-папки при импорте
for d in (TMP_DIR, IMAGES_DIR, LOGS_DIR, STATE_DIR, PROFILES_DIR):
    d.mkdir(parents=True, exist_ok=True)

# UTF-8 fix for Windows
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


# === ENV loader (как в publisher_skill/post_channels.py:45-54) ===
def load_env(path: Optional[Path] = None) -> None:
    """Прочитать .env построчно, os.environ.setdefault() — не перезаписывает существующие.

    Обрезает trailing inline-комментарии (после ' #').
    """
    env_path = path or (SKILL_ROOT / ".env")
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = v.strip()
        # Strip inline comments: split on " #" but only if preceded by content
        if " #" in v:
            v = v.split(" #", 1)[0].strip()
        os.environ.setdefault(k.strip(), v)


def get_env(key: str, default: str = "") -> str:
    """Получить ENV, обрезав trailing комментарий (например 'b1xxx  # comment')."""
    val = os.environ.get(key, default).strip()
    # Strip trailing inline comments (anything after first ' #' preceded by space)
    if " #" in val:
        val = val.split(" #", 1)[0].strip()
    return val


# === Time helpers ===
def now_iso() -> str:
    """UTC ISO с Z (как в publisher_skill)."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# === MITM bypass (по memory corporate-mitm-proxy) ===
def mitm_bypass_ssl():
    """SSL context с отключённой верификацией (для корпоративного MITM)."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


# === Profile helpers ===
def list_profile_names() -> list[str]:
    """Список имён профилей = имена .yaml файлов без расширения в data/profiles/."""
    if not PROFILES_DIR.exists():
        return []
    return sorted(p.stem for p in PROFILES_DIR.glob("*.yaml"))


def default_profile_name() -> str:
    """Из env PROFILE_DEFAULT, иначе первый существующий, иначе 'lab'."""
    env = get_env("PROFILE_DEFAULT")
    if env and (PROFILES_DIR / f"{env}.yaml").exists():
        return env
    if list_profile_names():
        return list_profile_names()[0]
    return "lab"


# === Format registry ===
def load_formats() -> dict:
    """Загрузить registry форматов из data/formats.yaml."""
    import yaml  # type: ignore
    if not FORMATS_PATH.exists():
        return {}
    return yaml.safe_load(FORMATS_PATH.read_text(encoding="utf-8")).get("formats", {})


def get_format(name: str) -> dict:
    """Получить формат по имени. Бросает KeyError если не найден."""
    formats = load_formats()
    if name not in formats:
        raise KeyError(f"Unknown format '{name}'. Available: {list(formats.keys())}")
    return formats[name]


# Вызываем load_env() на модульном уровне
load_env()


if __name__ == "__main__":
    # Smoke-test
    print(f"SKILL_ROOT: {SKILL_ROOT}")
    print(f"PROFILES_DIR: {PROFILES_DIR}")
    print(f"profile names: {list_profile_names()}")
    print(f"default profile: {default_profile_name()}")
    print(f"now_iso(): {now_iso()}")
    print(f"formats: {list(load_formats().keys())}")
