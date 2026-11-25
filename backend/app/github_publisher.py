"""Publish one validated recipe as a reviewable pull request through the GitHub App.

The publisher turns already-validated recipe data into exactly one new
``recipes/<slug>.yaml`` file on a server-generated branch and opens one PR against
the configured base branch. Public input never chooses the repository, branch,
path, file structure, PR title or workflow; the caller supplies only recipe data
and the rendered PR body.

Contract for callers (the submission endpoint):

* Call :meth:`RecipePublisher.publish` only after Turnstile, rate limits, size
  limits and the submissions availability switch have passed.
* ``pr_body`` is the complete Markdown PR body, rendered by the caller from the
  recipe PR template. The publisher sends it verbatim and never interprets it.
* Retrying the same recipe is safe: the branch name is derived from the content
  digest, so partial or ambiguous earlier attempts are resumed and an existing open
  PR is returned (``created=False``) instead of a duplicate.
* Every :class:`PublisherError` message is safe to log or show to an operator; it
  never contains credentials, tokens, recipe text or the PR body.

Credentials come only from :class:`backend.app.config.Settings`: the App ID,
installation ID and a mounted private-key file. Installation tokens are requested
with only Contents and Pull requests write for the configured repository, cached
in memory and refreshed before expiry.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import logging
import random
import sys
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
import jwt
from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import serialization

from backend.app.config import Settings
from recipes.validate import (
    RecipeError,
    dump_recipe_yaml,
    load_recipe_yaml,
    validate_file,
    validate_recipe,
)

logger = logging.getLogger(__name__)

API_VERSION = "2022-11-28"
REQUIRED_PERMISSIONS = {"contents": "write", "pull_requests": "write"}
JWT_BACKDATE_SECONDS = 60
JWT_LIFETIME_SECONDS = 540
TOKEN_REFRESH_MARGIN_SECONDS = 300
MAX_PR_BODY_CHARS = 65_536
MAX_PENDING_BRANCHES = 20
TRANSIENT_STATUSES = frozenset({500, 502, 503, 504})
SECONDARY_RATE_LIMIT_WAIT_SECONDS = 60.0
DEFAULT_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


class PublisherError(Exception):
    """Publishing failed; the message is safe to log and contains no secrets or recipe text."""


class PublisherConfigError(PublisherError):
    """The publisher is not configured or its private key cannot be loaded."""


class PublisherPermissionError(PublisherError):
    """GitHub refused the App credentials or the required repository permissions."""


class GitHubAPIError(PublisherError):
    """GitHub returned a permanent, unexpected error.

    Attributes:
        status: The HTTP status code.
    """

    def __init__(self, message: str, status: int) -> None:
        super().__init__(message)
        self.status = status


class TransientGitHubError(PublisherError):
    """Bounded retries were exhausted; the outcome may be unknown, and retrying is safe."""


class RateLimitedError(PublisherError):
    """GitHub rate-limited the request beyond the configured wait.

    Attributes:
        retry_after: Seconds GitHub asked the client to wait.
    """

    def __init__(self, message: str, retry_after: float) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class RecipeCollisionError(PublisherError):
    """A recipe with this slug already exists or another submission for it awaits review."""


class PublisherConflictError(PublisherError):
    """Existing branch state is not exactly this recipe's single new file; nothing was overwritten."""


@dataclass(frozen=True)
class AppCredentials:
    """GitHub App identity used to mint installation tokens."""

    app_id: int
    installation_id: int
    private_key: str = field(repr=False)

    @classmethod
    def from_settings(cls, settings: Settings) -> AppCredentials:
        """Load credentials from settings and the mounted private-key file.

        Raises:
            PublisherConfigError: A setting is missing or the key file is unreadable
                or not an unencrypted PEM private key.
        """
        missing = [
            name
            for name, value in (
                ("GITHUB_APP_ID", settings.github_app_id),
                ("GITHUB_APP_INSTALLATION_ID", settings.github_app_installation_id),
                ("GITHUB_APP_PRIVATE_KEY_FILE", settings.github_app_private_key_file),
            )
            if value is None
        ]
        if missing:
            raise PublisherConfigError(
                f"GitHub App publisher is not configured; missing {', '.join(missing)}"
            )
        try:
            private_key = settings.github_app_private_key_file.read_text(
                encoding="utf-8"
            )
        except (OSError, UnicodeDecodeError) as exc:
            raise PublisherConfigError(
                f"cannot read GITHUB_APP_PRIVATE_KEY_FILE ({type(exc).__name__})"
            ) from None
        try:
            serialization.load_pem_private_key(private_key.encode(), password=None)
        except (ValueError, TypeError, UnsupportedAlgorithm):
            raise PublisherConfigError(
                "GITHUB_APP_PRIVATE_KEY_FILE is not an unencrypted PEM private key"
            ) from None
        return cls(
            settings.github_app_id, settings.github_app_installation_id, private_key
        )


