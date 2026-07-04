import json
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Delivery, DeliveryAttempt, DeliveryState
from app.services.delivery_worker import process_due_deliveries_once

HOOK_URL = "https://hooks.example.com/notify"


def create_sub(client: TestClient, rules: dict[str, Any] | None = None, url: str = HOOK_URL) -> str:
    body: dict[str, Any] = {"url": url}
    if rules is not None:
        body["rules"] = rules
    response = client.post("/api/v1/subscriptions", json=body)
    assert response.status_code == 201
    return response.json()["id"]


def post_event(client: TestClient, **overrides: Any) -> str:
    body: dict[str, Any] = {
        "type": "order.created",
        "source": "checkout",
        "payload": {"amount": 250},
        **overrides,
    }
    response = client.post("/api/v1/events", json=body)
    assert response.status_code == 202
    return response.json()["event_id"]


def tick(session: Session, now: datetime | None = None) -> int:
    with httpx.Client() as http:
        return process_due_deliveries_once(session, http, now=now)


def utcnow() -> datetime:
    """Naive UTC, matching the app's storage convention."""
    return datetime.now(UTC).replace(tzinfo=None)


def far_future() -> datetime:
    return utcnow() + timedelta(hours=1)


class TestFanoutMatching:
    def test_matching_event_enqueues_pending_delivery(
        self, client: TestClient, db_session: Session
    ) -> None:
        sub_id = create_sub(client, rules={"type": "order.created"})
        event_id = post_event(client)

        delivery = db_session.scalars(select(Delivery)).one()
        assert delivery.subscription_id == sub_id
        assert delivery.event_id == event_id
        assert delivery.state == DeliveryState.PENDING
        assert delivery.attempt_count == 0

    def test_only_matching_subscriptions_get_deliveries(
        self, client: TestClient, db_session: Session
    ) -> None:
        match_all = create_sub(client)
        create_sub(client, rules={"type": "user.signup"}, url=HOOK_URL + "/other")
        post_event(client)

        deliveries = db_session.scalars(select(Delivery)).all()
        assert [d.subscription_id for d in deliveries] == [match_all]

    def test_payload_conditions_filter_events(
        self, client: TestClient, db_session: Session
    ) -> None:
        create_sub(client, rules={"payload": [{"path": "amount", "op": "gt", "value": 100}]})
        post_event(client, id="evt-big", payload={"amount": 250})
        post_event(client, id="evt-small", payload={"amount": 50})

        deliveries = db_session.scalars(select(Delivery)).all()
        assert [d.event_id for d in deliveries] == ["evt-big"]

    def test_deleted_subscription_gets_no_deliveries(
        self, client: TestClient, db_session: Session
    ) -> None:
        sub_id = create_sub(client)
        client.delete(f"/api/v1/subscriptions/{sub_id}")
        post_event(client)

        assert db_session.scalars(select(Delivery)).all() == []


class TestDeliveryWorker:
    def test_successful_delivery(self, client: TestClient, db_session: Session) -> None:
        create_sub(client)
        event_id = post_event(client)

        with respx.mock:
            route = respx.post(HOOK_URL).mock(return_value=httpx.Response(200))
            assert tick(db_session) == 1

        delivery = db_session.scalars(select(Delivery)).one()
        assert delivery.state == DeliveryState.DELIVERED
        assert delivery.attempt_count == 1

        sent = route.calls.last.request
        assert json.loads(sent.content) == {
            "event_id": event_id,
            "type": "order.created",
            "source": "checkout",
            "payload": {"amount": 250},
        }
        assert sent.headers["X-Delivery-Id"] == delivery.id
        assert sent.headers["X-Event-Id"] == event_id

        attempt = db_session.scalars(select(DeliveryAttempt)).one()
        assert attempt.http_status == 200
        assert attempt.error is None

    def test_non_2xx_schedules_backoff_retry_then_succeeds(
        self, client: TestClient, db_session: Session
    ) -> None:
        create_sub(client)
        post_event(client)
        started = utcnow()

        with respx.mock:
            respx.post(HOOK_URL).mock(
                side_effect=[httpx.Response(500), httpx.Response(200)]
            )
            assert tick(db_session) == 1

            delivery = db_session.scalars(select(Delivery)).one()
            assert delivery.state == DeliveryState.PENDING
            assert delivery.attempt_count == 1
            assert delivery.next_attempt_at > started

            # not due yet: nothing is retried before the backoff elapses
            assert tick(db_session) == 0

            assert tick(db_session, now=far_future()) == 1

        assert delivery.state == DeliveryState.DELIVERED
        statuses = [a.http_status for a in db_session.scalars(select(DeliveryAttempt))]
        assert statuses == [500, 200]

    def test_timeout_is_recorded_as_failed_attempt(
        self, client: TestClient, db_session: Session
    ) -> None:
        create_sub(client)
        post_event(client)

        with respx.mock:
            respx.post(HOOK_URL).mock(side_effect=httpx.ConnectTimeout("connect timed out"))
            assert tick(db_session) == 1

        delivery = db_session.scalars(select(Delivery)).one()
        assert delivery.state == DeliveryState.PENDING

        attempt = db_session.scalars(select(DeliveryAttempt)).one()
        assert attempt.http_status is None
        assert "ConnectTimeout" in (attempt.error or "")

    def test_permanent_failure_dead_letters_after_max_attempts(
        self, client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MAX_DELIVERY_ATTEMPTS", "2")
        get_settings.cache_clear()

        create_sub(client)
        post_event(client)

        with respx.mock:
            respx.post(HOOK_URL).mock(return_value=httpx.Response(503))
            assert tick(db_session) == 1
            assert tick(db_session, now=far_future()) == 1
            # dead-lettered: no further attempts, even long after
            assert tick(db_session, now=far_future()) == 0

        delivery = db_session.scalars(select(Delivery)).one()
        assert delivery.state == DeliveryState.FAILED
        assert delivery.attempt_count == 2
        attempts = db_session.scalars(select(DeliveryAttempt)).all()
        assert [a.http_status for a in attempts] == [503, 503]

    def test_tick_with_nothing_due_processes_nothing(
        self, client: TestClient, db_session: Session
    ) -> None:
        assert tick(db_session) == 0
