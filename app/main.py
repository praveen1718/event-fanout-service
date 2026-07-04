import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import APIRouter, FastAPI

from app.api import deliveries, events, subscriptions
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.middleware import RequestIdMiddleware
from app.db.engine import get_engine
from app.db.models import Base
from app.models.schemas import HealthResponse
from app.services.delivery_worker import run_loop


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # No Alembic for this exercise; see README "what we sacrifice for simplicity".
    Base.metadata.create_all(get_engine())
    worker_task = asyncio.create_task(run_loop()) if get_settings().worker_enabled else None
    yield
    if worker_task is not None:
        worker_task.cancel()
        with suppress(asyncio.CancelledError):
            await worker_task


def create_app() -> FastAPI:
    configure_logging(get_settings().log_level)
    app = FastAPI(title="Event Fanout Service", version="0.1.0", lifespan=lifespan)
    app.add_middleware(RequestIdMiddleware)

    @app.get("/health", response_model=HealthResponse, tags=["ops"])
    def health() -> HealthResponse:
        """Liveness probe: fast and dependency-free (no DB access)."""
        return HealthResponse()

    api_v1 = APIRouter(prefix="/api/v1")
    api_v1.include_router(events.router)
    api_v1.include_router(subscriptions.router)
    api_v1.include_router(deliveries.router)
    app.include_router(api_v1)
    return app


app = create_app()
