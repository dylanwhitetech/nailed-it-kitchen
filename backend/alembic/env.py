"""Run Alembic with the same environment-backed database settings as the API."""

from logging.config import fileConfig

from alembic import context

from backend.app.config import Settings
from backend.app.database import create_database_engine
from backend.app.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    raise RuntimeError("Offline migrations are not supported; configure DATABASE_URL")
elif connection := config.attributes.get("connection"):
    run_migrations(connection)
else:
    engine = create_database_engine(Settings())
    try:
        with engine.connect() as connection:
            run_migrations(connection)
    finally:
        engine.dispose()
