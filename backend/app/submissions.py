"""Public recipe submission guards and endpoints.

Every control runs on the server, in this order, before any GitHub write:

1. Availability: ``SUBMISSIONS_ENABLED`` (default off), valid submission configuration and a
   configured recipe publisher. Disabled requests are refused before the body is read.
2. Cheap request checks: JSON content type and a declared ``Content-Length`` within 32 KiB.
3. Client identity from the TCP peer, or ``CF-Connecting-IP`` only from trusted proxy CIDRs.
4. Per-client and aggregate rate limits (in memory, keyed by a per-process HMAC).
5. A bounded body read that stops at 32 KiB even without a truthful ``Content-Length``.
6. Strict JSON parsing, recipe normalization and validation (20,000-character content cap,
   field bounds, no control characters or executable markup).
7. Fail-closed Cloudflare Turnstile verification with a bounded timeout.
8. The publisher (``app.state.recipe_publisher``) creates the pull request.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import ipaddress
import json
import logging
import math
import re
import secrets
import threading
import time
import unicodedata
from collections import deque
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any, Protocol

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import Field, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from recipes.validate import normalize_line, slugify, validate_recipe

logger = logging.getLogger(__name__)

MAX_REQUEST_BYTES = 32 * 1024
MAX_TURNSTILE_TOKEN_CHARS = 2048
TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
RECIPE_FIELDS = ("title", "source", "ingredients", "instructions", "notes")
REQUEST_FIELDS = ("recipe", "turnstile_token")

# C0/C1 controls except tab, which normalizes to a space like other whitespace runs.
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0a-\x1f\x7f-\x9f]")
_ALLOWED_FORMAT_CHARS = {"\u200d"}  # zero-width joiner inside emoji sequences
# A tag start such as "<b", "< /div" or "<!--"; a tag needs a later ">" (see _contains_markup).
_MARKUP_TAG_START = re.compile(r"<\s*(?:/\s*)?[a-z!?]", re.IGNORECASE)
_SCRIPT_URL = re.compile(
    r"\b(?:javascript|vbscript)\s*:|\bdata\s*:\s*[a-z]+/[a-z0-9.+-]+", re.IGNORECASE
)
_WORKFLOW_EXPRESSION = re.compile(r"\$\{\{")
_TURNSTILE_CONFIG_ERRORS = {"missing-input-secret", "invalid-input-secret"}


class SubmissionSettings(BaseSettings):
    """Submission configuration, kept separate so invalid values never affect readiness.

    Attributes:
        submissions_enabled: Server-side switch; defaults off.
        turnstile_site_key: Public widget key returned to the UI.
        turnstile_secret_key: Server-side verification secret; never logged or returned.
        turnstile_timeout_seconds: Total budget for one siteverify call.
        trusted_proxy_cidrs: Comma-separated peer networks whose ``CF-Connecting-IP`` is used.
        submission_rate_limit_per_client: Attempts per client network per window.
        submission_rate_limit_aggregate: Attempts across all clients per window.
        submission_rate_limit_window_seconds: Sliding window length.
    """

    model_config = SettingsConfigDict(extra="ignore")

    submissions_enabled: bool = False
    turnstile_site_key: str = ""
    turnstile_secret_key: SecretStr = SecretStr("")
    turnstile_timeout_seconds: float = Field(default=5.0, gt=0, le=30)
    trusted_proxy_cidrs: str = ""
    submission_rate_limit_per_client: int = Field(default=3, ge=1, le=1000)
    submission_rate_limit_aggregate: int = Field(default=20, ge=1, le=100_000)
    submission_rate_limit_window_seconds: int = Field(default=3600, ge=1, le=86_400)

    def trusted_networks(
        self,
    ) -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]:
        """Parse ``trusted_proxy_cidrs``.

        Raises:
            ValueError: An entry is not a valid IP network.
        """
        return tuple(
            ipaddress.ip_network(entry.strip(), strict=True)
            for entry in self.trusted_proxy_cidrs.split(",")
            if entry.strip()
        )


class PublishError(Exception):
    """A publisher could not create the pull request.

    Attributes:
        message: Text safe to show the submitter (no tokens, keys or raw responses).
        retryable: Whether the same submission may be retried later.
    """

    def __init__(self, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.message = message
        self.retryable = retryable


class RecipePublisher(Protocol):
    """Creates exactly one recipe pull request; set on ``app.state.recipe_publisher``."""

    async def publish(self, recipe: dict[str, Any]) -> str:
        """Publish a validated recipe and return the created pull request URL.

        Args:
            recipe: Normalized, schema-valid recipe including the server-derived slug.

        Raises:
            PublishError: The pull request was not created.
        """
        ...


class TurnstileRejected(Exception):
    """Cloudflare rejected the token (invalid, expired or already used)."""


class TurnstileUnavailable(Exception):
    """Verification could not complete (timeout, outage, bad response or misconfiguration)."""


class TurnstileVerifier:
    """Verifies Turnstile tokens with Cloudflare's siteverify API and fails closed."""

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._transport = transport

    async def verify(
        self, token: str, secret: SecretStr, timeout_seconds: float
    ) -> None:
        """Verify one token.

        Raises:
            TurnstileRejected: Cloudflare reported the token as invalid.
            TurnstileUnavailable: No definitive success could be obtained.
        """
        if not secret.get_secret_value():
            raise TurnstileUnavailable("secret not configured")
        try:
            async with asyncio.timeout(timeout_seconds):
                async with httpx.AsyncClient(
                    transport=self._transport, timeout=timeout_seconds
                ) as client:
                    response = await client.post(
                        TURNSTILE_VERIFY_URL,
                        data={"secret": secret.get_secret_value(), "response": token},
                    )
                body = response.json()
        except (httpx.HTTPError, ValueError, TimeoutError) as exc:
            raise TurnstileUnavailable(type(exc).__name__) from None
        if response.status_code != 200 or not isinstance(body, dict):
            raise TurnstileUnavailable(f"HTTP {response.status_code}")
        if body.get("success") is True:
            return
        codes = body.get("error-codes")
        codes = (
            {code for code in codes if isinstance(code, str)}
            if isinstance(codes, list)
            else set()
        )
        if not codes or codes & _TURNSTILE_CONFIG_ERRORS or "internal-error" in codes:
            raise TurnstileUnavailable(",".join(sorted(codes)) or "no error codes")
        raise TurnstileRejected(",".join(sorted(codes)))


