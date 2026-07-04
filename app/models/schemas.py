from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


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


ConditionOp = Literal["eq", "neq", "gt", "gte", "lt", "lte", "exists"]
ORDERING_OPS = {"gt", "gte", "lt", "lte"}


class PayloadCondition(BaseModel):
    """One payload filter condition; syntax documented in the README."""

    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1, max_length=512)
    op: ConditionOp
    value: Any = None

    @model_validator(mode="after")
    def _validate_value(self) -> "PayloadCondition":
        if self.op == "exists" and self.value is not None:
            raise ValueError("'exists' does not take a value")
        if self.op in ORDERING_OPS and (
            isinstance(self.value, bool) or not isinstance(self.value, int | float)
        ):
            raise ValueError(f"'{self.op}' requires a numeric value")
        return self


class FilterRules(BaseModel):
    """Omitted type/source match any event; payload conditions are ANDed."""

    model_config = ConfigDict(extra="forbid")

    type: str | None = Field(default=None, min_length=1, max_length=256)
    source: str | None = Field(default=None, min_length=1, max_length=256)
    payload: list[PayloadCondition] = Field(default_factory=list, max_length=32)


class SubscriptionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: HttpUrl
    rules: FilterRules = Field(default_factory=FilterRules)


class SubscriptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    url: str
    rules: FilterRules
    active: bool
    created_at: datetime


class DeliveryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    event_id: str
    subscription_id: str
    state: Literal["pending", "delivered", "failed"]
    attempt_count: int
    next_attempt_at: datetime
    created_at: datetime
    updated_at: datetime


class DeliveryAttemptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    attempted_at: datetime
    http_status: int | None
    error: str | None


class DeliveryAudit(BaseModel):
    """Full audit trail for one delivery: final state plus every attempt."""

    delivery: DeliveryOut
    attempts: list[DeliveryAttemptOut]
