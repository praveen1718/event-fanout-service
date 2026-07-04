import enum
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    # Naive UTC everywhere: the sqlite driver drops tzinfo on write, so storing
    # aware values would read back naive and poison comparisons. All stored
    # timestamps are UTC by convention.
    return datetime.now(UTC).replace(tzinfo=None)


def _new_id() -> str:
    return uuid.uuid4().hex


class Base(DeclarativeBase):
    pass


class Event(Base):
    """An accepted event. The primary key doubles as the idempotency key."""

    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    type: Mapped[str] = mapped_column(String(256), index=True)
    source: Mapped[str] = mapped_column(String(256), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=_utcnow)


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_new_id)
    url: Mapped[str] = mapped_column(String(2048))
    # Declarative filter rules; syntax documented in the README.
    rules: Mapped[dict[str, Any]] = mapped_column(JSON)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=_utcnow)


class DeliveryState(enum.StrEnum):
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"


class Delivery(Base):
    """One row per (event, matching subscription); the durable fanout queue."""

    __tablename__ = "deliveries"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_new_id)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), index=True)
    subscription_id: Mapped[str] = mapped_column(ForeignKey("subscriptions.id"), index=True)
    state: Mapped[DeliveryState] = mapped_column(
        Enum(DeliveryState, native_enum=False), default=DeliveryState.PENDING, index=True
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(), default=_utcnow, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(), default=_utcnow, onupdate=_utcnow
    )


class DeliveryAttempt(Base):
    """Append-only audit record: one row per webhook attempt, success or not."""

    __tablename__ = "delivery_attempts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_new_id)
    delivery_id: Mapped[str] = mapped_column(ForeignKey("deliveries.id"), index=True)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(), default=_utcnow)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