class GitHubClient:
    """Minimal GitHub REST client with installation-token caching and bounded retries.

    Transport errors, timeouts and HTTP 500/502/503/504 are retried with exponential
    backoff up to ``max_attempts``. Primary and secondary rate limits wait for the
    time GitHub requests when it is within ``max_wait_seconds``; otherwise
    :class:`RateLimitedError` is raised immediately. Other statuses are returned
    to the caller unchanged.
    """

    def __init__(
        self,
        credentials: AppCredentials,
        repository: str,
        *,
        api_url: str = "https://api.github.com",
        http: httpx.Client | None = None,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
        max_attempts: int = 3,
        max_wait_seconds: float = 30.0,
    ) -> None:
        self._credentials = credentials
        self._repository = repository
        self._http = http or httpx.Client(
            base_url=api_url, timeout=DEFAULT_TIMEOUT, follow_redirects=False
        )
        self._clock = clock
        self._sleep = sleep
        self._max_attempts = max_attempts
        self._max_wait_seconds = max_wait_seconds
        self._lock = threading.Lock()
        self._token: str | None = None
        self._token_expires_at = 0.0

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._http.close()

    def request(
        self,
        method: str,
        path: str,
        *,
        operation: str,
        json: Any = None,
        params: Mapping[str, str] | None = None,
    ) -> httpx.Response:
        """Send an installation-authenticated request.

        A 401 invalidates the cached token and is retried once with a fresh token.

        Raises:
            PublisherError: Credentials, permissions, rate limits or transient
                failures prevented a usable response.
        """
        for auth_attempt in (1, 2):
            token = self._installation_token()
            response = self._send(
                method,
                path,
                operation=operation,
                authorization=f"Bearer {token}",
                json=json,
                params=params,
            )
            if response.status_code != 401 or auth_attempt == 2:
                return response
            logger.warning(
                "%s: installation token rejected; minting a new one", operation
            )
            with self._lock:
                if self._token == token:
                    self._token = None
        raise AssertionError("unreachable")

    def _installation_token(self) -> str:
        with self._lock:
            now = self._clock()
            if (
                self._token is not None
                and now < self._token_expires_at - TOKEN_REFRESH_MARGIN_SECONDS
            ):
                return self._token
            operation = "mint installation token"
            response = self._send(
                "POST",
                f"/app/installations/{self._credentials.installation_id}/access_tokens",
                operation=operation,
                authorization=f"Bearer {self._app_jwt(now)}",
                json={
                    "repositories": [self._repository.split("/", 1)[1]],
                    "permissions": REQUIRED_PERMISSIONS,
                },
            )
            if response.status_code == 401:
                raise PublisherPermissionError(
                    f"{operation}: GitHub rejected the App JWT; check GITHUB_APP_ID and "
                    f"the private key{_request_id(response)}"
                )
            if response.status_code in {403, 404, 422}:
                raise PublisherPermissionError(
                    f"{operation}: GitHub refused Contents and Pull requests write for "
                    f"{self._repository} (HTTP {response.status_code}); the installation "
                    f"must be granted them (see docs/github-app.md){_request_id(response)}"
                )
            _expect(response, operation, 201)
            try:
                data = response.json()
                token = data["token"]
                expires_at = datetime.fromisoformat(data["expires_at"]).timestamp()
                granted = data.get("permissions") or {}
                repositories = data.get("repositories")
            except (ValueError, KeyError, TypeError):
                raise GitHubAPIError(
                    f"{operation}: unexpected response from GitHub",
                    response.status_code,
                ) from None
            if any(
                granted.get(name) != level
                for name, level in REQUIRED_PERMISSIONS.items()
            ):
                raise PublisherPermissionError(
                    f"{operation}: token lacks Contents and Pull requests write; "
                    f"granted {sorted(granted)}"
                )
            if repositories is not None and [
                repo.get("full_name") for repo in repositories
            ] != [self._repository]:
                raise PublisherPermissionError(
                    f"{operation}: token is not restricted to {self._repository}"
                )
            self._token = token
            self._token_expires_at = expires_at
            logger.info("%s: installation token minted", operation)
            return token

    def _app_jwt(self, now: float) -> str:
        issued_at = int(now) - JWT_BACKDATE_SECONDS
        return jwt.encode(
            {
                "iat": issued_at,
                "exp": int(now) + JWT_LIFETIME_SECONDS,
                "iss": str(self._credentials.app_id),
            },
            self._credentials.private_key,
            algorithm="RS256",
        )

    def _send(
        self,
        method: str,
        path: str,
        *,
        operation: str,
        authorization: str,
        json: Any = None,
        params: Mapping[str, str] | None = None,
    ) -> httpx.Response:
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": authorization,
            "X-GitHub-Api-Version": API_VERSION,
        }
        for attempt in range(1, self._max_attempts + 1):
            last_attempt = attempt == self._max_attempts
            try:
                response = self._http.request(
                    method, path, headers=headers, json=json, params=params
                )
            except httpx.TransportError as exc:
                if last_attempt:
                    raise TransientGitHubError(
                        f"{operation}: GitHub request failed after {attempt} attempts "
                        f"({type(exc).__name__}); the outcome is unknown and the same "
                        "recipe can be resubmitted safely"
                    ) from None
                logger.warning(
                    "%s: %s on attempt %d; retrying",
                    operation,
                    type(exc).__name__,
                    attempt,
                )
                self._sleep(self._backoff(attempt))
                continue

            wait = self._rate_limit_wait(response)
            if wait is not None:
                if wait > self._max_wait_seconds or last_attempt:
                    raise RateLimitedError(
                        f"{operation}: GitHub rate limit; retry after {wait:.0f} seconds"
                        f"{_request_id(response)}",
                        retry_after=wait,
                    )
                logger.warning(
                    "%s: rate limited on attempt %d; waiting %.0f seconds",
                    operation,
                    attempt,
                    wait,
                )
                self._sleep(wait)
                continue

            if response.status_code in TRANSIENT_STATUSES:
                if last_attempt:
                    raise TransientGitHubError(
                        f"{operation}: GitHub returned HTTP {response.status_code} after "
                        f"{attempt} attempts; the same recipe can be resubmitted safely"
                        f"{_request_id(response)}"
                    )
                logger.warning(
                    "%s: HTTP %d on attempt %d; retrying",
                    operation,
                    response.status_code,
                    attempt,
                )
                self._sleep(self._backoff(attempt))
                continue
            return response
        raise AssertionError("unreachable")

    def _backoff(self, attempt: int) -> float:
        return min(self._max_wait_seconds, 0.5 * 2 ** (attempt - 1)) + random.uniform(
            0, 0.25
        )

    def _rate_limit_wait(self, response: httpx.Response) -> float | None:
        if response.status_code not in {403, 429}:
            return None
        retry_after = response.headers.get("retry-after")
        if retry_after is not None:
            try:
                return max(0.0, float(retry_after))
            except ValueError:
                return SECONDARY_RATE_LIMIT_WAIT_SECONDS
        if response.headers.get("x-ratelimit-remaining") == "0":
            try:
                reset = float(response.headers["x-ratelimit-reset"])
            except (KeyError, ValueError):
                return SECONDARY_RATE_LIMIT_WAIT_SECONDS
            return max(0.0, reset - self._clock())
        if response.status_code == 429 or "rate limit" in response.text.lower():
            return SECONDARY_RATE_LIMIT_WAIT_SECONDS
        return None


