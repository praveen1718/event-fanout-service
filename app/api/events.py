from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.engine import get_session
from app.models.schemas import EventAccepted, EventIn
from app.services.ingestion import ingest_event

router = APIRouter(prefix="/events", tags=["events"])


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=EventAccepted)
def create_event(
    event_in: EventIn, session: Annotated[Session, Depends(get_session)]
) -> EventAccepted:
    """Accept an event for fanout. 202 is only returned after the event is durable."""
    return ingest_event(session, event_in)
