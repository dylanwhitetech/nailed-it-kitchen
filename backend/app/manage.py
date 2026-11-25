"""Database lifecycle commands for Compose and the Helm migration/seed Job.

``python -m backend.app.manage`` upgrades the schema to this image's Alembic head and then
seeds the reviewed recipes. ``--wait-for-database SECONDS`` first waits for PostgreSQL to accept
connections. ``python -m backend.app.manage wait-for-schema --timeout SECONDS`` only waits until
the schema is ready for this image (used by API init containers) and never migrates.

Every command exits nonzero with a message on failure or timeout.
"""

import argparse
import logging
import sys
import time
from collections.abc import Callable
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Connection, Engine, text
from sqlalchemy.exc import SQLAlchemyError

from backend.app.config import Settings
from backend.app.database import create_database_engine
from backend.app.seed import seed_recipes

logger = logging.getLogger("backend.app.manage")

# Session-level advisory lock serializing concurrent migration/seed runs on one database.
MIGRATION_LOCK_ID = 7_412_025
POLL_SECONDS = 5.0


def alembic_config() -> Config:
    """Return the packaged Alembic configuration."""
    return Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))


def schema_state(connection: Connection, script: ScriptDirectory) -> str:
    """Classify the database schema relative to this image's migrations.

    Returns:
        ``"current"`` at this image's head, ``"newer"`` when the database has a revision this
        image does not know (a later release migrated it, for example before a rollback), or
        ``"behind"`` otherwise, including an empty database.
    """
    current = set(MigrationContext.configure(connection).get_current_heads())
    known = {revision.revision for revision in script.walk_revisions()}
    if current - known:
        return "newer"
    if current == set(script.get_heads()):
        return "current"
    return "behind"


def wait_until(
    description: str, timeout: float, check: Callable[[], bool], poll: float
) -> None:
    """Call ``check`` until it returns true, retrying database errors until ``timeout``.

    Raises:
        TimeoutError: The deadline passed; the message includes the last error, if any.
    """
    deadline = time.monotonic() + timeout
    last_error = ""
    while True:
        try:
            if check():
                return
            last_error = ""
        except (SQLAlchemyError, OSError) as exc:
            last_error = f" (last error: {type(exc).__name__})"
        if time.monotonic() >= deadline:
            raise TimeoutError(
                f"timed out after {timeout:g}s waiting for {description}{last_error}"
            )
        time.sleep(poll)


def wait_for_database(engine: Engine, timeout: float, poll: float = POLL_SECONDS):
    """Wait until PostgreSQL accepts connections and answers a query."""

    def check() -> bool:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True

    wait_until("the database to accept connections", timeout, check, poll)


def wait_for_schema(engine: Engine, timeout: float, poll: float = POLL_SECONDS):
    """Wait until the schema is at this image's head or at a newer revision."""
    script = ScriptDirectory.from_config(alembic_config())
    state = {"value": "unknown"}

    def check() -> bool:
        with engine.connect() as connection:
            state["value"] = schema_state(connection, script)
        return state["value"] in {"current", "newer"}

    try:
        wait_until("the schema to reach this image's head", timeout, check, poll)
    except TimeoutError as exc:
        raise TimeoutError(f"{exc}; schema state: {state['value']}") from exc
    if state["value"] == "newer":
        logger.warning("database schema is newer than this image; continuing")


def migrate_and_seed(engine: Engine) -> None:
    """Upgrade to head and seed under an advisory lock.

    A database already migrated by a newer release is left untouched (no downgrade and no
    seeding of older recipe content), so a rolled-back release can start.
    """
    config = alembic_config()
    script = ScriptDirectory.from_config(config)
    with engine.connect() as connection:
        connection.execute(
            text("SELECT pg_advisory_lock(:id)"), {"id": MIGRATION_LOCK_ID}
        )
        connection.commit()
        try:
            if schema_state(connection, script) == "newer":
                logger.warning(
                    "database schema is newer than this image; skipping migration and seed"
                )
                return
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
            connection.commit()
            seed_recipes(engine)
            logger.info("database migrated to head and recipes seeded")
        finally:
            connection.rollback()
            connection.execute(
                text("SELECT pg_advisory_unlock(:id)"), {"id": MIGRATION_LOCK_ID}
            )
            connection.commit()


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--wait-for-database",
        type=float,
        default=0,
        metavar="SECONDS",
        help="wait up to SECONDS for PostgreSQL before migrating (default: no wait)",
    )
    commands = parser.add_subparsers(dest="command")
    schema = commands.add_parser(
        "wait-for-schema", help="wait until the schema is ready for this image"
    )
    schema.add_argument("--timeout", type=float, required=True, metavar="SECONDS")
    args = parser.parse_args(argv)
    if args.wait_for_database < 0 or getattr(args, "timeout", 0) < 0:
        parser.error("timeouts must not be negative")
    return args


def main(argv: list[str] | None = None) -> int:
    """Run the selected command and return a process exit status."""
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    args = parse_args(argv)
    try:
        engine = create_database_engine(Settings())
    except ValueError as exc:
        logger.error("%s", exc)
        return 1
    try:
        if args.command == "wait-for-schema":
            wait_for_schema(engine, args.timeout)
            logger.info("database schema is ready for this image")
        else:
            if args.wait_for_database:
                wait_for_database(engine, args.wait_for_database)
            migrate_and_seed(engine)
    except TimeoutError as exc:
        logger.error("%s", exc)
        return 1
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(main())