@dataclass(frozen=True)
class RecipeChange:
    """The single file change a recipe submission produces.

    Attributes:
        slug: Validated recipe slug.
        path: Fixed repository path, ``recipes/<slug>.yaml``.
        branch: Server-generated branch, ``recipe/<slug>/<content digest prefix>``.
        content: Canonical safe YAML for the recipe.
    """

    slug: str
    path: str
    branch: str
    content: str


@dataclass(frozen=True)
class PublishResult:
    """Outcome of a successful publish.

    Attributes:
        url: The pull request's HTML URL.
        number: The pull request number.
        branch: The server-generated head branch.
        path: The added recipe file path.
        created: ``False`` when an existing open PR for the same content was reused.
    """

    url: str
    number: int
    branch: str
    path: str
    created: bool


def prepare_recipe_change(recipe: Mapping[str, Any]) -> RecipeChange:
    """Validate a recipe and derive its fixed path, branch and canonical YAML.

    Raises:
        RecipeError: The recipe is invalid or does not survive safe serialization.
    """
    problems = validate_recipe(recipe)
    if problems:
        raise RecipeError(problems)
    content = dump_recipe_yaml(recipe)
    if load_recipe_yaml(content) != dict(recipe):
        raise RecipeError(["recipe did not survive safe serialization unchanged"])
    slug = recipe["slug"]
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return RecipeChange(
        slug=slug,
        path=f"recipes/{slug}.yaml",
        branch=f"recipe/{slug}/{digest[:16]}",
        content=content,
    )


