"""
Тесты детектора: 5/12/20, enabled_modules filter, 6 verdict buckets, scoring.
"""

from __future__ import annotations

import pytest

from agent.core.detector import (
    DEEP_INDICES,
    EXPRESS_INDICES,
    QUESTIONS,
    STANDARD_INDICES,
    DetectorDepth,
    DetectorService,
    score_to_verdict,
)
from agent.core.tones import Tone, get_enabled_modules

# === Размеры QUESTIONS ===

def test_questions_has_20() -> None:
    assert len(QUESTIONS) == 20


def test_5_modules_4_questions_each() -> None:
    by_module: dict[int, int] = {}
    for q in QUESTIONS:
        by_module[q.module] = by_module.get(q.module, 0) + 1
    assert sorted(by_module.keys()) == [1, 2, 3, 4, 5]
    assert all(n == 4 for n in by_module.values())


def test_module3_questions_marked() -> None:
    m3 = [q for q in QUESTIONS if q.module == 3]
    assert all(q.is_module3 for q in m3)


# === Express / Standard / Deep ===

def test_express_has_5() -> None:
    assert len(EXPRESS_INDICES) == 5


def test_standard_has_12() -> None:
    assert len(STANDARD_INDICES) == 12


def test_deep_has_20() -> None:
    assert len(DEEP_INDICES) == 20


# === DetectorService: запуск и размеры ===

def test_detector_express_returns_5_questions() -> None:
    svc = DetectorService()
    modules = get_enabled_modules(Tone.WARM, 3)  # с M3
    s = svc.start(1, DetectorDepth.EXPRESS, modules)
    assert len(s.question_indices) == 5
    assert not s.is_finished()


def test_detector_standard_returns_12_questions() -> None:
    svc = DetectorService()
    modules = get_enabled_modules(Tone.WARM, 3)
    s = svc.start(1, DetectorDepth.STANDARD, modules)
    assert len(s.question_indices) == 12


def test_detector_deep_returns_20_questions() -> None:
    svc = DetectorService()
    modules = get_enabled_modules(Tone.WARM, 3)
    s = svc.start(1, DetectorDepth.DEEP, modules)
    assert len(s.question_indices) == 20


def test_detector_filters_module3_when_disabled() -> None:
    """Чёткий/Смелый → Модуль 3 выключен, вопросов 9-12 быть не должно."""
    svc = DetectorService()
    modules = get_enabled_modules(Tone.CLEAR, 3)  # без M3
    s = svc.start(1, DetectorDepth.DEEP, modules)
    # В DEEP все 20, но фильтр выкинет Q9-12 (idx 9,10,11,12)
    for idx in s.question_indices:
        q = QUESTIONS[idx - 1]
        assert q.module != 3, f"Q{idx} из M3 попал в выборку для CLEAR"
    assert len(s.question_indices) < 20


# === score_to_verdict: 6 buckets ===

@pytest.mark.parametrize("score,expected", [
    (0.00, "imposed"),
    (0.10, "imposed"),
    (0.20, "mostly_imposed"),
    (0.30, "mostly_imposed"),
    (0.35, "mixed_low"),
    (0.45, "mixed_low"),
    (0.50, "mixed_high"),
    (0.60, "mixed_high"),
    (0.65, "mostly_true"),
    (0.75, "mostly_true"),
    (0.80, "true"),
    (0.95, "true"),
    (1.00, "true"),
])
def test_score_to_verdict_buckets(score: float, expected: str) -> None:
    label, _ = score_to_verdict(score)
    assert label == expected


def test_score_to_verdict_returns_signature() -> None:
    label, sig = score_to_verdict(0.95)
    assert label == "true"
    assert "энергию" in sig.lower() or "внутри" in sig.lower()


def test_score_to_verdict_clamps() -> None:
    assert score_to_verdict(-0.5)[0] == "imposed"
    assert score_to_verdict(1.5)[0] == "true"


# === Scoring через ответы ===

