"""
cmd_generate.py — главная sub-команда image_skill Phase 1.

Алгоритм:
1. resolve_params(cli_args, profile) → финальные параметры по override-матрице
2. resolve_format(format_name) → width_ratio, height_ratio, target_size из formats.yaml
3. build_prompt(params, profile, format_meta) → текст промпта (через LLM-стилизацию)
4. yandex_art.generate(prompt, width_ratio, height_ratio, seed) → PNG bytes
5. save_image(bytes, tmp/images/<profile>/<slug>-<format>.png)
6. validate_image_file (PNG signature, size)
7. state.update(...) → status="saved", image_path, image_size_kb, seed, ...
"""
from __future__ import annotations

import json
import random
import re
import sys
from pathlib import Path
from typing import Optional

from _image_common import (
    IMAGES_DIR, get_format, get_env, load_formats, now_iso,
)
from cmd_profile import load_profile
from slugify import slugify
from state import load as load_state, save, update as update_state
from yandex_art import generate as yandex_generate, save_image
from validate_image import validate_image_file

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


# === Override-матрица (как в video_skill) ===
def resolve_params(args, profile: dict) -> dict:
    """
    Приоритет (от высшего к низшему):
    1. CLI-флаг (args.format, args.style, args.mood, args.seed)
    2. profile.defaults.{format,style,mood,seed}
    3. format.aspect (если format задан)

    Обязательно: format.
    """
    defaults = profile.get("defaults", {})

    fmt = args.format or defaults.get("format")
    if not fmt:
        raise ValueError(
            "format обязателен: укажи --format=<name> или defaults.format в профиле. "
            f"Доступные: {list(load_formats().keys())}"
        )
    # Validate format exists
    try:
        fmt_meta = get_format(fmt)
    except KeyError as e:
        raise ValueError(str(e))

    style = args.style or defaults.get("style", "watercolor")
    mood = args.mood or defaults.get("mood", "soft")

    seed = args.seed
    if seed is None:
        seed = defaults.get("seed")
    if seed is None:
        seed = random.randint(0, 2**32 - 1)

    return {
        "format": fmt,
        "format_meta": fmt_meta,
        "style": style,
        "mood": mood,
        "aspect": fmt_meta["aspect"],
        "width_ratio": fmt_meta["width_ratio"],
        "height_ratio": fmt_meta["height_ratio"],
        "seed": int(seed),
    }


# === LLM-стилизация промпта ===
def build_prompt(user_text: str, params: dict, profile: dict) -> str:
    """
    Построить финальный EN-промпт для YandexART.

    Стратегия:
    1. Попробовать LLM-стилизацию через prompts/image-prompt.md (если LLM доступен)
    2. Fallback: ручная сборка EN-промпта по шаблону
    """
    prompt_styles = profile.get("prompt_styles", {})
    prompt_moods = profile.get("prompt_moods", {})
    palette = profile.get("branding", {}).get("palette", {})
    negative = profile.get("negative_prompts", [])

    style_hint = prompt_styles.get(params["style"], params["style"])
    mood_hint = prompt_moods.get(params["mood"], params["mood"])

    # Try LLM first
    try:
        from llm_factory import get_llm_client
        client = get_llm_client()
        template = (PROMPTS_DIR / "image-prompt.md").read_text(encoding="utf-8")
        # palette — dict, format() не может его представить, преобразуем в строку
        palette_str = ", ".join(f"{k}={v}" for k, v in palette.items()) if palette else "(none)"
        user_msg = template.format(
            format_label=params["format_meta"]["label"],
            aspect=params["aspect"],
            display_name=profile.get("display_name", ""),
            style=params["style"],
            style_hint=style_hint,
            mood=params["mood"],
            mood_hint=mood_hint,
            palette=palette_str,
            accent_color=profile.get("branding", {}).get("accent_color", ""),
            user_text=user_text,
            negative=", ".join(negative),
        )
        system_msg = (
            "Ты — prompt engineer для YandexART. "
            "Преобразуй запрос пользователя в подробный EN-промпт (1-2 предложения). "
            "Не добавляй пояснений, не используй markdown. "
            "Только итоговая строка-промпт."
        )
        llm_prompt = client.generate(
            system=system_msg,
            user=user_msg,
            max_tokens=200,
            temperature=0.7,
        ).strip()
        if llm_prompt and len(llm_prompt) > 10 and not llm_prompt.startswith("["):
            print(f"  → LLM-стилизованный промпт: {llm_prompt[:120]}…", file=sys.stderr)
            return llm_prompt
    except Exception as e:
        print(f"  ⚠ LLM-стилизация не удалась ({type(e).__name__}: {e}), fallback", file=sys.stderr)

    # Fallback: ручная EN-сборка
    primary = palette.get("primary", "#E11D48")
    primary_color = {
        "#E11D48": "rose-pink", "#881337": "deep-rose", "#FDA4AF": "soft-pink",
        "#FFF1F2": "pale-pink", "#3B82F6": "blue", "#F59E0B": "golden",
        "#7C3AED": "violet", "#10B981": "emerald-green",
    }.get(primary.upper(), primary)

    parts = [user_text.strip().rstrip(".")]
    if style_hint:
        parts.append(style_hint)
    if mood_hint:
        parts.append(mood_hint)
    parts.append(f"{primary_color} color scheme, {primary} accents")
    if negative:
        parts.append(f"no {', no '.join(negative[:3])}")
    parts.append("high quality, detailed, professional composition")
    return ", ".join(parts)


