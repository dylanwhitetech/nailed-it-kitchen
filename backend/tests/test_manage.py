"""Exercise the database lifecycle commands used by the Helm chart."""

import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from threading import Event
from urllib.error import HTTPError

import pytest
from conftest import RECIPES, ROOT
from sqlalchemy import inspect, text

from backend.app import manage
from recipes.validate import validate_file

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


def test_current_schema_waits_for_successful_release_seed(migrated_db, monkeypatch):
    release = ("installation-a", 1)

    with pytest.raises(TimeoutError):
        manage.wait_for_schema(migrated_db, timeout=0, release=release)

    original_seed = manage.seed_recipes

    def failed_seed(engine):
        raise RuntimeError("seed failed")

    monkeypatch.setattr(manage, "seed_recipes", failed_seed)
    with pytest.raises(RuntimeError, match="seed failed"):
        manage.migrate_and_seed(migrated_db, release=release)
    with pytest.raises(TimeoutError):
        manage.wait_for_schema(migrated_db, timeout=0, release=release)

    monkeypatch.setattr(manage, "seed_recipes", original_seed)
    manage.migrate_and_seed(migrated_db, release=release)
    manage.wait_for_schema(migrated_db, timeout=0, release=release)
    with migrated_db.connect() as connection:
        slugs = set(connection.execute(text("SELECT slug FROM recipes")).scalars())
    assert slugs == {validate_file(path)["slug"] for path in RECIPES.glob("*.yaml")}


def test_release_completion_is_scoped_to_installation_and_revision(
    migrated_db, monkeypatch
):
    monkeypatch.setattr(manage, "seed_recipes", lambda engine: None)
    completed = [("installation-a", 1), ("installation-b", 2)]

    for release in completed:
        manage.migrate_and_seed(migrated_db, release=release)

    for release in [("installation-a", 2), ("installation-b", 1)]:
        with pytest.raises(TimeoutError):
            manage.wait_for_schema(migrated_db, timeout=0, release=release)
    for release in completed:
        manage.wait_for_schema(migrated_db, timeout=0, release=release)


def test_release_waits_while_seed_is_running(database, monkeypatch):
    engine, _ = database
    release = ("installation-a", 1)
    seed_started = Event()
    job_progress = Event()
    allow_seed = Event()
    original_seed = manage.seed_recipes

    def delayed_seed(engine):
        seed_started.set()
        job_progress.set()
        if not allow_seed.wait(timeout=30):
            raise TimeoutError("test did not release the seed")
        original_seed(engine)

    monkeypatch.setattr(manage, "seed_recipes", delayed_seed)
    with ThreadPoolExecutor(max_workers=1) as executor:
        job = executor.submit(manage.migrate_and_seed, engine, release=release)
        job.add_done_callback(lambda _: job_progress.set())
        try:
            assert job_progress.wait(timeout=30), "migration job made no progress"
            if not seed_started.is_set():
                job.result(timeout=1)
                pytest.fail("migration job finished without reaching seed")
            # The migration reached head, but this release's seed is still running.
            manage.wait_for_schema(engine, timeout=0)
            with pytest.raises(TimeoutError):
                manage.wait_for_schema(engine, timeout=0, release=release)
        finally:
            allow_seed.set()
        job.result(timeout=30)

    manage.wait_for_schema(engine, timeout=0, release=release)


def test_newer_schema_waits_for_release_job_without_seeding(migrated_db, monkeypatch):
    release = ("installation-a", 2)
    with migrated_db.begin() as connection:
        connection.execute(text("UPDATE alembic_version SET version_num = 'future'"))
        connection.execute(
            text(
                "INSERT INTO recipes (slug, title, ingredients, instructions) "
                "VALUES ('newer-recipe', 'Newer recipe', "
                "'[\"water\"]'::jsonb, '[\"Cook\"]'::jsonb)"
            )
        )

    def unexpected_seed(engine):
        pytest.fail("rollback must not seed older recipe data")

    monkeypatch.setattr(manage, "seed_recipes", unexpected_seed)
    with pytest.raises(TimeoutError):
        manage.wait_for_schema(migrated_db, timeout=0, release=release)

    manage.migrate_and_seed(migrated_db, release=release)
    manage.wait_for_schema(migrated_db, timeout=0, release=release)
    with migrated_db.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            "future"
        )
        assert connection.execute(text("SELECT slug, title FROM recipes")).all() == [
            ("newer-recipe", "Newer recipe")
        ]


DEPLOYMENT_PATH = "/apis/apps/v1/namespaces/kitchen/deployments/api"
JOB_PATH = "/apis/batch/v1/namespaces/kitchen/jobs/migrate-1"
COMPLETE_JOB = {
    "metadata": {"name": "migrate-1"},
    "status": {"conditions": [{"type": "Complete", "status": "True"}]},
}


