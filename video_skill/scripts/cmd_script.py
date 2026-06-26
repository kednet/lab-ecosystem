"""
cmd_script.py — подкоманда `video.py script` (C-режим, Phase 1).

Генерирует сценарий через LLM (или stub) и сохраняет в:
- tmp/scripts/<profile>/<slug>.md  (markdown-каркас + frontmatter JSON)
- state/<profile>/<slug>.json       (метаданные идемпотентности)

Использование:
    python scripts/video.py script <platform> <goal> <tone> <duration> <source> \
        [--profile=<name>] [--dry-run] [--force] [--from-file=<path>]

Алгоритм:
1. resolve_params() — собрать финальные параметры по override-матрице
2. Проверить идемпотентность (state.status == script_ready + !force → skip)
3. build_prompt() — собрать system + user промпт с инъекцией профиля
4. generate_script_json() — вызвать LLM (или stub)
5. render_markdown() — JSON → markdown-каркас
6. save tmp/scripts/.../slug.md + state.update
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Optional

import yaml

from _video_common import (  # type: ignore  # noqa: E402
    SCRIPTS_DIR,
    TMP_DIR,
    now_iso,
    load_env,
    get_env,
    default_profile_name,
)
from slugify import slugify  # type: ignore  # noqa: E402
from state import load, save, update  # type: ignore  # noqa: E402
from cmd_profile import load_profile  # type: ignore  # noqa: E402
from llm_factory import generate_script_json  # type: ignore  # noqa: E402

# UTF-8 fix
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# Системный промпт — в Phase 1 хранится в этом модуле (позже вынесем в prompts/script-generate.md)
SYSTEM_PROMPT = """Ты — сценарист коротких видео для соцсетей.
Твоя задача — генерировать JSON-сценарии строго по схеме.

Формат вывода: ТОЛЬКО валидный JSON, без markdown-обёрток, без пояснений до или после.

Схема:
{
  "title": "<≤70 символов, цепляющий заголовок на русском>",
  "hook": "<первая фраза, 0-3 сек, ≤100 символов, вопрос или провокация>",
  "structure": [
    {"t_start": 0, "t_end": 3, "shot": "<что в кадре, на русском, ≤80 символов>",
     "vo_text": "<текст для голоса, ≤140 символов>"},
    ...минимум 3 шота, каждый ≤ duration/N сек (N = ceil(duration/5))
  ],
  "cta": "<≤100 символов, призыв к действию с watermark если задан>",
  "caption": "<≤200 символов, описание для поста>",
  "hashtags": ["#тег1", "#тег2", ...минимум 5, максимум 10],
  "voice_tone": "soulful|bold|inspiring|educational|playful|neutral|calm|confident|warm|energetic",
  "music_mood": "ambient|tide|bowls|cosmic|sea|uplifting|tense|playful|silence",
  "source_meta": "<откуда тема, ≤50 символов>"
}

Правила:
- vo_text: ≤15 символов в секунду (нормальный темп речи)
- shot.vo_text — строго на русском, разговорный, тёплый тон
- cta: естественно встраивает watermark (например "ссылка в закрепе @pulab_ru")
- hashtags: с #, без пробелов
- tone/voice_tone должны совпадать (или быть из voice_tones профиля)
"""


# === Resolve params (override-матрица) ===
def resolve_params(args, profile: dict) -> dict:
    """Собрать финальные параметры по матрице приоритетов.

    Приоритеты (от высшего к низшему):
    1. CLI-флаг (--voice, --duration, ...)
    2. profile.defaults.X
    3. profile.cta_profiles[tone][0] / cta_default
    """
    defaults = profile.get("defaults") or {}
    branding = profile.get("branding") or {}
    cta_profiles = profile.get("cta_profiles") or {}
    voice_tones_allowed = profile.get("voice_tones") or []

    # Параметры из CLI (могут быть None)
    platform = getattr(args, "platform", None) or defaults.get("platform")
    tone = getattr(args, "tone", None) or defaults.get("tone")
    goal = getattr(args, "goal", None) or defaults.get("goal")
    duration = getattr(args, "duration", None) or defaults.get("duration")
    voice = getattr(args, "voice", None) or defaults.get("voice")
    speed = getattr(args, "speed", None) or defaults.get("speed", 1.0)
    music_mood = getattr(args, "music_mood", None) or defaults.get("music_mood", "ambient")
    source = getattr(args, "source", None) or ""

    # Валидация обязательных
    if not platform:
        raise ValueError("platform обязателен: укажите явно или задайте в profile.defaults")
    if not tone:
        raise ValueError("tone обязателен: укажите явно или задайте в profile.defaults")
    if not goal:
        raise ValueError("goal обязателен: укажите явно или задайте в profile.defaults")
    if not duration:
        raise ValueError("duration обязателен: укажите явно или задайте в profile.defaults")
    if voice_tones_allowed and tone not in voice_tones_allowed:
        print(f"[resolve_params] WARN: tone='{tone}' не в voice_tones профиля ({voice_tones_allowed})", file=sys.stderr)

    # CTA: profile.cta_profiles[tone][0] → profile.branding.cta_default
    cta = getattr(args, "cta", None)
    if not cta:
        cta_list = cta_profiles.get(tone) or []
        cta = cta_list[0] if cta_list else branding.get("cta_default", "")

    # Hashtags: merge profile.hashtags_base + (потом LLM добавит ещё)
    hashtags_base = profile.get("hashtags_base") or []

    return {
        "platform": platform,
        "tone": tone,
        "goal": goal,
        "duration": int(duration),
        "voice": voice,
        "speed": float(speed),
        "music_mood": music_mood,
        "source": source,
        "cta": cta,
        "hashtags_base": hashtags_base,
        "watermark": branding.get("watermark", ""),
        "accent_color": branding.get("accent_color", ""),
    }


# === Build user-prompt ===
def build_prompt(params: dict, profile: dict) -> str:
    """Собрать user-prompt с инъекцией контекста профиля."""
    profile_block = f"""
