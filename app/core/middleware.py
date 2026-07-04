import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.logging import log_extra, request_id_var

logger = logging.getLogger("app.request")


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Assign a request id, echo it as X-Request-ID, and log one line per request.

    Also the last line of defense for unhandled exceptions: clients get a generic
    500 JSON body (never a stack trace), while the full exception is logged with
    the request id.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        token = request_id_var.set(request_id)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("unhandled error", extra=log_extra(path=request.url.path))
            response = JSONResponse(status_code=500, content={"detail": "Internal server error"})
        finally:
            request_id_var.reset(token)
        response.headers["X-Request-ID"] = request_id
        # request_id_var is already reset, so pass it explicitly
        logger.info(
            "request completed",
            extra=log_extra(
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                status=response.status_code,
                duration_ms=round((time.perf_counter() - start) * 1000, 2),
            ),
        )
        return response
