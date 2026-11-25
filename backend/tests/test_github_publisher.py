"""Mocked GitHub API tests for the restricted recipe PR publisher.

No test contacts GitHub. A stateful fake implements only the endpoints the
publisher is allowed to use, so any other endpoint (issues, labels, workflows,
merges) fails the test.
"""

import base64
import json
import logging
import re
from datetime import UTC, datetime
from urllib.parse import unquote

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from backend.app.config import Settings
from backend.app.github_publisher import (
    AppCredentials,
    GitHubAPIError,
    GitHubClient,
    PublisherConfigError,
    PublisherConflictError,
    PublisherPermissionError,
    RateLimitedError,
    RecipeCollisionError,
    RecipePublisher,
    TransientGitHubError,
    prepare_recipe_change,
)
from recipes.validate import (
    RecipeError,
    dump_recipe_yaml,
    load_recipe_yaml,
    validate_recipe,
)

REPO = "owner/kitchen"
APP_ID = 1234
INSTALLATION_ID = 5678
BODY = "## Recipe\n\nPR body rendered by the submission endpoint."
SECRET_INGREDIENT = "1 cup unmistakable-secret-ingredient"
RECIPE = {
    "slug": "test-bread",
    "title": "Test Bread",
    "ingredients": ["2 cups flour", SECRET_INGREDIENT],
    "instructions": ["Mix.", "Bake."],
}


@pytest.fixture(scope="module")
def key_pair():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    return pem, key.public_key()