class RecipePublisher:
    """Create one recipe-file PR per distinct recipe, idempotently."""

    def __init__(self, client: GitHubClient, repository: str, base_branch: str) -> None:
        self._client = client
        self._repository = repository
        self._owner = repository.split("/", 1)[0]
        self._base_branch = base_branch
        self._repo_path = f"/repos/{repository}"

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> RecipePublisher:
        """Build a publisher from environment settings.

        Raises:
            PublisherConfigError: The App credentials are missing or invalid.
        """
        settings = settings or Settings()
        client = GitHubClient(
            AppCredentials.from_settings(settings),
            settings.github_repository,
            api_url=settings.github_api_url,
        )
        return cls(client, settings.github_repository, settings.github_base_branch)

    def close(self) -> None:
        """Release the HTTP client."""
        self._client.close()

    def publish(self, recipe: Mapping[str, Any], *, pr_body: str) -> PublishResult:
        """Publish ``recipe`` as one new file on a new branch and return its PR.

        Args:
            recipe: Recipe data; it is revalidated here.
            pr_body: Complete Markdown PR body (1 to 65,536 characters).

        Returns:
            The created or reused open pull request.

        Raises:
            ValueError: ``pr_body`` is empty or too long.
            RecipeError: The recipe is invalid.
            RecipeCollisionError: The slug exists on the base branch or another
                submission for it is awaiting review.
            PublisherConflictError: Existing branch content differs from this recipe.
            PublisherError: Any other GitHub, permission or configuration failure.
        """
        if not isinstance(pr_body, str) or not pr_body.strip():
            raise ValueError("pr_body must be non-empty Markdown")
        if len(pr_body) > MAX_PR_BODY_CHARS:
            raise ValueError(f"pr_body must be at most {MAX_PR_BODY_CHARS} characters")
        change = prepare_recipe_change(recipe)
        digest = change.branch.rsplit("/", 1)[1]

        base_sha = self._base_sha()
        if self._read_file(change.path, self._base_branch) is not None:
            raise RecipeCollisionError("a recipe with this slug already exists")
        self._reject_pending_submissions(change)
        self._create_branch(change, base_sha)
        self._add_file(change)
        self._verify_single_new_file(change)

        existing = self._find_open_pr(change.branch)
        if existing is not None:
            logger.info("recipe PR reused for content %s", digest)
            return self._result(existing, change, created=False)
        response = self._client.request(
            "POST",
            f"{self._repo_path}/pulls",
            operation="create pull request",
            json={
                "title": f"Add recipe: {change.slug}",
                "head": change.branch,
                "base": self._base_branch,
                "body": pr_body,
                "maintainer_can_modify": False,
            },
        )
        if response.status_code == 422:
            existing = self._find_open_pr(change.branch)
            if existing is not None:
                logger.info("recipe PR reused after ambiguous create for %s", digest)
                return self._result(existing, change, created=False)
        _expect(response, "create pull request", 201)
        logger.info("recipe PR created for content %s", digest)
        return self._result(response.json(), change, created=True)

    def _base_sha(self) -> str:
        operation = "read base branch"
        response = self._client.request(
            "GET",
            f"{self._repo_path}/git/ref/heads/{_quote(self._base_branch)}",
            operation=operation,
        )
        _expect(response, operation, 200)
        return response.json()["object"]["sha"]

    def _read_file(self, path: str, ref: str) -> bytes | None:
        operation = "read recipe file"
        response = self._client.request(
            "GET",
            f"{self._repo_path}/contents/{_quote(path)}",
            operation=operation,
            params={"ref": ref},
        )
        if response.status_code == 404:
            return None
        _expect(response, operation, 200)
        data = response.json()
        if not isinstance(data, dict) or data.get("type", "file") != "file":
            raise PublisherConflictError(f"{path} exists and is not a regular file")
        return base64.b64decode(data.get("content", ""))

    def _reject_pending_submissions(self, change: RecipeChange) -> None:
        operation = "list pending submissions"
        prefix = f"heads/recipe/{change.slug}/"
        response = self._client.request(
            "GET", f"{self._repo_path}/git/matching-refs/{prefix}", operation=operation
        )
        _expect(response, operation, 200)
        others = [
            ref["ref"].removeprefix("refs/heads/")
            for ref in response.json()
            if ref["ref"] != f"refs/heads/{change.branch}"
        ]
        if len(others) > MAX_PENDING_BRANCHES:
            raise RecipeCollisionError(
                "too many submissions with this slug are pending; ask a maintainer to clean up"
            )
        for branch in others:
            if self._find_open_pr(branch) is not None:
                raise RecipeCollisionError(
                    "another submission with this slug is awaiting review"
                )

    def _create_branch(self, change: RecipeChange, base_sha: str) -> None:
        operation = "create branch"
        response = self._client.request(
            "POST",
            f"{self._repo_path}/git/refs",
            operation=operation,
            json={"ref": f"refs/heads/{change.branch}", "sha": base_sha},
        )
        if response.status_code == 422:
            logger.info("create branch: branch already exists; resuming")
            return
        _expect(response, operation, 201)

    def _add_file(self, change: RecipeChange) -> None:
        operation = "add recipe file"
        expected = change.content.encode("utf-8")
        # Omitting "sha" makes GitHub refuse to overwrite an existing file.
        response = self._client.request(
            "PUT",
            f"{self._repo_path}/contents/{_quote(change.path)}",
            operation=operation,
            json={
                "message": f"feat(recipes): add {change.slug}",
                "content": base64.b64encode(expected).decode("ascii"),
                "branch": change.branch,
            },
        )
        if response.status_code in {409, 422}:
            if self._read_file(change.path, change.branch) == expected:
                logger.info("add recipe file: identical file already present; resuming")
                return
            raise PublisherConflictError(
                "the submission branch already has a different file at the recipe path"
            )
        _expect(response, operation, 201)

    def _verify_single_new_file(self, change: RecipeChange) -> None:
        operation = "verify branch diff"
        response = self._client.request(
            "GET",
            f"{self._repo_path}/compare/"
            f"{_quote(self._base_branch)}...{_quote(change.branch)}",
            operation=operation,
        )
        _expect(response, operation, 200)
        files = [
            (item.get("filename"), item.get("status"))
            for item in response.json().get("files", [])
        ]
        if files != [(change.path, "added")]:
            raise PublisherConflictError(
                f"the submission branch does not add exactly one new {change.path}"
            )

    def _find_open_pr(self, branch: str) -> dict[str, Any] | None:
        operation = "find pull request"
        response = self._client.request(
            "GET",
            f"{self._repo_path}/pulls",
            operation=operation,
            params={
                "head": f"{self._owner}:{branch}",
                "base": self._base_branch,
                "state": "open",
                "per_page": "2",
            },
        )
        _expect(response, operation, 200)
        pulls = response.json()
        return pulls[0] if pulls else None

    def _result(
        self, pull: Mapping[str, Any], change: RecipeChange, *, created: bool
    ) -> PublishResult:
        return PublishResult(
            url=pull["html_url"],
            number=pull["number"],
            branch=change.branch,
            path=change.path,
            created=created,
        )


