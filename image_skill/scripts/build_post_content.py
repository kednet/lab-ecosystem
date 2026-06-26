"""
build_post_content.py — сборка JSON-контента в формате post_channels.py (Phase 3).

Используется в `cmd_publish.py`. Принимает slug_id, image_url, live_url.
Возвращает Path к JSON-файлу в формате templates/post-channels/detector.json.

Формат JSON (контракт post_channels.py):
{
  "title": "Заголовок",
  "url": "https://...",
  "image": "https://..." или "file:///...",
  "hashtags": ["#a", "#b"],
  "vk": "Текст для VK",
  "tg": "HTML для TG",
  "ok": "Текст для OK",
  "zen": "Длинный текст для Дзен"
}
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from _image_common import SKILL_ROOT, get_format  # noqa: E402
from announce_text import generate_announce  # noqa: E402
from cmd_profile import load_profile  # noqa: E402
from state import load as load_state  # noqa: E402


def build_post_json(
    slug_id: str,
    profile_name: str,
    image_url: str,
    live_url: str = "",
    book_type: str = "",
    book_tags: list[str] | None = None,
) -> Path:
    """
    Собрать JSON-контент в формате post_channels.py.

    Args:
        slug_id: 'lab/5-oshibok-karty-zhelanii'
        profile_name: 'lab'
        image_url: 'https://img.pulab.ru/...' или 'file:///...'
        live_url: 'https://pulab.online/...' (опц.)
        book_type: 'fiction-reflective' | 'nonfiction' (опц., v1.7)
        book_tags: ['#коэльо', '#алхимик'] (опц., v1.8 — per-book теги из books.json)

    Returns:
        Path к tmp/post-channels/<slug_id_safe>.json
    """
    state = load_state(slug_id)
    profile = load_profile(profile_name)
    fmt = get_format(state.get("format") or "vk_post")

    # v1.7: book_type из state (если задан) ИЛИ из аргумента (CLI переопределяет)
    if book_type:
        state["book_type"] = book_type

    # v1.8: теги книги → state для использования в generate_announce и финальном JSON
    if book_tags:
        state["book_tags"] = book_tags

    # Генерация 4 адаптаций
    announce = generate_announce(state, profile, fmt, image_url, live_url)

    # v1.4: сохранить копию JPEG в publisher_skill/tmp/img-cache/
    # чтобы post_channels.py не скачивал по сети (корпоративный SOCKS proxy мешает)
    local_image_path = _copy_image_to_publisher_cache(state, slug_id)

    # v1.8: мердж хэштегов: базовые + per-book теги (без дублей)
    base_ht = profile.get("hashtags_base", []) or []
    book_ht = book_tags or []
    seen = set()
    hashtags = []
    for h in base_ht + book_ht:
        h_norm = h.lower().strip()
        if h_norm and h_norm not in seen:
            hashtags.append(h)
            seen.add(h_norm)

    # Сборка JSON
    content = {
        "title": (state.get("title") or "Анонс")[:100],
        "url": live_url or image_url,
        "image": image_url,
        "image_local": local_image_path or "",  # v1.4: локальный путь для post_channels.py
        "hashtags": hashtags,
        "vk": announce["vk"],
        "tg": announce["tg"],
        "ok": announce["ok"],
        "zen": announce["zen"],
    }

    # Сохранение в tmp/post-channels/
    safe_slug = slug_id.replace("/", "_").replace(" ", "_")
    out_dir = SKILL_ROOT / "tmp" / "post-channels"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{safe_slug}.json"

    out_path.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ✓ JSON-контент: {out_path.relative_to(SKILL_ROOT)}", file=sys.stderr)
    return out_path


def _copy_image_to_publisher_cache(state: dict, slug_id: str) -> str:
    """Скопировать upscaled JPEG в publisher_skill/tmp/img-cache/ для локального доступа.

    Это позволяет post_channels.py не скачивать файл по URL (обход SOCKS proxy проблем).
    Возвращает абсолютный путь к копии или "" если state не имеет upscaled_path.
    """
    upscaled_rel = state.get("upscaled_path")
    if not upscaled_rel:
        return ""
    src = (SKILL_ROOT / upscaled_rel).resolve()
    if not src.exists():
        print(f"  ⚠ _copy_image_to_publisher_cache: файл не найден {src}", file=sys.stderr)
        return ""

    publisher_tmp = Path("C:/Users/kfigh/publisher_skill/tmp/img-cache")
    publisher_tmp.mkdir(parents=True, exist_ok=True)
    dst = publisher_tmp / f"{slug_id.replace('/', '_')}_{src.name}"
    try:
        import shutil
        shutil.copy2(src, dst)
        print(f"  ✓ Копия для post_channels.py: {dst}", file=sys.stderr)
        return str(dst)
    except Exception as e:
        print(f"  ⚠ Не удалось скопировать в publisher_skill: {e}", file=sys.stderr)
        return ""


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Сборка post_channels.py контента")
    p.add_argument("--slug-id", required=True)
    p.add_argument("--profile", default="lab")
    p.add_argument("--image-url", required=True)
    p.add_argument("--live-url", default="")
    args = p.parse_args()

    path = build_post_json(args.slug_id, args.profile, args.image_url, args.live_url)
    print(f"✅ {path}")
