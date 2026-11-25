"""Database lifecycle commands for Compose and the Helm migration/seed Job.

``python -m backend.app.manage`` upgrades the schema to this image's Alembic head and then
seeds the reviewed recipes. ``--wait-for-database SECONDS`` first waits for PostgreSQL to accept
connections. ``python -m backend.app.manage wait-for-schema --timeout SECONDS`` waits until
the schema is ready and, when configured by Helm, this release's migration/seed run
has completed. It never migrates.

Every command exits nonzero with a message on failure or timeout.
"""

import argparse
import json
import logging
import os
import ssl
import sys
import time
from collections.abc import Callable
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import HTTPSHandler, ProxyHandler, Request, build_opener

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
LIFECYCLE_TOKEN_DIR = Path("/var/run/secrets/naileditkitchen/lifecycle")


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
            reason = (
                f"HTTP {exc.code}" if isinstance(exc, HTTPError) else type(exc).__name__
            )
            last_error = f" (last error: {reason})"
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


def wait_for_schema(
    engine: Engine,
    timeout: float,
    poll: float = POLL_SECONDS,
    release: tuple[str, int] | None = None,
    job_check: Callable[[], bool] | None = None,
):
    """Wait for a compatible schema and, if supplied, a release completion marker."""
    script = ScriptDirectory.from_config(alembic_config())
    state = {"value": "unknown"}

    def check() -> bool:
        with engine.connect() as connection:
            state["value"] = schema_state(connection, script)
            if state["value"] not in {"current", "newer"}:
                return False
            if release is None:
                return True
            complete = bool(
                connection.scalar(
                    text(
                        "SELECT EXISTS (SELECT 1 FROM lifecycle_completions "
                        "WHERE installation_id = :installation_id AND revision = :revision)"
                    ),
                    {"installation_id": release[0], "revision": release[1]},
                )
            )
            return complete and (job_check is None or job_check())

    try:
        wait_until("the schema and release completion", timeout, check, poll)
    except TimeoutError as exc:
        raise TimeoutError(f"{exc}; schema state: {state['value']}") from exc
    if state["value"] == "newer":
        logger.warning("database schema is newer than this image; continuing")


def migrate_and_seed(engine: Engine, release: tuple[str, int] | None = None) -> None:
    """Upgrade to head and seed under an advisory lock.

    A database already migrated by a newer release is not downgraded or seeded with older
    content, so a rolled-back release can start. A supplied release marker is committed
    only after migration and seeding succeed, or after intentionally skipping them for a
    newer schema.
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
            else:
                config.attributes["connection"] = connection
                command.upgrade(config, "head")
                connection.commit()
                seed_recipes(engine)
                logger.info("database migrated to head and recipes seeded")
            if release is not None:
                connection.execute(
                    text(
                        "INSERT INTO lifecycle_completions (installation_id, revision) "
                        "VALUES (:installation_id, :revision) ON CONFLICT DO NOTHING"
                    ),
                    {"installation_id": release[0], "revision": release[1]},
                )
                connection.commit()
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


def release_from_environment() -> tuple[str, int] | None:
    """Read the paired Helm release marker or fail on an incomplete configuration."""
    installation_id = os.environ.get("LIFECYCLE_INSTALLATION_ID")
    revision = os.environ.get("LIFECYCLE_REVISION")
    if installation_id is None and revision is None:
        return None
    if not installation_id or len(installation_id) > 32 or not revision:
        raise ValueError("both lifecycle installation ID and revision must be set")
    try:
        number = int(revision)
    except ValueError as exc:
        raise ValueError("lifecycle revision must be a positive integer") from exc
    if number < 1:
        raise ValueError("lifecycle revision must be a positive integer")
    return installation_id, number


def kubernetes_release_complete(
    release: tuple[str, int],
    namespace: str,
    deployment: str,
    job: str,
    api_get: Callable[[str], dict | None],
) -> bool:
    """Require the current Job to finish; older pods may use their durable marker."""
    namespace = quote(namespace, safe="")
    deployment_path = (
        f"/apis/apps/v1/namespaces/{namespace}/deployments/{quote(deployment, safe='')}"
    )
    current = api_get(deployment_path)
    if current is None:
        return False
    annotations = (
        current.get("spec", {})
        .get("template", {})
        .get("metadata", {})
        .get("annotations", {})
    )
    revision = annotations.get("naileditkitchen.io/lifecycle-revision")
    if not isinstance(revision, str) or not revision.isdecimal():
        return False
    if int(revision) != release[1]:
        return True
    job_path = f"/apis/batch/v1/namespaces/{namespace}/jobs/{quote(job, safe='')}"
    current_job = api_get(job_path)
    if current_job is None or current_job.get("metadata", {}).get("deletionTimestamp"):
        return False
    return any(
        condition.get("type") == "Complete" and condition.get("status") == "True"
        for condition in current_job.get("status", {}).get("conditions", [])
    )


def kubernetes_api_get(path: str) -> dict | None:
    """Read one Kubernetes object using the init container's projected credentials."""
    host = os.environ["KUBERNETES_SERVICE_HOST"]
    if ":" in host:
        host = f"[{host}]"
    port = os.environ["KUBERNETES_SERVICE_PORT"]
    token = (LIFECYCLE_TOKEN_DIR / "token").read_text(encoding="utf-8").strip()
    request = Request(
        f"https://{host}:{port}{path}", headers={"Authorization": f"Bearer {token}"}
    )
    context = ssl.create_default_context(cafile=str(LIFECYCLE_TOKEN_DIR / "ca.crt"))
    opener = build_opener(ProxyHandler({}), HTTPSHandler(context=context))
    try:
        with opener.open(request, timeout=5) as response:
            return json.load(response)
    except HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def release_job_check(release: tuple[str, int]) -> Callable[[], bool]:
    """Build the Kubernetes Job check required by a Helm API init container."""
    names = (
        "KUBERNETES_SERVICE_HOST",
        "KUBERNETES_SERVICE_PORT",
        "LIFECYCLE_NAMESPACE",
        "LIFECYCLE_API_DEPLOYMENT",
        "LIFECYCLE_JOB",
    )
    if not all(os.environ.get(name) for name in names):
        raise ValueError("Kubernetes lifecycle Job check is not configured")
    return lambda: kubernetes_release_complete(
        release,
        os.environ["LIFECYCLE_NAMESPACE"],
        os.environ["LIFECYCLE_API_DEPLOYMENT"],
        os.environ["LIFECYCLE_JOB"],
        kubernetes_api_get,
    )


def main(argv: list[str] | None = None) -> int:
    """Run the selected command and return a process exit status."""
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    args = parse_args(argv)
    try:
        release = release_from_environment()
        job_check = (
            release_job_check(release)
            if args.command == "wait-for-schema" and release is not None
            else None
        )
        engine = create_database_engine(Settings())
    except ValueError as exc:
        logger.error("%s", exc)
        return 1
    try:
        if args.command == "wait-for-schema":
            wait_for_schema(engine, args.timeout, release=release, job_check=job_check)
            logger.info("database schema is ready for this image")
        else:
            if args.wait_for_database:
                wait_for_database(engine, args.wait_for_database)
            migrate_and_seed(engine, release=release)
    except TimeoutError as exc:
        logger.error("%s", exc)
        return 1
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(main())