class Clock:
    def __init__(self):
        self.now = 1_800_000_000.0
        self.sleeps = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class FakeGitHub:
    """In-memory GitHub subset; ``inject`` queues failures for matching requests."""

    def __init__(self, public_key, clock):
        self.public_key = public_key
        self.clock = clock
        self.base_files = {"recipes/existing.yaml": b"slug: existing\n"}
        self.branches = {}
        self.extra_compare_files = {}
        self.pulls = []
        self.tokens = {}
        self.minted = 0
        self.jwt_claims = []
        self.granted = {
            "contents": "write",
            "pull_requests": "write",
            "metadata": "read",
        }
        self.token_permissions = None
        self.token_lifetime = 3600
        self.requests = []
        self.injected = []

    def inject(self, method, pattern, *outcomes, after=False):
        """Queue outcomes (responses or exceptions); ``after`` applies the real effect first."""
        for outcome in outcomes:
            self.injected.append((method, re.compile(pattern), outcome, after))

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = unquote(request.url.path)
        self.requests.append((request.method, path, dict(request.url.params)))
        for index, (method, pattern, outcome, after) in enumerate(self.injected):
            if method == request.method and pattern.search(path):
                del self.injected[index]
                if after:
                    self.route(request, path)
                if isinstance(outcome, Exception):
                    raise outcome
                return outcome
        return self.route(request, path)

    def route(self, request, path):
        if path == f"/app/installations/{INSTALLATION_ID}/access_tokens":
            return self.mint(request)
        auth = request.headers.get("authorization", "")
        token = auth.removeprefix("Bearer ")
        if self.tokens.get(token, 0) <= self.clock():
            return httpx.Response(401, json={"message": "Bad credentials"})
        prefix = f"/repos/{REPO}"
        assert path.startswith(prefix), path
        path = path[len(prefix) :]
        body = json.loads(request.content) if request.content else None
        method = request.method

        if method == "GET" and path == "/git/ref/heads/main":
            return httpx.Response(200, json={"object": {"sha": "base-sha"}})
        if path.startswith("/contents/"):
            file_path = path.removeprefix("/contents/")
            if method == "GET":
                content = self.files(request.url.params["ref"]).get(file_path)
                if content is None:
                    return httpx.Response(404, json={"message": "Not Found"})
                return httpx.Response(
                    200,
                    json={
                        "type": "file",
                        "content": base64.b64encode(content).decode(),
                    },
                )
            if method == "PUT":
                assert "sha" not in body, "publisher must never update an existing file"
                branch = body["branch"]
                if file_path in self.files(branch):
                    return httpx.Response(
                        422, json={"message": '"sha" wasn\'t supplied.'}
                    )
                self.branches[branch][file_path] = base64.b64decode(body["content"])
                return httpx.Response(201, json={"content": {"path": file_path}})
        if method == "GET" and path.startswith("/git/matching-refs/heads/"):
            prefix = path.removeprefix("/git/matching-refs/heads/")
            return httpx.Response(
                200,
                json=[
                    {"ref": f"refs/heads/{name}"}
                    for name in self.branches
                    if name.startswith(prefix)
                ],
            )
        if method == "POST" and path == "/git/refs":
            name = body["ref"].removeprefix("refs/heads/")
            assert body["sha"] == "base-sha"
            if name in self.branches:
                return httpx.Response(422, json={"message": "Reference already exists"})
            self.branches[name] = {}
            return httpx.Response(201, json={"ref": body["ref"]})
        if method == "GET" and path.startswith("/compare/main..."):
            branch = path.removeprefix("/compare/main...")
            files = [
                {"filename": name, "status": "added"} for name in self.branches[branch]
            ] + self.extra_compare_files.get(branch, [])
            return httpx.Response(200, json={"files": files})
        if path == "/pulls" and method == "GET":
            params = request.url.params
            assert params["head"].startswith("owner:")
            head = params["head"].removeprefix("owner:")
            return httpx.Response(
                200,
                json=[
                    pull
                    for pull in self.pulls
                    if pull["head"] == head and pull["state"] == params["state"]
                ],
            )
        if path == "/pulls" and method == "POST":
            if any(
                p["head"] == body["head"] and p["state"] == "open" for p in self.pulls
            ):
                return httpx.Response(
                    422, json={"message": "A pull request already exists"}
                )
            number = len(self.pulls) + 1
            pull = {
                **body,
                "number": number,
                "state": "open",
                "html_url": f"https://github.com/{REPO}/pull/{number}",
            }
            self.pulls.append(pull)
            return httpx.Response(201, json=pull)
        raise AssertionError(f"publisher used a forbidden endpoint: {method} {path}")

    def mint(self, request):
        claims = jwt.decode(
            request.headers["authorization"].removeprefix("Bearer "),
            self.public_key,
            algorithms=["RS256"],
            issuer=str(APP_ID),
            options={"verify_exp": False, "verify_iat": False},
        )
        self.jwt_claims.append(claims)
        requested = json.loads(request.content)
        assert requested["repositories"] == ["kitchen"]
        if any(self.granted.get(k) != v for k, v in requested["permissions"].items()):
            return httpx.Response(422, json={"message": "permissions not granted"})
        self.minted += 1
        token = f"ghs_fake_token_{self.minted}"
        expires = self.clock() + self.token_lifetime
        self.tokens[token] = expires
        return httpx.Response(
            201,
            json={
                "token": token,
                "expires_at": datetime.fromtimestamp(expires, UTC)
                .isoformat()
                .replace("+00:00", "Z"),
                "permissions": self.token_permissions or requested["permissions"],
                "repositories": [{"full_name": REPO}],
            },
        )

    def files(self, ref):
        if ref == "main":
            return dict(self.base_files)
        return {**self.base_files, **self.branches[ref]}

    def repo_writes(self):
        return [r for r in self.requests if r[0] in {"POST", "PUT", "PATCH", "DELETE"}]


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def github(key_pair, clock):
    return FakeGitHub(key_pair[1], clock)


@pytest.fixture
def make_publisher(key_pair, github, clock):
    def make(**client_options):
        credentials = AppCredentials(APP_ID, INSTALLATION_ID, key_pair[0])
        http = httpx.Client(
            base_url="https://api.github.test",
            transport=httpx.MockTransport(github.handler),
        )
        client = GitHubClient(
            credentials,
            REPO,
            http=http,
            clock=clock,
            sleep=clock.sleep,
            **client_options,
        )
        return RecipePublisher(client, REPO, "main")

    return make


@pytest.fixture
def publisher(make_publisher):
    return make_publisher()


def recipe_branches(github):
    return [name for name in github.branches if name.startswith("recipe/")]


