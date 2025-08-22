import logging
import uuid
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from .api import router
from .db import init_db, seed_if_empty
from .logger_config import setup_logging

setup_logging()
log = logging.getLogger("app")

STATUS_TO_CODE = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    415: "UNSUPPORTED_MEDIA_TYPE",
    422: "UNPROCESSABLE_ENTITY",
}
def code_for(status: int) -> str:
    return STATUS_TO_CODE.get(status, f"HTTP_{status}")

def error_response(status: int, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code_for(status), "message": message}},
    )

class EnforceJSONMiddleware(BaseHTTPMiddleware):
    """Rejects non-JSON bodies for mutating methods to keep API contract strict."""
    async def dispatch(self, request: Request, call_next):
        if request.method in {"POST", "PUT", "PATCH"}:
            ct = request.headers.get("content-type", "").split(";")[0].strip().lower()
            if ct != "application/json":
                log.warning("Unsupported media type: %s %s", request.method, request.url.path)
                return error_response(415, "Content-Type must be application/json")
        return await call_next(request)

class RequestIDMiddleware(BaseHTTPMiddleware):
    """Adds a stable request id (from header or generated) into logs and response headers."""
    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("x-request-id") or str(uuid.uuid4())
        old_factory = logging.getLogRecordFactory()
        def record_factory(*args, **kwargs):
            rec = old_factory(*args, **kwargs)
            rec.request_id = rid
            return rec
        logging.setLogRecordFactory(record_factory)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = rid
            return response
        finally:
            logging.setLogRecordFactory(old_factory)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown hooks (preferred over deprecated on_event)."""
    init_db()
    if os.getenv("ATM_DISABLE_SEED") != "1":
        seed_if_empty()
    log.info("🚀 ATM API started")
    try:
        yield
    finally:
        log.info("🛑 ATM API stopped")

def create_app() -> FastAPI:
    app = FastAPI(title="ATM System", lifespan=lifespan)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(EnforceJSONMiddleware)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_: Request, exc: RequestValidationError):
        # Summarize first validation error for a compact, user-friendly message.
        msg = "Invalid request."
        try:
            err = exc.errors()[0]
            loc = ".".join(str(x) for x in err.get("loc", []))
            detail = err.get("msg", "")
            msg = f"{loc}: {detail}" if loc else (detail or msg)
        except Exception:
            pass
        return error_response(422, msg)

    @app.exception_handler(StarletteHTTPException)
    async def http_exc_handler(_: Request, exc: StarletteHTTPException):
        detail = exc.detail if isinstance(exc.detail, str) else code_for(exc.status_code).replace("_", " ").title()
        return error_response(exc.status_code, str(detail))

    app.include_router(router)
    return app

app = create_app()