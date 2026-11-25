"""Verify the foundation's operational API without relying on a running database."""

import pytest
from fastapi.testclient import TestClient
from prometheus_client.parser import text_string_to_metric_families
from sqlalchemy.exc import OperationalError


@pytest.fixture
def client():
    from backend.app.main import app

    with TestClient(app) as test_client:
        yield test_client


def test_health_is_live_even_if_database_is_unavailable(client, monkeypatch):
    from backend.app import main

    def fail_if_called(_settings):
        raise AssertionError("liveness must not connect to the database")

    monkeypatch.setattr(main, "create_database_engine", fail_if_called)
    response = client.get("/api/healthz")
    assert response.status_code == 200
    assert isinstance(response.json(), dict)


def test_readiness_returns_503_on_database_connection_failure(client, monkeypatch):
    from backend.app import main

    class BrokenEngine:
        disposed = False

        def connect(self):
            raise OperationalError("SELECT 1", {}, OSError("database unavailable"))

        def dispose(self):
            self.disposed = True

    engine = BrokenEngine()
    monkeypatch.setattr(main, "create_database_engine", lambda _settings: engine)
    response = client.get("/api/readyz")
    assert response.status_code == 503
    assert isinstance(response.json(), dict)
    assert "SELECT 1" not in response.text
    assert engine.disposed


def test_readiness_with_configured_database(client, migrated_db):
    from backend.app.config import Settings

    assert Settings().database_url
    assert client.get("/api/readyz").status_code == 200


def test_api_docs_and_metrics(client):
    assert client.get("/api/healthz").status_code == 200
    docs = client.get("/api/docs")
    assert docs.status_code == 200
    assert "text/html" in docs.headers["content-type"]
    schema = client.get("/api/openapi.json")
    assert schema.status_code == 200
    paths = schema.json()["paths"]
    assert "/api/healthz" in paths and "/api/readyz" in paths
    assert all(path.startswith("/api/") for path in paths)

    response = client.get("/api/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    families = list(text_string_to_metric_families(response.text))
    assert any(
        family.type == "counter"
        and any(
            sample.name.endswith("_total") and sample.value >= 1
            for sample in family.samples
        )
        for family in families
    )
