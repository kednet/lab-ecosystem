"""
Обёртка для YandexGPT Foundation Models API.
Использует ключ из .env (YANDEX_API_KEY + YANDEX_FOLDER_ID).
Корпоративный MITM: *_VERIFY_SSL=false через requests.
"""

import os
import sys
import json
import requests
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
    # Подхватываем .env из родителя (wish_market/.env) и из соседних проектов
    load_dotenv(Path(__file__).parent.parent / ".env")
    load_dotenv(Path("C:/Users/kfigh/audio_skill/.env"))  # fallback на проверенный ключ
    load_dotenv(Path("C:/Users/kfigh/wish_librarian/.env"))  # ещё один fallback
except ImportError:
    pass


class YandexGPT:
    BASE_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1"

    def __init__(
        self,
        api_key: Optional[str] = None,
        folder_id: Optional[str] = None,
        model: str = "yandexgpt-lite",
        temperature: float = 0.6,
        max_tokens: int = 2000,
    ):
        self.api_key = api_key or os.getenv("YANDEX_API_KEY") or os.getenv("YANDEX_GPT_API_KEY")
        self.folder_id = folder_id or os.getenv("YANDEX_FOLDER_ID") or os.getenv("YANDEX_GPT_FOLDER_ID")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        # Корпоративный MITM — отключаем SSL-проверку
        self.verify_ssl = os.getenv("YANDEX_VERIFY_SSL", "false").lower() != "true"

        if not self.api_key or not self.folder_id:
            raise ValueError(
                "YANDEX_API_KEY и YANDEX_FOLDER_ID должны быть в .env "
                "(или скопированы из audio_skill/.env)"
            )

    def completion(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Запрос к YandexGPT. Возвращает текст ответа.
        """
        url = f"{self.BASE_URL}/completion"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Api-Key {self.api_key}",
            "x-folder-id": self.folder_id,
        }
        payload = {
            "modelUri": f"gpt://{self.folder_id}/{self.model}",
            "completionOptions": {
                "stream": False,
                "temperature": temperature if temperature is not None else self.temperature,
                "maxTokens": str(max_tokens if max_tokens is not None else self.max_tokens),
            },
            "messages": [
                {"role": "system", "text": system_prompt},
                {"role": "user", "text": user_prompt},
            ],
        }

        try:
            resp = requests.post(url, headers=headers, json=payload, verify=self.verify_ssl, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            return data["result"]["alternatives"][0]["message"]["text"].strip()
        except requests.exceptions.RequestException as e:
            print(f"[!] YandexGPT API error: {e}", file=sys.stderr)
            if hasattr(e, "response") and e.response is not None:
                print(f"    Response: {e.response.text[:500]}", file=sys.stderr)
            raise

    def completion_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
    ) -> list | dict:
        """
        Запрос с парсингом JSON из ответа.
        YandexGPT иногда оборачивает в ```json ... ```, чистим это.
        """
        raw = self.completion(system_prompt, user_prompt, temperature=temperature, max_tokens=3000)
        # Чистим markdown-обёртку если есть
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            # Убираем первую строку ```json или ```
            lines = lines[1:]
            # Убираем последнюю ```
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            raw = "\n".join(lines).strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"[!] Невалидный JSON от YandexGPT: {e}", file=sys.stderr)
            print(f"    Сырой ответ:\n{raw[:1000]}", file=sys.stderr)
            raise


if __name__ == "__main__":
    # Smoke test
    gpt = YandexGPT()
    print(f"Модель: {gpt.model}, folder: {gpt.folder_id[:10]}...")
    answer = gpt.completion(
        system_prompt="Ты лаконичный помощник.",
        user_prompt="Скажи 'работает' одним словом.",
        max_tokens=10,
    )
    print(f"Ответ: {answer}")