def _quote(value: str) -> str:
    return quote(value, safe="/")


def _request_id(response: httpx.Response) -> str:
    request_id = response.headers.get("x-github-request-id")
    return f" (GitHub request ID {request_id})" if request_id else ""


def _expect(response: httpx.Response, operation: str, *ok: int) -> None:
    if response.status_code in ok:
        return
    if response.status_code in {401, 403}:
        raise PublisherPermissionError(
            f"{operation}: GitHub refused the installation token "
            f"(HTTP {response.status_code}){_request_id(response)}"
        )
    raise GitHubAPIError(
        f"{operation}: GitHub returned HTTP {response.status_code}{_request_id(response)}",
        response.status_code,
    )


VERIFICATION_PR_BODY = """\
Publisher verification PR for a benign recipe file.

Opened by the operator-run publisher check. Review the diff: it must add exactly one
`recipes/<slug>.yaml` file. Close this PR without merging unless it is the real
launch submission.
"""


def main(argv: list[str] | None = None) -> int:
    """Open one real verification PR from a benign recipe file (operator use only).

    Returns:
        0 on success, 1 on any validation or publishing failure.
    """
    parser = argparse.ArgumentParser(
        description="Open a real recipe PR with the configured GitHub App."
    )
    parser.add_argument("recipe", type=Path, help="benign recipes/<slug>.yaml file")
    parser.add_argument(
        "--confirm-real-pr",
        action="store_true",
        required=True,
        help="acknowledge that this writes a branch and PR to GitHub",
    )
    args = parser.parse_args(argv)
    try:
        recipe = validate_file(args.recipe)
        publisher = RecipePublisher.from_settings()
        try:
            result = publisher.publish(recipe, pr_body=VERIFICATION_PR_BODY)
        finally:
            publisher.close()
    except (OSError, RecipeError, PublisherError) as exc:
        print(f"publisher check failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(f"{'created' if result.created else 'reused'} {result.url}")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sys.exit(main())
