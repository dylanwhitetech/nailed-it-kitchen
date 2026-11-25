"""Recipe PR template loading and publisher wiring; no test contacts GitHub."""

import logging

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from backend.app import recipe_pr
from backend.app.recipe_pr import (
    CHECKS_MARKER,
    RECIPE_MARKER,
    GitHubRecipeSubmissions,
    build_submissions_publisher,
    load_template,
)

APP_ENV = (
    "GITHUB_APP_ID",
    "GITHUB_APP_INSTALLATION_ID",
    "GITHUB_APP_PRIVATE_KEY_FILE",
    "SUBMISSIONS_ENABLED",
    "TURNSTILE_SITE_KEY",
    "TURNSTILE_SECRET_KEY",
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in APP_ENV:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def key_file(tmp_path):
    pem = (
        rsa.generate_private_key(public_exponent=65537, key_size=2048)
        .private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        .decode()
    )
    path = tmp_path / "app.pem"
    path.write_text(pem, encoding="utf-8")
    return path


def configure_app(monkeypatch, key_file):
    monkeypatch.setenv("GITHUB_APP_ID", "1234")
    monkeypatch.setenv("GITHUB_APP_INSTALLATION_ID", "5678")
    monkeypatch.setenv("GITHUB_APP_PRIVATE_KEY_FILE", str(key_file))


def test_repository_template_has_each_marker_once_and_no_issue_link():
    template = load_template()
    assert template.count(RECIPE_MARKER) == template.count(CHECKS_MARKER) == 1
    assert "Closes #" not in template
    assert "- [ ] The diff adds exactly one new file" in template


@pytest.mark.parametrize("marker", [RECIPE_MARKER, CHECKS_MARKER])
def test_template_without_a_marker_is_rejected(tmp_path, marker):
    path = tmp_path / "recipe.md"
    path.write_text(load_template().replace(marker, ""), encoding="utf-8")
    with pytest.raises(ValueError, match="exactly once"):
        load_template(path)


def test_no_publisher_without_github_app_settings():
    assert build_submissions_publisher() is None


def test_invalid_or_partial_app_settings_fail_closed(monkeypatch, key_file, caplog):
    caplog.set_level(logging.ERROR)
    monkeypatch.setenv("GITHUB_APP_ID", "not-a-number")
    assert build_submissions_publisher() is None
    monkeypatch.setenv("GITHUB_APP_ID", "1234")
    assert build_submissions_publisher() is None
    assert "GITHUB_APP_INSTALLATION_ID" in caplog.text

    configure_app(monkeypatch, key_file)
    monkeypatch.setattr(recipe_pr, "TEMPLATE_PATH", key_file.parent / "missing.md")
    assert build_submissions_publisher() is None
    assert key_file.read_text(encoding="utf-8").splitlines()[1] not in caplog.text


def test_lifespan_wires_configured_publisher_but_submissions_stay_off(
    monkeypatch, key_file
):
    from backend.app.main import app

    configure_app(monkeypatch, key_file)
    assert app.state.recipe_publisher is None
    with TestClient(app) as client:
        assert isinstance(app.state.recipe_publisher, GitHubRecipeSubmissions)
        assert client.get("/api/submissions/availability").json() == {
            "enabled": False,
            "turnstile_site_key": None,
        }
        response = client.post("/api/submissions", json={})
        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "submissions_disabled"
    assert app.state.recipe_publisher is None


def test_lifespan_keeps_a_publisher_that_is_already_set(monkeypatch, key_file):
    from backend.app.main import app

    configure_app(monkeypatch, key_file)
    existing = object()
    app.state.recipe_publisher = existing
    try:
        with TestClient(app):
            assert app.state.recipe_publisher is existing
        assert app.state.recipe_publisher is existing
    finally:
        app.state.recipe_publisher = None
