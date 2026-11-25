"""Minimal PostgreSQL representation of reviewed recipes."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Computed,
    DateTime,
    Index,
    Integer,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Metadata for Alembic and the application."""


class LifecycleCompletion(Base):
    """A completed Helm migration/seed run for one installation and revision."""

    __tablename__ = "lifecycle_completions"
    __table_args__ = (
        CheckConstraint("revision > 0", name="ck_lifecycle_revision_positive"),
    )

    installation_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)


SEARCH_EXPRESSION = (
    "to_tsvector('english'::regconfig, title) || "
    """jsonb_to_tsvector('english'::regconfig, ingredients, '["string"]'::jsonb) || """
    """jsonb_to_tsvector('english'::regconfig, instructions, '["string"]'::jsonb)"""
)


class Recipe(Base):
    """A reviewed recipe and its durable, approximate view count."""

    __tablename__ = "recipes"
    __table_args__ = (
        CheckConstraint("view_count >= 0", name="ck_recipes_view_count_nonnegative"),
        CheckConstraint(
            "jsonb_typeof(ingredients) = 'array' AND jsonb_array_length(ingredients) > 0",
            name="ck_recipes_ingredients_nonempty",
        ),
        CheckConstraint(
            "jsonb_typeof(instructions) = 'array' AND jsonb_array_length(instructions) > 0",
            name="ck_recipes_instructions_nonempty",
        ),
        Index("ix_recipes_search_document", "search_document", postgresql_using="gin"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    source: Mapped[str | None] = mapped_column(String(300))
    ingredients: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    instructions: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    notes: Mapped[list[str] | None] = mapped_column(JSONB(none_as_null=True))
    view_count: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    search_document: Mapped[str] = mapped_column(
        TSVECTOR, Computed(SEARCH_EXPRESSION, persisted=True), nullable=False
    )
