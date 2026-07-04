import asyncio
import logging
import random
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import log_extra
from app.db.engine import get_session_factory
from app.db.models import Delivery, DeliveryState, Event, Subscription
from app.repositories.deliveries import add_attempt, due_deliveries

logger = logging.getLogger("app.delivery_worker")

BATCH_SIZE = 100
_MAX_ERROR_LEN = 500


def _utcnow() -> datetime:
    # naive UTC, matching the storage convention in app.db.models
    return datetime.now(UTC).replace(tzinfo=None)


def _attempt_webhook(
    client: httpx.Client, subscription: Subscription, event: Event, delivery: Delivery
) -> tuple[int | None, str | None]:
    """One webhook POST. Returns (http_status, error); status is None when no response came back."""
    body = {
        "event_id": event.id,
        "type": event.type,
        "source": event.source,
        "payload": event.payload,
    }
    headers = {"X-Delivery-Id": delivery.id, "X-Event-Id": event.id}
    try:
        response = client.post(
            subscription.url,
            json=body,
            headers=headers,
            timeout=get_settings().webhook_timeout_s,
        )
    except httpx.HTTPError as exc:
        return None, f"{type(exc).__name__}: {exc}"[:_MAX_ERROR_LEN]
    return response.status_code, None


def process_due_deliveries_once(
    session: Session, client: httpx.Client, now: datetime | None = None
) -> int:
    """Single worker tick: attempt every due pending delivery. Returns how many were attempted.

    Every attempt appends an audit row. Success (2xx) marks the delivery
    `delivered`; failure schedules a retry with exponential backoff + jitter
    until max attempts, then parks it as `failed` (dead-letter). Each delivery
    commits individually so a crash mid-tick re-attempts at most the one
    in-flight delivery (at-least-once).
    """
    settings = get_settings()
    now = now or _utcnow()
    batch = due_deliveries(session, now, BATCH_SIZE)
    for delivery, subscription, event in batch:
        http_status, error = _attempt_webhook(client, subscription, event, delivery)
        add_attempt(session, delivery_id=delivery.id, http_status=http_status, error=error)
        delivery.attempt_count += 1

        if http_status is not None and 200 <= http_status < 300:
            delivery.state = DeliveryState.DELIVERED
        elif delivery.attempt_count >= settings.max_delivery_attempts:
            delivery.state = DeliveryState.FAILED
        else:
            backoff = settings.backoff_base_s * 2 ** (delivery.attempt_count - 1)
            jitter = random.uniform(0, settings.backoff_base_s)  # noqa: S311 - not crypto
            delivery.next_attempt_at = now + timedelta(seconds=backoff + jitter)

        session.commit()
        logger.info(
            "delivery attempted",
            extra=log_extra(
                delivery_id=delivery.id,
                event_id=event.id,
                subscription_id=subscription.id,
                http_status=http_status,
                error=error,
                attempt=delivery.attempt_count,
                state=delivery.state.value,
            ),
        )
    return len(batch)


async def run_loop() -> None:
    """Background poll loop started from the app lifespan; a failing tick never kills it."""
    settings = get_settings()
    logger.info("delivery worker started")
    with httpx.Client() as client:
        while True:
            try:
                session = get_session_factory()()
                try:
                    await asyncio.to_thread(process_due_deliveries_once, session, client)
                finally:
                    session.close()
            except asyncio.CancelledError:
                logger.info("delivery worker stopped")
                raise
            except Exception:
                logger.exception("delivery worker tick failed")
            await asyncio.sleep(settings.worker_poll_interval_s)
