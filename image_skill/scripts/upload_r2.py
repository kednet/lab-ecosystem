"""
upload_r2.py — загрузка upscaled JPEG в Cloudflare R2 (Phase 3).

Используется в `cmd_publish.py` для получения публичного URL.

Что делает:
1. Читает ENV: R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET, R2_PUBLIC_URL
2. Если все есть — загружает через S3-compatible API (boto3) и возвращает https://url
3. Если нет — возвращает file:// URL (для dry-run / локального dev)

Когда токены появятся:
- pip install boto3
- Заполнить ENV
- Без изменений в коде

Why boto3, а не requests: R2 совместим с S3 API, boto3 — стандарт. ~30 строк кода, проверено.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional


def has_r2_credentials() -> bool:
    """Проверить, есть ли все нужные ENV переменные для R2."""
    required = ["R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET", "R2_PUBLIC_URL"]
    return all(os.environ.get(k, "").strip() for k in required)


def upload_to_r2(local_path: Path, key: Optional[str] = None) -> str:
    """
    Загрузить файл в R2 bucket. Возвращает публичный URL.

    Args:
        local_path: путь к локальному JPEG
        key: S3 key (default: имя файла в images/)

    Returns:
        https://<public_url>/<key> или file://<local_path> (fallback)
    """
    local_path = Path(local_path)
    if not local_path.exists():
        raise FileNotFoundError(f"Файл не найден: {local_path}")

    if key is None:
        key = f"images/{local_path.name}"

    if not has_r2_credentials():
        # Fallback: file:// URL (для dry-run)
        abs_path = local_path.resolve()
        print(f"  ⚠ R2 токены не заданы, fallback на file:// URL (только dry-run)", file=sys.stderr)
        print(f"    Для реальной публикации добавь в .env: R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY", file=sys.stderr)
        return f"file:///{abs_path.as_posix().lstrip('/')}"

    # === Реальный R2 upload через boto3 ===
    try:
        import boto3  # type: ignore
    except ImportError:
        print("  ⚠ boto3 не установлен. pip install boto3. Fallback на file://", file=sys.stderr)
        abs_path = local_path.resolve()
        return f"file:///{abs_path.as_posix().lstrip('/')}"

    account_id = os.environ["R2_ACCOUNT_ID"].strip()
    access_key = os.environ["R2_ACCESS_KEY_ID"].strip()
    secret_key = os.environ["R2_SECRET_ACCESS_KEY"].strip()
    bucket = os.environ["R2_BUCKET"].strip()
    public_url = os.environ["R2_PUBLIC_URL"].strip().rstrip("/")

    endpoint_url = f"https://{account_id}.r2.cloudflarestorage.com"

    # Config(proxies={}) явно отключает системный/корпоративный SOCKS proxy
    from botocore.config import Config
    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="auto",  # R2 требует 'auto'
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
        print(f"  ✗ R2 upload failed: {e}", file=sys.stderr)
        raise

    url = f"{public_url}/{key}"
    print(f"  ✓ Загружено в R2: {key} → {url}", file=sys.stderr)
    return url


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Upload JPEG/PNG to Cloudflare R2")
    p.add_argument("file", help="Локальный путь к файлу")
    p.add_argument("--key", default=None, help="S3 key (default: images/<basename>)")
    args = p.parse_args()

    url = upload_to_r2(Path(args.file), args.key)
    print(f"URL: {url}")