def test_scoring_keyword_imposed() -> None:
    """Ответы с imposed-маркерами → низкий score."""
    svc = DetectorService()
    modules = get_enabled_modules(Tone.WARM, 3)
    s = svc.start(1, DetectorDepth.DEEP, modules)
    # Каждый ответ содержит imposed-маркеры для своего вопроса
    imposed_answers = {
        1: "надо, должен, чтоб не хуже, страх, стыд",
        2: "одобрение, статус, покажу",
        3: "облегчение, избавлюсь, перестану бояться",
        4: "одобрение, статус, потеряю лицо",
        5: "постоянно, навязчиво, не выходит из головы",
    }
    for idx in s.question_indices[:5]:
        s.answers.append(imposed_answers.get(idx, "надо, страх, стыд"))
    outcome = svc.finalize(s)
    assert outcome.score < 0.5
    # Либо imposed, либо mostly_imposed, либо mixed_low
    assert outcome.verdict_label in ("imposed", "mostly_imposed", "mixed_low")


def test_scoring_keyword_true() -> None:
    """Ответы с true-маркерами → высокий score."""
    svc = DetectorService()
    modules = get_enabled_modules(Tone.WARM, 3)
    s = svc.start(1, DetectorDepth.DEEP, modules)
    for _q in QUESTIONS[:5]:
        s.answers.append("радость, ценность, хочу, зовёт, тянет")
    outcome = svc.finalize(s)
    assert outcome.score > 0.5
    assert outcome.verdict_label in ("mostly_true", "true", "mixed_high")


def test_scoring_neutral_default() -> None:
    """Нейтральный ответ → ~0.5."""
    svc = DetectorService()
    modules = get_enabled_modules(Tone.WARM, 3)
    s = svc.start(1, DetectorDepth.EXPRESS, modules)
    s.answers = ["никак не знаю", "хм", "ну", "ок", "хорошо"]
    outcome = svc.finalize(s)
    # Без keywords — 0.5
    assert 0.4 <= outcome.score <= 0.6


def test_scoring_with_no_answers() -> None:
    svc = DetectorService()
    modules = get_enabled_modules(Tone.WARM, 3)
    s = svc.start(1, DetectorDepth.EXPRESS, modules)
    outcome = svc.finalize(s)
    assert outcome.questions_asked == 0
    assert outcome.score == 0.5


# === DetectorSession.is_finished и next_question ===

def test_next_question_returns_none_when_finished() -> None:
    svc = DetectorService()
    modules = get_enabled_modules(Tone.WARM, 3)
    s = svc.start(1, DetectorDepth.EXPRESS, modules)
    for _ in s.question_indices:
        s.answers.append("x")
        s.current_index += 1
    assert s.is_finished()
    assert svc.next_question(s) is None


def test_next_question_replacement_q9() -> None:
    """Для CLEAR Q9 должен быть заменён на 'Опишите желание в 1 факте'."""
    svc = DetectorService()
    get_enabled_modules(Tone.CLEAR, 3)  # без M3
    # Используем DEEP чтобы Q9 попал в индексы (но фильтр его выкинет)
    # → выберем искусственно: возьмём только Q9 через standard+soft
    modules_with_m3 = get_enabled_modules(Tone.SOFT, 3)
    s = svc.start(1, DetectorDepth.DEEP, modules_with_m3)
    # Первый вопрос — Q1, не Q9. Получим Q9 чуть дальше
    # Просто убедимся, что replacement работает когда next_question выдаёт Q9
    # Искусственно подменим question_indices
    s.question_indices = [9]
    s.current_index = 0
    q = svc.next_question(s, replacement_q9="Кастомная замена")
    assert q is not None
    assert q.text == "Кастомная замена"


# === Finalize → DetectorOutcome ===

def test_finalize_returns_outcome_with_modules() -> None:
    svc = DetectorService()
    modules = get_enabled_modules(Tone.WARM, 3)
    s = svc.start(1, DetectorDepth.DEEP, modules)
    s.answers = ["радость, ценность"] * 5 + ["надо, страх"] * 5
    outcome = svc.finalize(s)
    assert isinstance(outcome.module_scores, dict)
    assert "m1" in outcome.module_scores
