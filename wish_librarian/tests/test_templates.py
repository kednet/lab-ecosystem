"""
Тесты для системы шаблонов (v2):
  - agent.templates.loader
  - agent.ai.prompts.build_style_directive / build_system_prompt
  - agent.storage.ai_cache: новый формат ключа + legacy fallback
  - agent.storage.templates.render_workbook_postprocess
  - agent.export._md_text_to_pdf_file с секцией «Поля для ответов»

Запуск: python tests/test_templates.py
"""
from __future__ import annotations

import os
import sys
import re
import tempfile
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# На Windows в консоль лезут юникодные эмодзи — принудительно UTF-8.
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

for _k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
           "http_proxy", "https_proxy", "all_proxy"):
    os.environ.pop(_k, None)


# ── Утилита ──────────────────────────────────────────────────────────
def _ok(msg: str) -> None:
    print(f"  ✅ {msg}")


# ── 1. parse_template_file ────────────────────────────────────────────
def test_parse_template_file() -> None:
    from agent.templates.loader import parse_template_file
    p = ROOT / "agent" / "templates" / "builtin" / "workbook" / "workbook_v2.md"
    tpl = parse_template_file(p)
    assert tpl.kind == "workbook", f"kind={tpl.kind}"
    assert tpl.version == "v2", f"version={tpl.version}"
    ids = {s.id for s in tpl.sections}
    expected = {
        "self_analysis", "answer_fields", "actions", "scenarios",
        "if_then", "weekly_plan", "habit_tracker", "reflection", "micro_habits",
    }
    missing = expected - ids
    assert not missing, f"missing sections: {missing}"
    assert "{{title}}" in tpl.body
    assert "HABIT_NAMES" in tpl.body
    _ok("parse_template_file → workbook_v2 имеет все 9 секций и плейсхолдеры")


# ── 2. TemplateRegistry: builtin + user override ─────────────────────
def test_registry_user_overrides_builtin() -> None:
    from agent.templates import TemplateRegistry
    with tempfile.TemporaryDirectory() as tmp:
        reg = TemplateRegistry(project_root=Path(tmp))
        # builtin
        t = reg.get("workbook", "workbook_v2")
        assert t.raw_path and t.raw_path.name == "workbook_v2.md"
        # user override
        user = Path(tmp) / "templates" / "workbook" / "workbook_v2.md"
        user.parent.mkdir(parents=True, exist_ok=True)
        user.write_text(
            "---\nname: workbook_v2\nkind: workbook\nversion: v999\n"
            "description: USER OVERRIDE\n---\nUSER BODY\n",
            encoding="utf-8",
        )
        # Сбрасываем in-memory кеш реестра, чтобы он перечитал диск
        reg.clear_cache()
        t2 = reg.get("workbook", "workbook_v2")
        assert "USER BODY" in t2.body
        assert t2.version == "v999"
        assert "USER OVERRIDE" in t2.description
    _ok("TemplateRegistry: user template перекрывает builtin")


# ── 3. render_body + SafeDict ────────────────────────────────────────
def test_render_body_safe_missing_var() -> None:
    from agent.templates import parse_template_file, render_body
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    ) as f:
        f.write("---\nname: t\nkind: workbook\nversion: v1\n---\n"
                "# {{title}} by {{author}} (year={{year}})\n")
        tmp_path = Path(f.name)
    try:
        tpl = parse_template_file(tmp_path)
        out = render_body(tpl, {"title": "X"})  # author + year отсутствуют
        assert "X" in out
        assert "{{author}}" in out  # не упал, оставил как есть
        assert "{{year}}" in out
    finally:
        tmp_path.unlink()
    _ok("render_body с SafeDict: отсутствующие плейсхолдеры остаются {{var}}")


# ── 4. build_style_directive ─────────────────────────────────────────
def test_style_directive() -> None:
    from agent.ai.prompts import build_style_directive
    s = build_style_directive("coaching", "long", "expert", "ru")
    assert "COACHING" in s
    assert "LONG" in s
    assert "EXPERT" in s
    # Регистр не важен
    s2 = build_style_directive("FORMAL", "SHORT", "TEEN", "EN")
    assert "FORMAL" in s2 and "SHORT" in s2 and "TEEN" in s2
    _ok("build_style_directive: тон/длина/аудитория/язык в верхнем регистре")


