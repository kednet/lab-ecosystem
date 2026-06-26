"""
quiz.py — детерминированный движок мини-тестов (без LLM).

API:
- load_quiz(tense_name) → dict (из data/quizzes/<tense>.yaml)
- check_answer(question, user_answer) → bool (multiple_choice точное совпадение, open — case-insensitive substring)
- run_quiz(tense_name, user_answers) → {score, total, per_question, recap}
- render_quiz_markdown(quiz) → markdown
"""
from pathlib import Path
from typing import Any

from _english_common import QUIZZES_DIR, load_yaml


# === Quiz loading ===

def list_quizzes() -> list[str]:
    """Возвращает список slug всех доступных квизов."""
    if not QUIZZES_DIR.exists():
        return []
    return sorted([p.stem for p in QUIZZES_DIR.glob("*.yaml")])


def load_quiz(tense_name: str) -> dict:
    """Загружает квиз по имени (slug)."""
    path = QUIZZES_DIR / f"{tense_name}.yaml"
    if not path.exists():
        raise FileNotFoundError(
            f"Квиз '{tense_name}' не найден. Доступные: {', '.join(list_quizzes())}"
        )
    return load_yaml(path)


# === Answer checking ===

def _normalize(s: str) -> str:
    """Нормализует строку: lowercase, strip, схлопывает пробелы."""
    if s is None:
        return ""
    return " ".join(str(s).lower().strip().split())


def check_answer(question: dict, user_answer: Any) -> bool:
    """
    Проверяет ответ пользователя.

    - multiple_choice: точное сравнение с correct (case-insensitive)
    - open: case-insensitive substring match с correct_answer,
            а также проверка в acceptable_answers
    """
    qtype = question.get("type")
    user_norm = _normalize(user_answer)

    if qtype == "multiple_choice":
        correct_norm = _normalize(question.get("correct", ""))
        return user_norm == correct_norm

    elif qtype == "open":
        correct_norm = _normalize(question.get("correct_answer", ""))
        if not user_norm:
            return False
        # Точное совпадение
        if user_norm == correct_norm:
            return True
        # Substring match (допускаем вставку/пропуск слов)
        if correct_norm and (correct_norm in user_norm or user_norm in correct_norm):
            return True
        # Проверка в acceptable_answers
        for alt in question.get("acceptable_answers", []):
            alt_norm = _normalize(alt)
            if user_norm == alt_norm or alt_norm in user_norm or user_norm in alt_norm:
                return True
        return False

    # Неизвестный тип → считаем неверным
    return False


def get_correct_display(question: dict) -> str:
    """Возвращает правильный ответ для отображения в feedback."""
    if question.get("type") == "multiple_choice":
        return question.get("correct", "")
    return question.get("correct_answer", "")


# === Quiz runner ===

def run_quiz(tense_name: str, user_answers: dict) -> dict:
    """
    Прогоняет квиз и возвращает результат.

    Args:
        tense_name: slug квиза (например, 'present-simple')
        user_answers: dict {question_id (int or str): user_answer}

    Returns:
        {
            "score": int (correct count),
            "total": int,
            "per_question": [
                {
                    "id": int,
                    "prompt": str,
                    "type": str,
                    "user_answer": str,
                    "correct": bool,
                    "correct_display": str,
                    "explanation": str,
                    "grammar_point": str,
                },
                ...
            ],
            "recap": str,
        }
    """
    quiz = load_quiz(tense_name)
    questions = quiz.get("questions", [])
    per_question = []

    for q in questions:
        qid = q.get("id")
        # Поддерживаем и int, и str ключи в user_answers
        user_answer = user_answers.get(qid)
        if user_answer is None:
            user_answer = user_answers.get(str(qid), "")

        is_correct = check_answer(q, user_answer)
        per_question.append({
            "id": qid,
            "prompt": q.get("prompt", ""),
            "type": q.get("type", ""),
            "user_answer": str(user_answer) if user_answer else "",
            "correct": is_correct,
            "correct_display": get_correct_display(q),
            "explanation": q.get("explanation", ""),
            "grammar_point": q.get("grammar_point", ""),
        })

    score = sum(1 for r in per_question if r["correct"])
    return {
        "score": score,
        "total": len(questions),
        "per_question": per_question,
        "recap": quiz.get("after_quiz", {}).get("recap", ""),
        "next_tense": quiz.get("after_quiz", {}).get("next_tense"),
        "recommended_review": quiz.get("after_quiz", {}).get("recommended_review"),
    }


# === Markdown rendering ===

