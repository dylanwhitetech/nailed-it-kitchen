"""Render recipe PR bodies and adapt the GitHub App publisher to the submission endpoint.

The submission endpoint calls :meth:`GitHubRecipeSubmissions.publish` only after the
availability switch, size caps, rate limits, validation, the unsafe-text scan and Turnstile
have passed, so the rendered "Automated validation" section lists exactly those checks.

The PR body comes from ``.github/PULL_REQUEST_TEMPLATE/recipe.md``. Submitted text is placed
in a fenced code block so GitHub never renders it as Markdown: mentions, issue references,
links, images, HTML and task-list boxes in a recipe stay inert text.
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from backend.app.config import GitHubPublisherSettings
from backend.app.github_publisher import (
    PublisherConfigError,
    PublisherError,
    RateLimitedError,
    RecipeCollisionError,
    RecipePublisher,
    TransientGitHubError,
)
from backend.app.submissions import PublishError, RecipeConflict
from recipes.validate import (
    MAX_CONTENT_CHARS,
    RecipeError,
    content_length,
    format_paste_template,
    validate_recipe,
)

logger = logging.getLogger(__name__)

TEMPLATE_PATH = (
    Path(__file__).resolve().parents[2]
    / ".github"
    / "PULL_REQUEST_TEMPLATE"
    / "recipe.md"
)
RECIPE_MARKER = "<!-- nik:recipe -->"
CHECKS_MARKER = "<!-- nik:checks -->"
_BACKTICK_RUN = re.compile(r"`+")

RETRY_MESSAGE = (
    "GitHub is busy right now. Please try submitting again in a few minutes."
)
CONFLICT_MESSAGE = (
    "A recipe with this title already exists or is waiting for review. "
    "Change the title and submit again."
)
FAILURE_MESSAGE = "The recipe could not be sent for review. Please try again later."


def load_template(path: Path = TEMPLATE_PATH) -> str:
    """Read the recipe PR template and check it has each marker exactly once.

    Raises:
        OSError: The template cannot be read.
        ValueError: A marker is missing or repeated.
    """
    template = path.read_text(encoding="utf-8")
    for marker in (RECIPE_MARKER, CHECKS_MARKER):
        if template.count(marker) != 1:
            raise ValueError(f"{path.name} must contain {marker} exactly once")
    return template


def _fence(text: str) -> str:
    longest = max((len(run) for run in _BACKTICK_RUN.findall(text)), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}text\n{text}\n{fence}"


def render_pr_body(recipe: Mapping[str, Any], template: str) -> str:
    """Fill the recipe PR template for one normalized, valid recipe.

    Args:
        recipe: Recipe including the server-derived slug.
        template: Text returned by :func:`load_template`.

    Returns:
        Deterministic Markdown: the same recipe always renders the same body.

    Raises:
        RecipeError: The recipe is invalid.
    """
    problems = validate_recipe(recipe)
    if problems:
        raise RecipeError(problems)
    slug = recipe["slug"]
    checks = "\n".join(
        [
            "- Recipe schema and normalization (`recipes/validate.py`): passed",
            (
                f"- Content length: {content_length(recipe):,} of "
                f"{MAX_CONTENT_CHARS:,} characters"
            ),
            (
                "- Unsafe-text scan (control and invisible characters, "
                "HTML-like markup, script or data URLs, `${{`): passed"
            ),
            "- Cloudflare Turnstile human check: verified",
            "- Per-client and aggregate submission rate limits: passed",
            f"- Change: one new file `recipes/{slug}.yaml` on branch `recipe/{slug}`",
        ]
    )
    return template.replace(
        RECIPE_MARKER, _fence(format_paste_template(recipe))
    ).replace(CHECKS_MARKER, checks)


class GitHubRecipeSubmissions:
    """Submission-endpoint publisher backed by the GitHub App :class:`RecipePublisher`.

    Retries are idempotent: the same recipe renders the same body, and the underlying
    publisher reuses the open pull request for the same content.
    """

    def __init__(self, publisher: RecipePublisher, template: str) -> None:
        self._publisher = publisher
        self._template = template

    async def publish(self, recipe: dict[str, Any]) -> str:
        """Open (or reuse) the recipe pull request and return its URL.

        Raises:
            RecipeConflict: The slug already exists or awaits review with other content.
            PublishError: Any other failure; ``retryable`` is set for transient GitHub
                outages and rate limits. Messages never include GitHub details.
        """
        try:
            body = render_pr_body(recipe, self._template)
            result = await asyncio.to_thread(
                self._publisher.publish, recipe, pr_body=body
            )
        except RecipeCollisionError:
            raise RecipeConflict(CONFLICT_MESSAGE) from None
        except (TransientGitHubError, RateLimitedError) as exc:
            logger.warning("Recipe PR publishing is temporarily unavailable: %s", exc)
            raise PublishError(RETRY_MESSAGE, retryable=True) from None
        except (PublisherError, RecipeError, ValueError) as exc:
            logger.error(
                "Recipe PR publishing failed (%s): %s", type(exc).__name__, exc
            )
            raise PublishError(FAILURE_MESSAGE, retryable=False) from None
        logger.info("Recipe PR %s (created=%s)", result.number, result.created)
        return result.url

    def close(self) -> None:
        """Release the publisher's HTTP client."""
        self._publisher.close()


def build_submissions_publisher() -> GitHubRecipeSubmissions | None:
    """Build the publisher when the GitHub App is configured, otherwise return ``None``.

    Missing ``GITHUB_APP_ID`` means publishing is intentionally not configured. Any other
    configuration problem is logged and also returns ``None``, so submissions stay
    unavailable (fail closed) instead of crashing the read-only site.
    """
    try:
        settings = GitHubPublisherSettings()
    except ValidationError as exc:
        fields = sorted(
            {str(error["loc"][0]) for error in exc.errors() if error["loc"]}
        )
        logger.error("Invalid GitHub publisher configuration: %s", ", ".join(fields))
        return None
    if settings.github_app_id is None:
        logger.info("GitHub App publisher is not configured; submissions unavailable")
        return None
    try:
        template = load_template(TEMPLATE_PATH)
        publisher = RecipePublisher.from_settings(settings)
    except (PublisherConfigError, OSError, ValueError) as exc:
        logger.error("Recipe publisher unavailable: %s", exc)
        return None
    return GitHubRecipeSubmissions(publisher, template)