# ── 5. build_system_prompt использует шаблон, не fallback ───────────
def test_system_prompt_prefers_template() -> None:
    from agent.templates import TemplateRegistry
    from agent.ai.prompts import build_system_prompt
    reg = TemplateRegistry(project_root=ROOT)
    tpl = reg.get("workbook", "workbook_v2")
    sp = build_system_prompt(tpl, tone="formal", length="long", audience="expert", language="en")
    # В шаблоне есть «коуч-практик» — он должен присутствовать
    assert "коуч-практик" in sp
    # style directive добавлен
    assert "FORMAL" in sp and "EXPERT" in sp
    _ok("build_system_prompt: берёт system_prompt из шаблона + style directive")


# ── 6. ai_cache: новый формат ключа ──────────────────────────────────
def test_cache_key_new_format() -> None:
    from agent.storage.ai_cache import _cache_path
    from agent.models import BookInfo
    book = BookInfo(title="T", author="A", year=2020, source_url="x")
    p = _cache_path(
        book, "workbook", "yandex/yandexgpt-lite",
        tpl="workbook_v2", style_hash="a3f9c1",
    )
    assert p.name == "workbook__yandex_yandexgpt-lite__v2__workbook_v2__a3f9c1.md", p.name
    _ok("ai_cache._cache_path: новый формат <kind>__<model>__<v2>__<tpl>__<hash>.md")


# ── 7. ai_cache: legacy не возвращается ─────────────────────────────
def test_cache_legacy_not_returned() -> None:
    from agent.storage.ai_cache import (
        _cache_path, _legacy_cache_path, get_cached, clear_cache_for,
    )
    from agent.models import BookInfo
    book = BookInfo(title="T", author="A", year=2020, source_url="x")

    # Создаём legacy-файл (старый формат v1)
    legacy = _legacy_cache_path(book, "summary", "x/y")
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text("LEGACY CONTENT", encoding="utf-8")
    try:
        # С новым ключом — НЕ должно найтись
        assert get_cached(
            book, "summary", "x/y", tpl="summary_v2", style_hash="zzz"
        ) is None
        # С allow_legacy=False — то же самое
        assert get_cached(
            book, "summary", "x/y", tpl="summary_v2", style_hash="zzz",
            allow_legacy=False,
        ) is None
    finally:
        legacy.unlink(missing_ok=True)
        clear_cache_for(book)
    _ok("ai_cache.get_cached: legacy-файлы не возвращаются (нужна регенерация)")


# ── 8. ai_cache roundtrip ───────────────────────────────────────────
def test_cache_roundtrip() -> None:
    from agent.storage.ai_cache import get_cached, save_cached, clear_cache_for
    from agent.models import BookInfo
    book = BookInfo(title="T", author="A", year=2020, source_url="x")
    clear_cache_for(book)
    assert get_cached(book, "workbook", "m", tpl="w", style_hash="h") is None
    save_cached(book, "workbook", "m", "CONTENT", tpl="w", style_hash="h")
    assert get_cached(book, "workbook", "m", tpl="w", style_hash="h") == "CONTENT"
    # Другой style_hash → не найдётся
    assert get_cached(book, "workbook", "m", tpl="w", style_hash="other") is None
    clear_cache_for(book)
    _ok("ai_cache: roundtrip + изоляция по style_hash")


