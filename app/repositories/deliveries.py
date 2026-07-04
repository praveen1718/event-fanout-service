from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Delivery, DeliveryAttempt, DeliveryState, Event, Subscription


def due_deliveries(
    session: Session, now: datetime, limit: int
) -> list[tuple[Delivery, Subscription, Event]]:
    """Pending deliveries whose next attempt is due, oldest first."""
    stmt = (
        select(Delivery, Subscription, Event)
        .join(Subscription, Delivery.subscription_id == Subscription.id)
        .join(Event, Delivery.event_id == Event.id)
        .where(Delivery.state == DeliveryState.PENDING, Delivery.next_attempt_at <= now)
        .order_by(Delivery.next_attempt_at)
        .limit(limit)
    )
    return [tuple(row) for row in session.execute(stmt)]


def add_attempt(
    session: Session, *, delivery_id: str, http_status: int | None, error: str | None
) -> DeliveryAttempt:
    attempt = DeliveryAttempt(delivery_id=delivery_id, http_status=http_status, error=error)
    session.add(attempt)
    return attempt


def list_deliveries(
    session: Session, *, event_id: str | None = None, subscription_id: str | None = None
) -> list[Delivery]:
    stmt = select(Delivery).order_by(Delivery.created_at)
    if event_id is not None:
        stmt = stmt.where(Delivery.event_id == event_id)
    if subscription_id is not None:
        stmt = stmt.where(Delivery.subscription_id == subscription_id)
    return list(session.scalars(stmt))


def get_delivery(session: Session, delivery_id: str) -> Delivery | None:
    return session.get(Delivery, delivery_id)


def list_attempts(session: Session, delivery_id: str) -> list[DeliveryAttempt]:
    stmt = (
        select(DeliveryAttempt)
        .where(DeliveryAttempt.delivery_id == delivery_id)
        .order_by(DeliveryAttempt.attempted_at)
    )
    return list(session.scalars(stmt))