def fake_kubernetes_api(deployment_revision, job):
    calls = []

    def api_get(path):
        calls.append(path)
        if path == DEPLOYMENT_PATH:
            return {
                "spec": {
                    "template": {
                        "metadata": {
                            "annotations": {
                                "naileditkitchen.io/lifecycle-revision": (
                                    deployment_revision
                                )
                            }
                        }
                    }
                }
            }
        assert path == JOB_PATH
        return job

    return api_get, calls


@pytest.mark.parametrize(
    ("job", "expected"),
    [
        (None, False),
        ({"metadata": {"name": "migrate-1"}, "status": {"active": 1}}, False),
        (
            {"status": {"conditions": [{"type": "Failed", "status": "True"}]}},
            False,
        ),
        (
            {"status": {"conditions": [{"type": "Complete", "status": "False"}]}},
            False,
        ),
        (
            {
                **COMPLETE_JOB,
                "metadata": {
                    "name": "migrate-1",
                    "deletionTimestamp": "2026-01-01T00:00:00Z",
                },
            },
            False,
        ),
        (COMPLETE_JOB, True),
    ],
    ids=["missing", "pending", "failed", "not-complete", "deleting", "complete"],
)
def test_current_deployment_checks_named_job(job, expected):
    api_get, calls = fake_kubernetes_api("1", job)

    assert (
        manage.kubernetes_release_complete(
            ("installation-a", 1), "kitchen", "api", "migrate-1", api_get
        )
        is expected
    )
    assert calls == [DEPLOYMENT_PATH, JOB_PATH]


def test_old_pod_skips_job_when_deployment_revision_differs():
    api_get, calls = fake_kubernetes_api("2", None)

    assert manage.kubernetes_release_complete(
        ("installation-a", 1), "kitchen", "api", "migrate-1", api_get
    )
    assert calls == [DEPLOYMENT_PATH]


def test_historical_marker_waits_for_current_rollback_job(migrated_db, monkeypatch):
    release = ("installation-a", 1)
    monkeypatch.setattr(manage, "seed_recipes", lambda engine: None)
    manage.migrate_and_seed(migrated_db, release=release)
    manage.wait_for_schema(migrated_db, timeout=0, release=release)

    for job in (
        None,
        {"status": {"active": 1}},
        {"status": {"conditions": [{"type": "Failed", "status": "True"}]}},
    ):
        api_get, _ = fake_kubernetes_api("1", job)
        job_check = partial(
            manage.kubernetes_release_complete,
            release,
            "kitchen",
            "api",
            "migrate-1",
            api_get,
        )
        with pytest.raises(TimeoutError):
            manage.wait_for_schema(
                migrated_db, timeout=0, release=release, job_check=job_check
            )

    api_get, _ = fake_kubernetes_api("1", COMPLETE_JOB)
    manage.wait_for_schema(
        migrated_db,
        timeout=0,
        release=release,
        job_check=lambda: manage.kubernetes_release_complete(
            release, "kitchen", "api", "migrate-1", api_get
        ),
    )


def test_old_pod_uses_its_marker_during_new_rollout(migrated_db, monkeypatch):
    release = ("installation-a", 1)
    monkeypatch.setattr(manage, "seed_recipes", lambda engine: None)
    manage.migrate_and_seed(migrated_db, release=release)
    api_get, calls = fake_kubernetes_api("2", None)

    def job_check():
        return manage.kubernetes_release_complete(
            release, "kitchen", "api", "migrate-1", api_get
        )

    manage.wait_for_schema(migrated_db, timeout=0, release=release, job_check=job_check)
    assert calls == [DEPLOYMENT_PATH]

    with pytest.raises(TimeoutError):
        manage.wait_for_schema(
            migrated_db, timeout=0, release=("installation-b", 1), job_check=job_check
        )


def test_job_check_reports_kubernetes_permission_failure(migrated_db, monkeypatch):
    release = ("installation-a", 1)
    monkeypatch.setattr(manage, "seed_recipes", lambda engine: None)
    manage.migrate_and_seed(migrated_db, release=release)

    def forbidden():
        raise HTTPError("", 403, "Forbidden", None, None)

    with pytest.raises(TimeoutError, match="HTTP 403"):
        manage.wait_for_schema(
            migrated_db, timeout=0, release=release, job_check=forbidden
        )


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


@pytest.mark.parametrize(
    ("installation_id", "revision"),
    [(None, "1"), ("installation-a", None), ("installation-a", "0")],
)
def test_incomplete_release_configuration_fails(monkeypatch, installation_id, revision):
    for name, value in (
        ("LIFECYCLE_INSTALLATION_ID", installation_id),
        ("LIFECYCLE_REVISION", revision),
    ):
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)
    with pytest.raises(ValueError):
        manage.release_from_environment()