@dataclass(frozen=True)
class RateLimitDecision:
    """Outcome of a rate-limit check; ``retry_after`` is whole seconds when refused."""

    allowed: bool
    retry_after: int = 0


class SubmissionRateLimiter:
    """Sliding-window per-client and aggregate limits held only in process memory.

    Client keys are HMACs of the client network under a random per-process key, so raw
    addresses are never stored and keys are useless after a restart. Only accepted attempts
    are recorded, which bounds tracked clients by the aggregate limit.
    """

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._key = secrets.token_bytes(32)
        self._lock = threading.Lock()
        self._clients: dict[bytes, deque[float]] = {}
        self._aggregate: deque[float] = deque()

    def client_key(
        self, network: ipaddress.IPv4Network | ipaddress.IPv6Network
    ) -> bytes:
        """Return the opaque in-memory key for a client network."""
        return hmac.new(self._key, str(network).encode(), hashlib.sha256).digest()

    def check(
        self, key: bytes, *, per_client: int, aggregate: int, window: int
    ) -> RateLimitDecision:
        """Record an attempt if both limits allow it; otherwise refuse without recording."""
        with self._lock:
            now = self._clock()
            cutoff = now - window
            _expire(self._aggregate, cutoff)
            for stale in [k for k, v in self._clients.items() if _expire(v, cutoff)]:
                del self._clients[stale]
            history = self._clients.get(key, deque())
            blocking = [
                entries[0] + window
                for entries, limit in (
                    (history, per_client),
                    (self._aggregate, aggregate),
                )
                if len(entries) >= limit
            ]
            if blocking:
                return RateLimitDecision(False, max(1, math.ceil(max(blocking) - now)))
            history.append(now)
            self._clients[key] = history
            self._aggregate.append(now)
            return RateLimitDecision(True)


