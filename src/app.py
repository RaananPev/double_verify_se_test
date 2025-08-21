import logging
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from .api import router
from .db import init_db, seed_if_empty
from .logger_config import setup_logging

# ---- logging bootstrap ----
setup_logging()
logger = logging.getLogger("app")

# ---- canonical status -> code mapping ----
STATUS_CODE_MAP = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    415: "UNSUPPORTED_MEDIA_TYPE",
    422: "UNPROCESSABLE_ENTITY",
}

def status_to_code(status: int) -> str:
    return STATUS_CODE_MAP.get(status, f"HTTP_{status}")

def create_app() -> FastAPI:
    # DB bootstrap (idempotent) + optional seeding
    init_db()
    seed_if_empty()

    app = FastAPI(title="ATM System")

    # ---- middleware: enforce JSON on write methods ----
    class EnforceJSONMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            if request.method in {"POST", "PUT", "PATCH"}:
                ct = request.headers.get("content-type", "").split(";")[0].strip().lower()
                if ct != "application/json":
                    logger.warning("Unsupported media type: %s %s", request.method, request.url.path)
                    return JSONResponse(
                        status_code=415,
                        content={
                            "error": {
                                "code": status_to_code(415),
                                "message": "Content-Type must be application/json",
                            }
                        },
                    )
            return await call_next(request)

    app.add_middleware(EnforceJSONMiddleware)

    # ---- error handlers (uniform error shape) ----
    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        try:
            err = exc.errors()[0]
            loc = ".".join(str(x) for x in err.get("loc", []))
            detail = err.get("msg", "")
            msg = f"{loc}: {detail}" if loc else (detail or "Invalid request.")
        except Exception:
            msg = "Invalid request."
        logger.warning("422 validation: %s %s -> %s", request.method, request.url.path, msg)
        return JSONResponse(
            status_code=422,
            content={"error": {"code": status_to_code(422), "message": msg}},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exc_handler(request: Request, exc: StarletteHTTPException):
        code = status_to_code(exc.status_code)
        default_msg = code.replace("_", " ").title()
        message = str(exc.detail) if getattr(exc, "detail", None) else default_msg
        logger.warning("%s %s -> %s (%s)", request.method, request.url.path, exc.status_code, message)
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": code, "message": message}},
        )

    # ---- lifecycle logs ----
    @app.on_event("startup")
    async def on_startup():
        logger.info("🚀 ATM API started")

    @app.on_event("shutdown")
    async def on_shutdown():
        logger.info("🛑 ATM API stopped")

    # ---- routes ----
    app.include_router(router)
    return app

app = create_app()