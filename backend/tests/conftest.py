"""Isolated PostgreSQL fixtures for backend integration tests."""

import os
from pathlib import Path
from uuid import uuid4

import pytest

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
RECIPES = ROOT / "recipes"


@pytest.fixture
def database(monkeypatch):
    """Create a disposable schema, not a disposable database or shared tables."""
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not set; PostgreSQL integration test")

    from alembic.config import Config
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url

    parsed_url = make_url(url)
    if parsed_url.get_backend_name() != "postgresql":
        pytest.fail("TEST_DATABASE_URL must point to a disposable PostgreSQL database")
    parsed_url = parsed_url.set(drivername="postgresql+psycopg")

    admin = create_engine(parsed_url)
    schema = f"nik_test_{uuid4().hex}"
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))

    # libpq applies the isolated search_path to Alembic and every application connection.
    # Never drop or alter objects outside this randomly named schema.
    scoped_url = parsed_url.update_query_dict({"options": f"-csearch_path={schema}"})
    rendered_url = scoped_url.render_as_string(hide_password=False)
    monkeypatch.setenv("DATABASE_URL", rendered_url)
    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "alembic"))
    config.set_main_option("sqlalchemy.url", rendered_url.replace("%", "%%"))
    engine = create_engine(scoped_url)
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT current_schema()")) == schema
        yield engine, config
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


@pytest.fixture
def migrated_db(database):
    """Apply the actual migrations within the isolated test schema."""
    from alembic import command

    engine, config = database
    command.upgrade(config, "head")
    return engine
