# Continuous integration and images

[`.github/workflows/ci.yml`](../.github/workflows/ci.yml) runs on every pull request and on every
push to `main`. It has no path filters, so every check reports on every pull request.
Superseded pull request runs are canceled; each `main` push has its own concurrency group so
another push cannot cancel its pending image publication.

| Check (job name) | Runs on | What it does |
| --- | --- | --- |
| `Backend` | PRs, `main` | Ruff lint and format check, then pytest against a disposable PostgreSQL 17 service. `TEST_DATABASE_URL` is set, so database tests run instead of being skipped. |
| `Frontend` | PRs, `main` | `npm ci`, Oxlint (warnings fail), Vitest, then type check and production build. |
| `Recipes` | PRs, `main` | Validates `recipes/*.yaml` against the plain recipe schema, runs the validator/fixture tests and Ruff. |
| `Helm chart applicability` | PRs, `main` | `helm lint` and `helm template` with pinned Helm (including checks that an unreleased chart or a `latest` tag does not render), then a disposable kind cluster with a pinned CloudNativePG operator runs [`deploy/chart/smoke-test.sh`](../deploy/chart/smoke-test.sh): fresh install, upgrade, backup and rollback. |
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

## Helm chart checks

The `chart` job keeps the name `Helm chart applicability` so the required check keeps its
meaning, and the publish jobs wait for it. It downloads Helm and kind at pinned versions and
verifies their SHA-256 checksums, creates a kind cluster from a digest-pinned node image with an
isolated kubeconfig, installs CloudNativePG chart 0.29.2, loads locally built images under two
tags and runs the smoke test described in the [deployment guide](deployment.md#smoke-test):

1. Fresh install: the Cluster and its credentials are created, the migration/seed Job completes,
   the web page loads, `/api/readyz` is ready and every reviewed recipe is served.
2. Upgrade to the second tag: a new revision Job completes, the previous Job is removed and both
   Deployments roll out to the new images.
3. Backup: a Job created from the backup CronJob writes and verifies a dump.
4. Rollback: a held migration lock keeps the old API serving while the new pod waits for the
   recreated migration Job, even though its historical completion marker exists.

To lint and render locally with Helm 3 (the smoke test needs a disposable cluster):

```bash
helm lint deploy/chart/naileditkitchen --set api.image.tag=dev --set web.image.tag=dev
helm template naileditkitchen deploy/chart/naileditkitchen --set api.image.tag=dev --set web.image.tag=dev
```

## Required checks

The `main` ruleset requires checks to pass on an up-to-date branch, but its required-check list is
empty until an owner adds them in repository settings (see
[repository settings](repo-settings.md#required-ci-checks)).