# ── 9. render_workbook_postprocess ──────────────────────────────────
def test_workbook_postprocess() -> None:
    from agent.models import BookInfo
    from agent.templates import TemplateRegistry
    from agent.storage.templates import render_workbook_postprocess
    reg = TemplateRegistry(project_root=ROOT)
    tpl = reg.get("workbook", "workbook_v2")
    book = BookInfo(title="T", author="A", year=2020, source_url="x")
    llm = (
        "## 🔍 Упражнение 1. Самоанализ\n"
        "1. Вопрос один\n2. Вопрос два\n3. Вопрос три\n"
        "4. Вопрос четыре\n5. Вопрос пять\n6. Вопрос шесть\n7. Вопрос семь\n\n"
        "## ✍️ Упражнение 2. Практика\n- [ ] a\n- [ ] b\n- [ ] c\n- [ ] d\n- [ ] e\n\n"
        "## 🔥 Трекер привычек (30 дней)\n\n"
        "Привычки для отслеживания:\n"
        "[HABIT_NAMES]\n1. Медитация\n2. Чтение\n3. Прогулка\n[/HABIT_NAMES]\n"
        "> ℹ️ _Таблица с 30 строками × 3 столбцами будет добавлена автоматически._\n"
    )
    out = render_workbook_postprocess(llm, tpl, book)
    assert "[HABIT_NAMES]" not in out
    assert "## 📝 Поля для ответов" in out
    assert "1. _Вопрос один_" in out
    assert "_______" in out
    assert "| День | Медитация | Чтение | Прогулка |" in out
    assert "| 30   |" in out
    _ok("render_workbook_postprocess: инжектит поля ответов + таблицу 30×3")


# ── 10. PDF рендерит секцию «Поля для ответов» ───────────────────────
def test_pdf_answer_fields() -> None:
    try:
        from reportlab.platypus import SimpleDocTemplate  # noqa: F401
    except ImportError:
        print("  ⏭  test_pdf_answer_fields: reportlab не установлен, skip")
        return
    from agent.export import _md_text_to_pdf_file
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "out.pdf"
        md = (
            "# Test\n\n"
            "## 📝 Поля для ответов\n"
            "1. _Вопрос 1_\n   _______\n   _______\n   _______\n   _______\n"
            "2. _Вопрос 2_\n   _______\n   _______\n   _______\n   _______\n"
        )
        _md_text_to_pdf_file(md, out, title="T")
        assert out.exists()
        assert out.read_bytes()[:5] == b"%PDF-"
        assert out.stat().st_size > 1000
    _ok("PDF: секция «Поля для ответов» рендерится в валидный PDF")


# ── 11. style_hash стабилен ─────────────────────────────────────────
def test_style_hash() -> None:
    from agent.templates import style_hash
    h1 = style_hash("coaching", "medium", "general", "ru")
    h2 = style_hash("coaching", "medium", "general", "ru")
    h3 = style_hash("formal", "medium", "general", "ru")
    assert h1 == h2
    assert h1 != h3
    assert len(h1) == 6
    _ok("style_hash: стабильный, 6 hex-символов, меняется при смене полей")


# ── 12. CLI --list-templates: smoke ─────────────────────────────────
def test_cli_list_templates() -> None:
    from click.testing import CliRunner
    from agent.cli import main as cli_main
    runner = CliRunner()
    result = runner.invoke(cli_main, ["--list-templates"])
    assert result.exit_code == 0, result.output
    assert "summary_v2" in result.output
    assert "workbook_v2" in result.output
    assert "tips_v1" in result.output
    _ok("CLI --list-templates показывает summary_v2/workbook_v2/tips_v1")


# ── Запуск ───────────────────────────────────────────────────────────
def main() -> int:
    tests = [
        test_parse_template_file,
        test_registry_user_overrides_builtin,
        test_render_body_safe_missing_var,
        test_style_directive,
        test_system_prompt_prefers_template,
        test_cache_key_new_format,
        test_cache_legacy_not_returned,
        test_cache_roundtrip,
        test_workbook_postprocess,
        test_pdf_answer_fields,
        test_style_hash,
        test_cli_list_templates,
    ]
    print("=" * 60)
    print(f"🧪 Запуск {len(tests)} тестов шаблонов")
    print("=" * 60)
    failed = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            failed += 1
            print(f"  ❌ {t.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"  💥 {t.__name__}: {type(e).__name__}: {e}")
    print("=" * 60)
    if failed:
        print(f"❌ {failed} тестов провалились")
        return 1
    print(f"✅ Все {len(tests)} тестов зелёные")
    return 0


if __name__ == "__main__":
    sys.exit(main())
