from typing import Any

import pytest

from app.db.models import Event
from app.services.matching import rules_match

PAYLOAD: dict[str, Any] = {
    "amount": 250,
    "flag": True,
    "customer": {"tier": "gold", "visits": 3},
}


def make_event(
    type_: str = "order.created", source: str = "checkout", payload: dict[str, Any] | None = None
) -> Event:
    payload = PAYLOAD if payload is None else payload
    return Event(id="evt-x", type=type_, source=source, payload=payload)


def cond(path: str, op: str, value: Any = None) -> dict[str, Any]:
    return {"path": path, "op": op, "value": value}


@pytest.mark.parametrize(
    ("rules", "expected", "reason"),
    [
        ({}, True, "empty rules match everything"),
        ({"type": "order.created"}, True, "type exact match"),
        ({"type": "user.signup"}, False, "type mismatch"),
        ({"source": "checkout"}, True, "source exact match"),
        ({"source": "billing"}, False, "source mismatch"),
        ({"type": "order.created", "source": "billing"}, False, "all top-level fields must match"),
        ({"payload": [cond("amount", "eq", 250)]}, True, "eq on number"),
        ({"payload": [cond("amount", "eq", 999)]}, False, "eq mismatch"),
        ({"payload": [cond("customer.tier", "eq", "gold")]}, True, "eq on nested path"),
        ({"payload": [cond("customer.tier", "neq", "silver")]}, True, "neq holds"),
        ({"payload": [cond("customer.tier", "neq", "gold")]}, False, "neq fails on equal value"),
        ({"payload": [cond("amount", "gt", 100)]}, True, "gt holds"),
        ({"payload": [cond("amount", "gt", 250)]}, False, "gt strict"),
        ({"payload": [cond("amount", "gte", 250)]}, True, "gte boundary"),
        ({"payload": [cond("amount", "lt", 300)]}, True, "lt holds"),
        ({"payload": [cond("amount", "lte", 249)]}, False, "lte fails"),
        ({"payload": [cond("customer.tier", "gt", 1)]}, False, "ordering op on non-number actual"),
        ({"payload": [cond("flag", "gt", 0)]}, False, "bool is not a number"),
        ({"payload": [cond("amount", "exists")]}, True, "exists on present path"),
        ({"payload": [cond("refund", "exists")]}, False, "exists on absent path"),
        ({"payload": [cond("refund.reason", "eq", "x")]}, False, "missing path never matches"),
        ({"payload": [cond("refund", "neq", "x")]}, False, "missing path never matches, even neq"),
        ({"payload": [cond("amount.sub", "eq", 1)]}, False, "path into a scalar is missing"),
        (
            {"payload": [cond("amount", "gt", 100), cond("customer.tier", "eq", "gold")]},
            True,
            "all conditions ANDed - both hold",
        ),
        (
            {"payload": [cond("amount", "gt", 100), cond("customer.tier", "eq", "silver")]},
            False,
            "all conditions ANDed - one fails",
        ),
    ],
)
def test_rules_match(rules: dict[str, Any], expected: bool, reason: str) -> None:
    assert rules_match(rules, make_event()) is expected, reason
