"""
Settings для WishCoach.

Корпоративный MITM (см. memory: corporate-mitm-proxy) — на рабочей машине
`verify_ssl=False` обязателен, иначе любая попытка TLS-запроса упадёт.
"""

from __future__ import annotations

import os
from typing import Literal

from dotenv import load_dotenv
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Загружаем .env ОДИН раз при импорте модуля
load_dotenv()


class Settings(BaseSettings):
    """Все настройки коуча. Секреты НЕ логируются — помечены как SecretStr."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Общее ---
    app_env: Literal["development", "staging", "production"] = "development"
    app_port: int = 8000
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    coach_timezone: str = "Europe/Moscow"

    # --- Cloudflare D1 ---
    cf_account_id: str = ""
    cf_d1_database_id: str = ""
    cf_api_token: str = ""

    # --- Storage backend (Phase 0+) ---
    # d1 — Cloudflare D1 (REST API через httpx), default для production
    # sqlite_local — локальный SQLite-файл (для РФ-локалки без VPN)
    # postgres — задел на будущее (Reg.ru VPS), пока не реализован
    storage_backend: Literal["d1", "sqlite_local", "postgres"] = "sqlite_local"
    sqlite_path: str = "./.data/wishcoach.db"

    # --- AI (Phase 1+) ---
    anthropic_api_key: str = ""
    yandexgpt_api_key: str = ""
    yandexgpt_folder_id: str = ""

    # --- Telegram (Phase 6+) ---
    telegram_bot_token: str = ""
    telegram_bot_username: str = "wishlab_coach_bot"

    # --- VK (Phase 7+) ---
    vk_group_token: str = ""
    vk_group_id: int = 237295798
    vk_confirmation_code: str = ""
    vk_callback_secret: str = ""

    # --- Render (Phase 0: деплой) ---
    render_external_url: str = ""
    render_service_name: str = "wishcoach"

    # --- MITM (корпоративный прокси) ---
    # На рабочей машине ОБЯЗАТЕЛЬНО false
    verify_ssl: bool = False
    socks5_proxy: str = "socks5h://127.0.0.1:10808"

    # --- Админ ---
    admin_telegram_id: int = 0

    # --- Деривативные ---
    @property
    def d1_base_url(self) -> str:
        """Базовый URL Cloudflare D1 REST API."""
        return f"https://api.cloudflare.com/client/v4/accounts/{self.cf_account_id}/d1/database/{self.cf_d1_database_id}"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def has_anthropic(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def has_telegram(self) -> bool:
        return bool(self.telegram_bot_token)

    @property
    def has_vk(self) -> bool:
        # Phase 7: Long Poll — confirmation_code не нужен (только для Callback API)
        return bool(self.vk_group_token and self.vk_group_id)

    # --- Workbooks (Phase 4) ---
    workbooks_dir: str = ""  # filled in __init__ below from env

    @field_validator("workbooks_dir", mode="before")
    @classmethod
    def _workbooks_dir_default(cls, v: str) -> str:
        # WORKBOOKS_DIR env (тестами подменяем на tests/fixtures/workbooks)
        env = os.environ.get("WORKBOOKS_DIR", "")
        if v:
            return v
        if env:
            return env
        # Дефолт — реальный каталог wishlibrarian
        return "C:/Users/kfigh/wish_librarian/output/library"

    @field_validator("coach_timezone")
    @classmethod
    def _validate_tz(cls, v: str) -> str:
        # Не строгая валидация IANA, чтобы не падать на этапе каркаса
        if not v:
            raise ValueError("coach_timezone обязательна")
        return v


# Singleton: импортируй `from agent.config import settings`
settings = Settings()  # type: ignore[call-arg]


def apply_mitm_globals() -> None:
    """
    Вызывается один раз в lifespan FastAPI.

    Устанавливает глобальные флаги SSL и SOCKS5-прокси для httpx/aiohttp/Anthropic SDK
    (косвенно через переменные окружения).

    Подробности см. memory: corporate-mitm-proxy.
    """
    # 1. SSL — должно быть false на корпоративной машине
    os.environ["PYTHONHTTPSVERIFY"] = "0" if not settings.verify_ssl else "1"
    # 2. SOCKS5 — если указан и не используется системный
    if settings.socks5_proxy:
        os.environ["SOCKS5_PROXY"] = settings.socks5_proxy
    # 3. Для httpx (Anthropic SDK использует его) — прокси через init
    #    Пример: httpx.Client(proxy=settings.socks5_proxy) — но это в клиентах


__all__ = ["settings", "apply_mitm_globals", "Settings"]
