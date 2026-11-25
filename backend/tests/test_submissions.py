"""Submission guards: availability, size caps, proxy trust, rate limits and Turnstile."""

import asyncio
import ipaddress
import json
import time

import httpx
import pytest
from fastapi.testclient import TestClient
from starlette.exceptions import HTTPException

from backend.app import submissions as submissions_module
from backend.app.submissions import (
    MAX_REQUEST_BYTES,
    PublishError,
    SubmissionRateLimiter,
    TurnstileVerifier,
    _contains_markup,
)
from recipes.validate import MAX_CONTENT_CHARS, content_length

TEST_SECRET = "1x0000000000000000000000000000000AA"
TEST_SITE_KEY = "1x00000000000000000000AA"
PEER = "203.0.113.10"
PROXY = "10.0.0.5"


class FakePublisher:
    def __init__(self, error=None):
        self.calls = []
        self.error = error

    async def publish(self, recipe):
        self.calls.append(recipe)
        if self.error:
            raise self.error
        return "https://github.com/example/repo/pull/1"


class FakeVerifier:
    def __init__(self, error=None):
        self.calls = []
        self.error = error

    async def verify(self, token, secret, timeout_seconds):
        self.calls.append((token, secret.get_secret_value(), timeout_seconds))
        if self.error:
            raise self.error


def recipe(**overrides):
    return {
        "title": "Buttered Toast",
        "ingredients": ["1 slice bread", "1 tbsp butter"],
        "instructions": ["Toast the bread.", "Spread with butter."],
        **overrides,
    }


def payload(**overrides):
    return {"recipe": recipe(), "turnstile_token": "XXXX.DUMMY.TOKEN.XXXX", **overrides}


@pytest.fixture
def app(monkeypatch):
    from backend.app.main import app

    for name, value in {
        "SUBMISSIONS_ENABLED": "true",
        "TURNSTILE_SITE_KEY": TEST_SITE_KEY,
        "TURNSTILE_SECRET_KEY": TEST_SECRET,
        "TRUSTED_PROXY_CIDRS": "10.0.0.0/24",
        "SUBMISSION_RATE_LIMIT_PER_CLIENT": "100",
        "SUBMISSION_RATE_LIMIT_AGGREGATE": "1000",
    }.items():
        monkeypatch.setenv(name, value)
    # Starlette's State is not compatible with monkeypatch, so restore it explicitly.
    names = ("recipe_publisher", "turnstile_verifier", "submission_rate_limiter")
    saved = {name: getattr(app.state, name) for name in names}
    app.state.recipe_publisher = FakePublisher()
    app.state.turnstile_verifier = FakeVerifier()
    app.state.submission_rate_limiter = SubmissionRateLimiter()
    yield app
    for name, value in saved.items():
        setattr(app.state, name, value)


def client_for(app, host=PEER):
    return TestClient(app, client=(host, 50000))


@pytest.fixture
def client(app):
    with client_for(app) as test_client:
        yield test_client


def post_json(client, body, headers=None):
    return client.post(
        "/api/submissions",
        content=body if isinstance(body, bytes) else json.dumps(body),
        headers={"Content-Type": "application/json", **(headers or {})},
    )


def padded_body(size):
    """A valid submission padded with JSON whitespace to exactly ``size`` bytes."""
    body = json.dumps(payload()).encode()
    return body[:-1] + b" " * (size - len(body)) + b"}"


# Availability and the server-side switch


def test_submissions_default_off_and_refuse_before_reading_or_writing(app, monkeypatch):
    monkeypatch.delenv("SUBMISSIONS_ENABLED")
    with client_for(app) as client:
        assert client.get("/api/submissions/availability").json() == {
            "enabled": False,
            "turnstile_site_key": None,
        }
        response = post_json(client, b"x" * (MAX_REQUEST_BYTES * 2))
        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "submissions_disabled"
        assert client.get("/api/healthz").status_code == 200
    assert app.state.recipe_publisher.calls == []
    assert app.state.turnstile_verifier.calls == []


