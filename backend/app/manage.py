"""Run migrations and synchronize reviewed recipes in one command."""

from pathlib import Path

from alembic import command
from alembic.config import Config

from backend.app.config import Settings
from backend.app.database import create_database_engine
from backend.app.seed import seed_recipes


def main() -> None:
    """Upgrade the database to head, then validate and seed the packaged recipes."""
    engine = create_database_engine(Settings())
    try:
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        with engine.connect() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        seed_recipes(engine)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