def _expire(entries: deque[float], cutoff: float) -> bool:
    """Drop timestamps at or before ``cutoff``; return whether none remain."""
    while entries and entries[0] <= cutoff:
        entries.popleft()
    return not entries


router = APIRouter(prefix="/api/submissions", tags=["submissions"])


def _fail(status: int, code: str, message: str, **extra: Any) -> HTTPException:
    headers = extra.pop("headers", None)
    return HTTPException(
        status_code=status,
        detail={"code": code, "message": message, **extra},
        headers=headers,
    )


def _load_settings() -> SubmissionSettings | None:
    try:
        settings = SubmissionSettings()
        settings.trusted_networks()
    except (ValidationError, ValueError) as exc:
        logger.error("Submission configuration is invalid: %s", type(exc).__name__)
        return None
    return settings


def _available_settings(request: Request) -> SubmissionSettings | None:
    """Return settings when new submissions can be accepted, otherwise None."""
    settings = _load_settings()
    if settings is None or not settings.submissions_enabled:
        return None
    if not (
        settings.turnstile_site_key and settings.turnstile_secret_key.get_secret_value()
    ):
        logger.error("Submissions are enabled but Turnstile keys are not configured")
        return None
    if getattr(request.app.state, "recipe_publisher", None) is None:
        logger.error("Submissions are enabled but no recipe publisher is configured")
        return None
    return settings


@router.get("/availability")
def availability(request: Request) -> dict[str, Any]:
    """Report whether new recipe submissions are currently accepted.

    The UI uses this to explain paused submissions; the submission endpoint enforces the
    same check independently. The Turnstile site key is public and only returned when
    submissions are open.
    """
    settings = _available_settings(request)
    return {
        "enabled": settings is not None,
        "turnstile_site_key": settings.turnstile_site_key if settings else None,
    }


def client_network(
    request: Request,
    trusted: Iterable[ipaddress.IPv4Network | ipaddress.IPv6Network],
) -> ipaddress.IPv4Network | ipaddress.IPv6Network:
    """Identify the submitting client network for rate limiting.

    ``CF-Connecting-IP`` is used only when the TCP peer is inside a trusted proxy network;
    otherwise every forwarding header is ignored. IPv6 clients are grouped by /64.

    Raises:
        HTTPException: The address cannot be determined safely (400).
    """
    peer = request.client.host if request.client else ""
    try:
        address = ipaddress.ip_address(peer)
    except ValueError:
        raise _fail(
            400, "client_unidentified", "The client address could not be determined."
        ) from None
    if any(address in network for network in trusted):
        forwarded = request.headers.getlist("cf-connecting-ip")
        try:
            if len(forwarded) != 1:
                raise ValueError("expected exactly one CF-Connecting-IP header")
            address = ipaddress.ip_address(forwarded[0].strip())
        except ValueError:
            raise _fail(
                400,
                "client_unidentified",
                "The client address could not be determined.",
            ) from None
    if isinstance(address, ipaddress.IPv6Address):
        if address.ipv4_mapped is None:
            return ipaddress.ip_network(f"{address}/64", strict=False)
        address = address.ipv4_mapped
    return ipaddress.ip_network(address)


async def read_bounded_body(request: Request, limit: int = MAX_REQUEST_BYTES) -> bytes:
    """Read the request body, refusing it as soon as it exceeds ``limit`` bytes.

    Raises:
        HTTPException: The body is larger than ``limit`` (413).
    """
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > limit:
            raise _fail(
                413,
                "request_too_large",
                f"The request is larger than {limit} bytes.",
            )
        body.extend(chunk)
    return bytes(body)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate key {key!r}")
        result[key] = value
    return result


def _reject_constant(name: str) -> None:
    raise ValueError(f"{name} is not allowed")