@pytest.mark.parametrize(
    ("env", "publisher"),
    [
        ({"SUBMISSIONS_ENABLED": "false"}, True),
        ({"TURNSTILE_SECRET_KEY": ""}, True),
        ({"TURNSTILE_SITE_KEY": ""}, True),
        ({"TRUSTED_PROXY_CIDRS": "not-a-network"}, True),
        ({"SUBMISSION_RATE_LIMIT_PER_CLIENT": "0"}, True),
        ({}, False),
    ],
)
def test_unavailable_when_disabled_or_misconfigured(app, monkeypatch, env, publisher):
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    if not publisher:
        app.state.recipe_publisher = None
    with client_for(app) as client:
        assert client.get("/api/submissions/availability").json()["enabled"] is False
        response = post_json(client, payload())
        assert response.status_code == 503
        assert TEST_SECRET not in response.text
        assert client.get("/api/healthz").status_code == 200


def test_enabled_submission_publishes_normalized_recipe(client, app):
    assert client.get("/api/submissions/availability").json() == {
        "enabled": True,
        "turnstile_site_key": TEST_SITE_KEY,
    }
    response = post_json(
        client,
        payload(
            recipe=recipe(
                title="  Cafe\u0301\tau  lait ",
                source="Grandma <3",
                notes=["1 < 2 cups"],
            )
        ),
    )
    assert response.status_code == 201
    assert response.json() == {
        "status": "submitted",
        "pull_request_url": "https://github.com/example/repo/pull/1",
    }
    published = app.state.recipe_publisher.calls[0]
    assert published["slug"] == "cafe-au-lait"
    assert published["title"] == "Caf\u00e9 au lait"
    assert published["source"] == "Grandma <3"
    assert app.state.turnstile_verifier.calls == [
        ("XXXX.DUMMY.TOKEN.XXXX", TEST_SECRET, 5.0)
    ]


# Request and content size boundaries


@pytest.mark.parametrize("chunked", [False, True])
def test_request_body_limit_is_exact_with_or_without_content_length(client, chunked):
    def send(body):
        content = iter([body[i : i + 1000] for i in range(0, len(body), 1000)])
        return client.post(
            "/api/submissions",
            content=content if chunked else body,
            headers={"Content-Type": "application/json"},
        )

    at_limit = send(padded_body(MAX_REQUEST_BYTES))
    assert at_limit.status_code == 201
    over_limit = send(padded_body(MAX_REQUEST_BYTES + 1))
    assert over_limit.status_code == 413
    assert over_limit.json()["detail"]["code"] == "request_too_large"


def test_oversized_chunk_is_rejected_before_it_is_buffered(monkeypatch):
    class TrackingBytearray(bytearray):
        largest_length = 0

        def extend(self, chunk):
            super().extend(chunk)
            type(self).largest_length = max(type(self).largest_length, len(self))

        def __iadd__(self, chunk):
            super().__iadd__(chunk)
            type(self).largest_length = max(type(self).largest_length, len(self))
            return self

    class RequestChunks:
        async def stream(self):
            yield b"x" * MAX_REQUEST_BYTES
            yield b"y" * (MAX_REQUEST_BYTES + 1)

    monkeypatch.setattr(
        submissions_module, "bytearray", TrackingBytearray, raising=False
    )

    with pytest.raises(HTTPException) as error:
        asyncio.run(
            submissions_module.read_bounded_body(
                RequestChunks(), limit=MAX_REQUEST_BYTES
            )
        )

    assert error.value.status_code == 413
    assert TrackingBytearray.largest_length == MAX_REQUEST_BYTES


def test_declared_oversize_is_refused_before_rate_limit_or_body(client, app):
    response = client.post(
        "/api/submissions",
        content=b"{}",
        headers={
            "Content-Type": "application/json",
            "Content-Length": str(MAX_REQUEST_BYTES + 1),
        },
    )
    assert response.status_code == 413
    assert (
        app.state.submission_rate_limiter._aggregate
        == type(app.state.submission_rate_limiter._aggregate)()
    )


def recipe_with_content_length(length):
    steps = ["s" * 2000] * 9
    candidate = recipe(instructions=steps)
    candidate["instructions"].append(
        "x"
        * (length - content_length({**candidate, "instructions": steps + ["x"]}) + 1)
    )
    assert content_length({**candidate, "slug": "buttered-toast"}) == length
    return candidate


