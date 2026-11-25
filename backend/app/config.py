"""Environment-backed application settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration shared by the API and database commands.

    DATABASE_URL must use SQLAlchemy's postgresql+psycopg dialect. It may be
    absent for liveness, but readiness and database commands require it.
    """

    model_config = SettingsConfigDict(extra="ignore")

    database_url: str | None = None