def test_publish_adds_exactly_one_schema_valid_file_and_opens_one_pr(publisher, github):
    result = publisher.publish(RECIPE, pr_body=BODY)

    change = prepare_recipe_change(RECIPE)
    assert result.created
    assert result.path == "recipes/test-bread.yaml"
    assert re.fullmatch(r"recipe/test-bread/[0-9a-f]{16}", result.branch)
    assert github.branches == {result.branch: {result.path: change.content.encode()}}
    stored = load_recipe_yaml(github.branches[result.branch][result.path])
    assert validate_recipe(stored, slug_from_filename="test-bread") == []
    assert stored == RECIPE
    assert [(p["head"], p["base"], p["body"], p["title"]) for p in github.pulls] == [
        (result.branch, "main", BODY, "Add recipe: test-bread")
    ]
    assert result.url == github.pulls[0]["html_url"]
    assert [
        (m, p.removeprefix(f"/repos/{REPO}")) for m, p, _ in github.repo_writes()
    ] == [
        ("POST", f"/app/installations/{INSTALLATION_ID}/access_tokens"),
        ("POST", "/git/refs"),
        ("PUT", "/contents/recipes/test-bread.yaml"),
        ("POST", "/pulls"),
    ]


@pytest.mark.parametrize(
    "override",
    [
        {"slug": "../.github/workflows/x"},
        {"slug": "test-bread.yaml"},
        {"slug": "Test-Bread"},
        {"path": ".github/workflows/evil.yml"},
        {"branch": "main"},
        {"repository": "attacker/repo"},
        {"ingredients": [{"nested": "structure"}]},
    ],
)
def test_public_input_cannot_choose_path_branch_repository_or_structure(
    publisher, github, override
):
    with pytest.raises(RecipeError):
        publisher.publish({**RECIPE, **override}, pr_body=BODY)
    assert github.requests == []


@pytest.mark.parametrize("body", ["", "   ", "x" * 65_537])
def test_invalid_pr_body_is_rejected_before_github(publisher, github, body):
    with pytest.raises(ValueError):
        publisher.publish(RECIPE, pr_body=body)
    assert github.requests == []


def test_existing_recipe_slug_is_a_collision_and_never_overwritten(publisher, github):
    original = b"slug: test-bread\n"
    github.base_files["recipes/test-bread.yaml"] = original

    with pytest.raises(RecipeCollisionError):
        publisher.publish(RECIPE, pr_body=BODY)

    assert github.base_files["recipes/test-bread.yaml"] == original
    assert github.branches == {} and github.pulls == []


def test_pending_submission_with_same_slug_is_a_collision(publisher, github):
    github.branches["recipe/test-bread/0000000000000000"] = {
        "recipes/test-bread.yaml": b"x"
    }
    github.pulls.append(
        {"head": "recipe/test-bread/0000000000000000", "state": "open", "number": 9}
    )

    with pytest.raises(RecipeCollisionError):
        publisher.publish(RECIPE, pr_body=BODY)
    assert len(github.pulls) == 1


def test_stale_branch_without_open_pr_does_not_block_and_similar_slugs_do_not_match(
    publisher, github
):
    github.branches["recipe/test-bread/0000000000000000"] = {
        "recipes/test-bread.yaml": b"x"
    }
    github.branches["recipe/test-bread-rolls/0000000000000000"] = {}
    github.pulls.append(
        {
            "head": "recipe/test-bread-rolls/0000000000000000",
            "state": "open",
            "number": 1,
        }
    )

    result = publisher.publish(RECIPE, pr_body=BODY)

    assert result.created
    assert github.branches["recipe/test-bread/0000000000000000"] == {
        "recipes/test-bread.yaml": b"x"
    }


def test_retrying_after_success_reuses_the_same_pr(publisher, github):
    first = publisher.publish(RECIPE, pr_body=BODY)
    second = publisher.publish(RECIPE, pr_body=BODY)

    assert second == type(first)(**{**first.__dict__, "created": False})
    assert len(github.pulls) == 1
    assert recipe_branches(github) == [first.branch]


@pytest.mark.parametrize("with_file", [False, True])
def test_recovers_from_partial_branch_and_file_creation(publisher, github, with_file):
    change = prepare_recipe_change(RECIPE)
    github.branches[change.branch] = (
        {change.path: change.content.encode()} if with_file else {}
    )

    result = publisher.publish(RECIPE, pr_body=BODY)

    assert result.created and len(github.pulls) == 1
    assert github.branches[change.branch] == {change.path: change.content.encode()}


