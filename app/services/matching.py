from typing import Any

from sqlalchemy.orm import Session

from app.db.models import Event, Subscription
from app.repositories.subscriptions import list_active

_MISSING = object()


def _resolve_path(payload: dict[str, Any], path: str) -> Any:
    """Walk a dot-separated path into the payload; _MISSING if any hop is absent."""
    current: Any = payload
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return _MISSING
        current = current[part]
    return current


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _condition_holds(condition: dict[str, Any], payload: dict[str, Any]) -> bool:
    actual = _resolve_path(payload, condition["path"])
    op = condition["op"]
    if op == "exists":
        return actual is not _MISSING
    if actual is _MISSING:
        # a missing path never matches, including for neq (documented in README)
        return False
    expected = condition.get("value")
    if op == "eq":
        return actual == expected
    if op == "neq":
        return actual != expected
    if not _is_number(actual):
        return False
    return {
        "gt": actual > expected,
        "gte": actual >= expected,
        "lt": actual < expected,
        "lte": actual <= expected,
    }[op]


def rules_match(rules: dict[str, Any], event: Event) -> bool:
    """Evaluate stored filter rules (FilterRules-shaped dict) against an event."""
    if rules.get("type") is not None and rules["type"] != event.type:
        return False
    if rules.get("source") is not None and rules["source"] != event.source:
        return False
    return all(_condition_holds(c, event.payload) for c in rules.get("payload", []))


def match_subscriptions(session: Session, event: Event) -> list[Subscription]:
    """Active subscriptions whose rules match `event`.

    Called inside the ingestion transaction so the event and its delivery rows
    commit atomically. Evaluates in Python over all active subscriptions —
    fine at this scale; an indexed type/source pre-filter is the first
    optimization if subscription counts grow.
    """
    return [sub for sub in list_active(session) if rules_match(sub.rules, event)]
