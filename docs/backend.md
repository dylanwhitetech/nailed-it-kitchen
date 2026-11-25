# Backend foundation

The Python 3.12 FastAPI service exposes `/api/healthz` (process liveness), `/api/readyz`
(a PostgreSQL `SELECT 1` with a three-second connection timeout), `/api/metrics` (Prometheus
request counts by method/status and request-duration histogram), and `/api/docs` (OpenAPI UI).
Metrics contain no URL, recipe, or visitor labels and reset when the process restarts.
Liveness does not depend on the database; readiness returns HTTP 503 when configuration or
the database is unavailable. Reading and searching recipes are not implemented yet.

Set `DATABASE_URL` to a SQLAlchemy `postgresql+psycopg://` URL, supplying credentials securely
through the environment. Do not commit credentials. With no URL, liveness still works, while
readiness and database commands fail. The deployment must provide database credentials; this
service does not read `.env` files on its own.

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
.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

**Downgrade to base deletes the recipe table and all its data.** Only run it on a disposable
database or as part of a deliberate recovery procedure with a tested backup. The combined
`python -m backend.app.manage` command upgrades to head and then seeds, and is the command
intended for the future Compose and Helm migration/seed job. It exits nonzero on any failure.
This does not verify production migration ordering, readiness, or deployment behavior.

Database integration tests require `TEST_DATABASE_URL` pointing to a **dedicated disposable
PostgreSQL database**. Those tests create and drop tables; never use a shared or production
database. The database role must be able to create and drop a temporary schema. Without
`TEST_DATABASE_URL`, database tests are explicitly skipped. `DATABASE_URL` configures the API and
commands, independently of `TEST_DATABASE_URL`.

Build the image from the repository root with `docker build -f backend/Dockerfile -t nik-api .`.
It contains the validator, schema and reviewed recipe files, runs as a non-root user on port
8000, and can be built for amd64 or arm64. For the image's migration/seed job use
`python -m backend.app.manage` as the container command with `DATABASE_URL` supplied securely.
Compose and Helm orchestration are not implemented yet.

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
