from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.engine import get_session
from app.models.schemas import SubscriptionIn, SubscriptionOut
from app.services.subscriptions import create_subscription, delete_subscription, list_subscriptions

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])

SessionDep = Annotated[Session, Depends(get_session)]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=SubscriptionOut)
def create(sub_in: SubscriptionIn, session: SessionDep) -> SubscriptionOut:
    """Register a webhook URL with filter rules. Invalid rules are rejected with 422."""
    return create_subscription(session, sub_in)


@router.get("", response_model=list[SubscriptionOut])
def list_all(session: SessionDep) -> list[SubscriptionOut]:
    return list_subscriptions(session)


@router.delete("/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(subscription_id: str, session: SessionDep) -> None:
    if not delete_subscription(session, subscription_id):
        raise HTTPException(status_code=404, detail="subscription not found")
