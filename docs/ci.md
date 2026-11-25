# Continuous integration and images

[`.github/workflows/ci.yml`](../.github/workflows/ci.yml) runs on every pull request and on every
push to `main`. It has no path filters, so every check reports on every pull request.

| Check (job name) | Runs on | What it does |
| --- | --- | --- |
| `Backend` | PRs, `main` | Ruff lint and format check, then pytest against a disposable PostgreSQL 17 service. `TEST_DATABASE_URL` is set, so database tests run instead of being skipped. |
| `Frontend` | PRs, `main` | `npm ci`, Oxlint (warnings fail), Vitest, then type check and production build. |
| `Recipes` | PRs, `main` | Validates `recipes/*.yaml` against the plain recipe schema, runs the validator/fixture tests and Ruff. |
| `Helm chart applicability` | PRs, `main` | **Not Helm validation.** Reports "not applicable" while `deploy/chart/` does not exist, and fails once it does until real chart checks replace it. |
| `Image build (api)`, `Image build (web)` | PRs | Buildx builds `linux/amd64` and `linux/arm64` images without pushing them. |
| `Image publish (api)`, `Image publish (web)` | pushes to `main` | After every check above passes, builds both platforms and pushes one tag per image. |

## Published images

Pushes to `main` in `dylanwhitetech/nailed-it-kitchen` publish multi-arch images tagged only with
the full commit SHA:

- `ghcr.io/dylanwhitetech/naileditkitchen-api:<commit-sha>`
- `ghcr.io/dylanwhitetech/naileditkitchen-web:<commit-sha>`

No moving tag such as `latest` is pushed; deployments reference a commit SHA. Each run's summary
records the pushed tag and digest. Builds use each Dockerfile's final stage, so any test or
development stage must come before the production stage. Package visibility and pull access are
owner-controlled GHCR settings and are not changed by the workflow.

## Security model

- Workflow token permissions default to `contents: read`. Only the publish jobs add
  `packages: write`, and only on trusted pushes to `main` in this repository.
- Pull requests use the `pull_request` event only (never `pull_request_target`), so pull request
  code runs without write tokens or repository secrets. No production or App secret is referenced.
- Checkouts do not persist credentials. Third-party Actions and the PostgreSQL service image are
  pinned to full SHAs/digests with the release tag in a comment.
- Recipe files are untrusted data: `recipes/validate.py` parses them with a strict safe YAML loader
  and JSON Schema. No file name or content is interpolated into shell or workflow code.

## Run the same checks locally

Python 3.12, Node.js 24 and Docker (for PostgreSQL and image builds) are required. From the
repository root, with a virtual environment as in the [backend guide](backend.md) (Windows:
substitute `.venv\Scripts\python`):

```bash
# Backend: start a disposable PostgreSQL and point the tests at it.
docker run -d --rm --name nik-test-pg -e POSTGRES_USER=nik -e POSTGRES_PASSWORD=nik \
  -e POSTGRES_DB=nik_test -p 5432:5432 postgres:17-alpine
export TEST_DATABASE_URL=postgresql+psycopg://nik:nik@localhost:5432/nik_test
.venv/bin/python -m pip install -r backend/requirements-dev.txt
.venv/bin/python -m ruff check backend
.venv/bin/python -m ruff format --check backend
.venv/bin/python -m pytest backend/tests -rs
docker stop nik-test-pg

# Recipes
.venv/bin/python -m pip install -r recipes/requirements.txt
.venv/bin/python recipes/validate.py
.venv/bin/python -m pytest recipes
.venv/bin/python -m ruff check recipes && .venv/bin/python -m ruff format --check recipes

# Frontend
(cd frontend && npm ci && npm run lint && npm test && npm run build)

# Multi-arch images (a docker-container builder is needed for multi-platform builds)
docker buildx create --name nik-multiarch --driver docker-container --use
docker buildx build --platform linux/amd64,linux/arm64 -f backend/Dockerfile .
docker buildx build --platform linux/amd64,linux/arm64 -f frontend/Dockerfile frontend
```

The `-rs` flag lists skipped tests; with `TEST_DATABASE_URL` set none should be skipped. The
PostgreSQL container's placeholder credentials are for a throwaway local database only.

## Adding the Helm chart checks

When `deploy/chart/` is added, the same pull request replaces the `Helm chart applicability` job
with real chart checks under the same job name, so the required check keeps its meaning:

1. `helm lint` and `helm template` of the chart with pinned Helm.
2. A fresh-install smoke test in a disposable cluster with a pinned CloudNativePG operator:
   resources and credentials are created, the migration/seed job completes, the API reports
   ready and the web page loads.
3. Upgrade coverage for the migration ordering contract.

Keep the job id `chart` so the publish jobs still wait for it, and update the table above.

## Required checks

The `main` ruleset requires checks to pass on an up-to-date branch, but its required-check list is
empty until an owner adds them in repository settings (see
[repository settings](repo-settings.md#required-ci-checks)).
