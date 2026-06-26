"""
cmd_auto.py — Phase 2 pipeline: upscale + text overlay + watermark.

Использование:
    python scripts/image.py auto <slug_id> --profile=lab
    python scripts/image.py auto <slug_id> --to=1080x1080 --no-text
    python scripts/image.py auto <slug_id> --force

Pipeline:
1. Загрузить state (slug_id), проверить status in (saved, upscaled)
2. Загрузить profile + format_meta
3. Upscale через Pillow Lanczos до format.target_size
4. Text overlay (если есть state.title и не --no-text)
5. Watermark (если есть profile.branding.watermark и не --no-watermark)
6. Update state → status="upscaled", upscaled_path, upscaled_at

Артефакты в tmp/images/<profile>/:
  <slug>-<format>.jpg         # Phase 1: YandexART generated
  <slug>-<format>-upscaled.jpg  # Phase 2 step 1: Pillow Lanczos
  <slug>-<format>-texted.jpg    # Phase 2 step 2: + text overlay (если title)
  <slug>-<format>-final.jpg     # Phase 2 step 3: + watermark
"""
from __future__ import annotations

import sys
from pathlib import Path

from _image_common import SKILL_ROOT, get_format, now_iso  # noqa: E402
from cmd_profile import load_profile  # noqa: E402
from state import load as load_state, update as update_state  # noqa: E402
from upscale_pillow import parse_target, upscale_to_target  # noqa: E402
from burn_text import burn_text  # noqa: E402
from burn_watermark import burn_watermark  # noqa: E402


def _resolve_src_path(image_path: str) -> Path:
    """state.image_path → абсолютный Path. Если относительный — относительно SKILL_ROOT."""
    p = Path(image_path)
    if not p.is_absolute():
        p = SKILL_ROOT / image_path
    return p


def run(args) -> int:
    """CLI: image.py auto <slug_id> --profile=lab [--to=WxH] [--no-text] [--no-watermark] [--force]"""
    slug_id = args.slug_id
    profile_name = args.profile

    # 1. Загрузить state
    state = load_state(slug_id)
    status = state.get("status")
    if status not in ("saved", "upscaled"):
        print(f"❌ status={status!r}, ожидается saved или upscaled. Сначала: image.py generate")
        return 1

    if not state.get("image_path"):
        print(f"❌ state.image_path пустой — нечего upscal'ить")
        return 2

    # Idempotency: если уже upscaled и не --force
    if status == "upscaled" and state.get("upscaled_path") and not args.force:
        print(f"⏭ Уже upscaled: {state['upscaled_path']}")
        print(f"   Для перегенерации: --force")
        return 0

    # 2. Загрузить profile + format_meta
    profile = load_profile(profile_name)
    fmt_meta = get_format(state["format"])

    # 3. Upscale
    src = _resolve_src_path(state["image_path"])
    if not src.exists():
        print(f"❌ Исходник не найден: {src}")
        return 1

    target = parse_target(args.to)
    if target is None:
        target = tuple(fmt_meta["target_size"])
    if target != tuple(fmt_meta["target_size"]):
        print(f"⚠ Custom target {target} (формат {state['format']} ожидает {fmt_meta['target_size']})")

    print(f"🔧 Phase 2: upscale {src.name} → {target[0]}×{target[1]}")
    upscaled_path, size_kb = upscale_to_target(src, target[0], target[1])

    # 4. Text overlay
    current_path = upscaled_path
    title = state.get("title") or ""
    if not args.no_text and title.strip():
        print(f"🔧 Phase 2: text overlay '{title[:50]}{'…' if len(title) > 50 else ''}'")
        current_path, size_kb = burn_text(upscaled_path, title, fmt_meta, profile)
    else:
        if args.no_text:
            print(f"  ⊘ Text overlay отключён (--no-text)")
        else:
            print(f"  ⊘ Text overlay пропущен (title пустой)")

    # 5. Watermark
    final_path = current_path
    watermark = (profile.get("branding") or {}).get("watermark")
    if not args.no_watermark and watermark:
        print(f"🔧 Phase 2: watermark '{watermark}'")
        final_path, size_kb = burn_watermark(current_path, watermark, profile)
    else:
        if args.no_watermark:
            print(f"  ⊘ Watermark отключён (--no-watermark)")
        else:
            print(f"  ⊘ Watermark пропущен (branding.watermark пустой)")

    # 6. Update state
    rel = str(final_path.relative_to(SKILL_ROOT)) if final_path.is_absolute() else str(final_path)
    update_state(
        slug_id,
        status="upscaled",
        upscaled_path=rel,
        upscaled_at=now_iso(),
        upscaled_size_kb=size_kb,
        upscaled_w=target[0],
        upscaled_h=target[1],
        upscaled_no_text=bool(args.no_text),
        upscaled_no_watermark=bool(args.no_watermark),
    )

    print(f"\n✅ Phase 2 done!")
    print(f"   📁 {final_path}")
    print(f"   📊 {size_kb} КБ, {target[0]}×{target[1]}")
    print(f"   📋 state: {slug_id} → status=upscaled")
    return 0


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Phase 2 auto pipeline: upscale + text + watermark")
    p.add_argument("slug_id", help="profile/slug или просто slug (default profile)")
    p.add_argument("--profile", default="lab")
    p.add_argument("--to", default=None, help="Custom target WxH (default из format.target_size)")
    p.add_argument("--no-text", action="store_true", help="Пропустить text overlay")
    p.add_argument("--no-watermark", action="store_true", help="Пропустить watermark")
    p.add_argument("--force", action="store_true", help="Перезаписать существующий upscaled")
    args = p.parse_args()
    sys.exit(run(args))
