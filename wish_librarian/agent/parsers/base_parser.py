"""
Базовый класс для всех парсеров.

Содержит общую логику HTTP-запросов с ретраями, задержкой и кэшированием.
"""
from __future__ import annotations

import hashlib
import re
import time
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from agent.config import get_settings
from agent.utils.logger import get_logger
from agent.models import BookInfo


logger = get_logger()


class FetchError(Exception):
    """Не удалось получить страницу."""


class ParseError(Exception):
    """Не удалось распарсить страницу."""


class BaseParser:
    """Базовый класс парсера."""

    name: str = "base"

    def __init__(self, session: Optional[requests.Session] = None):
        self.settings = get_settings()
        self.session = session or self._build_session()

    # ── HTTP ────────────────────────────────────────────────────
    def _build_session(self) -> requests.Session:
        s = requests.Session()
        s.headers.update(
            {
                "User-Agent": self.settings.user_agent,
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;q=0.9,"
                    "image/webp,*/*;q=0.8"
                ),
                "Accept-Language": "ru,en;q=0.9",
            }
        )
        # Отключаем чтение HTTP(S)_PROXY/ALL_PROXY из окружения: socks4:// от
        # VPN-клиента ломает requests без зависимости PySocks.
        s.trust_env = False
        retries = Retry(
            total=self.settings.max_retries,
            backoff_factor=0.6,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(["GET", "HEAD"]),
        )
        s.mount("https://", HTTPAdapter(max_retries=retries))
        s.mount("http://", HTTPAdapter(max_retries=retries))
        return s

    def fetch(
        self,
        url: str,
        *,
        use_cache: bool = True,
        cache_subdir: str = "http",
    ) -> str:
        """
        Скачать HTML-страницу с кэшированием.

        Кэш хранится в cache_dir/{cache_subdir}/{md5(url)}.html

        Поддерживает также `file://` URL для офлайн-тестирования
        (на случай, когда koob.ru недоступен, но есть локальный HTML).
        """
        # Поддержка file:// для офлайн-тестов
        if url.startswith("file://"):
            local_path = Path(url[len("file://"):].lstrip("/"))
            if not local_path.exists():
                # Windows: file:///C:/path → C:/path
                win_match = re.match(r"file:///([A-Za-z]:.*)", url)
                if win_match:
                    local_path = Path(win_match.group(1))
            if not local_path.exists():
                raise FetchError(f"Локальный файл не найден: {url}")
            logger.debug("📁 Чтение локального файла: {}", local_path)
            raw = local_path.read_bytes()
            return self._decode_bytes(raw)

        cache_dir: Path = self.settings.cache_dir / cache_subdir
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / f"{hashlib.md5(url.encode()).hexdigest()}.html"

        if use_cache and cache_file.exists():
            logger.debug("📦 Кэш найден для {}", url)
            raw = cache_file.read_bytes()
            return self._decode_bytes(raw)

        logger.debug("🌐 GET {}", url)
        time.sleep(self.settings.request_delay)

        try:
            resp = self.session.get(
                url,
                timeout=self.settings.request_timeout,
                allow_redirects=True,
            )
        except requests.RequestException as e:
            raise FetchError(f"Ошибка запроса {url}: {e}") from e

        if resp.status_code != 200:
            raise FetchError(
                f"HTTP {resp.status_code} для {url} (попыток: {self.settings.max_retries})"
            )

        # Скачиваем сырые байты и сами определяем кодировку — некоторые
        # сайты (например, www.koob.ru) отдают windows-1251, а requests
        # угадывает её как ISO-8859-1, из-за чего русский текст портится.
        raw = resp.content
        html = self._decode_bytes(raw)

        if use_cache:
            try:
                cache_file.write_bytes(raw)
            except OSError as e:
                logger.warning("Не удалось сохранить кэш {}: {}", cache_file, e)

        return html

    # ── Кодировка ────────────────────────────────────────────────
    @staticmethod
    def _detect_encoding(raw: bytes) -> str:
        """
        Пытаемся определить кодировку страницы.

        Приоритет:
          1. Content-Type из HTTP-ответа / HTTP-equiv meta-тега
             (самый надёжный источник).
          2. Эвристика: если в теле есть характерные кириллические байты
             и при этом текст НЕ декодируется как utf-8 — пробуем cp1251.
          3. fallback → utf-8.
        """
        head = raw[:4096].decode("ascii", errors="ignore").lower()
        if "charset=windows-1251" in head or "charset=cp1251" in head:
            return "cp1251"
        if "charset=utf-8" in head or "charset=utf8" in head:
            return "utf-8"
        # Попробуем utf-8
        try:
            raw.decode("utf-8")
            return "utf-8"
        except UnicodeDecodeError:
            # Типичные русские байты в cp1251 (0xC0–0xFF) — основной признак
            if any(b in raw for b in (0xC0, 0xC1, 0xD0, 0xD1, 0xE0, 0xE1, 0xF0, 0xF1)):
                return "cp1251"
            return "cp1251"  # безопасный fallback для русскоязычных сайтов

    @classmethod
    def _decode_bytes(cls, raw: bytes) -> str:
        """Определить кодировку и вернуть декодированный текст."""
        enc = cls._detect_encoding(raw)
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            return raw.decode("utf-8", errors="ignore")

    def parse_soup(self, html: str) -> BeautifulSoup:
        # v1: fallback на html.parser если lxml недоступен (на этой машине lxml не установлен)
        try:
            return BeautifulSoup(html, "lxml")
        except Exception:
            return BeautifulSoup(html, "html.parser")

    # ── Скачивание файлов ────────────────────────────────────────
    def download_file(self, url: str, dest: Path) -> bool:
        """Скачать файл (например, обложку)."""
        try:
            resp = self.session.get(
                url, timeout=self.settings.request_timeout, stream=True
            )
            resp.raise_for_status()
            dest.parent.mkdir(parents=True, exist_ok=True)
            with dest.open("wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            logger.info("🖼  Скачано: {} → {}", url, dest)
            return True
        except Exception as e:
            logger.warning("Не удалось скачать {}: {}", url, e)
            return False

    # ── Абстрактный метод ────────────────────────────────────────
    def parse(self, url: str, **kwargs) -> BookInfo:
        """
        Главный метод парсинга. По умолчанию бросает NotImplementedError.

        Конкретные парсеры могут переопределять его (например, KoobParser)
        или добавлять свои публичные методы (ScientificParser.search,
        ReviewsParser.search), наследуя дефолтную заглушку.
        """
        raise NotImplementedError(
            f"Парсер {self.__class__.__name__} не реализует parse() — "
            "используйте его собственный публичный метод."
        )
