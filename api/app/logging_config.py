"""Structured logging configuration for DukeCook.

All log output is JSON-formatted for easy parsing and troubleshooting.
Every request gets a unique request_id for tracing.
"""

import logging
import json
import sys
import uuid
import time
from datetime import datetime, timezone
from contextvars import ContextVar
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

# Context variable for per-request tracing
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
current_user_var: ContextVar[str] = ContextVar("current_user", default="-")


class JSONFormatter(logging.Formatter):
    """JSON log formatter with request context."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_var.get("-"),
            "user": current_user_var.get("-"),
        }

        # Add source location for warnings and errors
        if record.levelno >= logging.WARNING:
            log_entry["source"] = {
                "file": record.pathname,
                "line": record.lineno,
                "function": record.funcName,
            }

        # Add exception info if present
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info),
            }

        # Add any extra fields
        if hasattr(record, "extra_data"):
            log_entry["data"] = record.extra_data

        return json.dumps(log_entry)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware that assigns request IDs and logs request/response details."""

    async def dispatch(self, request: Request, call_next):
        rid = str(uuid.uuid4())[:8]
        request_id_var.set(rid)

        # Extract user from header or cookie
        user = request.headers.get("X-User", "") or request.cookies.get("dukecook_user", "-")
        current_user_var.set(user)

        logger = logging.getLogger("dukecook.http")
        start_time = time.time()

        logger.info(
            f"{request.method} {request.url.path}",
            extra={
                "extra_data": {
                    "method": request.method,
                    "path": str(request.url.path),
                    "query": str(request.url.query),
                    "client": request.client.host if request.client else "-",
                }
            },
        )

        try:
            response = await call_next(request)
            duration_ms = round((time.time() - start_time) * 1000, 1)

            logger.info(
                f"{request.method} {request.url.path} → {response.status_code} ({duration_ms}ms)",
                extra={
                    "extra_data": {
                        "method": request.method,
                        "path": str(request.url.path),
                        "status": response.status_code,
                        "duration_ms": duration_ms,
                    }
                },
            )
            return response

        except Exception as e:
            duration_ms = round((time.time() - start_time) * 1000, 1)
            logger.error(
                f"{request.method} {request.url.path} → ERROR ({duration_ms}ms): {e}",
                exc_info=True,
                extra={
                    "extra_data": {
                        "method": request.method,
                        "path": str(request.url.path),
                        "duration_ms": duration_ms,
                    }
                },
            )
            raise


def setup_logging(log_level: str = "INFO"):
    """Configure structured JSON logging for the entire application."""
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Remove existing handlers
    root_logger.handlers.clear()

    # JSON handler to stdout
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root_logger.addHandler(handler)

    # Quiet down noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    logger = logging.getLogger("dukecook")
    logger.info(f"Logging initialized at {log_level} level")
    return logger
