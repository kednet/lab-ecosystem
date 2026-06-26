"""
lib/llm_client.py — обёртка LLM.

Поддерживаемые провайдеры:
  - yandex (YandexGPT, приоритет — есть ключ)
  - claude (Anthropic, если появится ANTHROPIC_API_KEY)
  - gigachat (Сбер, если потребуется)

Переменные окружения (читаются из .env других скилов):
  YandexGPT:
    YANDEX_API_KEY
    YANDEX_FOLDER_ID
    YANDEX_MODEL (default: yandexgpt)
  Claude:
    ANTHROPIC_API_KEY
    CLAUDE_MODEL (default: claude-sonnet-4-5)
  GigaChat:
    GIGACHAT_AUTHORIZATION_KEY
    GIGACHAT_SCOPE
    GIGACHAT_MODEL
    GIGACHAT_VERIFY_SSL (default: false)
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

# Force UTF-8
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

# Подавляем SSL-варнинги для GigaChat (корпоративный MITM)
try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except ImportError:
    pass

# Резервные пути к .env (для токенов других скилов)
ENV_FALLBACKS = [
    Path("C:/Users/kfigh/wish_librarian/.env"),
    Path("C:/Users/kfigh/publisher_skill/.env"),
    Path("C:/Users/kfigh/seo-advisor-skill/.env"),
    Path("C:/Users/kfigh/expert-reviews-hub/.env"),
    Path(__file__).parent.parent.parent / ".env",  # Свой .env
]


def _load_env() -> None:
    """Загрузить .env файлы с приоритетом (override=True, последний побеждает)."""
    from dotenv import load_dotenv
    for env_path in ENV_FALLBACKS:
        if env_path.exists():
            load_dotenv(env_path, override=False)  # Не перезаписываем уже установленные


class LLMClient:
    """Обёртка LLM."""

    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None):
        _load_env()

        self.provider = provider or self._detect_provider()
        self.model = model or self._default_model()
        self.api_key = self._get_api_key()

    def _detect_provider(self) -> str:
        """Определить провайдера по наличию ключей."""
        if os.environ.get("YANDEX_API_KEY") and os.environ.get("YANDEX_FOLDER_ID"):
            return "yandex"
        if os.environ.get("ANTHROPIC_API_KEY") and not os.environ["ANTHROPIC_API_KEY"].startswith("sk-ant-your"):
            return "claude"
        if os.environ.get("GIGACHAT_AUTHORIZATION_KEY"):
            return "gigachat"
        return "stub"

    def _default_model(self) -> str:
        defaults = {
            "yandex": "yandexgpt",
            "claude": "claude-sonnet-4-5",
            "gigachat": "GigaChat",
        }
        env_key = {
            "yandex": "YANDEX_MODEL",
            "claude": "CLAUDE_MODEL",
            "gigachat": "GIGACHAT_MODEL",
        }
        return os.environ.get(env_key[self.provider], defaults.get(self.provider, "unknown"))

    def _get_api_key(self) -> Optional[str]:
        if self.provider == "yandex":
            return os.environ.get("YANDEX_API_KEY")
        if self.provider == "claude":
            return os.environ.get("ANTHROPIC_API_KEY")
        if self.provider == "gigachat":
            return os.environ.get("GIGACHAT_AUTHORIZATION_KEY")
        return None

    def is_available(self) -> bool:
        """Доступен ли провайдер (есть ключ и не stub)."""
        return self.provider != "stub" and bool(self.api_key)

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 2000,
        temperature: float = 0.7,
    ) -> str:
        """
        Генерация текста.

        Returns: текст ответа (str)
        Raises: RuntimeError если провайдер не поддерживается или ошибка API.
        """
        if not self.is_available():
            raise RuntimeError(
                f"LLM провайдер '{self.provider}' недоступен. "
                f"Проверьте ключи в .env. Доступные провайдеры: yandex, claude, gigachat."
            )

        if self.provider == "yandex":
            return self._yandex_generate(prompt, system, max_tokens, temperature)
        elif self.provider == "claude":
            return self._claude_generate(prompt, system, max_tokens, temperature)
        elif self.provider == "gigachat":
            return self._gigachat_generate(prompt, system, max_tokens, temperature)
        else:
            raise RuntimeError(f"Провайдер '{self.provider}' не реализован")

    def classify(
        self,
        text: str,
        categories: List[str],
    ) -> str:
        """Классификация текста по категориям. Возвращает одну категорию."""
        cats_str = ", ".join(f'"{c}"' for c in categories)
        prompt = (
            f"Классифицируй следующий комментарий по одной из категорий: {cats_str}.\n"
            f"Верни ТОЛЬКО название категории, без пояснений.\n\n"
            f"Комментарий: {text}\n\n"
            f"Категория:"
        )
        response = self.generate(prompt, system="Ты классификатор комментариев.", max_tokens=50, temperature=0.1)
        # Берём первую строку, очищаем
        first_line = response.strip().split("\n")[0].strip().strip('"').strip("'")
        # Ищем точное совпадение с категорией
        for c in categories:
            if c.lower() in first_line.lower():
                return c
        return first_line

    def extract_themes(
        self,
        texts: List[str],
        top_n: int = 10,
    ) -> List[str]:
        """Извлечение тем из списка текстов. Возвращает список тем."""
        joined = "\n".join(f"- {t}" for t in texts[:50])  # Лимит — первые 50
        prompt = (
            f"Извлеки {top_n} ключевых тем/паттернов из следующих текстов. "
            f"Верни список тем (по одной на строку, начни с '-').\n\n{joined}\n\n"
            f"Темы:"
        )
        response = self.generate(prompt, system="Ты аналитик тем.", max_tokens=500, temperature=0.3)
        themes = []
        for line in response.split("\n"):
            line = line.strip().lstrip("-").lstrip("•").strip()
            if line and len(line) > 3:
                themes.append(line)
            if len(themes) >= top_n:
                break
        return themes

    # === Реализации провайдеров ===

    def _yandex_generate(
        self,
        prompt: str,
        system: Optional[str],
        max_tokens: int,
        temperature: float,
    ) -> str:
        """YandexGPT API."""
        import requests
        folder_id = os.environ["YANDEX_FOLDER_ID"]
        url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
        headers = {
            "Authorization": f"Api-Key {self.api_key}",
            "Content-Type": "application/json",
        }
        messages = []
        if system:
            messages.append({"role": "system", "text": system})
        messages.append({"role": "user", "text": prompt})

        payload = {
            "modelUri": f"gpt://{folder_id}/{self.model}",
            "completionOptions": {
                "stream": False,
                "temperature": temperature,
                "maxTokens": max_tokens,
            },
            "messages": messages,
        }
        try:
            resp = requests.post(url, headers=headers, json=payload, verify=False, timeout=60)
        except requests.exceptions.Timeout:
            raise RuntimeError("YandexGPT timeout (60s)")
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"YandexGPT network error: {e}")

        if resp.status_code != 200:
            raise RuntimeError(f"YandexGPT API error {resp.status_code}: {resp.text[:300]}")

        data = resp.json()
        return data["result"]["alternatives"][0]["message"]["text"]

    def _claude_generate(
        self,
        prompt: str,
        system: Optional[str],
        max_tokens: int,
        temperature: float,
    ) -> str:
        """Anthropic Claude API."""
        try:
            import anthropic
        except ImportError:
            raise RuntimeError("anthropic SDK не установлен. pip install anthropic")

        client = anthropic.Anthropic(api_key=self.api_key)
        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system

        try:
            message = client.messages.create(**kwargs)
        except Exception as e:
            raise RuntimeError(f"Claude API error: {e}")

        # Извлекаем текст из content blocks
        if hasattr(message, "content") and message.content:
            return message.content[0].text
        return ""

    def _gigachat_generate(
        self,
        prompt: str,
        system: Optional[str],
        max_tokens: int,
        temperature: float,
    ) -> str:
        """GigaChat API (Сбер)."""
        try:
            import requests
        except ImportError:
            raise RuntimeError("requests не установлен")

        verify_ssl = os.environ.get("GIGACHAT_VERIFY_SSL", "false").lower() != "false"
        scope = os.environ.get("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")

        # 1. Получаем OAuth-токен
        token_url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
        token_headers = {
            "Authorization": f"Basic {self.api_key}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        token_data = {"scope": scope}

        try:
            token_resp = requests.post(
                token_url, headers=token_headers, data=token_data,
                verify=verify_ssl, timeout=30,
            )
        except requests.exceptions.SSLError as e:
            if verify_ssl:
                raise RuntimeError(
                    f"GigaChat SSL ошибка. Установите GIGACHAT_VERIFY_SSL=false. "
                    f"Оригинал: {e}"
                )
            raise

        if token_resp.status_code != 200:
            raise RuntimeError(f"GigaChat OAuth error {token_resp.status_code}: {token_resp.text[:200]}")

        access_token = token_resp.json()["access_token"]

        # 2. Отправляем запрос
        chat_url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
        chat_headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        chat_data = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        chat_resp = requests.post(
            chat_url, headers=chat_headers, json=chat_data,
            verify=verify_ssl, timeout=60,
        )
        if chat_resp.status_code != 200:
            raise RuntimeError(f"GigaChat API error {chat_resp.status_code}: {chat_resp.text[:200]}")

        return chat_resp.json()["choices"][0]["message"]["content"]


def quick_test() -> None:
    """Быстрый self-test: показать какой провайдер выбран и работает ли он."""
    client = LLMClient()
    print(f"[LLM] Provider: {client.provider}")
    print(f"[LLM] Model: {client.model}")
    print(f"[LLM] Available: {client.is_available()}")
    if client.is_available():
        try:
            response = client.generate(
                "Скажи одним предложением: какой сегодня день недели?",
                system="Ты ассистент. Отвечай кратко.",
                max_tokens=50,
            )
            print(f"[LLM] Test response: {response!r}")
        except Exception as e:
            print(f"[LLM] Test failed: {e}")


if __name__ == "__main__":
    quick_test()