## Контекст профиля "{profile.get('display_name', '?')}"
- Описание: {profile.get('description', '')}
- Бренд watermark: {params['watermark']}
- Акцентный цвет: {params['accent_color']}
- Базовые хештеги: {', '.join(params['hashtags_base'])}
- Подсказки по темам: {'; '.join(profile.get('source_domains', []))}
- CTA-варианты для тона '{params['tone']}': {' || '.join((profile.get('cta_profiles') or {}).get(params['tone'], []))}
""".strip()

    user = f"""Сгенерируй сценарий видео по параметрам:

## Параметры
- platform: {params['platform']}
- goal: {params['goal']}
- tone: {params['tone']}
- duration: {params['duration']} секунд
- voice (Yandex SpeechKit): {params['voice']}
- music_mood: {params['music_mood']}
- source (тема): "{params['source']}"

{profile_block}

## Дополнительные правила
- Количество шотов: ровно N = ceil({params['duration']} / 5), минимум 3
- Каждый шот ровно покрывает duration: t_start=предыдущий t_end, последний t_end = {params['duration']}
- vo_text говорящий, тёплый, разговорный, от женского рода (аудитория женщины 25-55)
- cta: естественно упоминает watermark "{params['watermark']}"
- hashtags: минимум 5, должны включать {', '.join(params['hashtags_base'][:2])}

