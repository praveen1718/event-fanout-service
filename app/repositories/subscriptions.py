from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Subscription


def insert_subscription(session: Session, *, url: str, rules: dict[str, Any]) -> Subscription:
    subscription = Subscription(url=url, rules=rules)
    session.add(subscription)
    session.flush()
    return subscription


def list_active(session: Session) -> list[Subscription]:
    stmt = select(Subscription).where(Subscription.active).order_by(Subscription.created_at)
    return list(session.scalars(stmt))


def deactivate(session: Session, subscription_id: str) -> bool:
    """Soft-delete so past deliveries keep a resolvable subscription for audit."""
    subscription = session.get(Subscription, subscription_id)
    if subscription is None or not subscription.active:
        return False
    subscription.active = False
    return True
