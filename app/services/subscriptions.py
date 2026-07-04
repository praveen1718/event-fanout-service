import logging

from sqlalchemy.orm import Session

from app.core.logging import log_extra
from app.models.schemas import SubscriptionIn, SubscriptionOut
from app.repositories.subscriptions import deactivate, insert_subscription, list_active

logger = logging.getLogger("app.subscriptions")


def create_subscription(session: Session, sub_in: SubscriptionIn) -> SubscriptionOut:
    subscription = insert_subscription(
        session, url=str(sub_in.url), rules=sub_in.rules.model_dump()
    )
    session.commit()
    logger.info(
        "subscription created",
        extra=log_extra(subscription_id=subscription.id, url=subscription.url),
    )
    return SubscriptionOut.model_validate(subscription)


def list_subscriptions(session: Session) -> list[SubscriptionOut]:
    return [SubscriptionOut.model_validate(sub) for sub in list_active(session)]


def delete_subscription(session: Session, subscription_id: str) -> bool:
    """Returns False when the id is unknown (or already deleted)."""
    deleted = deactivate(session, subscription_id)
    session.commit()
    if deleted:
        logger.info("subscription deleted", extra=log_extra(subscription_id=subscription_id))
    return deleted
