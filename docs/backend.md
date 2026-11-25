# Backend API

The Python 3.12 FastAPI service exposes `/api/healthz` (process liveness), `/api/readyz`
(a PostgreSQL `SELECT 1` with a three-second connection timeout), `/api/metrics` (Prometheus
request counts by method/status and request-duration histogram), and `/api/docs` (OpenAPI UI).
Metrics contain no URL, recipe, or visitor labels and reset when the process restarts.
Liveness does not depend on the database; readiness returns HTTP 503 when configuration or
the database is unavailable. Recipe discovery and detail reads require the configured database
and return HTTP 503 on database failures rather than an empty success.
Submission guards and the submission availability endpoint are described in
[recipe submissions](submissions.md); they never affect liveness or readiness.

Set `DATABASE_URL` to a SQLAlchemy `postgresql+psycopg://` URL, supplying credentials securely
through the environment. Do not commit credentials. With no URL, liveness still works, while
readiness and database commands fail. The deployment must provide database credentials; this
service does not read `.env` files on its own.

## Recipe discovery

`GET /api/recipes` returns `{"items": [...], "next_offset": null}`. Each item includes
`id`, `slug`, `title`, `view_count`, `created_at` and `updated_at`, without the full cooking
text or internal search vector. Timestamps are timezone-aware ISO 8601 strings.

- `limit` defaults to 20 and accepts integers from 1 through 100.
- `offset` defaults to 0 and accepts integers from 0 through PostgreSQL's signed bigint
  maximum (9,223,372,036,854,775,807). Fetch the returned `next_offset`
  with the same `q` and `limit`; null means the last page. The API reads at most `limit + 1`
  rows and does not count or load the whole catalog.
- Pages always sort by PostgreSQL `lower(title)`, then slug, then ID, including search results.
  This is stable for unchanged content; concurrent additions or title changes can shift offset
  boundaries. Browsing is not a frozen catalog snapshot.
- `q` defaults to empty and accepts at most 200 characters before trimming. Empty or
  whitespace-only input browses all recipes. Nonempty input uses the existing GIN search
  index and English `plainto_tsquery`: all searchable words must match somewhere in the title,
  ingredients or instructions. English stemming applies (for example, `bake` matches `baking`);
  stopwords are ignored. Punctuation is parsed as ordinary text, not operators, quoted phrases
  or executable query syntax. Punctuation-only and stopword-only queries return an empty page.
  Source and notes are not searched.

`GET /api/most-viewed` returns a list of the same summaries, sorted by `view_count`
descending, then slug and ID. Its `limit` defaults to 5 and accepts integers from 1 through 10.
Zero-view recipes can appear when there are fewer viewed recipes than the limit. This is a
separate landing-page section; `/api/recipes` remains A-Z, never popularity-sorted.
The separate path leaves every valid recipe slug available for detail reads.
Invalid query bounds/types return HTTP 422. Empty results return an empty list/page.
Typed response schemas and parameters are available at `/api/docs`.

`GET /api/recipes/{slug}` returns the summary metadata plus ordered `ingredients` and
`instructions`, optional plain-text `source`, and optional ordered `notes`. Absent source/notes
are JSON null. It does not expose graph data, tags, ratings or the search vector.
Unknown slugs return HTTP 404.

## Approximate views and read abuse

Each successful detail GET performs one transactional `view_count = view_count + 1` update
and returns the new count. PostgreSQL row locking prevents lost increments under concurrent
reads or content reseeding. Views persist across process restarts and reseeding; reading
does not change content timestamps. Database failures roll back instead of reporting success.
The count describes server detail reads, **not unique people**: retries, crawlers, prefetches
and repeated requests count again. No client identifier, IP address, cookie or browsing history
is stored for counting, and there is no separate public view-write endpoint or browsing CAPTCHA.

List, keyword search, most-viewed, health/readiness, metrics and failed detail requests do not
increment views. HEAD is unsupported (HTTP 405) on recipe routes and never counts. Detail
responses use `Cache-Control: no-store`, so intermediary caches must not replay an old
counter-bearing response. The frontend should fetch detail only when opening a recipe,
not prefetch every result.

The API bounds page output and query length but currently has **no application read-rate
limiter or per-visitor deduplication**. Repeated detail GETs can inflate popularity and consume
database capacity. Before public exposure, operators must configure aggregate read-rate and
bot controls at the Cloudflare/ingress boundary, including `/api/recipes/*`; choose thresholds
from observed traffic/capacity and return 429 on throttled requests before they reach the API.
Read throttling must not require visitor identity storage or a CAPTCHA. These edge controls
and production thresholds are deployment work, not verified by local API tests. Turnstile and
submission write-rate protection remain independent of browsing.

## Local commands

From the repository root, create a Python 3.12 virtual environment and install dependencies:

```bash
python -m venv .venv
.venv/bin/python -m pip install -r backend/requirements-dev.txt
```