@pytest.mark.parametrize(
    ("method", "pattern"),
    [("POST", r"/git/refs$"), ("PUT", r"/contents/"), ("POST", r"/pulls$")],
)
def test_ambiguous_timeouts_after_github_applied_a_write_do_not_duplicate(
    publisher, github, method, pattern
):
    github.inject(method, pattern, httpx.ReadTimeout("timed out"), after=True)

    result = publisher.publish(RECIPE, pr_body=BODY)

    assert len(github.pulls) == 1 and result.url == github.pulls[0]["html_url"]
    assert recipe_branches(github) == [result.branch]
    assert len(github.branches[result.branch]) == 1


def test_branch_with_different_file_is_a_conflict_not_an_overwrite(publisher, github):
    change = prepare_recipe_change(RECIPE)
    github.branches[change.branch] = {change.path: b"slug: test-bread\ntitle: Other\n"}

    with pytest.raises(PublisherConflictError):
        publisher.publish(RECIPE, pr_body=BODY)

    assert (
        github.branches[change.branch][change.path]
        == b"slug: test-bread\ntitle: Other\n"
    )
    assert github.pulls == []


def test_branch_with_any_extra_change_is_refused(publisher, github):
    change = prepare_recipe_change(RECIPE)
    github.branches[change.branch] = {}
    github.extra_compare_files[change.branch] = [
        {"filename": ".github/workflows/ci.yml", "status": "modified"}
    ]

    with pytest.raises(PublisherConflictError):
        publisher.publish(RECIPE, pr_body=BODY)
    assert github.pulls == []


def test_app_jwt_is_short_lived_and_installation_token_is_cached_and_refreshed(
    publisher, github, clock
):
    publisher.publish(RECIPE, pr_body=BODY)
    assert github.minted == 1
    (claims,) = github.jwt_claims
    assert claims["iss"] == str(APP_ID)
    assert claims["iat"] <= clock() and claims["exp"] - clock() <= 600
    assert claims["exp"] - claims["iat"] <= 600

    clock.now += 3600 - 301
    publisher.publish(RECIPE, pr_body=BODY)
    assert github.minted == 1, "a token outside the refresh margin is reused"

    clock.now += 2
    publisher.publish(RECIPE, pr_body=BODY)
    assert github.minted == 2, "token within five minutes of expiry must be refreshed"


def test_revoked_token_is_reminted_once(publisher, github):
    publisher.publish(RECIPE, pr_body=BODY)
    github.tokens.clear()

    publisher.publish(RECIPE, pr_body=BODY)
    assert github.minted == 2


def test_repeated_401_fails_explicitly(publisher, github):
    github.inject("GET", r"/git/ref/heads/main", *[httpx.Response(401)] * 2)
    with pytest.raises(PublisherPermissionError):
        publisher.publish(RECIPE, pr_body=BODY)


def test_issues_only_installation_is_never_treated_as_sufficient(publisher, github):
    github.granted = {"issues": "write", "metadata": "read"}

    with pytest.raises(PublisherPermissionError, match="Contents and Pull requests"):
        publisher.publish(RECIPE, pr_body=BODY)
    assert github.repo_writes() == [
        ("POST", f"/app/installations/{INSTALLATION_ID}/access_tokens", {})
    ]


def test_token_with_fewer_permissions_than_required_is_refused(publisher, github):
    github.token_permissions = {"contents": "read", "pull_requests": "write"}
    with pytest.raises(PublisherPermissionError):
        publisher.publish(RECIPE, pr_body=BODY)
    assert github.branches == {}


def test_rejected_app_jwt_fails_explicitly(publisher, github):
    github.inject("POST", r"/access_tokens$", httpx.Response(401))
    with pytest.raises(PublisherPermissionError, match="JWT"):
        publisher.publish(RECIPE, pr_body=BODY)


def test_rate_limit_retry_after_is_honored(publisher, github, clock):
    github.inject("POST", r"/pulls$", httpx.Response(429, headers={"retry-after": "7"}))
    publisher.publish(RECIPE, pr_body=BODY)
    assert clock.sleeps == [7.0]