def test_normalized_content_limit_is_exact(client):
    ok = post_json(
        client, payload(recipe=recipe_with_content_length(MAX_CONTENT_CHARS))
    )
    assert ok.status_code == 201
    too_long = post_json(
        client, payload(recipe=recipe_with_content_length(MAX_CONTENT_CHARS + 1))
    )
    assert too_long.status_code == 422
    assert any(
        "maximum is 20000" in error for error in too_long.json()["detail"]["errors"]
    )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("title", "t" * 161, "recipe.title: must be at most 160 characters"),
        (
            "ingredients",
            ["i"] * 101,
            "recipe.ingredients: must have at most 100 entries",
        ),
        ("notes", [], "recipe.notes: must have at least 1 entry"),
    ],
)
def test_field_bounds_are_enforced(client, field, value, message):
    response = post_json(client, payload(recipe=recipe(**{field: value})))
    assert response.status_code == 422
    assert message in response.json()["detail"]["errors"]


# Malformed and unsafe input


@pytest.mark.parametrize(
    "body",
    [
        b"{not json",
        b"\xff\xfe",
        b"[" * 16_000 + b"]" * 16_000,
        b'{"recipe": {}, "recipe": {}}',
        b'{"recipe": NaN}',
    ],
)
def test_malformed_json_is_rejected(client, app, body):
    response = post_json(client, body)
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "invalid_json"
    assert app.state.turnstile_verifier.calls == []


def test_non_json_content_type_is_rejected(client):
    response = client.post(
        "/api/submissions",
        content=json.dumps(payload()),
        headers={"Content-Type": "text/plain"},
    )
    assert response.status_code == 415


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        (payload(recipe=recipe(slug="x")), "recipe.slug: is generated by the server"),
        (payload(extra=1), "extra: unknown field"),
        (payload(turnstile_token=""), "turnstile_token: is required"),
        (payload(turnstile_token="t" * 2049), "turnstile_token: must be at most 2048"),
        (
            payload(recipe=recipe(title="!!!")),
            "recipe.title: must contain at least one",
        ),
        (
            payload(recipe=recipe(ingredients="flour")),
            "recipe.ingredients: must be a list",
        ),
    ],
)
def test_invalid_submission_shape(client, app, body, expected):
    response = post_json(client, body)
    assert response.status_code == 422
    assert any(e.startswith(expected) for e in response.json()["detail"]["errors"])
    assert app.state.turnstile_verifier.calls == []
    assert app.state.recipe_publisher.calls == []


@pytest.mark.parametrize(
    "text",
    [
        "<script>alert(1)</script>",
        "<img src=x onerror=alert(1)>",
        "</div>",
        "<!-- hidden -->",
        "see javascript:alert(1)",
        "data:text/html;base64,AAAA",
        "${{ secrets.TOKEN }}",
        "line one\nline two",
        "bell\x07",
        "reversed \u202etext",
        "zero\u200bwidth",
    ],
)
def test_executable_markup_and_controls_are_rejected(client, app, text):
    response = post_json(client, payload(recipe=recipe(ingredients=["flour", text])))
    assert response.status_code == 422
    assert response.json()["detail"]["errors"][0].startswith("recipe.ingredients[1]:")
    assert app.state.recipe_publisher.calls == []


def test_plain_symbols_and_emoji_remain_text(client, app):
    text = "Mix < 5 min; heat > 200\u00b0C & serve \U0001f468\u200d\U0001f373"
    response = post_json(client, payload(recipe=recipe(notes=[text])))
    assert response.status_code == 201
    assert app.state.recipe_publisher.calls[0]["notes"] == [text]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("< b>", True),
        ("<  /  div >", True),
        ("<?xml?>", True),
        ("a <b and later c>", True),
        ("<b", False),
        ("> then <b", False),
        ("1 < 2 > 0", False),
        ("< / >", False),
        ("<>", False),
    ],
)
def test_markup_detection_requires_tag_start_before_closing(text, expected):
    assert _contains_markup(text) is expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("<" + " " * 50_000, False),
        ("<" + " " * 50_000 + ">", False),
        ("<!" * 25_000, False),
        ("<!" * 25_000 + ">", True),
        ("< /" * 15_000, False),
    ],
)
def test_markup_detection_is_linear_on_hostile_input(text, expected):
    started = time.perf_counter()
    assert _contains_markup(text) is expected
    assert time.perf_counter() - started < 0.5


