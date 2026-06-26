"""
WishLibrarian — главный класс ИИ-агента «Библиотекарь желаний».

Оркестрирует:
  1. Парсинг книги (UniversalBookParser / KoobParser)
  2. Скачивание обложки
  3. Генерацию конспекта (AI-провайдер: claude/yandex/gigachat/fallback)
  4. Генерацию воркбука
  5. Поиск отзывов (LiveLib + www.koob.ru)
  6. Поиск научных статей (КиберЛенинка)
  7. Генерацию партнёрских ссылок
  8. Сохранение всего в структурированную папку

Поддерживаемые источники книг:
  - www.koob.ru / oko.koob.ru
  - livelib.ru
  - labirint.ru
  - litres.ru / litres.com
  - author.today
  - любой URL с Open Graph / Schema.org (generic fallback)

Добавить новый источник: положите .yaml в agent/parsers/sites/.
"""
from __future__ import annotations

import re
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from agent.ai.base import BaseAIClient
from agent.ai.factory import get_ai_client
from agent.ai.prompts import (
    build_system_prompt,
    render_user_prompt,
)
from agent.config import get_settings
from agent.cover import CoverGenerator, CoverStyle
from agent.models import (
    AffiliateLink,
    BookAssets,
    BookInfo,
    ReviewBundle,
    ScientificArticle,
)
from agent.parsers.affiliate_links import AffiliateLinksGenerator
from agent.parsers.koob_parser import KoobParser
from agent.parsers.reviews_parser import ReviewsParser
from agent.parsers.scientific_parser import ScientificParser
from agent.parsers.universal_parser import UniversalBookParser
from agent.storage.file_manager import FileManager
from agent.storage.templates import (
    render_buy_links_md,
    render_cover_note,
    render_metadata_json,
    render_reviews_md,
    render_scientific_md,
    render_tips_md_fallback,
    render_workbook_postprocess,
)
from agent.templates import TemplateRegistry, style_hash
from agent.utils.logger import get_logger


logger = get_logger()