# === Main run ===
def run(args) -> int:
    """CLI: generate <format> <source_text> [--profile] [--style] [--mood] [--seed] [--force] [--dry-run]"""
    profile = load_profile(args.profile)
    params = resolve_params(args, profile)
    slug = slugify(args.source_text, max_length=60)
    slug_id = f"{args.profile}/{slug}"

    # Idempotency check
    existing = load_state(slug_id)
    if existing.get("status") == "saved" and existing.get("image_path") and not args.force:
        print(f"⏭ Изображение уже есть: {existing['image_path']}")
        print(f"   Для перегенерации используй --force")
        return 0

    # Build prompt
    print(f"📝 Генерирую: profile={args.profile}, format={params['format']}, "
          f"style={params['style']}, mood={params['mood']}, seed={params['seed']}")
    final_prompt = build_prompt(args.source_text, params, profile)
    print(f"  → Промпт ({len(final_prompt)} chars): {final_prompt[:150]}…")

    if args.dry_run:
        print("\n🧪 DRY-RUN: API не вызывается, файлы не создаются")
        print(json.dumps({
            "slug_id": slug_id,
            "params": {k: v for k, v in params.items() if k != "format_meta"},
            "prompt": final_prompt,
            "would_save_to": str(IMAGES_DIR / args.profile / f"{slug}-{params['format']}.png"),
        }, ensure_ascii=False, indent=2))
        return 0

    # Generate
    try:
        png_bytes = yandex_generate(
            prompt=final_prompt,
            width_ratio=params["width_ratio"],
            height_ratio=params["height_ratio"],
            seed=params["seed"],
        )
    except Exception as e:
        update_state(slug_id, status="failed", error=str(e), error_at=now_iso())
        print(f"❌ YandexART упал: {e}", file=sys.stderr)
        return 1

    # Save image (PNG или JPEG — YandexART часто отдаёт JPEG)
    out_dir = IMAGES_DIR / args.profile
    out_path = out_dir / f"{slug}-{params['format']}.jpg"  # дефолт .jpg, save_image может поменять
    size_kb, actual_format = save_image(png_bytes, out_path)
    print(f"  ✓ Сохранено: {out_path} ({size_kb} КБ, format={actual_format})")

    # Validate
    errors = validate_image_file(out_path)
    if errors:
        update_state(slug_id, status="failed", error="; ".join(errors))
        print(f"❌ Валидация: {errors}", file=sys.stderr)
        return 1

    # Update state
    update_state(
        slug_id,
        profile=args.profile,
        slug=slug,
        status="saved",
        title=args.source_text[:100],
        format=params["format"],
        style=params["style"],
        mood=params["mood"],
        aspect=params["aspect"],
        width_ratio=params["width_ratio"],
        height_ratio=params["height_ratio"],
        seed=params["seed"],
        prompt_text=final_prompt,
        image_path=str(out_path.relative_to(Path(__file__).resolve().parent.parent)),
        image_size_kb=size_kb,
        image_mime=f"image/{actual_format}" if actual_format != "unknown" else "application/octet-stream",
        created_at=existing.get("created_at") or now_iso(),
        prompt_at=now_iso(),
        generated_at=now_iso(),
        error=None,
    )

    print(f"\n✅ Готово!")
    print(f"   📁 {out_path}")
    print(f"   📊 {size_kb} КБ, seed={params['seed']}, aspect={params['aspect']}")
    print(f"   📋 state: {slug_id} → status=saved")
    return 0


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Image generation")
    p.add_argument("format", help="Format name: vk_post | vk_story | pinterest | wb | og")
    p.add_argument("source_text", help="Текст запроса на русском или английском")
    p.add_argument("--profile", default="lab")
    p.add_argument("--style", default=None)
    p.add_argument("--mood", default=None)
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--force", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    sys.exit(run(args))
