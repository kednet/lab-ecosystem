"""
upload_storage.py — мульти-провайдер upload (Phase 3, v1.4).

Диспетчер: пробует R2 → Yandex Object Storage → file:// fallback.

Использование:
  from upload_storage import upload_to_storage
  url = upload_to_storage(local_path, key, provider="auto")

Провайдеры:
  - r2      Cloudflare R2 (S3-compatible, region=auto)
  - yandex  Yandex Object Storage (S3-compatible, region=ru-central1)
  - auto    R2 → Yandex → file:// (default)

ENV:
  STORAGE_PROVIDER=auto|r2|yandex  (default: auto)

Конфигурация провайдеров:
  R2:      R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET, R2_PUBLIC_URL
  Yandex:  YANDEX_STORAGE_ACCESS_KEY, YANDEX_STORAGE_SECRET_KEY, YANDEX_STORAGE_BUCKET, YANDEX_STORAGE_PUBLIC_URL
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional


def _file_fallback(local_path: Path) -> str:
    """Вернуть file:// URL (для dry-run)."""
    abs_path = Path(local_path).resolve()
    url = f"file:///{abs_path.as_posix().lstrip('/')}"
    print(f"  ⚠ Ни один storage provider не настроен, fallback на {url}", file=sys.stderr)
    print("    Поддерживаемые провайдеры: R2 (R2_*), Yandex Object Storage (YANDEX_STORAGE_*)", file=sys.stderr)
    return url


def upload_to_storage(
    local_path: Path,
    key: Optional[str] = None,
    provider: str = "",
) -> str:
    """
    Загрузить файл в выбранный storage. Авто-выбор провайдера если provider пуст.

    Args:
        local_path: путь к локальному JPEG
        key: S3 key (default: images/<basename>)
        provider: 'auto' | 'r2' | 'yandex' (default: из ENV STORAGE_PROVIDER или 'auto')

    Returns:
        https://<public_url>/<key> или file:// URL
    """
    local_path = Path(local_path)
    if not local_path.exists():
        raise FileNotFoundError(f"Файл не найден: {local_path}")

    provider = (provider or os.environ.get("STORAGE_PROVIDER", "auto")).strip().lower()
    if provider not in ("auto", "r2", "yandex"):
        print(f"  ⚠ Неизвестный STORAGE_PROVIDER={provider!r}, использую 'auto'", file=sys.stderr)
        provider = "auto"

    if provider in ("auto", "r2"):
        try:
            from upload_r2 import has_r2_credentials, upload_to_r2
            if has_r2_credentials():
                print(f"  → Storage: Cloudflare R2 (provider={provider})", file=sys.stderr)
                return upload_to_r2(local_path, key)
            if provider == "r2":
                print("  ⚠ STORAGE_PROVIDER=r2, но R2 токены не заданы", file=sys.stderr)
        except ImportError:
            if provider == "r2":
                print("  ⚠ scripts/upload_r2.py не найден", file=sys.stderr)

    if provider in ("auto", "yandex"):
        try:
            from upload_yandex import (
                has_yandex_storage_credentials,
                upload_to_yandex_storage,
            )
            if has_yandex_storage_credentials():
                print(f"  → Storage: Yandex Object Storage (provider={provider})", file=sys.stderr)
                return upload_to_yandex_storage(local_path, key)
            if provider == "yandex":
                print("  ⚠ STORAGE_PROVIDER=yandex, но Yandex Storage токены не заданы", file=sys.stderr)
        except ImportError:
            if provider == "yandex":
                print("  ⚠ scripts/upload_yandex.py не найден", file=sys.stderr)

    return _file_fallback(local_path)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Upload to R2/Yandex Object Storage (auto-detect)")
    p.add_argument("file", help="Локальный путь к файлу")
    p.add_argument("--key", default=None, help="S3 key (default: images/<basename>)")
    p.add_argument("--provider", default="", help="auto|r2|yandex (default: STORAGE_PROVIDER env)")
    args = p.parse_args()

    url = upload_to_storage(Path(args.file), args.key, args.provider)
    print(f"URL: {url}")
