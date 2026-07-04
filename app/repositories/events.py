from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Event


def insert_event(
    session: Session, *, event_id: str, type_: str, source: str, payload: dict[str, Any]
) -> tuple[Event, bool]:
    """Insert an event; on a duplicate id return the existing row.

    Returns (event, duplicate). Race-safe: relies on the primary-key constraint
    rather than check-then-insert, so concurrent replays cannot both insert.
    Uses a nested transaction (SAVEPOINT) so an IntegrityError does not poison
    the caller's outer transaction.
    """
    try:
        with session.begin_nested():
            event = Event(id=event_id, type=type_, source=source, payload=payload)
            session.add(event)
        return event, False
    except IntegrityError:
        existing = session.get(Event, event_id)
        if existing is None:  # pragma: no cover - only reachable via concurrent delete
            raise
        return existing, True