Верни ТОЛЬКО JSON, без пояснений."""
    return user


# === Render markdown из JSON ===
def render_markdown(script: dict, params: dict, profile: dict) -> str:
    """Рендерит dict-сценарий → markdown-файл с YAML-frontmatter (JSON) + body."""
    # Фронтматтер — JSON-строка, чтобы validate_script мог парсить
    frontmatter_dict = {
        **script,
        "platform": params["platform"],
        "goal": params["goal"],
        "duration": params["duration"],
        "voice": params["voice"],
        "profile": profile.get("name", ""),
    }
    frontmatter_json = json.dumps(frontmatter_dict, ensure_ascii=False, indent=2)

    # Body — читаемая таблица шотов
    lines = [
        "---",
        "```json",
        frontmatter_json,
        "```",
        "---",
        "",
        f"# {script.get('title', 'Без названия')}",
        "",
        f"> **Hook (0-{params['duration']//6} сек):** {script.get('hook', '')}",
        "",
        f"**Платформа:** {params['platform']} · **Тон:** {params['tone']} · "
        f"**Длительность:** {params['duration']} сек · **Голос:** {params['voice']}",
        f"**Профиль:** {profile.get('display_name', '')} · **Watermark:** {params['watermark']}",
        "",
        "## Структура",
        "",
        "| # | t_start | t_end | Shot | VO text |",
        "|---|---------|-------|------|---------|",
    ]
    for i, shot in enumerate(script.get("structure") or [], 1):
        lines.append(
            f"| {i} | {shot.get('t_start', 0)} | {shot.get('t_end', 0)} | "
            f"{shot.get('shot', '')} | {shot.get('vo_text', '')} |"
        )
    lines.extend([
        "",
        "## CTA",
        "",
        f"> {script.get('cta', '')}",
        "",
        f"**URL:** {profile.get('branding', {}).get('cta_url', '')}",
        "",
        "## Caption (для поста)",
        "",
        script.get("caption", ""),
        "",
        "## Hashtags",
        "",
        " ".join(script.get("hashtags") or []),
        "",
        "## Мета",
        "",
        f"- voice_tone: `{script.get('voice_tone', '')}`",
        f"- music_mood: `{script.get('music_mood', '')}`",
        f"- source_meta: {script.get('source_meta', '')}",
        "",
    ])
    return "\n".join(lines)


# === Main entry ===
def run(args) -> int:
    """CLI entry: вызывается из video.py:script подкоманды."""
    load_env()
    profile_name = getattr(args, "profile", None) or default_profile_name()
    try:
        profile = load_profile(profile_name)
    except Exception as e:
        print(f"❌ {e}", file=sys.stderr)
        return 1

    # Source: из --from-file или позиционного аргумента
    source = getattr(args, "source", None) or ""
    from_file = getattr(args, "from_file", None)
    if from_file:
        try:
            source = Path(from_file).read_text(encoding="utf-8").strip()
        except Exception as e:
            print(f"❌ Не удалось прочитать --from-file={from_file}: {e}", file=sys.stderr)
            return 1

    # Подставляем source в args для resolve_params
    args.source = source

    # Параметры
    try:
        params = resolve_params(args, profile)
    except ValueError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 2

    # Slug
    slug = slugify(params["source"] or "video")
    if not slug:
        slug = "video"

    # State
    slug_id = f"{profile_name}/{slug}"
    state_data = load(slug_id)

    # Идемпотентность
    if state_data.get("status") == "script_ready" and not getattr(args, "force", False):
        print(f"⏭  Сценарий уже есть: {state_data.get('script_path')}")
        print(f"   status={state_data.get('status')}, script_at={state_data.get('script_at')}")
        print(f"   Используйте --force чтобы перезаписать")
        return 0

    # Dry-run
    if getattr(args, "dry_run", False):
        print("=" * 60)
        print("DRY RUN — параметры:")
        print(json.dumps(params, ensure_ascii=False, indent=2))
        print("=" * 60)
        print("USER PROMPT:")
        print(build_prompt(params, profile))
        print("=" * 60)
        print(f"Будет сохранено в: tmp/scripts/{profile_name}/{slug}.md")
        print(f"State: state/{profile_name}/{slug}.json")
        return 0

    # Генерация через LLM (или stub)
    print(f"🎬 Генерирую сценарий для '{params['source'][:50]}' (profile={profile_name})...")
    user_prompt = build_prompt(params, profile)
    script = generate_script_json(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        profile_meta=profile,
        max_tokens=1500,
        temperature=0.7,
    )

    # Рендер markdown
    md = render_markdown(script, params, profile)
    md_dir = SCRIPTS_DIR / profile_name
    md_dir.mkdir(parents=True, exist_ok=True)
    md_path = md_dir / f"{slug}.md"
    md_path.write_text(md, encoding="utf-8")

    # State
    state_data = update(
        slug_id,
        title=script.get("title", ""),
        status="script_ready",
        script_at=now_iso(),
        script_path=str(md_path.relative_to(Path(__file__).resolve().parent.parent)),
        created_at=state_data.get("created_at") or now_iso(),
        error=None,
    )

    print(f"✅ Сценарий готов:")
    print(f"   📄 {md_path}")
    print(f"   📊 state/{profile_name}/{slug}.json (status=script_ready)")
    print(f"   🎯 {script.get('title', '?')[:60]}")
    print(f"   🎬 {len(script.get('structure') or [])} шотов, ~{params['duration']} сек")
    return 0


if __name__ == "__main__":
    # Standalone test (использовать через video.py в норме)
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("platform")
    p.add_argument("goal")
    p.add_argument("tone")
    p.add_argument("duration", type=int)
    p.add_argument("source")
    p.add_argument("--profile", default=None)
    p.add_argument("--voice", default=None)
    p.add_argument("--speed", type=float, default=None)
    p.add_argument("--music-mood", default=None)
    p.add_argument("--cta", default=None)
    p.add_argument("--from-file", default=None)
    p.add_argument("--out", default=None)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--force", action="store_true")
    args = p.parse_args()
    sys.exit(run(args))
