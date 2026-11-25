"""Create database connections for the API and management commands."""

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url

from backend.app.config import Settings


def create_database_engine(settings: Settings) -> Engine:
    """Create a PostgreSQL engine without opening a connection.

    Raises:
        ValueError: DATABASE_URL is missing or uses an unsupported driver.
    """
    if not settings.database_url:
        raise ValueError("DATABASE_URL is required for database operations")
    url = make_url(settings.database_url)
    if url.drivername != "postgresql+psycopg":
        raise ValueError("DATABASE_URL must use postgresql+psycopg")
    return create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 3})
