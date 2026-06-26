"""RAG по mock-базе объектов Whitewill.

Используется простой vector search + metadata filter.
В production — заменить на Yandex Cloud Vector Search (pgvector или специализированный).
"""

import json
import logging
from pathlib import Path

import numpy as np

from ..shared.llm import get_llm
from .schemas import PropertyMatch

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent / "data"


class RAGIndex:
    """In-memory индекс объектов с косинусным сходством."""

    def __init__(self) -> None:
        self.properties: list[dict] = []
        self.embeddings: np.ndarray | None = None
        self._loaded = False

    async def load(self) -> None:
        """Загрузить объекты и эмбеддинги из файла + базы."""

        if self._loaded:
            return

        # Загружаем mock-объекты
        props_path = DATA_DIR / "properties.json"
        if not props_path.exists():
            logger.warning("properties.json not found, RAG will be empty")
            return

        with open(props_path, encoding="utf-8") as f:
            self.properties = json.load(f)

        if not self.properties:
            return

        # Получаем эмбеддинги
        llm = get_llm()
        texts = [
            f"{p['title']}. {p['district']}. {p.get('description', '')}" for p in self.properties
        ]

        vectors = await llm.embed(texts)
        self.embeddings = np.array(vectors, dtype=np.float32)

        # Нормализуем для косинусного сходства
        norms = np.linalg.norm(self.embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1
        self.embeddings = self.embeddings / norms

        self._loaded = True
        logger.info(f"RAG loaded: {len(self.properties)} properties, dim={self.embeddings.shape[1]}")

    # Список районов, которые точно НЕ в московской базе — для них district-фильтр пропускаем
    _INTERNATIONAL_DISTRICTS = {"dubai", "abu dhabi", "abu-dabi", "abu dabi", "london", "milan", "paris", "new york", "monaco"}

    async def search(
        self,
        query: str,
        top_k: int = 3,
        budget_max: int | None = None,
        budget_min: int | None = None,
        district: str | None = None,
    ) -> list[PropertyMatch]:
        """Семантический поиск + опциональная фильтрация по метаданным.

        Если в базе ничего не нашлось (например, район Dubai, которого нет в моковой базе)
        — возвращаем fallback: топ объектов по бюджету без district-фильтра.
        """

        if not self._loaded:
            await self.load()

        if not self.properties or self.embeddings is None:
            return []

        llm = get_llm()
        query_vec = (await llm.embed([query]))[0]
        query_vec = np.array(query_vec, dtype=np.float32)
        norm = np.linalg.norm(query_vec)
        if norm > 0:
            query_vec = query_vec / norm

        # Косинусное сходство
        scores = self.embeddings @ query_vec

        # Если район международный (Dubai и т.п.) — НЕ подбираем из московской базы,
        # пусть бот выдаст handoff-сообщение со ссылкой на каталог
        is_international = district and district.lower() in self._INTERNATIONAL_DISTRICTS
        if is_international:
            return []

        # Фильтрация по метаданным
        candidates = []
        for idx, score in enumerate(scores):
            p = self.properties[idx]

            if budget_max is not None and p["price_rub"] > budget_max:
                continue
            if budget_min is not None and p["price_rub"] < budget_min:
                continue
            if not is_international and district and district.lower() not in p["district"].lower():
                continue

            candidates.append((idx, float(score)))

        # Сортировка по score
        candidates.sort(key=lambda x: x[1], reverse=True)
        candidates = candidates[:top_k]

        # Если ничего не нашлось — возвращаем пустой результат.
        # Лучше показать "брокер подберёт лично", чем выдавать объекты вне бюджета/района.
        # Раньше здесь был fallback на топ без фильтров — это путало клиентов
        # (показывали объекты за 850 млн при бюджете "до 100 млн").

        results = []
        for idx, score in candidates:
            p = self.properties[idx]
            results.append(
                PropertyMatch(
                    id=p.get("id", idx),
                    title=p.get("title", ""),
                    title_en=p.get("title_en", ""),
                    district=p.get("district", ""),
                    price_rub=p.get("price_rub", 0),
                    area_sqm=p.get("area_sqm", 0),
                    rooms=p.get("rooms", 0),
                    score=score,
                )
            )

        return results


# Singleton
_rag_instance: RAGIndex | None = None


def get_rag() -> RAGIndex:
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = RAGIndex()
    return _rag_instance
