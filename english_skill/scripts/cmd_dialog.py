"""
cmd_dialog.py — ролевой диалог для speaking-практики.

Без --answer: показывает скрипт с [YOUR TURN] репликами для проговаривания вслух.
С --answer=<yaml-файл с юзер-репликами>: показывает diff с эталоном + feedback.
"""
from pathlib import Path
import yaml

from _english_common import fix_utf8, ensure_dirs, print_header, DIALOGS_DIR


def _load_dialog(name: str) -> dict:
    """Загружает диалог по slug."""
    path = DIALOGS_DIR / f"{name}.yaml"
    if not path.exists():
        available = sorted([p.stem for p in DIALOGS_DIR.glob("*.yaml")]) if DIALOGS_DIR.exists() else []
        raise FileNotFoundError(
            f"Диалог '{name}' не найден. Доступные: {', '.join(available)}"
        )
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _render_dialog(dialog: dict, with_answers: bool = False, user_answers: dict = None) -> str:
    """Рендерит диалог в markdown.

    with_answers=True — показывает model_answer рядом с user-репликой.
    user_answers: {step_id: user_text} — словарь с ответами пользователя.
    """
    user_answers = user_answers or {}
    meta = dialog.get("meta", {})
    context = dialog.get("context", {})
    script = dialog.get("script", [])

    # Шаг может не иметь id — присваиваем по позиции
    step_counter = 0
    def _next_step_id():
        nonlocal step_counter
        step_counter += 1
        return step_counter

    lines = []
    lines.append(f"# 🎭 Диалог: {meta.get('display_name') or meta.get('title') or meta.get('name', dialog.get('id', '?'))}")
    lines.append("")
    lines.append(f"**Категория:** {meta.get('category', '—')}")
    lines.append(f"**Сложность:** {meta.get('level', 'B1')}")
    lines.append(f"**Длительность:** ~{meta.get('duration_min', 5)} мин")
    if meta.get("why"):
        lines.append(f"_{meta['why']}_")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Контекст
    lines.append("## 🎬 Setting")
    lines.append("")
    for k in ("role", "team", "scenario", "place"):
        if context.get(k):
            label = {
                "role": "Твоя роль",
                "team": "Команда",
                "scenario": "Сценарий",
                "place": "Место",
            }.get(k, k)
            lines.append(f"- **{label}:** {context[k]}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Скрипт
    lines.append("## 📜 Script")
    lines.append("")
    lines.append("_Читай вслух. Где видишь **[YOUR TURN]** — остановись и произнеси свою реплику._")
    lines.append("")

    for step in script:
        sid = step.get("id") or _next_step_id()
        speaker = step.get("speaker", "")
        line = step.get("line", "")
        hint = step.get("hint", "")
        model = step.get("model_answer", "")
        alts = step.get("alternatives", [])

        if speaker == "facilitator":
            # Реплика собеседника
            lines.append(f"**🗣️ Собеседник:** {line}")
            lines.append("")
        elif speaker == "user":
            # Реплика пользователя (надо произнести)
            lines.append("---")
            lines.append("")
            lines.append(f"### ✍️ [YOUR TURN] — Step {sid}")
            lines.append("")
            if hint:
                lines.append(f"💡 **Hint:** {hint}")
                lines.append("")
            if with_answers:
                user_text = user_answers.get(str(sid), user_answers.get(sid, ""))
                lines.append(f"**Твой ответ:** _{user_text}_")
                lines.append("")
                lines.append(f"**Эталон:** _{model}_")
                if alts:
                    lines.append("")
                    lines.append("**Альтернативы:**")
                    for a in alts:
                        lines.append(f"- _{a}_")
            else:
                lines.append(f"**Что сказать:** _{model}_")
                if alts:
                    lines.append("")
                    lines.append("**Или так:**")
                    for a in alts:
                        lines.append(f"- _{a}_")
            lines.append("")
            lines.append("---")
            lines.append("")
        else:
            # Заметка / комментарий
            if line:
                lines.append(f"> 📝 {line}")
                lines.append("")

    # Recap
    after = dialog.get("after_dialog", {})
    if after.get("recap_vocab"):
        lines.append("## 📚 Vocab из диалога")
        lines.append("")
        for v in after["recap_vocab"]:
            lines.append(f"- **{v}**")
        lines.append("")

    if after.get("grammar_notes"):
        lines.append("## 🧠 Grammar notes")
        lines.append("")
        gn = after["grammar_notes"]
        if isinstance(gn, list):
            for note in gn:
                lines.append(f"- {note}")
        else:
            lines.append(gn)
        lines.append("")

    if after.get("next_dialog"):
        lines.append("## ➡️ Следующий диалог")
        lines.append("")
        lines.append(f"`python scripts/english.py dialog {after['next_dialog']}`")

    return "\n".join(lines)


def _save_dialog_template(dialog: dict) -> Path:
    """Сохраняет шаблон для user-реплик в tmp/dialog_answers/<name>.yaml."""
    from _english_common import TMP_DIR
    out_dir = TMP_DIR / "dialog_answers"
    out_dir.mkdir(parents=True, exist_ok=True)
    dialog_id = dialog.get("meta", {}).get("name") or dialog.get("id") or "dialog"
    out_path = out_dir / f"{dialog_id}.yaml"
    template = {"# Заполни поле 'answer' для каждой [YOUR TURN] реплики": None}
    step_counter = 0
    for step in dialog.get("script", []):
        if step.get("speaker") == "user":
            step_counter += 1
            template[str(step_counter)] = {
                "hint": step.get("hint", ""),
                "answer": "",
            }
    with open(out_path, "w", encoding="utf-8") as f:
        yaml.dump(template, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
    return out_path


def run(args) -> int:
    fix_utf8()
    ensure_dirs()

    name = getattr(args, "name", None)
    answer_file = getattr(args, "answer", None)

    if not name:
        print("❌ Укажи название диалога: standup, code-review, demo, ...")
        return 1

    try:
        dialog = _load_dialog(name)
    except FileNotFoundError as e:
        print(f"❌ {e}")
        return 1

    # === Режим --answer (показать diff с эталоном) ===
    if answer_file:
        path = Path(answer_file)
        if not path.exists():
            print(f"❌ Файл ответов не найден: {path}")
            return 1
        with open(path, "r", encoding="utf-8") as f:
            answers_raw = yaml.safe_load(f) or {}
        # Нормализуем: {step_id: answer_string}
        answers = {}
        for k, v in answers_raw.items():
            if isinstance(v, dict):
                answers[k] = v.get("answer", "")
            else:
                answers[k] = v
        print(_render_dialog(dialog, with_answers=True, user_answers=answers))
        print()
        print("---")
        print()
        n_filled = sum(1 for v in answers.values() if v and str(v).strip())
        n_total = sum(1 for s in dialog.get("script", []) if s.get("speaker") == "user")
        print(f"📊 Заполнено: {n_filled}/{n_total} [YOUR TURN] реплик")
        if n_filled < n_total:
            print("⚠️  Не все реплики заполнены — прочитай эталон вслух для пустых.")
        return 0

    # === Обычный режим ===
    print_header(f"🎭 {dialog.get('meta', {}).get('title', name)}")
    print()
    print(_render_dialog(dialog, with_answers=False))
    print()
    print("## 📝 Как записать свои ответы")
    print()
    print("1. Произнеси вслух каждую [YOUR TURN] реплику 2-3 раза")
    print("2. Создай файл с вариантами (шаблон ниже):")
    print()

    template_path = _save_dialog_template(dialog)
    print(f"   📄 Шаблон: `{template_path.relative_to(Path.cwd())}`")
    print()
    print("3. Заполни `answer` для каждой реплики и запусти:")
    print(f"   `python scripts/english.py dialog {name} --answer={template_path}`")
    print()
    print("💡 **Совет:** произноси вслух, даже если не записываешь. Цель — speaking muscle memory.")
    return 0