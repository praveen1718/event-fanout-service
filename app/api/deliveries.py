from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.engine import get_session
from app.models.schemas import DeliveryAttemptOut, DeliveryAudit, DeliveryOut
from app.repositories.deliveries import get_delivery, list_attempts, list_deliveries

router = APIRouter(prefix="/deliveries", tags=["deliveries"])

SessionDep = Annotated[Session, Depends(get_session)]


@router.get("", response_model=list[DeliveryOut])
def query_deliveries(
    session: SessionDep, event_id: str | None = None, subscription_id: str | None = None
) -> list[DeliveryOut]:
    """Delivery state per event and/or per subscription."""
    if event_id is None and subscription_id is None:
        raise HTTPException(
            status_code=422, detail="provide event_id and/or subscription_id as query parameters"
        )
    rows = list_deliveries(session, event_id=event_id, subscription_id=subscription_id)
    return [DeliveryOut.model_validate(row) for row in rows]


@router.get("/{delivery_id}/attempts", response_model=DeliveryAudit)
def delivery_audit(delivery_id: str, session: SessionDep) -> DeliveryAudit:
    """Full audit trail: final state plus timestamp/HTTP status/error for every attempt."""
    delivery = get_delivery(session, delivery_id)
    if delivery is None:
        raise HTTPException(status_code=404, detail="delivery not found")
    attempts = list_attempts(session, delivery_id)
    return DeliveryAudit(
        delivery=DeliveryOut.model_validate(delivery),
        attempts=[DeliveryAttemptOut.model_validate(a) for a in attempts],
    )
