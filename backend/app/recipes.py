"""Bounded recipe discovery and durable detail-read telemetry."""

import logging
from collections.abc import Iterator
from datetime import datetime
from threading import Lock
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Connection, Engine, func, select, update
from sqlalchemy.exc import SQLAlchemyError

from backend.app.config import Settings
from backend.app.database import create_database_engine
from backend.app.models import Recipe

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api",
    tags=["recipes"],
    responses={503: {"description": "Recipe database is unavailable"}},
)


class RecipeSummary(BaseModel):
    """Recipe identity and useful metadata, without its full cooking text."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    title: str
    view_count: int = Field(ge=0)
    created_at: datetime
    updated_at: datetime


class RecipeDetail(RecipeSummary):
    """The plain recipe contract; source and ordered notes remain optional."""

    ingredients: list[str]
    instructions: list[str]
    source: str | None
    notes: list[str] | None


class RecipePage(BaseModel):
    """A bounded A-Z page; next_offset is null when there is no next page."""

    items: list[RecipeSummary]
    next_offset: int | None


SUMMARY_COLUMNS = (
    Recipe.id,
    Recipe.slug,
    Recipe.title,
    Recipe.view_count,
    Recipe.created_at,
    Recipe.updated_at,
)
DETAIL_COLUMNS = (
    *SUMMARY_COLUMNS,
    Recipe.ingredients,
    Recipe.instructions,
    Recipe.source,
    Recipe.notes,
)


class RecipeDatabase:
    """Lazily own one bounded engine pool for an application lifespan."""

    def __init__(self) -> None:
        self._engine: Engine | None = None
        self._lock = Lock()

    def engine(self) -> Engine:
        """Create the engine once, including under concurrent first requests."""
        with self._lock:
            if self._engine is None:
                self._engine = create_database_engine(Settings())
            return self._engine

    def dispose(self) -> None:
        """Release pooled connections when the application shuts down."""
        with self._lock:
            if self._engine is not None:
                self._engine.dispose()


def recipe_connection(request: Request) -> Iterator[Connection]:
    """Provide a request transaction from the application-lifetime pool.

    Database errors roll back the transaction and return 503 without logging
    database URLs, SQL parameters, recipe content, or visitor information.
    """
    try:
        database: RecipeDatabase = request.state.recipe_database
        engine = database.engine()
        with engine.begin() as connection:
            yield connection
    except (ValueError, SQLAlchemyError, OSError) as exc:
        logger.error("Recipe database request failed: %s", type(exc).__name__)
        raise HTTPException(503, "Recipe database is unavailable") from exc


# Function scope commits before the response starts so commit failures still become 503s.
Database = Annotated[Connection, Depends(recipe_connection, scope="function")]


@router.get("/recipes", response_model=RecipePage)
def list_recipes(
    connection: Database,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0, le=9_223_372_036_854_775_807)] = 0,
    q: Annotated[str, Query(max_length=200)] = "",
) -> RecipePage:
    """Browse case-insensitive A-Z pages, optionally matching English keywords.

    Empty or whitespace-only q browses all recipes. Other input uses plain
    full-text search: all non-stopword terms must match title, ingredients, or
    instructions. Punctuation is not query syntax; a query without searchable
    terms returns no matches. Keep q and limit unchanged when using next_offset.
    """
    statement = select(*SUMMARY_COLUMNS)
    query = q.strip()
    if query:
        statement = statement.where(
            Recipe.search_document.op("@@")(func.plainto_tsquery("english", query))
        )
    statement = (
        statement.order_by(func.lower(Recipe.title), Recipe.slug, Recipe.id)
        .offset(offset)
        .limit(limit + 1)
    )
    rows = connection.execute(statement).mappings().all()
    return RecipePage(
        items=[RecipeSummary.model_validate(row) for row in rows[:limit]],
        next_offset=offset + limit if len(rows) > limit else None,
    )


@router.get("/most-viewed", response_model=list[RecipeSummary])
def most_viewed(
    connection: Database,
    limit: Annotated[int, Query(ge=1, le=10)] = 5,
) -> list[RecipeSummary]:
    """Return a small list by descending durable views, then slug and identity.

    This separate landing-page section does not change default A-Z browsing.
    """
    rows = (
        connection.execute(
            select(*SUMMARY_COLUMNS)
            .order_by(Recipe.view_count.desc(), Recipe.slug, Recipe.id)
            .limit(limit)
        )
        .mappings()
        .all()
    )
    return [RecipeSummary.model_validate(row) for row in rows]


@router.get(
    "/recipes/{slug}",
    response_model=RecipeDetail,
    responses={404: {"description": "Recipe was not found"}},
)
def recipe_detail(slug: str, connection: Database, response: Response) -> RecipeDetail:
    """Read one plain recipe and atomically count this successful detail read.

    Counts are approximate server reads, not unique visitors. Repeated reads
    count again; list/search/operational and unsupported HEAD requests do not.
    Unknown slugs return 404. Content modification timestamps do not change.
    """
    row = (
        connection.execute(
            update(Recipe)
            .where(Recipe.slug == slug)
            .values(view_count=Recipe.view_count + 1)
            .returning(*DETAIL_COLUMNS)
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise HTTPException(404, "Recipe was not found")
    detail = RecipeDetail.model_validate(row)
    response.headers["Cache-Control"] = "no-store"
    return detail
