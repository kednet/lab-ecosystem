"""
upload_yandex.py — загрузка upscaled JPEG в Yandex Object Storage (Phase 3, v1.4).

Используется в `cmd_publish.py` (через `upload_storage.upload_to_storage`) когда
R2 недоступен. S3-compatible, через boto3.

ENV:
  YANDEX_STORAGE_ACCESS_KEY     — статический ключ (Access Key)
  YANDEX_STORAGE_SECRET_KEY     — статический ключ (Secret Key)
  YANDEX_STORAGE_BUCKET         — имя бакета
  YANDEX_STORAGE_PUBLIC_URL     — публичный URL бакета
                                 (например https://storage.yandexcloud.net/<bucket>
                                  или https://<bucket>.storage.yandexcloud.net)

Когда токены появятся:
  1. https://console.yandex.cloud/ → Object Storage → бакет
  2. Сервисный аккаунт с ролью storage.editor → статический ключ
  3. pip install boto3
  4. Заполнить ENV
  5. STORAGE_PROVIDER=yandex (или auto)

Стоимость: 0.01 ₽/ГБ/мес хранение + 0.20 ₽/ГБ исходящий трафик.
~100 картинок × 400 КБ = 40 МБ = менее 1 ₽/мес.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional


def has_yandex_storage_credentials() -> bool:
    """Проверить, есть ли все нужные ENV переменные для Yandex Object Storage."""
    required = [
        "YANDEX_STORAGE_ACCESS_KEY",
        "YANDEX_STORAGE_SECRET_KEY",
        "YANDEX_STORAGE_BUCKET",
        "YANDEX_STORAGE_PUBLIC_URL",
    ]
    return all(os.environ.get(k, "").strip() for k in required)


def upload_to_yandex_storage(local_path: Path, key: Optional[str] = None) -> str:
    """
    Загрузить файл в Yandex Object Storage. Возвращает публичный URL.

    Args:
        local_path: путь к локальному JPEG
        key: S3 key (default: images/<basename>)

    Returns:
        https://<public_url>/<key> или file://<local_path> (fallback)
    """
    local_path = Path(local_path)
    if not local_path.exists():
        raise FileNotFoundError(f"Файл не найден: {local_path}")

    if key is None:
        key = f"images/{local_path.name}"

    if not has_yandex_storage_credentials():
        abs_path = local_path.resolve()
        print(
            f"  ⚠ Yandex Storage токены не заданы, fallback на file:// URL (только dry-run)",
            file=sys.stderr,
        )
        print(
            "    Для реальной публикации добавь в .env: YANDEX_STORAGE_ACCESS_KEY, _SECRET_KEY, _BUCKET, _PUBLIC_URL",
            file=sys.stderr,
        )
        return f"file:///{abs_path.as_posix().lstrip('/')}"

    try:
        import boto3  # type: ignore
    except ImportError:
        print("  ⚠ boto3 не установлен. pip install boto3. Fallback на file://", file=sys.stderr)
        abs_path = local_path.resolve()
        return f"file:///{abs_path.as_posix().lstrip('/')}"

    access_key = os.environ["YANDEX_STORAGE_ACCESS_KEY"].strip()
    secret_key = os.environ["YANDEX_STORAGE_SECRET_KEY"].strip()
    bucket = os.environ["YANDEX_STORAGE_BUCKET"].strip()
    public_url = os.environ["YANDEX_STORAGE_PUBLIC_URL"].strip().rstrip("/")

    # Yandex Object Storage: S3-compatible, region ru-central1, endpoint storage.yandexcloud.net
    # Config(proxies={}) явно отключает системный/корпоративный SOCKS proxy, который
    # иначе ломает boto3 (urllib3 не понимает схему socks4://).
    from botocore.config import Config
    s3 = boto3.client(
        "s3",
        endpoint_url="https://storage.yandexcloud.net",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="ru-central1",
        config=Config(proxies={}, retries={"max_attempts": 3, "mode": "standard"}),
    )

    content_type = "image/jpeg" if local_path.suffix.lower() in (".jpg", ".jpeg") else "image/png"

    try:
        s3.upload_file(
            str(local_path),
            bucket,
            key,
            ExtraArgs={"ContentType": content_type, "CacheControl": "public, max-age=31536000"},
        )
    except Exception as e:
        print(f"  ✗ Yandex Storage upload failed: {e}", file=sys.stderr)
        raise

    url = f"{public_url}/{key}"
    print(f"  ✓ Загружено в Yandex Storage: {key} → {url}", file=sys.stderr)
    return url


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Upload JPEG/PNG to Yandex Object Storage")
    p.add_argument("file", help="Локальный путь к файлу")
    p.add_argument("--key", default=None, help="S3 key (default: images/<basename>)")
    args = p.parse_args()

    url = upload_to_yandex_storage(Path(args.file), args.key)
    print(f"URL: {url}")
