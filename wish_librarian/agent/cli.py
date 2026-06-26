"""
CLI-обёртка для WishLibrarian.

Запуск:
    python -m agent.cli --url "https://oko.koob.ru/..."
    python -m agent.cli --file urls.txt
    python -m agent.cli --test
    python -m agent.cli --ai yandex --url "..."   # переопределить AI_PROVIDER на лету
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional

import click
from rich.console import Console
from rich.table import Table

from agent.ai.factory import get_ai_client, reset_ai_client
from agent.config import get_settings, reload_settings
from agent.librarian import WishLibrarian
from agent.utils.logger import get_logger, setup_logging


console = Console()
logger = get_logger()


def _read_urls_from_file(path: Path) -> List[str]:
    if not path.exists():
        raise click.BadParameter(f"Файл не найден: {path}")
    urls: List[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            urls.append(s)
    return urls


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--url", "-u", multiple=True,
    help="URL книги на Koob.ru (можно несколько раз).",
)
@click.option(
    "--file", "-f", "file", type=click.Path(exists=False, path_type=Path),
    help="Путь к файлу со списком URL (по одному на строку).",
)
@click.option(
    "--force", is_flag=True,
    help="Перепарсить даже если книга уже обработана.",
)
@click.option(
    "--parse-only", is_flag=True,
    help="Только парсинг, без вызова AI (экономия токенов).",
)
@click.option(
    "--test", "test_connection", is_flag=True,
    help="Проверить подключение к активному AI-провайдеру и завершить работу.",
)
@click.option(
    "--ai", "ai_provider", default=None,
    type=click.Choice(["claude", "yandex", "gigachat", "fallback"], case_sensitive=False),
    help="Переопределить AI_PROVIDER на лету (без правки .env).",
)
@click.option(
    "--list-sources", "list_sources", is_flag=True,
    help="Показать список поддерживаемых источников книг и выйти.",
)
@click.option(
    "--no-ai-cache", "no_ai_cache", is_flag=True,
    help="Игнорировать кеш AI-ответов (всегда вызывать модель).",
)
@click.option(
    "--doctor", "doctor", is_flag=True,
    help="Запустить диагностику и завершить работу.",
)
@click.option(
    "--query", "-q", "query", default=None,
    help="Поиск по обработанным книгам (по summary.md).",
)
@click.option(
    "--export", "export_formats", default=None,
    help="Экспорт всех книг в форматы через запятую: pdf,epub,docx,txt,html.",
)
@click.option(
    "--no-pdf", "no_pdf", is_flag=True,
    help="Не генерировать PDF автоматически после summary/workbook.",
)
@click.option(
    "--seo/--no-seo", "seo", default=None,
    help="Генерировать SEO-пакет (meta/schema/OG/FAQ). По умолчанию из .env (SEO_AUTO).",
)
@click.option(
    "--seo-ai-faq", "seo_ai_faq", is_flag=True,
    help="Генерировать FAQ через AI (тратит токены, ответы качественнее).",
)
@click.option(
    "--template", "tpl_name", default=None,
    help="Имя шаблона для summary+workbook (ищется в templates/ и builtin/).",
)
@click.option(
    "--template-summary", default=None,
    help="Имя шаблона только для summary (перекрывает --template).",
)
@click.option(
    "--template-workbook", default=None,
    help="Имя шаблона только для workbook (перекрывает --template).",
)
@click.option(
    "--list-templates", "list_templates", is_flag=True,
    help="Показать все доступные шаблоны и выйти.",
)
@click.option(
    "--purge-legacy-cache", "purge_legacy", is_flag=True,
    help="Удалить legacy-файлы кеша AI (без tpl/style в имени) и выйти.",
)
@click.option(
    "--cover-style", default=None,
    help="Стиль обложки: auto (по жанру) | minimal | gradient | geometric | mystical | business | none.",
)
@click.option(
    "--cover-source", type=click.Choice(["generate", "download"], case_sensitive=False),
    default=None,
    help="Источник обложки: generate (своя SVG, default) | download (с сайта-источника, юр. риски).",
)
@click.option(
    "--cover-format", type=click.Choice(["jpg", "svg", "both"], case_sensitive=False),
    default=None,
    help="Формат обложки: jpg (через cairosvg) | svg | both.",
)
def main(
    url: tuple[str, ...],
    file: Optional[Path],
    force: bool,
    parse_only: bool,
    test_connection: bool,
    ai_provider: Optional[str],
    list_sources: bool,
    no_ai_cache: bool,
    doctor: bool,
    query: Optional[str],
    export_formats: Optional[str],
    no_pdf: bool,
    tpl_name: Optional[str],
    template_summary: Optional[str],
    template_workbook: Optional[str],
    list_templates: bool,
    purge_legacy: bool,
    seo: Optional[bool],
    seo_ai_faq: bool,
    cover_style: Optional[str],
    cover_source: Optional[str],
    cover_format: Optional[str],
) -> None:
    """📚 WishLibrarian — ИИ-агент «Библиотекарь желаний»."""
    setup_logging()

    # Если передан --ai, временно патчим ENV и пересоздаём settings
    if ai_provider:
        import os
        os.environ["AI_PROVIDER"] = ai_provider
        reload_settings()
        reset_ai_client()
        logger.info("🔧 AI_PROVIDER переопределён через CLI: {}", ai_provider)

    # Шаблоны: --template* патчит ENV до reload_settings
    template_env_patched = False
    import os
    if tpl_name:
        os.environ["TEMPLATE_SUMMARY"] = tpl_name
        os.environ["TEMPLATE_WORKBOOK"] = tpl_name
        template_env_patched = True
    if template_summary:
        os.environ["TEMPLATE_SUMMARY"] = template_summary
        template_env_patched = True
    if template_workbook:
        os.environ["TEMPLATE_WORKBOOK"] = template_workbook
        template_env_patched = True
    # Cover-настройки: патчим ENV до reload_settings
    cover_env_patched = False
    if cover_style:
        os.environ["COVER_STYLE_DEFAULT"] = cover_style
        cover_env_patched = True
    if cover_format:
        os.environ["COVER_OUTPUT_FORMAT"] = cover_format
        cover_env_patched = True
    if template_env_patched or cover_env_patched:
        reload_settings()
        if template_env_patched:
            logger.info("🔧 Шаблоны переопределены через CLI")
        if cover_env_patched:
            logger.info("🔧 Cover-настройки переопределены через CLI")

    settings = get_settings()

    if purge_legacy:
        from agent.storage.ai_cache import clear_legacy_cache
        n = clear_legacy_cache()
        console.print(f"🧹 Удалено legacy-файлов кеша: [bold]{n}[/bold]")
        sys.exit(0)

    if list_templates:
        from agent.templates import TemplateRegistry
        from agent.config import PROJECT_ROOT
        reg = TemplateRegistry(project_root=PROJECT_ROOT)
        tbl = Table(title="📐 Доступные шаблоны", show_lines=False)
        tbl.add_column("Kind", style="cyan", no_wrap=True)
        tbl.add_column("Name", style="bold")
        tbl.add_column("Version", justify="center")
        tbl.add_column("Source", style="dim")
        tbl.add_column("Description")
        for tpl in reg.list():
            # user dir → "user", иначе "builtin"
            if reg.env_dir and tpl.raw_path and str(tpl.raw_path).startswith(str(reg.env_dir)):
                src = "env override"
            elif tpl.raw_path and "templates" in str(tpl.raw_path) and "builtin" not in str(tpl.raw_path):
                src = "user"
            else:
                src = "builtin"
            tbl.add_row(
                tpl.kind, tpl.name, tpl.version, src,
                (tpl.description or "—")[:60],
            )
        console.print(tbl)
        console.print(
            "\n[dim]Создать свой: положите .md в templates/<kind>/<name>.md "
            "(YAML-фронтматтер + markdown-тело с {{плейсхолдерами}}).[/]"
        )
        sys.exit(0)

    if test_connection:
        try:
            cli = get_ai_client()
            if cli.test_connection():
                console.print(
                    f"✅ [green]{cli.name}[/] работает! "
                    f"[dim]({cli.model_name})[/]"
                )
                sys.exit(0)
            else:
                console.print(
                    f"❌ [red]Ошибка подключения к {cli.name}[/]"
                )
                sys.exit(1)
        except Exception as e:
            console.print(f"❌ [red]Ошибка: {e}[/]")
            sys.exit(1)

    if list_sources:
        from agent.parsers.universal_parser import UniversalBookParser
        up = UniversalBookParser()
        tbl = Table(title="📚 Поддерживаемые источники книг", show_lines=False)
        tbl.add_column("Карта", style="cyan")
        tbl.add_column("Сайт", style="bold")
        tbl.add_column("Host pattern")
        for s in up.supported_sites:
            tbl.add_row(
                s.get("name", "?"),
                s.get("display", "—"),
                "; ".join(s.get("host_patterns", [])),
            )
        console.print(tbl)
        console.print(
            f"\n[dim]Всего: {len(up.supported_sites)} карт. "
            "Добавить новый источник: .yaml в agent/parsers/sites/[/]"
        )
        sys.exit(0)

    if doctor:
        from agent.doctor import run_doctor
        sys.exit(run_doctor())

    if query:
        from agent.search import search_library
        results = search_library(query, settings.output_dir)
        if not results:
            console.print(f"[yellow]По запросу «{query}» ничего не найдено.[/]")
            sys.exit(0)
        tbl = Table(title=f"🔍 Результаты: «{query}»", show_lines=False)
        tbl.add_column("№", style="cyan", no_wrap=True)
        tbl.add_column("Книга", style="bold")
        tbl.add_column("Score", justify="right")
        tbl.add_column("Сниппет", style="dim")
        for i, (folder, score, snip) in enumerate(results, start=1):
            tbl.add_row(str(i), folder.name, str(score), snip[:120])
        console.print(tbl)
        sys.exit(0)

    if export_formats:
        from agent.export import export_book
        formats = [f.strip() for f in export_formats.split(",") if f.strip()]
        n_files = 0
        for folder in sorted(settings.output_dir.iterdir()):
            if not folder.is_dir():
                continue
            if not (folder / "summary.md").exists():
                continue
            files = export_book(folder, formats)
            n_files += len(files)
            for f in files:
                console.print(f"  📄 {f.relative_to(settings.output_dir)}")
        console.print(f"\n✅ Экспортировано: {n_files} файлов в {len(formats)} форматах")
        sys.exit(0)

    urls: List[str] = list(url)
    if file:
        urls.extend(_read_urls_from_file(file))
    urls = [u for u in urls if u]

    if not urls:
        console.print(
            "[yellow]Не указано ни одного URL. "
            "Используйте --url или --file[/]"
        )
        console.print("Пример: python -m agent.cli --url https://www.koob.ru/zeland/level1")
        console.print("        python -m agent.cli --list-sources   # все поддерживаемые сайты")
        sys.exit(2)

    if not parse_only and not settings.has_any_ai_key():
        console.print(
            f"[red]Нет ключей для AI-провайдера '{settings.ai_provider}'![/]\n"
            "Заполните соответствующие переменные в .env, "
            "либо переключитесь через --ai yandex / --ai gigachat.\n"
            "Или используйте --parse-only для парсинга без AI."
        )
        sys.exit(3)

    librarian = WishLibrarian(
        use_ai_cache=not no_ai_cache,
        auto_pdf=not no_pdf,
        template=tpl_name,
        template_summary=template_summary,
        template_workbook=template_workbook,
        seo=seo,
        seo_ai_faq=seo_ai_faq,
        cover_style=cover_style,
        cover_source=cover_source,
        cover_format=cover_format,
    )
    try:
        if len(urls) == 1:
            result = librarian.process_book(
                urls[0], force=force, parse_only=parse_only
            )
            _print_summary([result])
        else:
            results = librarian.process_batch(
                urls, force=force, parse_only=parse_only
            )
            _print_summary(results)
    except KeyboardInterrupt:
        console.print("\n[yellow]Прервано пользователем[/]")
        sys.exit(130)


def _print_summary(results: list) -> None:
    table = Table(title="📚 Результаты обработки", show_lines=False)
    table.add_column("№", style="cyan", no_wrap=True)
    table.add_column("Книга", style="bold")
    table.add_column("Автор")
    table.add_column("Папка", style="dim")
    table.add_column("PDF", justify="center")
    table.add_column("Статус", justify="center")

    for i, r in enumerate(results, start=1):
        status = "❌" if r.errors else "✅"
        title = r.book.title or "—"
        author = r.book.author or "—"
        folder = Path(r.folder).name if r.folder else "—"
        pdf_mark = "✅" if r.summary_path and Path(r.summary_path).with_suffix(".pdf").exists() else "—"
        table.add_row(str(i), title, author, folder, pdf_mark, status)
    console.print(table)


if __name__ == "__main__":
    main()
