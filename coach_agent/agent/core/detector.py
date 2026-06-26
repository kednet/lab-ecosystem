"""
Детектор «навязанное vs истинное»: 20 вопросов, 5 модулей, 3 глубины.

Источник: PRD v2.0 раздел 5.
- 5 модулей × 4 вопроса = 20 вопросов
- Глубины: express (5), standard (12), deep (20)
- Поведение Модуля 3 в зависимости от тона (5.7) — учитывается через enabled_modules
- Шкала вердиктов 0..1 → 6 подписей (5.9)

Scoring (Phase 1): простой keyword-based (imposed_keywords=0.2, true_keywords=0.8,
neutral=0.5). В Phase 2 можно подключить AI-assisted scoring.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

# === Типы ===

class DetectorDepth(StrEnum):
    EXPRESS = "express"   # 5 вопросов
    STANDARD = "standard"  # 12 вопросов
    DEEP = "deep"        # 20 вопросов


@dataclass
class Question:
    """Один вопрос детектора."""

    idx: int                # 1..20
    module: int             # 1..5
    text: str               # сам вопрос (с тон-специфичной формулировкой для Q9)
    imposed_keywords: list[str] = field(default_factory=list)
    true_keywords: list[str] = field(default_factory=list)
    # Если true — это вопрос Модуля 3 (телесный), может быть заменён по тону
    is_module3: bool = False


@dataclass
class DetectorSession:
    """Состояние детектора в рамках одной сессии."""

    desire_id: int
    depth: DetectorDepth
    enabled_modules: list[int]
    answers: list[str] = field(default_factory=list)
    question_indices: list[int] = field(default_factory=list)  # индексы по QUESTIONS
    current_index: int = 0  # следующий вопрос к задаче

    def is_finished(self) -> bool:
        return self.current_index >= len(self.question_indices)


@dataclass
class DetectorOutcome:
    """Результат детектора."""

    score: float                           # 0.0..1.0
    verdict_label: str                     # 6 подписей
    module_scores: dict[int, float]        # {1: 0.6, 2: 0.3, ...}
    reasoning: str
    depth: DetectorDepth
    questions_asked: int


# === 20 вопросов (PRD 5.2) ===
# Модуль 1: Глубинная мотивация («5 почему»)
# Модуль 2: Качество желания
# Модуль 3: Телесный интеллект (is_module3=True)
# Модуль 4: Социальный контекст
# Модуль 5: Временная перспектива

QUESTIONS: list[Question] = [
    # --- Модуль 1: Глубинная мотивация ---
    Question(
        idx=1, module=1,
        text="Почему ты этого хочешь? (расскажи подробно)",
        imposed_keywords=["надо", "должен", "чтоб не хуже", "страх", "стыд"],
        true_keywords=["радость", "ценность", "хочу", "зовёт", "тянет"],
    ),
    Question(
        idx=2, module=1,
        text="Что это тебе даст в жизни?",
        imposed_keywords=["не хуже других", "одобрение", "статус", "покажу"],
        true_keywords=["больше собой", "свобода", "смысл", "буду настоящим"],
    ),
    Question(
        idx=3, module=1,
        text="Какое чувство ты ожидаешь, когда это случится?",
        imposed_keywords=["облегчение", "избавлюсь", "перестану бояться"],
        true_keywords=["радость", "полнота", "благодарность", "светлость"],
    ),
    Question(
        idx=4, module=1,
        text="Что ты потеряешь, если это не случится?",
        imposed_keywords=["статус", "одобрение", "лицо"],
        true_keywords=["часть себя", "смысл", "важное"],
    ),
    # --- Модуль 2: Качество желания ---
    Question(
        idx=5, module=2,
        text="Как часто ты думаешь об этом за день?",
        imposed_keywords=["постоянно", "навязчиво", "всё время", "не выходит из головы"],
        true_keywords=["спокойно", "пару раз", "иногда"],
    ),
    Question(
        idx=6, module=2,
        text="Можешь описать конкретно, что именно ты хочешь?",
        imposed_keywords=["не знаю", "как-нибудь", "что-то такое"],
        true_keywords=["конкретно", "вот это", "представляю чётко"],
    ),
    Question(
        idx=7, module=2,
        text="Что изменится в твоей жизни, если это не случится?",
        imposed_keywords=["ничего", "досадно", "ну ладно"],
        true_keywords=["потеряет смысл", "опустеет", "станет тускло"],
    ),
    Question(
        idx=8, module=2,
        text="Кто ещё выиграет, если это сбудется?",
        imposed_keywords=["только я", "будут восхищаться", "завидовать"],
        true_keywords=["близкие", "семья", "окружение", "дети"],
    ),
    # --- Модуль 3: Телесный интеллект ---
    Question(
        idx=9, module=3,
        text="Представь, что желание сбылось. Что чувствует тело?",
        imposed_keywords=["напряжение", "сжатие", "ком"],
        true_keywords=["расслабление", "тепло", "разлилось", "дышится"],
        is_module3=True,
    ),
    Question(
        idx=10, module=3,
        text="Представь, что отказался от этого. Что чувствуешь?",
        imposed_keywords=["облегчение", "ну и ладно", "ничего"],
        true_keywords=["пустота", "грусть", "тоска", "потеря"],
        is_module3=True,
    ),
    Question(
        idx=11, module=3,
        text="Где в теле ты ощущаешь это желание?",
        imposed_keywords=["в голове", "ком в груди", "тревога"],
        true_keywords=["в животе", "солнечное сплетение", "грудь тепло"],
        is_module3=True,
    ),
    Question(
        idx=12, module=3,
        text="Какой цвет у этого желания?",
        imposed_keywords=["серый", "красный", "мутный"],
        true_keywords=["жёлтый", "зелёный", "синий", "тёплый"],
        is_module3=True,
    ),
    # --- Модуль 4: Социальный контекст ---
    Question(
        idx=13, module=4,
        text="Назови людей, у которых это уже есть. Сравниваешь ли ты себя с ними?",
        imposed_keywords=["есть, и завидую", "сравниваю", "у неё есть"],
        true_keywords=["есть, но не про сравнение", "у каждого своё"],
    ),
    Question(
        idx=14, module=4,
        text='Если бы никто никогда не узнал — ты бы всё равно этого хотел?',
        imposed_keywords=["нет, смысл в признании", "без публики нет смысла"],
        true_keywords=["да, это для меня", "мне важно само"],
    ),
    Question(
        idx=15, module=4,
        text='Чей голос в голове говорит "тебе это нужно"?',
        imposed_keywords=["родители", "соцсети", "реклама", "начальник"],
        true_keywords=["мой собственный", "моё"],
    ),
    Question(
        idx=16, module=4,
        text="Что скажет твой лучший друг, если узнает про это желание?",
        imposed_keywords=["обидится", "осудит", "посмеётся"],
        true_keywords=["задумается", "поддержит", "обсудим"],
    ),
    # --- Модуль 5: Временная перспектива ---
    Question(
        idx=17, module=5,
        text="Сколько времени готов уделять этому в неделю?",
        imposed_keywords=["как-нибудь", "не знаю", "найду время"],
        true_keywords=["час", "два", "конкретные часы", "каждое утро"],
    ),
    Question(
        idx=18, module=5,
        text="От чего готов отказаться ради этого?",
        imposed_keywords=["ни от чего", "не готов жертвовать"],
        true_keywords=["от сериалов", "от привычки", "от лишнего"],
    ),
    Question(
        idx=19, module=5,
        text="Готов ли сделать один маленький шаг сегодня? Какой?",
        imposed_keywords=["потом", "не сейчас", "на следующей неделе"],
        true_keywords=["да", "вот этот", "прямо сегодня"],
    ),
    Question(
        idx=20, module=5,
        text="Что готов вложить прямо сейчас? (время, деньги, усилия)",
        imposed_keywords=["ничего", "пока ничего", "посмотрим"],
        true_keywords=["время", "деньги", "усилия", "конкретное"],
    ),
]


# === Списки индексов для глубин (PRD 5.3, 5.6) ===
# Express: по 1 ключевому из модулей 1, 3, 4, 5, 1 (idx 1, 9, 14, 19, 2)
EXPRESS_INDICES: list[int] = [1, 9, 14, 19, 2]
# Standard: 12 — по 2-3 из каждого модуля (без Q9, 11, 12 для тонов без M3)
# По умолчанию: [1, 2, 5, 6, 9, 13, 14, 15, 17, 18, 19, 20] (12 вопросов)
STANDARD_INDICES: list[int] = [1, 2, 5, 6, 9, 13, 14, 15, 17, 18, 19, 20]
# Deep: все 20
DEEP_INDICES: list[int] = list(range(1, 21))


# === Шкала вердиктов (PRD 5.9) ===
# Кортежи: (low, high, verdict_label, signature_for_client)
VERDICT_LABELS: list[tuple[float, float, str, str]] = [
    (0.00, 0.20, "imposed",         "Это желание в основном про страх и внешнее давление"),
    (0.20, 0.35, "mostly_imposed",  "Больше навязанного, но есть зерно истинного"),
    (0.35, 0.50, "mixed_low",       "Есть и настоящее, и наносное — больше шума"),
    (0.50, 0.65, "mixed_high",      "Больше истинного, но есть социальный шум"),
    (0.65, 0.80, "mostly_true",     "В основном идёт изнутри"),
    (0.80, 1.01, "true",            "Идёт изнутри, даёт энергию и ясность"),
]


def score_to_verdict(score: float) -> tuple[str, str]:
    """Возвращает (verdict_label, signature_for_client) по score 0..1."""
    s = max(0.0, min(1.0, score))
    for low, high, label, signature in VERDICT_LABELS:
        if low <= s < high:
            return label, signature
    return "true", VERDICT_LABELS[-1][3]


def _score_answer(question: Question, answer: str) -> float:
    """Phase 1 scoring: keyword overlap, нейтральный fallback 0.5."""
    if not answer or not answer.strip():
        return 0.5
    a = answer.lower()
    imposed_hits = sum(1 for kw in question.imposed_keywords if kw in a)
    true_hits = sum(1 for kw in question.true_keywords if kw in a)
    if imposed_hits == 0 and true_hits == 0:
        return 0.5
    if imposed_hits == 0:
        return min(1.0, 0.7 + 0.1 * true_hits)
    if true_hits == 0:
        return max(0.0, 0.3 - 0.1 * imposed_hits)
    # Смешано — берём соотношение
    total = imposed_hits + true_hits
    return 0.5 + 0.5 * (true_hits - imposed_hits) / total


# === Сервис ===

class DetectorService:
    """Управление ходом детектора внутри сессии."""

    def start(
        self,
        desire_id: int,
        depth: DetectorDepth,
        enabled_modules: list[int],
    ) -> DetectorSession:
        indices = self._indices_for_depth(depth, enabled_modules)
        return DetectorSession(
            desire_id=desire_id,
            depth=depth,
            enabled_modules=enabled_modules,
            question_indices=indices,
        )

    def _indices_for_depth(
        self, depth: DetectorDepth, enabled_modules: list[int]
    ) -> list[int]:
        if depth == DetectorDepth.EXPRESS:
            base = EXPRESS_INDICES
        elif depth == DetectorDepth.STANDARD:
            base = STANDARD_INDICES
        else:
            base = DEEP_INDICES
        # Фильтруем: оставляем вопросы из активных модулей
        # Если модуль 3 отключён, выкидываем Q9-12
        valid_modules = set(enabled_modules)
        return [i for i in base if QUESTIONS[i - 1].module in valid_modules]

    def next_question(
        self, session: DetectorSession, replacement_q9: str | None = None
    ) -> Question | None:
        """Возвращает следующий вопрос или None, если детектор закончен."""
        if session.is_finished():
            return None
        q = QUESTIONS[session.question_indices[session.current_index] - 1]
        if q.idx == 9 and replacement_q9:
            # Заменяем текст Q9 для тонов с отключённым Модулем 3
            return Question(
                idx=q.idx,
                module=q.module,
                text=replacement_q9,
                imposed_keywords=q.imposed_keywords,
                true_keywords=q.true_keywords,
                is_module3=q.is_module3,
            )
        return q

    def record_answer(self, session: DetectorSession, answer: str) -> None:
        """Записать ответ и сдвинуть курсор."""
        session.answers.append(answer)
        session.current_index += 1

    def finalize(self, session: DetectorSession) -> DetectorOutcome:
        """Подсчитать score по всем ответам, вернуть DetectorOutcome."""
        if not session.answers:
            return DetectorOutcome(
                score=0.5,
                verdict_label="mixed_high",
                module_scores={},
                reasoning="Нет ответов для анализа.",
                depth=session.depth,
                questions_asked=0,
            )

        # Скоринг по модулям
        module_scores: dict[int, list[float]] = {}
        for ans, idx in zip(session.answers, session.question_indices, strict=False):
            q = QUESTIONS[idx - 1]
            s = _score_answer(q, ans)
            module_scores.setdefault(q.module, []).append(s)

        avg_by_module = {m: sum(ss) / len(ss) for m, ss in module_scores.items()}
        overall = sum(avg_by_module.values()) / len(avg_by_module) if avg_by_module else 0.5

        label, signature = score_to_verdict(overall)

        return DetectorOutcome(
            score=round(overall, 3),
            verdict_label=label,
            module_scores={f"m{m}": round(s, 3) for m, s in avg_by_module.items()},
            reasoning=signature,
            depth=session.depth,
            questions_asked=len(session.answers),
        )


__all__ = [
    "DetectorDepth",
    "Question",
    "DetectorSession",
    "DetectorOutcome",
    "QUESTIONS",
    "EXPRESS_INDICES",
    "STANDARD_INDICES",
    "DEEP_INDICES",
    "VERDICT_LABELS",
    "score_to_verdict",
    "DetectorService",
]
