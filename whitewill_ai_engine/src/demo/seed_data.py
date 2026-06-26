"""Скрипт для загрузки mock-данных в БД."""

import asyncio
import json
import logging
import sys
from pathlib import Path

# Добавляем корень в sys.path
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from src.shared.db import init_db, get_session
from src.shared.models import Property

logger = logging.getLogger(__name__)


async def seed_properties() -> None:
    """Загрузить mock-объекты в БД."""

    await init_db()

    props_path = ROOT / "data" / "properties.json"
    if not props_path.exists():
        logger.error(f"File not found: {props_path}")
        return

    with open(props_path, encoding="utf-8") as f:
        properties = json.load(f)

    async for session in get_session():
        # Проверяем, есть ли уже объекты
        stmt = select(Property)
        result = await session.execute(stmt)
        existing = result.scalars().all()

        if existing:
            logger.info(f"Properties already loaded: {len(existing)}")
            return

        for p in properties:
            prop = Property(
                id=p["id"],
                title=p["title"],
                title_en=p["title_en"],
                description=p.get("description", ""),
                description_en=p.get("description_en", ""),
                district=p["district"],
                address=p["address"],
                price_rub=p["price_rub"],
                area_sqm=p["area_sqm"],
                rooms=p["rooms"],
                floor=p["floor"],
                total_floors=p["total_floors"],
                property_type=p["property_type"],
                is_premium=p.get("is_premium", False),
                is_luxury=p.get("is_luxury", False),
                features=p.get("features", {}),
                embedding=[],
            )
            session.add(prop)

        await session.commit()
        logger.info(f"Seeded {len(properties)} properties")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(seed_properties())
    print("✅ Mock-данные загружены")
