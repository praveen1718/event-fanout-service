from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EventIn(BaseModel):
    """Ingestion request. `id` is the client's idempotency key; server generates one if absent."""

    model_config = ConfigDict(extra="forbid")

    id: str | None = Field(default=None, min_length=1, max_length=128)
    type: str = Field(min_length=1, max_length=256)
    source: str = Field(min_length=1, max_length=256)
    payload: dict[str, Any]


class EventAccepted(BaseModel):
    """202 response body. `duplicate=True` means this id was already accepted earlier."""

    event_id: str
    duplicate: bool = False


class HealthResponse(BaseModel):
    status: str = "ok"


# TODO(iteration 2 — subscriptions): SubscriptionIn (url + rules, validated against the
# filter-rule syntax in the README), SubscriptionOut, and rule condition models.
# TODO(iteration 2 — audit): DeliveryOut / DeliveryAttemptOut for the audit endpoints.
