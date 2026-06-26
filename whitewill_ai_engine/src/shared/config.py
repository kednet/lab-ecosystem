"""Конфигурация проекта на базе pydantic-settings."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Все настройки проекта — загружаются из .env или переменных окружения."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Yandex Cloud
    yandex_folder_id: str = Field(default="mock-folder-id", description="Folder ID в Yandex Cloud")
    yandex_api_key: str = Field(default="mock-api-key", description="API-ключ сервисного аккаунта")
    yandex_iam_token: str = Field(default="", description="IAM-токен (для SpeechKit/Translate)")

    # LLM
    yandex_gpt_model: str = "yandexgpt"
    yandex_gpt_version: str = "rc"  # rc = latest
    yandex_embeddings_model: str = "text-search-doc"
    yandex_gpt_input_price: float = 0.5
    yandex_gpt_output_price: float = 2.0

    # SpeechKit
    speechkit_enabled: bool = False
    speechkit_lang: str = "ru-RU"
    speechkit_voice: str = "alena"

    # Telegram
    telegram_bot_token: str = ""
    telegram_broker_chat_id: str = ""
    telegram_admin_chat_id: str = ""

    # Bitrix24
    bitrix24_webhook_url: str = ""
    bitrix24_mock_mode: bool = True

    # Off-market
    egrn_api_mode: str = "mock"  # real | mock
    egrn_api_key: str = ""
    fssp_api_mode: str = "mock"

    # Storage
    database_url: str = "sqlite+aiosqlite:///./data/whitewill.db"
    redis_url: str = "redis://localhost:6379/0"

    # Logging
    log_level: str = "INFO"
    env: str = "development"

    # Demo flags
    use_mock_llm: bool = True  # если True — не обращаемся к YandexGPT, отвечаем из шаблонов

    @property
    def is_demo(self) -> bool:
        return self.env == "development" and self.use_mock_llm


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
