"""Модели БД для консьержа и off-market."""

from datetime import datetime

from sqlalchemy import JSON, Float, ForeignKey, Integer, String, Text, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class Property(Base):
    """Объект недвижимости (mock-данные Whitewill)."""

    __tablename__ = "properties"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    title_en: Mapped[str] = mapped_column(String(255), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    description_en: Mapped[str] = mapped_column(Text, default="")
    district: Mapped[str] = mapped_column(String(100), index=True)  # Хамовники, Остоженка...
    address: Mapped[str] = mapped_column(String(500))
    price_rub: Mapped[int] = mapped_column(Integer)  # в рублях
    area_sqm: Mapped[float] = mapped_column(Float)
    rooms: Mapped[int] = mapped_column(Integer)
    floor: Mapped[int] = mapped_column(Integer)
    total_floors: Mapped[int] = mapped_column(Integer)
    property_type: Mapped[str] = mapped_column(String(50))  # apartment, penthouse, townhouse
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False)
    is_luxury: Mapped[bool] = mapped_column(Boolean, default=False)
    features: Mapped[dict] = mapped_column(JSON, default=dict)  # {"view": "river", "parking": true}
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Вектор для RAG (256-мерный)
    embedding: Mapped[list] = mapped_column(JSON, default=list)


class Dialog(Base):
    """Диалог клиента с консьержем."""

    __tablename__ = "dialogs"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True, unique=True)
    source: Mapped[str] = mapped_column(String(20), default="web")  # web / telegram / whatsapp
    client_lang: Mapped[str] = mapped_column(String(5), default="ru")
    status: Mapped[str] = mapped_column(String(20), default="active")  # active / qualified / dropped
    intent: Mapped[str] = mapped_column(String(50), default="")  # buy / rent / invest
    budget: Mapped[str] = mapped_column(String(50), default="")
    district: Mapped[str] = mapped_column(String(100), default="")
    timeline: Mapped[str] = mapped_column(String(50), default="")
    payment: Mapped[str] = mapped_column(String(50), default="")
    score: Mapped[float] = mapped_column(Float, default=0.0)
    is_qualified: Mapped[bool] = mapped_column(Boolean, default=False)
    crm_lead_id: Mapped[str] = mapped_column(String(100), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    messages: Mapped[list["Message"]] = relationship(
        back_populates="dialog", cascade="all, delete-orphan"
    )


class Message(Base):
    """Одно сообщение в диалоге."""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    dialog_id: Mapped[int] = mapped_column(ForeignKey("dialogs.id"))
    role: Mapped[str] = mapped_column(String(20))  # user / assistant / system
    content: Mapped[str] = mapped_column(Text)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    dialog: Mapped[Dialog] = relationship(back_populates="messages")


class OffMarketSignal(Base):
    """Off-market сигнал по кадастровому номеру."""

    __tablename__ = "off_market_signals"

    id: Mapped[int] = mapped_column(primary_key=True)
    cadastral_number: Mapped[str] = mapped_column(String(50), index=True, unique=True)
    address: Mapped[str] = mapped_column(String(500))
    district: Mapped[str] = mapped_column(String(100), index=True)
    estimated_value_rub: Mapped[int] = mapped_column(Integer, default=0)

    # Сигналы
    egrn_change_type: Mapped[str] = mapped_column(String(50), default="")  # sale, inheritance, gift
    egrn_change_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    has_encumbrance: Mapped[bool] = mapped_column(Boolean, default=False)
    encumbrance_type: Mapped[str] = mapped_column(String(50), default="")
    fssp_amount: Mapped[int] = mapped_column(Integer, default=0)
    has_inheritance: Mapped[bool] = mapped_column(Boolean, default=False)
    is_bankruptcy: Mapped[bool] = mapped_column(Boolean, default=False)

    # Скоринг
    score: Mapped[float] = mapped_column(Float, default=0.0, index=True)
    signals: Mapped[list] = mapped_column(JSON, default=list)
    priority: Mapped[str] = mapped_column(String(20), default="low")  # low / medium / high

    # Действие
    broker_telegram_id: Mapped[str] = mapped_column(String(50), default="")
    status: Mapped[str] = mapped_column(String(20), default="new")  # new / sent / taken / dismissed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    notified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
