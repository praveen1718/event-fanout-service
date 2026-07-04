from sqlalchemy.orm import Session

from app.db.models import Event, Subscription


def match_subscriptions(session: Session, event: Event) -> list[Subscription]:
    """Return the active subscriptions whose filter rules match `event`.

    Called inside the ingestion transaction so that the event and its
    delivery rows commit atomically.

    TODO(iteration 2 — fanout): evaluate filter rules (exact match on
    type/source + payload-path conditions per the README syntax) against all
    active subscriptions. Until subscriptions exist this correctly matches
    nothing.
    """
    _ = (session, event)
    return []