class WishLibrarian:
    """Главный класс-оркестратор."""

    def __init__(
        self,
        *,
        koob_parser: Optional[KoobParser] = None,
        universal_parser: Optional[UniversalBookParser] = None,
        reviews_parser: Optional[ReviewsParser] = None,
        scientific_parser: Optional[ScientificParser] = None,
        affiliate: Optional[AffiliateLinksGenerator] = None,
        ai: Optional[BaseAIClient] = None,
        claude: Optional[BaseAIClient] = None,  # backward-compat alias
        file_manager: Optional[FileManager] = None,
        use_ai_cache: bool = True,             # читать AI-ответы из кеша
        auto_pdf: Optional[bool] = None,       # None → берётся из .env (AUTO_PDF)
        template: Optional[str] = None,        # имя шаблона (для обоих)
        template_summary: Optional[str] = None,
        template_workbook: Optional[str] = None,
        seo: Optional[bool] = None,            # None → из .env (SEO_AUTO)
        seo_ai_faq: bool = False,              # генерировать FAQ через AI (тратит токены)
        cover_style: Optional[str] = None,     # None → из .env (COVER_STYLE_DEFAULT)
        cover_source: Optional[str] = None,    # "generate" | "download" — None → generate
        cover_format: Optional[str] = None,    # "jpg" | "svg" | "both" — None → из .env
    ):
        self.settings = get_settings()
        self.koob = koob_parser or KoobParser()
        self.universal = universal_parser or UniversalBookParser(session=self.koob.session)
        self.reviews = reviews_parser or ReviewsParser(session=self.koob.session)
        self.scientific = scientific_parser or ScientificParser(session=self.koob.session)
        self.affiliate = affiliate or AffiliateLinksGenerator()
        self.fm = file_manager or FileManager()
        # `ai` — основной клиент; `claude` — алиас для старого API
        injected = ai or claude
        self._ai: Optional[BaseAIClient] = injected
        self._ai_cache_bypass = not use_ai_cache
        # auto_pdf: из .env по умолчанию, CLI может переопределить
        self._auto_pdf = auto_pdf if auto_pdf is not None else self.settings.auto_pdf
        # SEO: из .env по умолчанию, CLI может переопределить
        self._seo_enabled = seo if seo is not None else self.settings.seo_auto
        self._seo_ai_faq = seo_ai_faq

        # Cover generator: генерирует SVG-копию (по умолчанию).
        # Скачивание — только если явно cover_source="download".
        self.cover_gen = CoverGenerator()
        self._cover_style = (
            cover_style if cover_style is not None
            else self.settings.cover_style_default
        )
        self._cover_source = cover_source or "generate"
        self._cover_format = (
            cover_format if cover_format is not None
            else self.settings.cover_output_format
        )

        # Шаблоны: явный аргумент → .env → builtin-дефолт
        self._tpl_summary = (
            template_summary or template or self.settings.template_summary
        )
        self._tpl_workbook = (
            template_workbook or template or self.settings.template_workbook
        )
        self._tpl_tips = self.settings.template_tips
        # PROJECT_ROOT лежит в agent/config.py
        from agent.config import PROJECT_ROOT
        self._registry = TemplateRegistry(
            project_root=PROJECT_ROOT,
            env_templates_dir=None,
        )
        self._style_hash = style_hash(
            self.settings.writing_tone,
            self.settings.writing_length,
            self.settings.writing_audience,
            self.settings.writing_language,
        )
        logger.info(
            "📚 WishLibrarian инициализирован "
            "(AI через .env, auto_pdf={}, use_ai_cache={}, "
            "templates: summary={}, workbook={}, tips={}, style={})",
            self._auto_pdf, use_ai_cache,
            self._tpl_summary, self._tpl_workbook, self._tpl_tips,
            f"{self.settings.writing_tone}/{self.settings.writing_length}/"
            f"{self.settings.writing_audience}/{self.settings.writing_language}",
        )

    # ── Вспомогательное ─────────────────────────────────────────
    @property
    def ai(self) -> BaseAIClient:
        """Вернуть активный AI-клиент (lazy)."""
        if self._ai is None:
            self._ai = get_ai_client()
        return self._ai

    @property
    def claude(self) -> BaseAIClient:
        """
        ⚠️ DEPRECATED: алиас для `self.ai`. Сохранён для обратной совместимости.
        В новом коде используйте `librarian.ai`.
        """
        return self.ai

    # ── Главные методы ──────────────────────────────────────────
    def process_book(
        self,
        url: str,
        *,
        force: bool = False,
        parse_only: bool = False,
        template: Optional[str] = None,
        template_summary: Optional[str] = None,
        template_workbook: Optional[str] = None,
    ) -> BookAssets:
        """Обработать одну книгу и создать все файлы.

        Доп. kwargs ``template*`` позволяют переопределить выбор шаблона
        для одного вызова (например, из Telegram /template).
        """
        # Локально подменяем выбор шаблона и сбрасываем кеш реестра,
        # чтобы новые имена гарантированно подхватились.
        if template or template_summary or template_workbook:
            if template_summary:
                self._tpl_summary = template_summary
            elif template:
                self._tpl_summary = template
            if template_workbook:
                self._tpl_workbook = template_workbook
            elif template:
                self._tpl_workbook = template
            self._registry.clear_cache()
        logger.info("=" * 70)
        logger.info("📖 Обрабатываю книгу: {}", url)
        logger.info("=" * 70)

        assets = BookAssets(book=BookInfo(title="?", author="?", source_url=url))

        try:
            # 1) Парсим книгу. Универсальный парсер сам выберет стратегию
            #    по URL (www.koob.ru / oko.koob.ru / livelib / labirint /
            #    litres / author.today / generic Open Graph).
            site_name = self.universal.detect_site(url)
            parser = self.universal
            logger.info("🔍 Источник: {}", site_name or "(автодетект)")
            book = parser.parse(url, save_raw_to=None)
            assets.book = book

            # Создаём папку и кладём raw
            book_folder = self.fm.book_folder(book)
            assets.folder = str(book_folder)
            raw_path = self.fm.raw_html_path(book)

            if not raw_path.exists():
                # Положим raw, если парсер не сохранил
                try:
                    raw_path.write_text(
                        self.koob.session.get(url, timeout=self.settings.request_timeout).text,
                        encoding="utf-8",
                    )
                except Exception as e:
                    logger.warning("Не удалось сохранить raw HTML: {}", e)
            assets.raw_path = str(raw_path)

            if not force and self.fm.is_processed(book):
                logger.info("⏭  Пропускаю (уже обработано): {}", book.title)
                return assets

            # Дедуп по каноническому отпечатку (ISBN / title+author+year)
            existing = self.fm.find_existing_by_fingerprint(book)
            if existing and existing != book_folder:
                logger.warning(
                    "♻️  Эта книга уже есть под именем «{}» (fingerprint совпал)",
                    existing.name,
                )
                # Используем существующую папку, чтобы не плодить дубли
                book_folder = existing
                assets.folder = str(book_folder)

            # Создаём пустой metadata.json — он будет дописан в _save_metadata()
            assets.metadata_path = str(book_folder / "metadata.json")

            if parse_only:
                logger.info("⚙️  parse_only — генерация контента пропущена")
                self._save_metadata(assets)
                return assets

            # 2) Обложка: генерируем SVG (по умолчанию) ИЛИ скачиваем (opt-in)
            assets.cover_path = self._resolve_cover(book, book_folder)

            # 3) AI: конспект
            assets.summary_path = self._generate_summary(book, book_folder)

            # 4) AI: воркбук
            assets.workbook_path = self._generate_workbook(book, book_folder)

            # 5) AI: практические советы
            assets.tips_path = self._generate_tips(book, book_folder, assets.summary_path)

            # 6) Отзывы
            assets.reviews_path = self._collect_reviews(book, book_folder)

            # 7) Научные статьи
            assets.scientific_path = self._search_scientific_articles(book, book_folder)

            # 8) Партнёрские ссылки
            assets.buy_links_path = self._generate_buy_links(book, book_folder)

            # 9) SEO-пакет (от SEO Advisor skill v2.0)
            if self._seo_enabled:
                seo_paths = self._generate_seo(book, book_folder)
                assets.seo_meta_path = seo_paths.get("meta_md")
                assets.seo_schema_path = seo_paths.get("schema")
                assets.seo_og_path = seo_paths.get("og")
                assets.seo_faq_path = seo_paths.get("faq")
                assets.seo_keywords_path = seo_paths.get("keywords")
                assets.seo_slug_path = seo_paths.get("slug")
                assets.seo_report_path = seo_paths.get("report")

            # 10) Финал: ставим processed_at ДО сохранения metadata
            assets.processed_at = datetime.now()
            self._save_metadata(assets)
            logger.success("🎉 Книга обработана: {}", book_folder)
        except KeyboardInterrupt:
            logger.warning("⚠️ Прервано пользователем")
            assets.errors.append("KeyboardInterrupt")
            raise
        except Exception as e:
            logger.exception("💥 Ошибка при обработке {}: {}", url, e)
            assets.errors.append(str(e))

        return assets

    def process_batch(
        self,
        urls: List[str],
        *,
        force: bool = False,
        parse_only: bool = False,
    ) -> List[BookAssets]:
        """Пакетная обработка списка URL."""
        logger.info("📦 Пакетная обработка: {} книг", len(urls))
        results: List[BookAssets] = []
        for i, url in enumerate(urls, start=1):
            logger.info("📖 [{}/{}] {}", i, len(urls), url)
            try:
                a = self.process_book(url, force=force, parse_only=parse_only)
                results.append(a)
            except KeyboardInterrupt:
                logger.warning("Прерывание пакетной обработки")
                break
            except Exception as e:
                logger.error("Ошибка на URL {}: {}", url, e)
        ok = sum(1 for r in results if not r.errors)
        logger.info("✅ Готово: {}/{} книг успешно", ok, len(results))
        return results

    # ── Обработка локального файла ──────────────────────────────
    def process_local_file(
        self,
        file_path: str | Path,
        *,
        max_chars: int = 60_000,
    ) -> BookAssets:
        """Обработать книгу из локального файла (.txt/.fb2/.epub/.pdf).

        В отличие от :meth:`process_book`, здесь нет парсинга внешнего сайта —
        пользователь сам скачал книгу и положил в ``books_input/``.

        Args:
            file_path: путь к .txt/.fb2/.epub/.pdf.
            max_chars: сколько символов исходного текста отдать в LLM.
                60 000 ≈ 15 000 токенов, влезает в yandexgpt-32k.

        Returns:
            :class:`BookAssets` с теми же полями, что и ``process_book``.
        """
        from agent.book_reader import read_book, truncate_for_llm
        from agent.models import ChapterInfo

        file_path = Path(file_path)
        logger.info("=" * 70)
        logger.info(f"📂 Обрабатываю локальный файл: {file_path}")
        logger.info("=" * 70)

        assets = BookAssets(
            book=BookInfo(
                title=file_path.stem,
                author="—",
                source_url=f"file://{file_path.resolve()}",
            ),
        )
        try:
            data = read_book(file_path)
        except Exception as e:
            logger.error(f"💥 Не удалось прочитать {file_path}: {e}")
            assets.errors.append(f"read: {e}")
            return assets

        full_text = data["text"]
        if not full_text or len(full_text) < 500:
            msg = f"Файл слишком короткий: {len(full_text)} символов"
            logger.error(f"💥 {msg}")
            assets.errors.append(msg)
            return assets

        assets.book.title = data["title"] or file_path.stem
        assets.book.author = data["author"] or "—"
        if data.get("chapters"):
            assets.book.chapters = [
                ChapterInfo(number=i + 1, title=t)
                for i, t in enumerate(data["chapters"][:80])
            ]
        # Описание — первые 5 предложений
        sentences = re.split(r"(?<=[.!?])\s+", full_text)
        assets.book.short_description = " ".join(sentences[:5])[:500]
        # «Идеи» — фрагменты первых абзацев
        assets.book.key_ideas = [
            p[:200] for p in full_text.split("\n\n") if len(p) > 50
        ][:10]

        # Папка
        book_folder = self.fm.book_folder(assets.book)
        assets.folder = str(book_folder)

        # Полный текст → в source.txt
        try:
            (book_folder / "source.txt").write_text(full_text, encoding="utf-8")
        except OSError as e:
            logger.warning(f"⚠️ Не удалось сохранить source.txt: {e}")

        # Контекст для AI: усечённый полный текст
        self._extra_context = truncate_for_llm(full_text, max_chars=max_chars)

        try:
            # 0) Обложка: всегда генерируем (локальный файл → cover_url=None,
            #    скачивать нечего → только generate)
            assets.cover_path = self._generate_cover(assets.book, book_folder)
            # 1) Summary
            assets.summary_path = self._generate_summary(assets.book, book_folder)
            # 2) Workbook
            assets.workbook_path = self._generate_workbook(assets.book, book_folder)
            # 3) Tips
            assets.tips_path = self._generate_tips(
                assets.book, book_folder, assets.summary_path,
            )
            # 4) Reviews
            assets.reviews_path = self._collect_reviews(assets.book, book_folder)
            # 5) Scientific
            assets.scientific_path = self._search_scientific_articles(assets.book, book_folder)
            # 6) Buy links
            assets.buy_links_path = self._generate_buy_links(assets.book, book_folder)
            # 7) SEO-пакет (от SEO Advisor skill v2.0)
            if self._seo_enabled:
                seo_paths = self._generate_seo(assets.book, book_folder)
                assets.seo_meta_path = seo_paths.get("meta_md")
                assets.seo_schema_path = seo_paths.get("schema")
                assets.seo_og_path = seo_paths.get("og")
                assets.seo_faq_path = seo_paths.get("faq")
                assets.seo_keywords_path = seo_paths.get("keywords")
                assets.seo_slug_path = seo_paths.get("slug")
                assets.seo_report_path = seo_paths.get("report")
            # 8) Финал
            assets.processed_at = datetime.now()
            self._save_metadata(assets)
            logger.success(f"🎉 Локальная книга обработана: {book_folder}")
        except KeyboardInterrupt:
            assets.errors.append("KeyboardInterrupt")
            raise
        except Exception as e:
            logger.exception(f"💥 Ошибка при обработке {file_path}: {e}")
            assets.errors.append(str(e))
        finally:
            self._extra_context = None
        return assets

    # ── Подэтапы ────────────────────────────────────────────────
    def _prepare_ai_content(self, book: BookInfo) -> str:
        """Подготовить текстовое представление книги для AI."""
        parts: list[str] = []
        parts.append(f"Книга: {book.title} ({book.author}, {book.year or '—'})")
        if book.short_description:
            parts.append(f"\nОписание:\n{book.short_description}")
        if book.key_ideas:
            parts.append("\nКлючевые идеи:")
            parts.extend(f"- {i}" for i in book.key_ideas[:10])
        if book.quotes:
            parts.append("\nЦитаты:")
            parts.extend(f"- {q}" for q in book.quotes[:5])
        if book.chapters:
            parts.append("\nГлавы:")
            parts.extend(f"- Глава {c.number}. {c.title}" for c in book.chapters[:30])
        # Дополнительный контекст: полный текст книги (для process_local_file)
        extra = getattr(self, "_extra_context", None)
        if extra:
            parts.append("\n\n=== ПОЛНЫЙ ТЕКСТ КНИГИ (фрагмент) ===\n")
            parts.append(extra)
        return "\n".join(parts)

    def _tpl_for(self, kind: str):
        """Получить шаблон по виду контента."""
        name = {
            "summary": self._tpl_summary,
            "workbook": self._tpl_workbook,
            "tips": self._tpl_tips,
        }[kind]
        return self._registry.get(kind, name)

    def _generate_summary(self, book: BookInfo, folder: Path) -> Optional[str]:
        logger.info("📝 Генерация конспекта для «{}»", book.title)
        from agent.storage.ai_cache import get_cached, save_cached
        tpl = self._tpl_for("summary")
        cached = get_cached(
            book, "summary", self.ai.model_name,
            tpl=tpl.name, style_hash=self._style_hash,
        )
        if cached and not self._ai_cache_bypass:
            path = self.fm.write_text(folder / "summary.md", cached)
            logger.success("📝 Конспект из кеша: {} ({} симв.)", path.name, len(cached))
            self._maybe_pdf(folder, "summary.md")
            return str(path)

        try:
            content = self.ai.generate(
                system=build_system_prompt(
                    tpl,
                    tone=self.settings.writing_tone,
                    length=self.settings.writing_length,
                    audience=self.settings.writing_audience,
                    language=self.settings.writing_language,
                ),
                user=render_user_prompt(tpl, book),
                max_tokens=self.settings.summary_max_tokens,
            )
        except Exception as e:
            logger.error("Не удалось сгенерировать конспект: {}", e)
            return None

        save_cached(
            book, "summary", self.ai.model_name, content,
            tpl=tpl.name, style_hash=self._style_hash,
        )
        path = self.fm.write_text(folder / "summary.md", content)
        logger.success("📝 Конспект готов: {} ({} симв.)", path.name, len(content))
        self._maybe_pdf(folder, "summary.md")
        return str(path)

    def _generate_workbook(self, book: BookInfo, folder: Path) -> Optional[str]:
        logger.info("✍️  Генерация воркбука для «{}»", book.title)
        from agent.storage.ai_cache import get_cached, save_cached
        tpl = self._tpl_for("workbook")
        cached = get_cached(
            book, "workbook", self.ai.model_name,
            tpl=tpl.name, style_hash=self._style_hash,
        )
        if cached and not self._ai_cache_bypass:
            path = self.fm.write_text(folder / "workbook.md", cached)
            logger.success("✍️ Воркбук из кеша: {}", path.name)
            self._maybe_pdf(folder, "workbook.md")
            return str(path)

        summary_md = ""
        summary_file = folder / "summary.md"
        if summary_file.exists():
            summary_md = summary_file.read_text(encoding="utf-8")[:6000]

        try:
            raw_content = self.ai.generate(
                system=build_system_prompt(
                    tpl,
                    tone=self.settings.writing_tone,
                    length=self.settings.writing_length,
                    audience=self.settings.writing_audience,
                    language=self.settings.writing_language,
                ),
                user=render_user_prompt(
                    tpl, book,
                    tone=self.settings.writing_tone,
                    length=self.settings.writing_length,
                ),
                max_tokens=self.settings.workbook_max_tokens,
            )
        except Exception as e:
            logger.error("Не удалось сгенерировать воркбук: {}", e)
            return None

        # В кеш кладём СЫРОЙ ответ LLM (без пост-процессинга) — это
        # позволяет перерендерить поля/трекер при изменении шаблона без
        # обращения к AI. Пост-процессинг детерминированный.
        save_cached(
            book, "workbook", self.ai.model_name, raw_content,
            tpl=tpl.name, style_hash=self._style_hash,
        )

        # Пост-процессинг: инжектим поля для ответов и трекер привычек
        try:
            content = render_workbook_postprocess(raw_content, tpl, book)
        except Exception as e:
            logger.warning("⚠️  Пост-процессинг воркбука не удался ({}) — пишу как есть", e)
            content = raw_content

        path = self.fm.write_text(folder / "workbook.md", content)
        logger.success("✍️ Воркбук готов: {} ({} симв.)", path.name, len(content))
        self._maybe_pdf(folder, "workbook.md")
        return str(path)

    def _generate_tips(
        self, book: BookInfo, folder: Path, summary_path: Optional[str]
    ) -> Optional[str]:
        logger.info("💡 Генерация практических советов")
        from agent.storage.ai_cache import get_cached, save_cached
        tpl = self._tpl_for("tips")
        cached = get_cached(
            book, "tips", self.ai.model_name,
            tpl=tpl.name, style_hash=self._style_hash,
        )
        if cached and not self._ai_cache_bypass:
            path = self.fm.write_text(folder / "practical_tips.md", cached)
            logger.success("💡 Советы из кеша: {}", path.name)
            return str(path)

        summary_md = ""
        if summary_path:
            try:
                summary_md = Path(summary_path).read_text(encoding="utf-8")[:4000]
            except OSError:
                pass

        try:
            content = self.ai.generate(
                system=build_system_prompt(
                    tpl,
                    tone=self.settings.writing_tone,
                    length=self.settings.writing_length,
                    audience=self.settings.writing_audience,
                    language=self.settings.writing_language,
                ),
                user=render_user_prompt(tpl, book, summary_md=summary_md),
                max_tokens=self.settings.tips_max_tokens,
            )
        except Exception as e:
            logger.warning("Tips не сгенерированы: {}. Пишу fallback.", e)
            self.fm.write_text(folder / "practical_tips.md", render_tips_md_fallback(book))
            return str(folder / "practical_tips.md")

        from agent.storage.ai_cache import save_cached
        save_cached(
            book, "tips", self.ai.model_name, content,
            tpl=tpl.name, style_hash=self._style_hash,
        )
        path = self.fm.write_text(folder / "practical_tips.md", content)
        logger.success("💡 Практические советы готовы");
        return str(path)

    def _maybe_pdf(self, folder: Path, md_filename: str) -> None:
        """Сгенерировать PDF из .md файла, если включён auto_pdf."""
        if not self._auto_pdf:
            return
        md_path = folder / md_filename
        if not md_path.exists():
            return
        pdf_path = md_path.with_suffix(".pdf")
        try:
            from agent.export import md_to_pdf
            md_to_pdf(md_path, pdf_path)
            logger.info("📄 PDF: {}", pdf_path.name)
        except Exception as e:
            logger.warning("⚠️  Не удалось сконвертировать {} в PDF: {}", md_filename, e)

    def _download_cover(self, book: BookInfo, folder: Path) -> Optional[str]:
        """
        Скачать обложку с сайта-источника (OPT-IN, юридические риски!).
        Включается явно: enable_cover_download=True или --cover-source=download.
        """
        if not self.settings.enable_cover_download or not book.cover_url:
            return None

        cover_path = folder / "cover.jpg"
        ok = self.koob.download_file(book.cover_url, cover_path)
        if not ok:
            self.fm.write_text(folder / "cover.jpg.note.md", render_cover_note(book))
        return str(cover_path) if ok else None

    def _generate_cover(self, book: BookInfo, folder: Path) -> Optional[str]:
        """
        Сгенерировать SVG-обложку (+ опц. PNG/JPG через cairosvg).
        Возвращает путь к cover.jpg (приоритет для Publisher) или cover_local.svg.
        """
        # Если выключено через ENV — ничего не делаем
        if self._cover_style == "none":
            return None

        # Стиль: CLI > дефолт > авто-детект по жанру
        style = None
        if self._cover_style and self._cover_style != "auto":
            style = CoverStyle.parse(self._cover_style)
        if style is None:
            style = self.cover_gen.detect_style(book)

        # Генерация
        try:
            result = self.cover_gen.generate(
                title=book.title,
                author=book.author,
                genre=book.genre,
                style=style,
                brand_name=self.settings.brand_name,
                disclaimer=self.settings.cover_disclaimer,
            )
        except Exception as e:
            logger.error("⚠️  Генерация обложки не удалась: {}", e)
            return None

        # Формат сохранения
        png_format = (
            "jpg"   if self._cover_format == "jpg"   else
            "png"   if self._cover_format == "png"   else
            "jpg"   if self._cover_format == "both"  else  # jpg + svg
            "none"
        )
        paths = self.cover_gen.save(
            result, folder,
            svg_name="cover_local.svg",
            png_format=png_format,
        )
        # Приоритет: jpg/png > svg (Publisher уже умеет искать оба)
        return str(paths["png"]) if paths["png"] else str(paths["svg"])

    def _resolve_cover(self, book: BookInfo, folder: Path) -> Optional[str]:
        """
        Главная точка входа: выбирает download/generate по cover_source.
        Fallback: если скачивание провалилось — генерируем.
        """
        if self._cover_source == "download":
            downloaded = self._download_cover(book, folder)
            if downloaded:
                return downloaded
            logger.info("Скачивание не удалось — генерирую обложку")
        return self._generate_cover(book, folder)

    def _collect_reviews(self, book: BookInfo, folder: Path) -> Optional[str]:
        if not self.settings.enable_reviews_search:
            return None
        bundle: ReviewBundle = self.reviews.search(book)
        # Дополним отзывами с www.koob.ru, если они уже сохранены локально
        try:
            raw_path = folder / "raw" / "source.html"
            if raw_path.exists():
                extra = self.reviews.collect_www_koob_reviews(book, str(raw_path))
                if extra:
                    bundle = self.reviews.merge_bundles(book, bundle, extra)
        except Exception as e:
            logger.debug("Не удалось добавить www.koob.ru отзывы: {}", e)
        md = render_reviews_md(book, bundle)
        path = self.fm.write_text(folder / "reviews.md", md)
        return str(path)

    def _search_scientific_articles(
        self, book: BookInfo, folder: Path
    ) -> Optional[str]:
        if not self.settings.enable_scientific_search:
            return None
        articles: List[ScientificArticle] = self.scientific.search(book)
        md = render_scientific_md(book, articles)
        path = self.fm.write_text(folder / "scientific.md", md)
        return str(path)

    def _generate_buy_links(self, book: BookInfo, folder: Path) -> Optional[str]:
        links: List[AffiliateLink] = self.affiliate.generate(book)
        md = render_buy_links_md(book, links)
        path = self.fm.write_text(folder / "buy_links.md", md)
        return str(path)

    def _generate_seo(self, book: BookInfo, folder: Path) -> dict[str, str]:
        """
        SEO-пакет (от SEO Advisor skill v2.0):
        - meta.md / meta.json
        - schema.json (JSON-LD @graph)
        - og.md (OG / VK / Twitter)
        - faq.md (FAQ + JSON-LD)
        - keywords.md (LSI + PAA)
        - slug.txt
        - seo-report.md (человекочитаемый отчёт)

        Детерминированный, не вызывает AI (кроме опции --seo-ai-faq).
        """
        from agent.seo.generator import SEOPackageGenerator, render_seo_files

        logger.info("🔍 Генерация SEO-пакета для «{}»", book.title)
        try:
            generator = SEOPackageGenerator()
            ai_client = self.ai if self._seo_ai_faq else None
            pkg = generator.generate(book, use_ai_faq=self._seo_ai_faq, ai_client=ai_client)
            seo_dir = folder / "seo"
            paths = render_seo_files(pkg, seo_dir)
            logger.success(
                "🔍 SEO-пакет готов: {} файлов в seo/",
                len(paths),
            )
            return paths
        except Exception as e:
            logger.error("⚠️  SEO-генерация не удалась: {}", e)
            return {}

    # ── Сохранение metadata.json ────────────────────────────────
    def _save_metadata(self, assets: BookAssets) -> None:
        if not assets.folder or not assets.metadata_path:
            return
        extra = {
            "ai_provider": self.ai.name,
            "ai_model": self.ai.model_name,
            "templates": {
                "summary": self._tpl_summary,
                "workbook": self._tpl_workbook,
                "tips": self._tpl_tips,
            },
            "style": {
                "tone": self.settings.writing_tone,
                "length": self.settings.writing_length,
                "audience": self.settings.writing_audience,
                "language": self.settings.writing_language,
            },
            "style_hash": self._style_hash,
            "paths": {
                "summary": assets.summary_path,
                "workbook": assets.workbook_path,
                "reviews": assets.reviews_path,
                "tips": assets.tips_path,
                "scientific": assets.scientific_path,
                "buy_links": assets.buy_links_path,
                "cover": assets.cover_path,
                "raw": assets.raw_path,
            },
            "errors": assets.errors,
            "processed_at": (
                assets.processed_at.isoformat() if assets.processed_at else None
            ),
            "folder": assets.folder,
        }
        # render_metadata_json возвращает JSON-строку — пишем как текст,
        # чтобы сохранить порядок ключей и эмодзи как есть
        from pathlib import Path
        Path(assets.metadata_path).write_text(
            render_metadata_json(assets.book, extra), encoding="utf-8"
        )
        logger.info(
            "📋 metadata.json обновлён (AI: {}, style: {})",
            self.ai.model_name, self._style_hash,
        )
