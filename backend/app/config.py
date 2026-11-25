"""Environment-backed application settings."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration shared by the API and database commands.

    DATABASE_URL must use SQLAlchemy's postgresql+psycopg dialect. It may be
    absent for liveness, but readiness and database commands require it.

    The GITHUB_APP_* values configure the recipe PR publisher. The private key is
    read only from the file named by GITHUB_APP_PRIVATE_KEY_FILE (a mounted secret),
    never from an environment value. Repository and base branch are operator
    settings; public input can never choose them.
    """

    model_config = SettingsConfigDict(extra="ignore")

    database_url: str | None = None

    github_app_id: int | None = Field(default=None, gt=0)
    github_app_installation_id: int | None = Field(default=None, gt=0)
    github_app_private_key_file: Path | None = None
    github_repository: str = Field(
        default="dylanwhitetech/nailed-it-kitchen",
        pattern=r"^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$",
    )
    github_base_branch: str = Field(
        default="main", pattern=r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,99}$"
    )
    github_api_url: str = Field(default="https://api.github.com", pattern=r"^https://")