# Client identity and proxy trust


def test_untrusted_peer_cannot_spoof_forwarding_headers(app, monkeypatch):
    monkeypatch.setenv("SUBMISSION_RATE_LIMIT_PER_CLIENT", "2")
    with client_for(app, PEER) as client:
        statuses = [
            post_json(
                client,
                payload(),
                {
                    "CF-Connecting-IP": f"198.51.100.{i}",
                    "X-Forwarded-For": f"192.0.2.{i}",
                },
            ).status_code
            for i in range(3)
        ]
    assert statuses == [201, 201, 429]


def test_trusted_proxy_uses_cf_connecting_ip_per_client(app, monkeypatch):
    monkeypatch.setenv("SUBMISSION_RATE_LIMIT_PER_CLIENT", "1")
    with client_for(app, PROXY) as client:
        first = post_json(client, payload(), {"CF-Connecting-IP": "198.51.100.1"})
        second = post_json(client, payload(), {"CF-Connecting-IP": "198.51.100.2"})
        repeat = post_json(client, payload(), {"CF-Connecting-IP": "198.51.100.1"})
    assert (first.status_code, second.status_code, repeat.status_code) == (
        201,
        201,
        429,
    )
    assert int(repeat.headers["Retry-After"]) > 0


def test_ipv6_clients_are_grouped_by_64(app, monkeypatch):
    monkeypatch.setenv("SUBMISSION_RATE_LIMIT_PER_CLIENT", "1")
    with client_for(app, PROXY) as client:
        first = post_json(client, payload(), {"CF-Connecting-IP": "2001:db8:1:2::1"})
        same_64 = post_json(client, payload(), {"CF-Connecting-IP": "2001:db8:1:2::ff"})
        other_64 = post_json(client, payload(), {"CF-Connecting-IP": "2001:db8:1:3::1"})
    assert (first.status_code, same_64.status_code, other_64.status_code) == (
        201,
        429,
        201,
    )


@pytest.mark.parametrize(
    "headers",
    [
        [],
        [("CF-Connecting-IP", "not-an-ip")],
        [("CF-Connecting-IP", "198.51.100.1"), ("CF-Connecting-IP", "198.51.100.2")],
    ],
)
def test_trusted_proxy_without_one_valid_client_ip_fails_closed(app, headers):
    with client_for(app, PROXY) as client:
        response = client.post(
            "/api/submissions",
            content=json.dumps(payload()),
            headers=[("Content-Type", "application/json"), *headers],
        )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "client_unidentified"
    assert app.state.recipe_publisher.calls == []


def test_non_ip_peer_fails_closed(app):
    with client_for(app, "testclient") as client:
        assert post_json(client, payload()).status_code == 400


# Rate limits


def test_aggregate_limit_caps_all_clients(app, monkeypatch):
    monkeypatch.setenv("SUBMISSION_RATE_LIMIT_AGGREGATE", "2")
    with client_for(app, PROXY) as client:
        statuses = [
            post_json(
                client, payload(), {"CF-Connecting-IP": f"198.51.100.{i}"}
            ).status_code
            for i in range(3)
        ]
    assert statuses == [201, 201, 429]
    assert len(app.state.recipe_publisher.calls) == 2


def test_rate_limiter_window_expiry_and_memory():
    now = [1000.0]
    limiter = SubmissionRateLimiter(clock=lambda: now[0])
    key_a = limiter.client_key(ipaddress.ip_network("198.51.100.1"))
    key_b = limiter.client_key(ipaddress.ip_network("198.51.100.2"))
    limits = {"per_client": 1, "aggregate": 2, "window": 60}

    assert limiter.check(key_a, **limits).allowed
    refused = limiter.check(key_a, **limits)
    assert (refused.allowed, refused.retry_after) == (False, 60)
    assert limiter.check(key_b, **limits).allowed
    now[0] += 59.5
    assert limiter.check(key_a, **limits).retry_after == 1
    now[0] += 0.5
    assert limiter.check(key_a, **limits).allowed
    assert list(limiter._clients) == [key_a]
    assert b"198.51.100.1" not in key_a