def test_primary_rate_limit_reset_is_honored(publisher, github, clock):
    headers = {
        "x-ratelimit-remaining": "0",
        "x-ratelimit-reset": str(int(clock() + 12)),
    }
    github.inject("GET", r"/git/ref/heads/main", httpx.Response(403, headers=headers))
    publisher.publish(RECIPE, pr_body=BODY)
    assert clock.sleeps == [12.0]


def test_long_rate_limit_fails_without_waiting(publisher, github, clock):
    github.inject(
        "GET",
        r"/git/ref/heads/main",
        httpx.Response(429, headers={"retry-after": "600"}),
    )
    with pytest.raises(RateLimitedError) as caught:
        publisher.publish(RECIPE, pr_body=BODY)
    assert caught.value.retry_after == 600 and clock.sleeps == []


def test_transient_errors_back_off_within_bounds(publisher, github, clock):
    github.inject(
        "GET",
        r"/git/ref/heads/main",
        httpx.Response(502),
        httpx.ConnectError("refused"),
    )
    publisher.publish(RECIPE, pr_body=BODY)
    assert len(clock.sleeps) == 2 and all(0 < s <= 1.25 for s in clock.sleeps)


def test_persistent_transient_errors_fail_explicitly(publisher, github, clock):
    github.inject("GET", r"/git/ref/heads/main", *[httpx.Response(503)] * 3)
    with pytest.raises(TransientGitHubError, match="HTTP 503 after 3 attempts"):
        publisher.publish(RECIPE, pr_body=BODY)
    assert len(clock.sleeps) == 2


@pytest.mark.parametrize("status", [403, 404])
def test_permanent_errors_are_not_retried(publisher, github, clock, status):
    github.inject(
        "GET",
        r"/git/ref/heads/main",
        httpx.Response(status, headers={"x-github-request-id": "ABC:123"}),
    )
    with pytest.raises((GitHubAPIError, PublisherPermissionError), match="ABC:123"):
        publisher.publish(RECIPE, pr_body=BODY)
    assert clock.sleeps == []


def test_credentials_tokens_and_submitted_text_never_reach_logs_or_errors(
    make_publisher, github, key_pair, caplog
):
    caplog.set_level(logging.DEBUG)
    publisher = make_publisher()
    github.inject("POST", r"/pulls$", httpx.ReadTimeout("timed out"), after=True)
    publisher.publish(RECIPE, pr_body=BODY)
    github.inject("GET", r"/git/ref/heads/main", *[httpx.Response(500)] * 3)
    with pytest.raises(TransientGitHubError) as caught:
        publisher.publish(RECIPE, pr_body=BODY)

    key_body = key_pair[0].splitlines()[1]
    for text in (caplog.text, str(caught.value)):
        for secret in (key_body, "ghs_fake_token", SECRET_INGREDIENT, BODY):
            assert secret not in text
    assert key_body not in repr(AppCredentials(APP_ID, INSTALLATION_ID, key_pair[0]))


def test_credentials_are_read_only_from_settings_and_the_key_file(key_pair, tmp_path):
    key_file = tmp_path / "app.pem"
    key_file.write_text(key_pair[0], encoding="utf-8")
    settings = Settings(
        github_app_id=APP_ID,
        github_app_installation_id=INSTALLATION_ID,
        github_app_private_key_file=key_file,
    )
    assert AppCredentials.from_settings(settings).private_key == key_pair[0]

    with pytest.raises(PublisherConfigError, match="GITHUB_APP_INSTALLATION_ID"):
        AppCredentials.from_settings(Settings(github_app_id=APP_ID))
    with pytest.raises(PublisherConfigError, match="cannot read"):
        AppCredentials.from_settings(
            settings.model_copy(
                update={"github_app_private_key_file": tmp_path / "missing"}
            )
        )
    key_file.write_text("not a key", encoding="utf-8")
    with pytest.raises(PublisherConfigError, match="not an unencrypted PEM"):
        AppCredentials.from_settings(settings)


def test_canonical_yaml_is_what_gets_published():
    change = prepare_recipe_change(RECIPE)
    assert change.content == dump_recipe_yaml(RECIPE)
