"""
cmd_quiz.py — мини-тест.

Без --check: печатает вопросы для прохождения.
С --check=<yaml-файл с ответами>: проверяет и выводит результат.
"""
from pathlib import Path
import yaml

from _english_common import fix_utf8, ensure_dirs, print_header, print_section, TMP_DIR
import state
from quiz import load_quiz, render_quiz_markdown, render_result_markdown, run_quiz, list_quizzes


def _parse_answers_file(path: Path) -> dict:
    """Парсит YAML с ответами {question_id: user_answer}."""
    if not path.exists():
        raise FileNotFoundError(f"Файл ответов не найден: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Ожидается dict в YAML, получен {type(data)}")
    return data


def _save_answers_template(tense_name: str, quiz: dict) -> Path:
    """Сохраняет шаблон для ответов в tmp/quiz_answers/<tense>.yaml."""
    out_dir = TMP_DIR / "quiz_answers"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{tense_name}.yaml"
    template = {"# Заполни поле 'answer' и запусти с --check=...": None}
    for q in quiz.get("questions", []):
        template[str(q["id"])] = {"prompt": q["prompt"], "type": q["type"], "answer": ""}
    with open(out_path, "w", encoding="utf-8") as f:
        yaml.dump(template, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
    return out_path


def run(args) -> int:
    fix_utf8()
    ensure_dirs()

    tense = getattr(args, "tense", None)
    check_file = getattr(args, "check", None)
    force = getattr(args, "force", False)

    if not tense:
        print("❌ Укажи название времени: present-simple, past-simple, ... и т.д.")
        print(f"Доступные: {', '.join(list_quizzes())}")
        return 1

    try:
        quiz = load_quiz(tense)
    except FileNotFoundError as e:
        print(f"❌ {e}")
        return 1

    meta = quiz.get("meta", {})

    # === Режим --check ===
    if check_file:
        answers_path = Path(check_file)
        try:
            answers_raw = _parse_answers_file(answers_path)
        except (FileNotFoundError, ValueError) as e:
            print(f"❌ {e}")
            return 1

        # Нормализуем: {qid: answer_string}
        answers = {}
        for k, v in answers_raw.items():
            if isinstance(v, dict):
                answers[k] = v.get("answer", "")
            else:
                answers[k] = v

        result = run_quiz(tense, answers)
        # Сохраняем score в state
        state.set_quiz_score(tense, result["score"])
        state.update_streak_on_active()
        # Помечаем связанный урок как done, если есть
        # (quiz обычно связан с днём 6 урока, но для простоты не трогаем)

        print(render_result_markdown(quiz, result))
        print()
        print(f"📁 Score сохранён в state/progress.json: quiz_scores['{tense}'] = {result['score']}")
        if result["next_tense"]:
            print(f"➡️  Следующее время: `python scripts/english.py quiz {result['next_tense']}`")
        return 0

    # === Обычный режим (вывод вопросов) ===
    # Идемпотентность: если score уже есть — предлагаем --force
    if not force:
        existing_score = state.get_quiz_score(tense)
        if existing_score is not None:
            print(f"⏭  Ты уже проходила этот тест: {existing_score}/{len(quiz.get('questions', []))}.")
            print("Используй --force чтобы пройти заново.")
            return 0

    print_header(f"Mini-quiz: {meta.get('display_name', tense)}")
    print(f"_{meta.get('description', '')}_")
    print()
    print(f"⏱ ~{meta.get('estimated_min', 5)} мин | "
          f"{len(quiz.get('questions', []))} вопросов")
    print()
    print("## Как пройти")
    print()
    print("1. Прочитай вопросы ниже и подумай над ответами")
    print("2. Создай файл с ответами (шаблон сохранён ниже):")
    print()

    template_path = _save_answers_template(tense, quiz)
    print(f"   📄 Шаблон: `{template_path.relative_to(Path.cwd())}`")
    print()
    print("3. Заполни поле `answer` в шаблоне и запусти:")
    print(f"   `python scripts/english.py quiz {tense} --check={template_path}`")
    print()
    print("---")
    print()
    print(render_quiz_markdown(quiz, with_answers=False))

    return 0
