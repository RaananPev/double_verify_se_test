import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import os
from .api import router
from .db import init_db, seed_if_empty# add seed_if_empty if you have it
from .logger_config import setup_logging

# ---- logging ----
setup_logging()
log = logging.getLogger("app")


# ---- status -> code mapping ----
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
    return JSONResponse(status_code=status, content={"error": {"code": code_for(status), "message": message}})

# ---- middleware ----
class EnforceJSONMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in {"POST", "PUT", "PATCH"}:
            ct = request.headers.get("content-type", "").split(";")[0].strip().lower()
            if ct != "application/json":
                log.warning("Unsupported media type: %s %s", request.method, request.url.path)
                return error_response(415, "Content-Type must be application/json")
        return await call_next(request)

class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # pick client-provided or generate one
        rid = request.headers.get("x-request-id") or str(uuid.uuid4())
        # inject into LogRecord via a temporary record factory
        old_factory = logging.getLogRecordFactory()
        def record_factory(*args, **kwargs):
            rec = old_factory(*args, **kwargs)
            # logger_config.RequestIDFilter will also default this if missing,
            # but we set it explicitly here for safety.
            rec.request_id = rid
            return rec
        logging.setLogRecordFactory(record_factory)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = rid
            return response
        finally:
            logging.setLogRecordFactory(old_factory)

def create_app() -> FastAPI:
    # DB bootstrapping
    init_db()
    if os.getenv("ATM_DISABLE_SEED") != "1":
        seed_if_empty()

    app = FastAPI(title="ATM System")

    # middleware
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(EnforceJSONMiddleware)

    # exception handlers
    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        # build concise message from first error
        msg = "Invalid request."
        try:
            err = exc.errors()[0]
            loc = ".".join(str(x) for x in err.get("loc", []))
            detail = err.get("msg", "")
            msg = f"{loc}: {detail}" if loc else (detail or msg)
        except Exception:
            pass
        log.warning("422 validation: %s %s -> %s", request.method, request.url.path, msg)
        return error_response(422, msg)

    @app.exception_handler(StarletteHTTPException)
    async def http_exc_handler(request: Request, exc: StarletteHTTPException):
        # Preserve provided detail; map status to canonical code
        detail = exc.detail if isinstance(exc.detail, str) else code_for(exc.status_code).replace("_", " ").title()
        log.warning("%s %s -> %s (%s)", request.method, request.url.path, exc.status_code, detail)
        return error_response(exc.status_code, str(detail))

    @app.on_event("startup")
    async def on_startup():
        log.info("🚀 ATM API started")

    @app.on_event("shutdown")
    async def on_shutdown():
        log.info("🛑 ATM API stopped")

    # routers
    app.include_router(router)

    return app

app = create_app()