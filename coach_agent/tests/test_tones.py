"""
Тесты тонов: 4 тона × 5 интенсивностей, enabled_modules, build_system_prompt.
"""

from __future__ import annotations

import pytest

from agent.ai.prompts import ContextBlock, build_system_prompt
from agent.core.tones import (
    INTENSITY_MODIFIERS,
    TONE_ADDONS,
    Tone,
    get_enabled_modules,
    get_module3_replacement,
)

# === Базовая структура ===

def test_tone_enum_has_4_values() -> None:
    assert set(t.value for t in Tone) == {"warm", "clear", "bold", "soft"}


def test_intensity_modifiers_has_5_values() -> None:
    assert set(INTENSITY_MODIFIERS.keys()) == {1, 2, 3, 4, 5}


def test_tone_addons_has_4_values() -> None:
    assert set(TONE_ADDONS.keys()) == set(Tone)


# === enabled_modules по PRD 5.7 ===

def test_enabled_modules_warm_1_2_no_m3() -> None:
    for i in (1, 2):
        modules = get_enabled_modules(Tone.WARM, i)
        assert 3 not in modules
        assert {1, 2, 4, 5}.issubset(set(modules))


def test_enabled_modules_warm_3_4_5_with_m3() -> None:
    for i in (3, 4, 5):
        modules = get_enabled_modules(Tone.WARM, i)
        assert 3 in modules
        assert set(modules) == {1, 2, 3, 4, 5}


def test_enabled_modules_clear_never_m3() -> None:
    for i in (1, 2, 3, 4, 5):
        modules = get_enabled_modules(Tone.CLEAR, i)
        assert 3 not in modules
        assert set(modules) == {1, 2, 4, 5}


def test_enabled_modules_bold_never_m3() -> None:
    for i in (1, 2, 3, 4, 5):
        modules = get_enabled_modules(Tone.BOLD, i)
        assert 3 not in modules
        assert set(modules) == {1, 2, 4, 5}


def test_enabled_modules_soft_always_m3() -> None:
    for i in (1, 2, 3, 4, 5):
        modules = get_enabled_modules(Tone.SOFT, i)
        assert 3 in modules
        assert set(modules) == {1, 2, 3, 4, 5}


# === Module3 replacement ===

def test_module3_replacement_clear() -> None:
    r = get_module3_replacement(Tone.CLEAR)
    assert r is not None
    assert "факт" in r.lower() or "конкретн" in r.lower()


def test_module3_replacement_bold() -> None:
    r = get_module3_replacement(Tone.BOLD)
    assert r is not None
    assert "недел" in r.lower() or "сделает" in r.lower()


def test_module3_replacement_warm_none() -> None:
    # Warm — модуль 3 включается при 3-5, замены нет
    assert get_module3_replacement(Tone.WARM) is None


def test_module3_replacement_soft_none() -> None:
    # Soft — модуль 3 всегда работает, замены нет
    assert get_module3_replacement(Tone.SOFT) is None


# === build_system_prompt: все 20 комбинаций ===

# Маппинг tone → кириллическое имя (как в TONE_ADDONS)
_TONE_NAMES: dict[Tone, str] = {
    Tone.WARM: "ТЁПЛЫЙ",
    Tone.CLEAR: "ЧЁТКИЙ",
    Tone.BOLD: "СМЕЛЫЙ",
    Tone.SOFT: "МЯГКИЙ",
}


@pytest.mark.parametrize("tone", [Tone.WARM, Tone.CLEAR, Tone.BOLD, Tone.SOFT])
@pytest.mark.parametrize("intensity", [1, 2, 3, 4, 5])
def test_build_system_prompt_all_combinations(tone: Tone, intensity: int) -> None:
    ctx = ContextBlock(channel="web")
    prompt = build_system_prompt(tone, intensity, ctx)
    assert isinstance(prompt, str)
    assert len(prompt) > 100
    # Содержит маркер тона (кириллица в верхнем регистре)
    assert _TONE_NAMES[tone] in prompt
    # Содержит маркер интенсивности
    assert str(intensity) in prompt


def test_build_system_prompt_with_active_desire() -> None:
    ctx = ContextBlock(active_desire_title="Купить MacBook", channel="web")
    prompt = build_system_prompt(Tone.WARM, 3, ctx)
    assert "MacBook" in prompt


def test_build_system_prompt_with_recent_messages() -> None:
    ctx = ContextBlock(
        recent_messages=["[user] Хочу разобраться"],
        channel="telegram",
    )
    prompt = build_system_prompt(Tone.SOFT, 5, ctx)
    assert "Хочу разобраться" in prompt
    assert "telegram" in prompt.lower()


def test_build_system_prompt_invalid_intensity_raises() -> None:
    ctx = ContextBlock()
    with pytest.raises(ValueError):
        build_system_prompt(Tone.WARM, 6, ctx)
    with pytest.raises(ValueError):
        build_system_prompt(Tone.WARM, 0, ctx)
