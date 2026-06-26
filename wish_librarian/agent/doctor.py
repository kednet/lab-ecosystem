"""
`--doctor` — самодиагностика установки.

Проверяет:
  - Версия Python и зависимости.
  - Кеш и его размер.
  - Все 7+ карт загружаются.
  - AI-провайдер отвечает на тестовый запрос.
  - Количество обработанных книг.
  - Оценочное использование диска.
  - Рекомендации (если что-то не так).
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import List, Tuple

from rich.console import Console
from rich.table import Table


def _check_python() -> Tuple[str, str]:
    v = sys.version_info
    return (f"{v.major}.{v.minor}.{v.micro}", "✅")


def _check_deps() -> List[Tuple[str, str, str]]:
    """(пакет, статус, версия_или_сообщение)."""
    out = []
    for pkg in ["pydantic", "pydantic_settings", "bs4", "lxml", "requests",
                "httpx", "loguru", "tenacity", "anthropic", "click", "rich", "yaml"]:
        try:
            mod = __import__(pkg if pkg != "yaml" else "yaml")
            v = getattr(mod, "__version__", "?")
            out.append((pkg, "✅", v))
        except ImportError as e:
            out.append((pkg, "❌", str(e).split("'")[-2] if "'" in str(e) else "не найден"))
    return out


def _check_sites() -> Tuple[int, str]:
    from agent.parsers.prompts import load_all_sites
    sites = load_all_sites()
    return (len(sites), "✅" if len(sites) >= 3 else "⚠️ мало карт")


def _check_ai() -> Tuple[str, str, str]:
    from agent.ai.factory import get_ai_client
    try:
        cli = get_ai_client()
        ok = cli.test_connection()
        return (cli.name, "✅ работает" if ok else "❌ не отвечает", cli.model_name)
    except Exception as e:
        return ("?", "❌ ошибка", str(e)[:60])


def _check_disk() -> List[Tuple[str, str, str]]:
    rows = []
    from agent.config import get_settings
    s = get_settings()
    for label, path in (("output", s.output_dir), ("cache", s.cache_dir), ("logs", s.logs_dir)):
        if path.exists():
            size = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
            files = sum(1 for _ in path.rglob("*") if _.is_file())
            rows.append((label, f"{size/1024/1024:.1f} MB", f"{files} файлов"))
        else:
            rows.append((label, "—", "не создан"))
    return rows


def _check_books() -> Tuple[int, str]:
    from agent.config import get_settings
    s = get_settings()
    if not s.output_dir.exists():
        return (0, "—")
    n = sum(1 for _ in s.output_dir.glob("*/metadata.json"))
    return (n, "✅" if n > 0 else "ℹ️ пока нет")


def run_doctor() -> int:
    console = Console()
    console.print("\n[bold]🩺 WishLibrarian — диагностика[/]\n")

    # ── Python и зависимости
    py_v, py_status = _check_python()
    t = Table(title="1. Окружение", show_lines=False)
    t.add_column("Параметр"); t.add_column("Значение"); t.add_column("Статус")
    t.add_row("Python", py_v, py_status)
    t.add_row("Платформа", sys.platform, "✅")
    console.print(t)

    t = Table(title="2. Зависимости", show_lines=False)
    t.add_column("Пакет"); t.add_column("Статус"); t.add_column("Версия / Примечание")
    for pkg, st, info in _check_deps():
        t.add_row(pkg, st, info)
    console.print(t)

    # ── Карты парсера
    n_sites, st = _check_sites()
    console.print(f"\n[bold]3. Карты парсера:[/] {n_sites} загружено  {st}")

    # ── AI
    ai_name, ai_st, ai_model = _check_ai()
    console.print(f"[bold]4. AI-провайдер:[/] {ai_name} ({ai_model})  {ai_st}")

    # ── Диск
    t = Table(title="5. Диск", show_lines=False)
    t.add_column("Каталог"); t.add_column("Размер"); t.add_column("Файлов")
    for label, size, files in _check_disk():
        t.add_row(label, size, files)
    console.print(t)

    # ── Книги
    n_books, st = _check_books()
    console.print(f"\n[bold]6. Обработано книг:[/] {n_books}  {st}")

    # ── Рекомендации
    recs = []
    if n_sites < 3:
        recs.append("⚠️  Загружено мало карт парсера. Проверьте agent/parsers/sites/")
    if "❌" in ai_st:
        recs.append("❌ AI-провайдер не отвечает. Проверьте .env или --ai")
    if n_books == 0:
        recs.append("💡 Обработайте первую книгу: python -m agent.cli --url <URL> --ai gigachat")
    if not recs:
        recs.append("✅ Всё в порядке. Можно работать.")
    console.print("\n[bold]Рекомендации:[/]")
    for r in recs:
        console.print(f"  {r}")
    console.print()
    return 0
