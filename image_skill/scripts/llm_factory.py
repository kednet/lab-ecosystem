"""
llm_factory.py — обёртка над wish_librarian/agent/ai/factory.py для Video Creator Skill v1.0.

Использует singleton `get_ai_client(use_cache=True)` из WL.
API клиента: generate(system, user, max_tokens, temperature) → str (TEXT, не JSON!)

В этом модуле:
- parse_script_json(raw_text) — парсит text→dict (json.loads + regex fallback)
- generate_script_json(prompt, system, profile_meta) — основная точка входа
- stub_script(source, profile) — fallback если LLM-ключ отсутствует

Phase 1: используется в cmd_script.py для генерации сценариев
Phase 2/3: будет использоваться для генерации BGM-тегов, анонсов и т.д.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Optional

# Добавляем путь к wish_librarian в sys.path
_SKILL_ROOT = Path(__file__).resolve().parent.parent
_WL_ROOT = Path("C:/Users/kfigh/wish_librarian")
if _WL_ROOT.exists() and str(_WL_ROOT) not in sys.path:
    sys.path.insert(0, str(_WL_ROOT))

try:
    from agent.ai.factory import get_ai_client
    _WL_AVAILABLE = True
except Exception as _e:
    _WL_AVAILABLE = False
    _WL_IMPORT_ERROR = str(_e)


# UTF-8 fix
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


# === JSON-парсер с fallback ===
_JSON_FENCE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def parse_script_json(raw: str) -> dict:
    """Парсит text-вывод LLM → dict.

    Стратегия:
    1. Попробовать json.loads на всю строку
    2. Попробовать найти ```json ... ``` блок
    3. Попробовать найти первую {...} в тексте (greedy)
    4. Бросить ValueError

    >>> parse_script_json('{"title": "x", "hook": "y"}')['title']
    'x'
    """
    raw = raw.strip()

    # 1. Прямой JSON
    try:
        return json.loads(raw)
    except Exception:
        pass

    # 2. Markdown-fenced JSON
    m = _JSON_FENCE.search(raw)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass

    # 3. Greedy: первая {...} в тексте
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass

    raise ValueError(f"Не удалось распарсить JSON из вывода LLM (длина={len(raw)}): {raw[:200]}...")


# === LLM-вызов с fallback ===
def get_llm_client():
    """Singleton LLM-клиент из WL. Бросает ImportError если WL недоступен."""
    if not _WL_AVAILABLE:
        raise ImportError(f"wish_librarian.agent.ai.factory недоступен: {_WL_IMPORT_ERROR}")
    return get_ai_client(use_cache=True)


# === Stub-генератор (если LLM не сработал) ===
def stub_script(source: str, profile_meta: dict) -> dict:
    """Заглушка, когда LLM-вызов упал. Возвращает валидный скелет сценария.

    profile_meta — словарь из data/profiles/<name>.yaml (для watermark/hashtags_base/voice_tone).
    """
    title_seed = source.strip()[:60]
    if not title_seed:
        title_seed = "Без названия"
    watermark = profile_meta.get("branding", {}).get("watermark", "@pulab")
    hashtags = profile_meta.get("hashtags_base", [])
    return {
        "title": title_seed,
        "hook": f"Стой. {title_seed.lower()} — это меняет всё.",
        "structure": [
            {"t_start": 0, "t_end": 3, "shot": "Крупный план: рука на сердце, тёплый свет", "vo_text": f"{title_seed}."},
            {"t_start": 3, "t_end": 10, "shot": "Средний план: задумчивое лицо", "vo_text": "Ты замечала это в себе?"},
            {"t_start": 10, "t_end": 18, "shot": "Натюрморт: книга, блокнот, цветы", "vo_text": "Вот что об этом пишут те, кто прошёл путь."},
            {"t_start": 18, "t_end": 25, "shot": "Общий план: рассвет/закат", "vo_text": "Попробуй применить сегодня."},
            {"t_start": 25, "t_end": 30, "shot": "Стоп-кадр: логотип", "vo_text": "Сохрани и пересмотри"},
        ],
        "cta": f"Больше — в закрепе {watermark}",
        "caption": f"{title_seed}. Коротко, по делу, без воды. #видео",
        "hashtags": hashtags + ["#stub"],
        "voice_tone": "neutral",
        "music_mood": "ambient",
        "source_meta": f"stub:{title_seed[:30]}",
    }


# === Главная точка входа ===
def generate_script_json(
    system_prompt: str,
    user_prompt: str,
    profile_meta: dict,
    *,
    max_tokens: int = 1500,
    temperature: float = 0.7,
    use_stub_on_error: bool = True,
) -> dict:
    """Генерирует сценарий через LLM. Парсит text→dict. Fallback на stub при ошибке.

    Args:
        system_prompt: системный промпт (роль, формат вывода)
        user_prompt: пользовательский промпт (задача + параметры + контекст профиля)
        profile_meta: dict из data/profiles/<name>.yaml
        max_tokens, temperature: LLM-параметры
        use_stub_on_error: если True — при ошибке вернёт stub_script (НЕ throw)

    Returns:
        dict с полями: title, hook, structure[], cta, caption, hashtags[], voice_tone, music_mood, source_meta
    """
    source_in_user = re.search(r'"source":\s*"([^"]+)"', user_prompt)
    source_fallback = source_in_user.group(1) if source_in_user else ""

    try:
        client = get_llm_client()
        raw = client.generate(
            system=system_prompt,
            user=user_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return parse_script_json(raw)
    except Exception as e:
        if use_stub_on_error:
            print(f"[llm_factory] WARN: LLM упал ({type(e).__name__}: {e}). Возвращаю stub.", file=sys.stderr)
            return stub_script(source_fallback or "видео", profile_meta)
        raise


# === CLI ===
if __name__ == "__main__":
    # Smoke-test
    print(f"WL available: {_WL_AVAILABLE}")
    if not _WL_AVAILABLE:
        print(f"Import error: {_WL_IMPORT_ERROR}")
    else:
        try:
            client = get_llm_client()
            print(f"Client type: {type(client).__name__}")
        except Exception as e:
            print(f"get_ai_client error: {e}")

    # Тест stub
    test_meta = {"branding": {"watermark": "@pulab_ru"}, "hashtags_base": ["#test"]}
    stub = stub_script("5 ошибок карты желаний", test_meta)
    print(f"Stub keys: {sorted(stub.keys())}")
    print(f"Stub title: {stub['title']}")
    print(f"Stub shots: {len(stub['structure'])}")