# Turnstile verification


def turnstile(handler):
    return TurnstileVerifier(transport=httpx.MockTransport(handler))


def test_turnstile_sends_secret_and_token_with_bounded_timeout(
    client, app, monkeypatch
):
    seen = {}

    def handler(request):
        seen["form"] = dict(httpx.QueryParams(request.content.decode()))
        seen["timeout"] = request.extensions["timeout"]
        return httpx.Response(200, json={"success": True, "hostname": "example.com"})

    monkeypatch.setenv("TURNSTILE_TIMEOUT_SECONDS", "2.5")
    app.state.turnstile_verifier = turnstile(handler)
    assert post_json(client, payload()).status_code == 201
    assert seen["form"] == {"secret": TEST_SECRET, "response": "XXXX.DUMMY.TOKEN.XXXX"}
    assert set(seen["timeout"].values()) == {2.5}


class SlowTurnstileStream(httpx.AsyncByteStream):
    async def __aiter__(self):
        yield b'{"success'
        await asyncio.sleep(0.1)
        yield b'":'
        await asyncio.sleep(0.1)
        yield b"true"
        await asyncio.sleep(0.1)
        yield b"}"

    async def aclose(self):
        pass


def test_turnstile_total_deadline_rejects_slow_stream_without_publishing(
    client, app, monkeypatch
):
    monkeypatch.setenv("TURNSTILE_TIMEOUT_SECONDS", "0.25")
    app.state.turnstile_verifier = TurnstileVerifier(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, stream=SlowTurnstileStream())
        )
    )

    response = post_json(client, payload())

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "turnstile_unavailable"
    assert app.state.recipe_publisher.calls == []


def raise_timeout(request):
    raise httpx.ReadTimeout("timed out", request=request)


def raise_connect_error(request):
    raise httpx.ConnectError("unreachable", request=request)


@pytest.mark.parametrize(
    ("handler", "status", "code"),
    [
        (
            lambda r: httpx.Response(
                200, json={"success": False, "error-codes": ["invalid-input-response"]}
            ),
            403,
            "turnstile_failed",
        ),
        (
            lambda r: httpx.Response(
                200, json={"success": False, "error-codes": ["timeout-or-duplicate"]}
            ),
            403,
            "turnstile_failed",
        ),
        (
            lambda r: httpx.Response(
                200, json={"success": False, "error-codes": ["invalid-input-secret"]}
            ),
            503,
            "turnstile_unavailable",
        ),
        (
            lambda r: httpx.Response(
                200, json={"success": False, "error-codes": ["internal-error"]}
            ),
            503,
            "turnstile_unavailable",
        ),
        (
            lambda r: httpx.Response(200, json={"success": False}),
            503,
            "turnstile_unavailable",
        ),
        (
            lambda r: httpx.Response(200, json={"success": "true"}),
            503,
            "turnstile_unavailable",
        ),
        (
            lambda r: httpx.Response(500, json={"success": True}),
            503,
            "turnstile_unavailable",
        ),
        (lambda r: httpx.Response(200, text="<html>"), 503, "turnstile_unavailable"),
        (raise_timeout, 503, "turnstile_unavailable"),
        (raise_connect_error, 503, "turnstile_unavailable"),
    ],
)
def test_turnstile_fails_closed(client, app, monkeypatch, handler, status, code):
    app.state.turnstile_verifier = turnstile(handler)
    response = post_json(client, payload())
    assert response.status_code == status
    assert response.json()["detail"]["code"] == code
    assert TEST_SECRET not in response.text
    assert app.state.recipe_publisher.calls == []
    assert client.get("/api/healthz").status_code == 200


# Publisher composition


@pytest.mark.parametrize(("retryable", "status"), [(True, 503), (False, 502)])
def test_publish_errors_are_explicit(client, app, monkeypatch, retryable, status):
    publisher = FakePublisher(
        PublishError("GitHub is unavailable.", retryable=retryable)
    )
    app.state.recipe_publisher = publisher
    response = post_json(client, payload())
    assert response.status_code == status
    assert response.json()["detail"] == {
        "code": "publish_failed",
        "message": "GitHub is unavailable.",
        "retryable": retryable,
    }