def render_quiz_markdown(quiz: dict, with_answers: bool = False) -> str:
    """
    Рендерит квиз в markdown.

    with_answers=True: показывает правильные ответы и explanation (для самопроверки после прохождения).
    """
    lines = []
    meta = quiz.get("meta", {})
    lines.append(f"# Mini-quiz: {meta.get('display_name', quiz.get('meta', {}).get('name', ''))}")
    lines.append("")
    lines.append(f"**Уровень:** {meta.get('level', 'B1')} | "
                 f"**Время:** ~{meta.get('estimated_min', 5)} мин | "
                 f"**Вопросов:** {len(quiz.get('questions', []))}")
    lines.append("")
    lines.append(f"_{meta.get('description', '')}_")
    lines.append("")
    lines.append("---")
    lines.append("")

    for q in quiz.get("questions", []):
        lines.append(f"## Вопрос {q['id']}")
        lines.append("")
        lines.append(f"**{q['prompt']}**")
        lines.append("")

        if q.get("type") == "multiple_choice":
            for opt in q.get("options", []):
                marker = ""
                if with_answers:
                    if opt == q.get("correct"):
                        marker = " ✅"
                lines.append(f"- [ ] {opt}{marker}")
        elif q.get("type") == "open":
            lines.append("_Напишите свой ответ:_")
            lines.append("")
            lines.append("```")
            lines.append("[your answer here]")
            lines.append("```")
            if with_answers:
                lines.append("")
                lines.append(f"**Правильный ответ:** `{q.get('correct_answer', '')}`")
                if q.get("acceptable_answers"):
                    lines.append(f"**Допустимо:** {', '.join(q['acceptable_answers'])}")

        if with_answers and q.get("explanation"):
            lines.append("")
            lines.append(f"💡 {q['explanation']}")

        lines.append("")
        lines.append("---")
        lines.append("")

    # После-квиз блок (recap)
    if quiz.get("after_quiz", {}).get("recap"):
        lines.append("## 📚 Recap")
        lines.append("")
        lines.append(quiz["after_quiz"]["recap"])

    return "\n".join(lines)


def render_result_markdown(quiz: dict, result: dict) -> str:
    """Рендерит результат прохождения квиза (с score + per-question feedback)."""
    meta = quiz.get("meta", {})
    score = result["score"]
    total = result["total"]
    pct = round(100 * score / total) if total > 0 else 0

    emoji = "🎉" if pct >= 90 else ("👍" if pct >= 70 else ("💪" if pct >= 50 else "📚"))

    lines = []
    lines.append(f"# Результат: {meta.get('display_name', meta.get('name', ''))}")
    lines.append("")
    lines.append(f"## {emoji} Score: **{score}/{total}** ({pct}%)")
    lines.append("")

    if pct == 100:
        lines.append("_Идеально! Время идти дальше._")
    elif pct >= 80:
        lines.append("_Отлично! Ты уверенно владеешь этим временем._")
    elif pct >= 60:
        lines.append("_Хорошо, но есть куда расти. Перечитай explanation._")
    else:
        lines.append("_Нужно повторить. Открой урок и пройди тест снова._")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Per-question feedback")
    lines.append("")

    for r in result["per_question"]:
        marker = "✅" if r["correct"] else "❌"
        lines.append(f"### {marker} Вопрос {r['id']}")
        lines.append("")
        lines.append(f"**{r['prompt']}**")
        lines.append("")
        lines.append(f"- Твой ответ: `{r['user_answer']}`")
        if not r["correct"]:
            lines.append(f"- Правильный ответ: `{r['correct_display']}`")
        if r.get("explanation"):
            lines.append(f"- 💡 {r['explanation']}")
        lines.append("")

    if result.get("recap"):
        lines.append("---")
        lines.append("")
        lines.append("## 📚 Recap")
        lines.append("")
        lines.append(result["recap"])

    return "\n".join(lines)


# === Smoke test ===

if __name__ == "__main__":
    print("quiz.py — smoke test")
    print(f"Available quizzes: {list_quizzes()}")
    q = load_quiz("present-simple")
    print(f"Loaded 'present-simple': {len(q.get('questions', []))} questions")

    # Test answer checking
    q1 = q["questions"][0]
    print(f"\nQ1: {q1['prompt']}")
    print(f"Correct: {q1['correct']}")
    print(f"User answer 'works' → {check_answer(q1, 'works')}")
    print(f"User answer 'WORKS' → {check_answer(q1, 'WORKS')}")
    print(f"User answer 'work' → {check_answer(q1, 'work')}")
