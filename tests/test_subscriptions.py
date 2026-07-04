from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Subscription

HOOK_URL = "https://hooks.example.com/notify"


def create_body(**overrides: Any) -> dict[str, Any]:
    return {"url": HOOK_URL, **overrides}


class TestCreateSubscription:
    def test_create_and_persist(self, client: TestClient, db_session: Session) -> None:
        rules = {
            "type": "order.created",
            "payload": [{"path": "amount", "op": "gt", "value": 100}],
        }
        response = client.post("/api/v1/subscriptions", json=create_body(rules=rules))

        assert response.status_code == 201
        body = response.json()
        assert body["url"] == HOOK_URL
        assert body["active"] is True
        assert body["rules"]["type"] == "order.created"
        assert body["rules"]["payload"][0] == {"path": "amount", "op": "gt", "value": 100}

        stored = db_session.get(Subscription, body["id"])
        assert stored is not None
        assert stored.url == HOOK_URL

    def test_rules_are_optional(self, client: TestClient) -> None:
        response = client.post("/api/v1/subscriptions", json=create_body())
        assert response.status_code == 201
        assert response.json()["rules"] == {"type": None, "source": None, "payload": []}

    @pytest.mark.parametrize(
        ("body", "reason"),
        [
            ({}, "url is required"),
            ({"url": "not-a-url"}, "url must parse"),
            ({"url": "ftp://example.com/hook"}, "url must be http(s)"),
            ({"url": HOOK_URL, "extra": 1}, "unknown fields rejected"),
        ],
    )
    def test_invalid_bodies_get_422(
        self, client: TestClient, body: dict[str, Any], reason: str
    ) -> None:
        response = client.post("/api/v1/subscriptions", json=body)
        assert response.status_code == 422, reason
        assert "detail" in response.json()

    @pytest.mark.parametrize(
        ("rules", "reason"),
        [
            ({"type": ""}, "blank type filter"),
            ({"nope": 1}, "unknown rule fields rejected"),
            ({"payload": {"path": "a", "op": "eq"}}, "payload rules must be a list"),
            ({"payload": [{"op": "eq", "value": 1}]}, "condition needs a path"),
            ({"payload": [{"path": "a", "op": "matches", "value": 1}]}, "unknown op"),
            ({"payload": [{"path": "a", "op": "gt", "value": "10"}]}, "gt needs a number"),
            ({"payload": [{"path": "a", "op": "gt", "value": True}]}, "gt rejects booleans"),
            ({"payload": [{"path": "a", "op": "gt"}]}, "gt needs a value"),
            ({"payload": [{"path": "a", "op": "exists", "value": 1}]}, "exists takes no value"),
            ({"payload": [{"path": "a", "op": "eq", "value": 1, "x": 2}]}, "no unknown fields"),
        ],
    )
    def test_invalid_rules_get_422(
        self, client: TestClient, rules: dict[str, Any], reason: str
    ) -> None:
        response = client.post("/api/v1/subscriptions", json=create_body(rules=rules))
        assert response.status_code == 422, reason
        assert "detail" in response.json()


class TestListAndDelete:
    def test_list_returns_created_subscriptions(self, client: TestClient) -> None:
        first = client.post("/api/v1/subscriptions", json=create_body()).json()["id"]
        second = client.post(
            "/api/v1/subscriptions", json=create_body(url=HOOK_URL + "/2")
        ).json()["id"]

        listed = client.get("/api/v1/subscriptions").json()
        assert [sub["id"] for sub in listed] == [first, second]

    def test_delete_removes_from_list(self, client: TestClient) -> None:
        sub_id = client.post("/api/v1/subscriptions", json=create_body()).json()["id"]

        assert client.delete(f"/api/v1/subscriptions/{sub_id}").status_code == 204
        assert client.get("/api/v1/subscriptions").json() == []

    def test_delete_is_not_idempotent_404_on_replay(self, client: TestClient) -> None:
        sub_id = client.post("/api/v1/subscriptions", json=create_body()).json()["id"]
        client.delete(f"/api/v1/subscriptions/{sub_id}")

        assert client.delete(f"/api/v1/subscriptions/{sub_id}").status_code == 404

    def test_delete_unknown_returns_404(self, client: TestClient) -> None:
        assert client.delete("/api/v1/subscriptions/nope").status_code == 404
