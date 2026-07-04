import logging
import uuid

from sqlalchemy.orm import Session

from app.core.logging import log_extra
from app.db.models import Delivery
from app.models.schemas import EventAccepted, EventIn
from app.repositories.events import insert_event
from app.services.matching import match_subscriptions

logger = logging.getLogger("app.ingestion")


def ingest_event(session: Session, event_in: EventIn) -> EventAccepted:
    """Durably accept an event.

    Invariant: the event row and one pending Delivery row per matching
    subscription commit in a single transaction — an event can never be
    accepted without its fanout being enqueued. Duplicate ids are detected via
    the primary-key constraint and acknowledged without re-enqueueing
    (at-least-once delivery, dedupe on event id is the subscriber's job).
    """
    event_id = event_in.id or uuid.uuid4().hex
    event, duplicate = insert_event(
        session,
        event_id=event_id,
        type_=event_in.type,
        source=event_in.source,
        payload=event_in.payload,
    )
    if not duplicate:
        matched = match_subscriptions(session, event)
        session.add_all(
            Delivery(event_id=event.id, subscription_id=sub.id) for sub in matched
        )
        session.commit()
        logger.info(
            "event accepted",
            extra=log_extra(event_id=event.id, type=event.type, deliveries=len(matched)),
        )
    else:
        session.rollback()
        logger.info("duplicate event acknowledged", extra=log_extra(event_id=event.id))
    return EventAccepted(event_id=event.id, duplicate=duplicate)
