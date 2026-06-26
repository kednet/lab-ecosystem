"""
Конфигурация WishLibrarian.

Все настройки загружаются из переменных окружения (.env).
Используется pydantic-settings для валидации.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Главный объект настроек приложения."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Anthropic Claude API ────────────────────────────────────────
    ai_provider: str = Field(
        default="claude",
        description="claude | yandex | gigachat | fallback",
    )
    anthropic_api_key: str = Field(default="", description="Anthropic API key")
    claude_model: str = Field(
        default="claude-sonnet-4-5", description="ID модели Claude"
    )
    # Глобальный лимит (по умолчанию используется, если per-task не задан)
    claude_max_tokens: int = Field(default=8192, ge=256, le=16000)
    claude_temperature: float = Field(default=0.7, ge=0.0, le=1.0)

    # ── Per-task лимиты токенов (переопределяют claude_max_tokens) ─
    # Конспект — 7000 символов ≈ 1800–2200 слов, помещается в один вызов
    summary_max_tokens: int = Field(default=7000, ge=256, le=16000)
    # Воркбук — 14000 символов (10 секций в v2: самоанализ + поля + практика
    # + кейсы + if-then + план + трекер + рефлексия + бонус)
    workbook_max_tokens: int = Field(default=14000, ge=256, le=16000)
    # Советы — короткие, 2500 хватит
    tips_max_tokens: int = Field(default=2500, ge=256, le=16000)

    # ── YandexGPT (Foundation Models) ─────────────────────────────
    yandex_api_key: str = Field(default="", description="Yandex Cloud API key")
    yandex_folder_id: str = Field(default="", description="Yandex Cloud folder ID")
    yandex_model: str = Field(default="yandexgpt-lite", description="ID модели")
    yandex_base_url: str = Field(
        default="https://llm.api.cloud.yandex.net/foundationModels/v1"
    )

    # ── GigaChat (Сбер) ───────────────────────────────────────────
    gigachat_authorization_key: str = Field(
        default="",
        description="base64(client_id:client_secret) из личного кабинета",
    )
    gigachat_scope: str = Field(
        default="GIGACHAT_API_PERS",
        description="GIGACHAT_API_PERS | GIGACHAT_API_CORP | GIGACHAT_API_B2B",
    )
    gigachat_model: str = Field(
        default="GigaChat",
        description="GigaChat | GigaChat-Pro | GigaChat-Max",
    )
    gigachat_base_url: str = Field(
        default="https://gigachat.devices.sberbank.ru/api/v1"
    )
    gigachat_oauth_url: str = Field(
        default="https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    )
    gigachat_verify_ssl: bool = Field(
        default=True,
        description="Отключить проверку SSL (только для корпоративных MITM)",
    )

    # ── Партнёрские ID магазинов ────────────────────────────────────
    litres_partner_id: str = Field(default="", description="ID партнёра Литрес")
    labirint_partner_id: str = Field(default="", description="ID партнёра Лабиринт")
    ozon_partner_id: str = Field(default="", description="ID партнёра Ozon")

    # ── Прокси (для Telegram из РФ и т.п.) ─────────────────────────
    # socks5://user:pass@host:port  или  http://host:port
    # Если пусто — прокси не используется.
    telegram_proxy_url: str = Field(
        default="", description="SOCKS5/HTTP прокси для Telegram Bot API (primary)"
    )
    telegram_proxy_url_backup: str = Field(
        default="", description="Запасной SOCKS5/HTTP прокси. Включается автоматически, "
                                "если primary не отвечает N запросов подряд (см. PROXY_FAILOVER_THRESHOLD)."
    )
    # Сколько подряд сетевых ошибок терпим, прежде чем переключиться на backup-прокси
    proxy_failover_threshold: int = Field(
        default=3, description="Failover: количество подряд ошибок перед переключением на backup"
    )
    vk_proxy_url: str = Field(
        default="", description="SOCKS5/HTTP прокси для VK API (обычно не нужен)"
    )

    # ── Telegram-бот ────────────────────────────────────────────────
    telegram_bot_token: str = Field(default="", description="Основной токен (alias на librarian)")
    telegram_bot_token_detector: str = Field(
        default="", description="Токен DetectorBot (@WLDetectorbot)"
    )
    telegram_bot_token_librarian: str = Field(
        default="", description="Токен WLBBibliobot (@WLBBibliobot)"
    )
    telegram_admin_id: int = Field(
        default=0,
        description="ID админа (int). 0 = принимать все сообщения",
    )

    # ── ВКонтакте-бот ───────────────────────────────────────────────
    # Получить: https://vk.com/groups → создать сообщество → Настройки →
    #   Работа с API → Создать ключ. Включить Long Poll API + Сообщения.
    vk_group_token: str = Field(
        default="",
        description="Токен сообщества VK (из настроек сообщества → API)",
    )
    vk_group_id: int = Field(
        default=0, description="ID сообщества VK (int, без минуса)"
    )

    # ── Пути ────────────────────────────────────────────────────────
    output_dir: Path = Field(
        default=PROJECT_ROOT / "output" / "library",
        description="Куда складывать обработанные книги",
    )
    cache_dir: Path = Field(
        default=PROJECT_ROOT / "cache", description="Кэш HTTP-запросов"
    )
    logs_dir: Path = Field(default=PROJECT_ROOT / "logs", description="Каталог логов")

    # ── Поведение ───────────────────────────────────────────────────
    log_level: str = Field(default="INFO", description="Уровень логирования")
    request_delay: float = Field(
        default=1.0, ge=0.0, description="Задержка между HTTP-запросами (сек.)"
    )
    request_timeout: int = Field(default=30, ge=5, le=300)
    max_retries: int = Field(default=3, ge=1, le=10)
    user_agent: str = Field(
        default=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    )

    # ── Генерация контента ──────────────────────────────────────────
    summary_language: str = Field(default="ru")
    workbook_language: str = Field(default="ru")
    enable_scientific_search: bool = Field(default=True)
    enable_reviews_search: bool = Field(default=True)
    # Скачивание чужой обложки с сайта-источника (юридические риски!).
    # По умолчанию ВЫКЛЮЧЕНО — генерируем свою SVG.
    enable_cover_download: bool = Field(default=False)
    # Авто-PDF: после summary.md/workbook.md сразу создавать .pdf
    auto_pdf: bool = Field(default=True)

    # ── Генератор обложек (Phase 1: cover/) ───────────────────────
    # Стиль: auto (по жанру) | minimal | gradient | geometric | mystical | business | none
    cover_style_default: str = Field(default="auto")
    # Бренд-строка в footer обложки (можно переопределить через ENV)
    brand_name: str = Field(default="ЛАБОРАТОРИЯ ЖЕЛАНИЙ")
    brand_url: str = Field(default="https://pulab.online")
    # Юридический disclaimer мелким шрифтом внизу обложки
    cover_disclaimer: str = Field(
        default="Обложка сгенерирована автоматически, не является официальным изданием"
    )
    # Выходной формат: jpg (через cairosvg, default) | svg | both
    cover_output_format: str = Field(default="jpg")

    # ── SEO (SEO Advisor skill v2.0) ─────────────────────────────────
    # Автогенерация SEO-пакета после обработки книги
    seo_auto: bool = Field(default=True)
    # Генерировать FAQ через AI-клиент (тратит токены, но ответы лучше)
    seo_ai_faq: bool = Field(default=False)

    # ── Стиль письма (style injection в system prompt) ─────────────
    writing_tone: str = Field(
        default="coaching",
        description="formal | casual | coaching",
    )
    writing_length: str = Field(
        default="medium",
        description="short | medium | long",
    )
    writing_audience: str = Field(
        default="general",
        description="general | expert | teen",
    )
    writing_language: str = Field(
        default="ru",
        description="Код языка вывода (ru, en, uk, …)",
    )

    # ── Шаблоны контента ────────────────────────────────────────────
    template_summary: str = Field(
        default="summary_v2",
        description="Имя шаблона summary (по умолчанию встроенный)",
    )
    template_workbook: str = Field(
        default="workbook_v2",
        description="Имя шаблона workbook (по умолчанию встроенный)",
    )
    template_tips: str = Field(
        default="tips_v1",
        description="Имя шаблона practical_tips (по умолчанию встроенный)",
    )
    templates_dir: Path = Field(
        default=PROJECT_ROOT / "templates",
        description="Каталог пользовательских шаблонов (перекрывает встроенные)",
    )

    # ── Источники ───────────────────────────────────────────────────
    # Поддерживаем оба зеркала koob.ru. По умолчанию — основной сайт
    # www.koob.ru (он содержит полные тексты и более стабилен).
    koob_base_url: str = Field(
        default="https://www.koob.ru",
        description="Базовый URL библиотеки koob.ru",
    )
    koob_alternate_mirror: str = Field(
        default="https://oko.koob.ru",
        description="Запасное зеркало (на случай, если основной недоступен)",
    )
    livelib_base_url: str = Field(default="https://www.livelib.ru")
    cyberleninka_base_url: str = Field(default="https://cyberleninka.ru")

    @field_validator("log_level")
    @classmethod
    def _validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v_up = v.upper()
        if v_up not in allowed:
            raise ValueError(f"log_level must be one of {allowed}")
        return v_up

    @field_validator("ai_provider", mode="before")
    @classmethod
    def _validate_ai_provider(cls, v) -> str:
        allowed = {"claude", "yandex", "gigachat", "fallback"}
        v_low = (v or "").lower().strip()
        if v_low not in allowed:
            raise ValueError(
                f"ai_provider must be one of {sorted(allowed)}, got {v!r}"
            )
        return v_low

    @field_validator("gigachat_scope", mode="before")
    @classmethod
    def _validate_gigachat_scope(cls, v) -> str:
        allowed = {"GIGACHAT_API_PERS", "GIGACHAT_API_CORP", "GIGACHAT_API_B2B"}
        v_up = (v or "").upper().strip()
        if v_up not in allowed:
            raise ValueError(
                f"gigachat_scope must be one of {sorted(allowed)}, got {v!r}"
            )
        return v_up

    @field_validator("writing_tone", mode="before")
    @classmethod
    def _validate_writing_tone(cls, v) -> str:
        allowed = {"formal", "casual", "coaching"}
        v_low = (v or "").lower().strip()
        if v_low not in allowed:
            # не валим приложение — возвращаем дефолт и логируем
            import logging
            logging.getLogger("wishlibrarian.config").warning(
                "writing_tone=%r не в %s, использую 'coaching'", v, sorted(allowed),
            )
            return "coaching"
        return v_low

    @field_validator("writing_length", mode="before")
    @classmethod
    def _validate_writing_length(cls, v) -> str:
        allowed = {"short", "medium", "long"}
        v_low = (v or "").lower().strip()
        if v_low not in allowed:
            import logging
            logging.getLogger("wishlibrarian.config").warning(
                "writing_length=%r не в %s, использую 'medium'", v, sorted(allowed),
            )
            return "medium"
        return v_low

    @field_validator("writing_audience", mode="before")
    @classmethod
    def _validate_writing_audience(cls, v) -> str:
        allowed = {"general", "expert", "teen"}
        v_low = (v or "").lower().strip()
        if v_low not in allowed:
            import logging
            logging.getLogger("wishlibrarian.config").warning(
                "writing_audience=%r не в %s, использую 'general'", v, sorted(allowed),
            )
            return "general"
        return v_low

    @field_validator("output_dir", "cache_dir", "logs_dir", mode="before")
    @classmethod
    def _expand_path(cls, v):
        if isinstance(v, str):
            return Path(v).expanduser().resolve()
        if isinstance(v, Path):
            return v.expanduser().resolve()
        return v

    def ensure_directories(self) -> None:
        """Создаёт все нужные каталоги, если их нет."""
        for d in (self.output_dir, self.cache_dir, self.logs_dir):
            d.mkdir(parents=True, exist_ok=True)

    def has_anthropic_key(self) -> bool:
        return bool(self.anthropic_api_key) and self.anthropic_api_key.startswith("sk-")

    def has_yandex_key(self) -> bool:
        return bool(self.yandex_api_key) and bool(self.yandex_folder_id)

    def has_gigachat_key(self) -> bool:
        return bool(self.gigachat_authorization_key)

    def has_any_ai_key(self) -> bool:
        """Хотя бы один провайдер сконфигурирован (с учётом выбора)."""
        provider = self.ai_provider
        if provider == "claude":
            return self.has_anthropic_key()
        if provider == "yandex":
            return self.has_yandex_key()
        if provider == "gigachat":
            return self.has_gigachat_key()
        if provider == "fallback":
            # fallback: Yandex + GigaChat. Claude НЕ нужен.
            return self.has_yandex_key() or self.has_gigachat_key()
        return False


# ── Синглтон ───────────────────────────────────────────────────────
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Возвращает единственный экземпляр настроек."""
    global _settings
    if _settings is None:
        _settings = Settings()
        _settings.ensure_directories()
    return _settings


def reload_settings() -> Settings:
    """Перезагрузить настройки (после изменения .env)."""
    global _settings
    _settings = None
    return get_settings()
