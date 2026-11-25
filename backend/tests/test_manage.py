"""Exercise the database lifecycle commands used by the Helm chart."""

import subprocess
import sys

from conftest import ROOT
from sqlalchemy import inspect, text

MANAGE = [sys.executable, "-m", "backend.app.manage"]


def run(*args, env=None):
    return subprocess.run(
        [*MANAGE, *args],
        check=False,
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )


def test_wait_for_schema_times_out_until_migrated(database):
    engine, _ = database
    waiting = run("wait-for-schema", "--timeout", "0")
    assert waiting.returncode == 1
    assert "schema state: behind" in waiting.stderr
    assert inspect(engine).get_table_names() == []

    assert run("--wait-for-database", "5").returncode == 0
    ready = run("wait-for-schema", "--timeout", "0")
    assert ready.returncode == 0, ready.stderr


def test_newer_schema_is_left_untouched_and_accepted(migrated_db):
    with migrated_db.begin() as connection:
        connection.execute(text("UPDATE alembic_version SET version_num = 'future'"))

    migrate = run()
    assert migrate.returncode == 0, migrate.stderr
    assert "skipping migration and seed" in migrate.stderr
    with migrated_db.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            "future"
        )
        assert connection.scalar(text("SELECT count(*) FROM recipes")) == 0

    schema = run("wait-for-schema", "--timeout", "0")
    assert schema.returncode == 0, schema.stderr
    assert "newer than this image" in schema.stderr


def test_wait_for_database_reports_timeout(monkeypatch):
    import os

    env = dict(
        os.environ,
        DATABASE_URL="postgresql+psycopg://user:pass@127.0.0.1:1/missing",
    )
    result = run("--wait-for-database", "0.1", env=env)
    assert result.returncode == 1
    assert "timed out after 0.1s waiting for the database" in result.stderr
    assert "pass" not in result.stderr
