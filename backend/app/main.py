"""FastAPI recipe discovery and operational endpoints for the beta backend."""

import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

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
from backend.app.recipe_pr import build_submissions_publisher
from backend.app.recipes import RecipeDatabase
from backend.app.recipes import router as recipes_router
from backend.app.submissions import SubmissionRateLimiter, TurnstileVerifier
from backend.app.submissions import router as submissions_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[dict[str, RecipeDatabase]]:
    """Pool recipe connections and, when configured, the recipe PR publisher.

    A publisher already set on ``app.state`` (for example a test double) is kept.
    Submissions still require ``SUBMISSIONS_ENABLED`` and Turnstile keys.
    """
    database = RecipeDatabase()
    created = None
    if app.state.recipe_publisher is None:
        created = build_submissions_publisher()
        app.state.recipe_publisher = created
    try:
        yield {"recipe_database": database}
    finally:
        database.dispose()
        if created is not None:
            created.close()
            app.state.recipe_publisher = None


app = FastAPI(
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
    swagger_ui_oauth2_redirect_url="/api/docs/oauth2-redirect",
    lifespan=lifespan,
)
app.include_router(recipes_router)
app.include_router(submissions_router)
# The lifespan sets the GitHub App publisher when configured; until then submissions are unavailable.
app.state.recipe_publisher = None
app.state.submission_rate_limiter = SubmissionRateLimiter()
app.state.turnstile_verifier = TurnstileVerifier()
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