def parse_json(body: bytes) -> Any:
    """Parse strict UTF-8 JSON with no duplicate keys or NaN/Infinity.

    Raises:
        HTTPException: The body is not valid JSON (400).
    """
    try:
        return json.loads(
            body.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise _fail(
            400, "invalid_json", "The request body is not valid JSON."
        ) from None


def _text_values(recipe: dict[str, Any]) -> Iterable[tuple[str, str]]:
    for key in ("title", "source"):
        if isinstance(recipe.get(key), str):
            yield key, recipe[key]
    for key in ("ingredients", "instructions", "notes"):
        values = recipe.get(key)
        if isinstance(values, list):
            for index, value in enumerate(values):
                if isinstance(value, str):
                    yield f"{key}[{index}]", value


def _contains_markup(value: str) -> bool:
    """Return whether ``value`` has a tag start followed later by ``>``.

    Bounding the search before the last ``>`` keeps this linear on hostile input such as
    ``"<" + " " * n`` or ``"<!" * n``, instead of rescanning to the end from every ``<``.
    """
    closing = value.rfind(">")
    return closing > 0 and _MARKUP_TAG_START.search(value, 0, closing) is not None


def _unsafe_text_problem(value: str) -> str | None:
    if _CONTROL_CHARS.search(value):
        return "contains a line break or control character; keep each entry on one line"
    if any(
        unicodedata.category(char) == "Cf" and char not in _ALLOWED_FORMAT_CHARS
        for char in value
    ):
        return "contains an invisible formatting character"
    if _contains_markup(value):
        return "contains HTML-like markup; describe it in plain text"
    if _SCRIPT_URL.search(value):
        return "contains a script or data URL"
    if _WORKFLOW_EXPRESSION.search(value):
        return "contains '${{', which is not allowed"
    return None


def normalize_submission(payload: Any) -> tuple[dict[str, Any], str]:
    """Validate the request shape and return the normalized recipe and Turnstile token.

    Text is checked for unsafe content before Unicode/whitespace normalization; the slug is
    derived from the normalized title and the result must pass the recipe-file contract,
    including field bounds and the 20,000-character content cap.

    Raises:
        HTTPException: The request or recipe is invalid (422), with every problem listed.
    """
    if not isinstance(payload, dict):
        raise _fail(422, "invalid_request", "The request must be a JSON object.")
    errors = [
        f"{key}: unknown field" for key in sorted(payload) if key not in REQUEST_FIELDS
    ]
    token = payload.get("turnstile_token")
    if not isinstance(token, str) or not token:
        errors.append("turnstile_token: is required")
    elif len(token) > MAX_TURNSTILE_TOKEN_CHARS:
        errors.append(
            f"turnstile_token: must be at most {MAX_TURNSTILE_TOKEN_CHARS} characters"
        )
    recipe = payload.get("recipe")
    if not isinstance(recipe, dict):
        errors.append("recipe: is required and must be an object")
        raise _fail(422, "invalid_recipe", "The submission is invalid.", errors=errors)
    errors += [
        f"recipe.{key}: is generated by the server"
        if key == "slug"
        else f"recipe.{str(key)[:60]}: unknown field"
        for key in sorted(recipe)
        if key not in RECIPE_FIELDS
    ]
    unsafe = [
        f"recipe.{location}: {problem}"
        for location, value in _text_values(recipe)
        if (problem := _unsafe_text_problem(value))
    ]
    if errors or unsafe:
        raise _fail(
            422, "invalid_recipe", "The submission is invalid.", errors=errors + unsafe
        )

    normalized: dict[str, Any] = {}
    if isinstance(recipe.get("title"), str):
        normalized["slug"] = slugify(normalize_line(recipe["title"]))
    for key in RECIPE_FIELDS:
        if key not in recipe:
            continue
        value = recipe[key]
        if isinstance(value, str):
            value = normalize_line(value)
        elif isinstance(value, list):
            value = [normalize_line(v) if isinstance(v, str) else v for v in value]
        normalized[key] = value
    if normalized.get("slug") == "":
        problems = [
            "recipe.title: must contain at least one ASCII letter or digit for the URL"
        ]
    else:
        problems = [f"recipe.{problem}" for problem in validate_recipe(normalized)]
    if problems:
        raise _fail(
            422, "invalid_recipe", "The submission is invalid.", errors=problems
        )
    return normalized, token


@router.post(
    "",
    status_code=201,
    responses={
        400: {"description": "Malformed JSON or unidentifiable client"},
        403: {"description": "Turnstile verification failed"},
        413: {"description": "Request body larger than 32 KiB"},
        415: {"description": "Content type is not application/json"},
        422: {"description": "Invalid submission; every problem is listed"},
        429: {"description": "Rate limited; see Retry-After"},
        502: {"description": "The pull request could not be created"},
        503: {"description": "Submissions are paused or a dependency is unavailable"},
    },
)
async def submit_recipe(request: Request) -> dict[str, str]:
    """Submit one recipe for public review as a GitHub pull request.

    The body is ``{"recipe": {...}, "turnstile_token": "..."}`` where the recipe has
    ``title``, ``ingredients``, ``instructions`` and optional ``source`` and ``notes``.
    The submission is published publicly on GitHub and reviewed by a human before merge.
    Errors use ``{"detail": {"code", "message", "errors"?}}``.
    """
    settings = _available_settings(request)
    if settings is None:
        raise _fail(
            503,
            "submissions_disabled",
            "Recipe submissions are paused. Browsing and search still work.",
        )
    content_type = request.headers.get("content-type", "")
    if content_type.split(";")[0].strip().lower() != "application/json":
        raise _fail(415, "unsupported_media_type", "Send the submission as JSON.")
    declared = request.headers.get("content-length")
    if declared is not None:
        if not declared.isdigit():
            raise _fail(400, "invalid_content_length", "Content-Length is invalid.")
        if int(declared) > MAX_REQUEST_BYTES:
            raise _fail(
                413,
                "request_too_large",
                f"The request is larger than {MAX_REQUEST_BYTES} bytes.",
            )

    limiter: SubmissionRateLimiter = request.app.state.submission_rate_limiter
    network = client_network(request, settings.trusted_networks())
    decision = limiter.check(
        limiter.client_key(network),
        per_client=settings.submission_rate_limit_per_client,
        aggregate=settings.submission_rate_limit_aggregate,
        window=settings.submission_rate_limit_window_seconds,
    )
    if not decision.allowed:
        raise _fail(
            429,
            "rate_limited",
            "Too many submissions. Please try again later.",
            headers={"Retry-After": str(decision.retry_after)},
        )

    recipe, token = normalize_submission(parse_json(await read_bounded_body(request)))

    verifier: TurnstileVerifier = request.app.state.turnstile_verifier
    try:
        await verifier.verify(
            token, settings.turnstile_secret_key, settings.turnstile_timeout_seconds
        )
    except TurnstileRejected as exc:
        logger.info("Turnstile rejected a submission: %s", exc)
        raise _fail(
            403,
            "turnstile_failed",
            "The human check failed or expired. Please complete it again.",
        ) from None
    except TurnstileUnavailable as exc:
        logger.warning("Turnstile verification unavailable: %s", exc)
        raise _fail(
            503,
            "turnstile_unavailable",
            "The human check could not be verified right now. Please try again later.",
        ) from None

    publisher: RecipePublisher | None = getattr(
        request.app.state, "recipe_publisher", None
    )
    if publisher is None:
        raise _fail(
            503,
            "submissions_disabled",
            "Recipe submissions are paused. Browsing and search still work.",
        )
    try:
        url = await publisher.publish(recipe)
    except PublishError as exc:
        logger.warning("Recipe publishing failed (retryable=%s)", exc.retryable)
        raise _fail(
            503 if exc.retryable else 502,
            "publish_failed",
            exc.message,
            retryable=exc.retryable,
        ) from None
    return {"status": "submitted", "pull_request_url": url}
