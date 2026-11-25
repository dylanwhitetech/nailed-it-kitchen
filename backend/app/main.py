"""FastAPI recipe discovery and operational endpoints for the beta backend."""

import logging
import time

from fastapi import FastAPI, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
)
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from backend.app.config import Settings
from backend.app.database import create_database_engine
from backend.app.recipes import router as recipes_router

logger = logging.getLogger(__name__)
app = FastAPI(
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
    swagger_ui_oauth2_redirect_url="/api/docs/oauth2-redirect",
)
app.include_router(recipes_router)
registry = CollectorRegistry()
requests_total = Counter(
    "naileditkitchen_http_requests",
    "HTTP requests served by the API",
    ("method", "status"),
    registry=registry,
)
request_duration = Histogram(
    "naileditkitchen_http_request_duration_seconds",
    "HTTP request duration in seconds",
    registry=registry,
)


@app.middleware("http")
async def count_requests(request, call_next):
    """Count requests without exposing unbounded URL or client labels."""
    method = (
        request.method
        if request.method
        in {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"}
        else "OTHER"
    )
    status = 500
    start = time.perf_counter()
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        requests_total.labels(method=method, status=str(status)).inc()
        request_duration.observe(time.perf_counter() - start)


@app.get("/api/healthz")
def healthz() -> dict[str, str]:
    """Report that the API process is alive, without querying the database."""
    return {"status": "ok"}


@app.get("/api/readyz", responses={503: {"description": "Database is unavailable"}})
def readyz(response: Response) -> dict[str, str]:
    """Report readiness only when the configured PostgreSQL database responds."""
    engine = None
    try:
        engine = create_database_engine(Settings())
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except (ValueError, SQLAlchemyError, OSError) as exc:
        logger.warning("Database readiness check failed: %s", type(exc).__name__)
        response.status_code = 503
        return {"status": "unavailable"}
    finally:
        if engine is not None:
            engine.dispose()
    return {"status": "ok"}


@app.get("/api/metrics", include_in_schema=False)
def metrics() -> Response:
    """Expose basic Prometheus request metrics."""
    return Response(
        generate_latest(registry), headers={"Content-Type": CONTENT_TYPE_LATEST}
    )