On Windows, substitute `.venv\Scripts\python` for `.venv/bin/python`. Start a disposable
PostgreSQL database and set `DATABASE_URL` and `TEST_DATABASE_URL` to its URL before running
database commands and integration tests. For example, replace the placeholders in
`postgresql+psycopg://USER:PASSWORD@HOST:5432/DBNAME`; URL-encode special characters in
credentials. The following all run from the repository root:

```bash
.venv/bin/python -m ruff check backend
.venv/bin/python -m ruff format --check backend
.venv/bin/python -m pytest backend/tests
.venv/bin/python -m alembic -c backend/alembic.ini upgrade head
.venv/bin/python -m backend.app.seed
.venv/bin/python -m alembic -c backend/alembic.ini downgrade base
.venv/bin/python -m backend.app.manage
.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --no-proxy-headers
```

Always pass `--no-proxy-headers`: the submission guards decide which proxy headers to trust (see
[recipe submissions](submissions.md)), and Uvicorn's default rewrites the client address first.

**Downgrade to base deletes the recipe table and all its data.** Only run it on a disposable
database or as part of a deliberate recovery procedure with a tested backup. The combined
`python -m backend.app.manage` command upgrades to head and then seeds, and is the command
used before each Compose API start. It exits nonzero on any failure. The Helm chart's
migration/seed Job runs it as `python -m backend.app.manage --wait-for-database SECONDS`, which
first waits (bounded) for PostgreSQL, holds a PostgreSQL advisory lock while migrating and
seeding, and skips both with a warning when the database schema is newer than the image (a
rollback). Helm supplies paired `LIFECYCLE_INSTALLATION_ID` and `LIFECYCLE_REVISION` environment
variables so the Job records completion for the specific installation and revision.
`python -m backend.app.manage wait-for-schema --timeout SECONDS` exits 0 once the schema is at or
beyond the image's head and, when these variables are present, that completion marker exists. It
is the API pods' init container and checks Kubernetes Job completion for the active revision,
preventing stale markers from bypassing a rollback Job. Both commands exit 1 with a message on
timeout. Without the paired variables, existing Compose behavior is unchanged. See
[deployment](deployment.md) for the ordering.

Database integration tests require `TEST_DATABASE_URL` pointing to a **dedicated disposable
PostgreSQL database**. Those tests create and drop tables; never use a shared or production
database. The database role must be able to create and drop a temporary schema. Without
`TEST_DATABASE_URL`, database tests are explicitly skipped. `DATABASE_URL` configures the API and
commands, independently of `TEST_DATABASE_URL`.

Build the image from the repository root with `docker build -f backend/Dockerfile -t nik-api .`.
It contains the validator, schema and reviewed recipe files, runs as a non-root user on port
8000, and can be built for amd64 or arm64. For the image's migration/seed job use
`python -m backend.app.manage` as the container command with `DATABASE_URL` supplied securely.
Compose runs this command before Uvicorn after Postgres is healthy; failure prevents API/web
readiness. The Helm chart runs the same image as its migration/seed Job. For Docker-only lint and tests use
`docker compose --profile checks run --build --rm backend-checks` from the repository root
after copying `.env.example` to `.env`. This includes the recipe tests and validator and starts
a separate disposable PostgreSQL test service. Stop it with `docker compose --profile checks down`.

## Recipe PR publisher

`backend/app/github_publisher.py` turns one validated recipe into one new
`recipes/<slug>.yaml` file on a server-generated branch and opens a PR for human review.
It is a library for the submission endpoint, not a public route. Callers must apply
Turnstile, rate limits, size limits and the submissions switch first, then call
`RecipePublisher.from_settings().publish(recipe, pr_body=markdown)` with the complete
Markdown PR body rendered from the recipe PR template. Repeating a call with the same
recipe returns the same open PR. Configuration, permissions, retries and diagnostics are
documented in [github-app.md](github-app.md). Tests use a mocked GitHub API and need no
credentials.

The submission integration owns template rendering and its async adapter: invoke this
blocking library in a worker thread, return `PublishResult.url`, and translate typed
`PublisherError` failures into the endpoint's safe error/retry contract. Installing that
adapter is separate from this library; an unconfigured endpoint must remain unavailable.

## Content synchronization and migrations

The seeder validates **all** `recipes/*.yaml` files against the shared recipe contract before
opening a database transaction, then upserts the validated content by slug atomically. An
unchanged row is not updated; a content change preserves its ID, creation time and view count
and updates its modification time. Source and notes are retained as plain text. Removing a
file does **not** delete its database row. Changing a slug creates a new row and leaves the old
one in place; explicitly plan any retirement or redirect separately. An empty recipe directory
or invalid input fails rather than silently emptying or partially updating the database.

To add a later field, update the SQLAlchemy model and generate a revision with
`.venv/bin/python -m alembic -c backend/alembic.ini revision --autogenerate -m "add field"`.
Review and edit the generated upgrade and downgrade, including defaults and any existing-data
transformation; run both directions against disposable PostgreSQL and add focused tests before
deploying. The generated full-text search document uses the English PostgreSQL configuration
and indexes title, ingredient lines, and instruction steps; query code must use the same
configuration.
