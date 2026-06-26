"""
yandex_art.py — обёртка над Yandex Cloud YandexART API.

Endpoint: POST https://llm.api.cloud.yandex.net/foundationModels/v1/imageGeneration_async
Auth: Authorization: Api-Key <YANDEX_API_KEY>
modelUri: art://<folder_id>/yandex-art/latest

См. sub-skills/yandex-art-api.md для полной документации.

Использование:
    from yandex_art import generate
    png_bytes = generate("a cat in watercolor style", width_ratio=8, height_ratio=8, seed=123)
"""
from __future__ import annotations

import base64
import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional

from _image_common import get_env, mitm_bypass_ssl, now_iso


ENDPOINT = "https://llm.api.cloud.yandex.net/foundationModels/v1/imageGenerationAsync"
OPERATION_ENDPOINT = "https://operation.api.cloud.yandex.net/operations"


def _api_key() -> str:
    """Получить YANDEX_API_KEY из ENV (image_skill/.env или wish_librarian/.env)."""
    key = get_env("YANDEX_API_KEY")
    if not key:
        raise RuntimeError("YANDEX_API_KEY не задан. Скопируй wish_librarian/.env в image_skill/.env")
    return key


def _folder_id() -> str:
    return get_env("YANDEX_FOLDER_ID")


def _model_uri() -> str:
    """art://<folder_id>/yandex-art/latest (или из ENV YANDEX_MODEL_ART)."""
    custom = get_env("YANDEX_MODEL_ART")
    if custom:
        return custom
    return f"art://{_folder_id()}/yandex-art/latest"


def generate(
    prompt: str,
    width_ratio: int = 8,
    height_ratio: int = 8,
    seed: Optional[int] = None,
    mime_type: str = "image/png",
    timeout: int = 60,
) -> bytes:
    """
    Сгенерировать картинку через YandexART.

    Args:
        prompt: Текстовый промпт на английском (1-2 предложения).
        width_ratio: Целое 1..8 (пропорция ширины).
        height_ratio: Целое 1..8 (пропорция высоты).
        seed: 0..2^32 для воспроизводимости, None = random.
        mime_type: image/png или image/jpeg.
        timeout: Таймаут HTTP-запроса (сек).

    Returns:
        bytes PNG/JPEG изображения.

    Raises:
        RuntimeError: При ошибке API.
    """
    if not 1 <= width_ratio <= 8:
        raise ValueError(f"width_ratio={width_ratio} вне [1..8]")
    if not 1 <= height_ratio <= 8:
        raise ValueError(f"height_ratio={height_ratio} вне [1..8]")
    if seed is not None and not (0 <= seed <= 2**32):
        raise ValueError(f"seed={seed} вне [0..2^32]")

    payload = {
        "modelUri": _model_uri(),
        "messages": [{"role": "user", "text": prompt}],
        "generationOptions": {
            "mimeType": mime_type,
            "aspectRatio": {"widthRatio": str(width_ratio), "heightRatio": str(height_ratio)},
        },
    }
    if seed is not None:
        payload["generationOptions"]["seed"] = seed

    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        ENDPOINT,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Api-Key {_api_key()}",
            "x-folder-id": _folder_id(),
        },
    )

    print(f"  → YandexART: prompt={prompt[:80]!r}…", file=sys.stderr)
    print(f"  → ratio={width_ratio}:{height_ratio}, seed={seed}, model={_model_uri()}", file=sys.stderr)

    ctx = mitm_bypass_ssl()
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            body = resp.read()
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"YandexART HTTP {e.code}: {err_body}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"YandexART network error: {e}") from e

    elapsed = time.time() - t0
    print(f"  → response {len(body)} bytes in {elapsed:.1f}s", file=sys.stderr)

    # Parse response: async — сначала operation ID, надо поллить
    try:
        result = json.loads(body)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Невалидный JSON от YandexART: {e}\nBody: {body[:200]}") from e

    if "image" in result:
        # Sync ответ (на всякий случай)
        return base64.b64decode(result["image"])
    if "id" in result:
        # Async — нужно поллить operation
        op_id = result["id"]
        if result.get("done"):
            # Уже готово (edge case)
            if "response" in result and "image" in result["response"]:
                return base64.b64decode(result["response"]["image"])
            raise RuntimeError(f"Operation done but no image: {result}")
        return _poll_operation(op_id, timeout=timeout, ctx=ctx)
    raise RuntimeError(f"Unexpected YandexART response: {result}")


def _poll_operation(op_id: str, timeout: int, ctx) -> bytes:
    """Поллинг для async-эндпоинта (если ответ — operation ID)."""
    poll_url = f"{OPERATION_ENDPOINT}/{op_id}"
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(3)
        req = urllib.request.Request(poll_url, method="GET", headers={"Authorization": f"Api-Key {_api_key()}"})
        try:
            with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
                body = resp.read()
        except Exception as e:
            print(f"  ⚠ poll error: {e}", file=sys.stderr)
            continue
        result = json.loads(body)
        if result.get("done"):
            if "error" in result:
                raise RuntimeError(f"YandexART operation error: {result['error']}")
            if "response" in result and "image" in result["response"]:
                return base64.b64decode(result["response"]["image"])
            raise RuntimeError(f"Operation done but no image: {result}")
    raise RuntimeError(f"YandexART timeout ({timeout}s) waiting for operation {op_id}")


def save_image(image_bytes: bytes, path: Path) -> tuple[int, str]:
    """Сохранить PNG/JPEG в файл, вернуть (size_kb, actual_format).

    YandexART возвращает JPEG даже при mime_type='image/png' (известная особенность).
    Определяем реальный формат по magic bytes и сохраняем с правильным расширением.
    """
    # Определяем реальный формат
    if image_bytes.startswith(b"\x89PNG"):
        actual_format = "png"
        ext = ".png"
    elif image_bytes.startswith(b"\xff\xd8\xff"):
        actual_format = "jpeg"
        ext = ".jpg"
    else:
        actual_format = "unknown"
        ext = ".bin"

    # Если расширение в path не совпадает с реальным форматом — поправим
    if path.suffix.lower() not in (".png", ".jpg", ".jpeg"):
        path = path.with_suffix(ext)
    elif actual_format == "jpeg" and path.suffix.lower() == ".png":
        path = path.with_suffix(".jpg")

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(image_bytes)
    return round(path.stat().st_size / 1024, 1), actual_format


if __name__ == "__main__":
    # Smoke-test: генерируем маленький PNG 64×64
    print("Smoke test: 1x1 ratio (64x64)...", file=sys.stderr)
    try:
        data = generate("a tiny red rose icon", width_ratio=1, height_ratio=1, seed=42)
        out = Path(__file__).resolve().parent.parent / "tmp" / "yandex_art_smoke.png"
        size = save_image(data, out)
        print(f"✅ OK: {out} ({size} КБ)")
    except Exception as e:
        print(f"❌ {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)
