# Nailed It Kitchen

A recipe app for the adulting millennial. Recipes are shown as an easy-to-read **grid**
(ingredients on the left, each cooking action combining them to the right), inspired by the
"Cooking for Engineers" recipe card.

**URL:** https://naileditkitchen.dylanlabs.dev (not live yet)

> **Status:** planning is done and application code has not started. Work is tracked in GitHub issues;
> use the pinned **`[S00] Getting started roadmap`** as navigation, not as a mandatory serial queue.
> Follow actual prerequisites and native issue dependencies; safe parallel work is encouraged.
> Issues #30/#31 (legacy `[S29]`/`[S30]`) are v0 foundation work before first deploy.

## Team

- [@dylanwhitetech](https://github.com/dylanwhitetech)
- [@ArthurW2](https://github.com/ArthurW2), Principal Engineer (frontend)

Both of us own the whole repo (see `CODEOWNERS`). Issues are unassigned; pick any ready issue whose
actual prerequisites are complete.

> **Contributions:** this repo is public but does not accept outside issues or PRs.
> Submit recipes and feedback **through the app**.

## Architecture

```mermaid
flowchart LR
  U[User] --> CF[Cloudflare edge + Turnstile] --> T[cloudflared tunnel] --> NG[ingress-nginx]
  NG -->|/| WEB[web: nginx + React/Vite build]
  NG -->|/api| API[api: FastAPI]
  API --> PG[(Postgres via CloudNativePG)]
  API -->|GitHub App| GHI[GitHub Issues]
  GHI -->|label recipe:approved| ACT[Action -> assign Copilot cloud agent]
  ACT --> PR[PR adds recipes/*.yaml] --> CI[CI validates schema] --> MERGE[human merge]
  MERGE --> REL[release-please + GHCR images + Helm chart] --> FLUX[Flux in k3s-infrastructure]
  FLUX -->|pre-upgrade Job| SEED[Alembic migrate + seed recipes into PG]
  PG -.nightly pg_dump.-> NFS[(ssd-nfs PVC)]
```

It runs on a 3-node Raspberry Pi 4 (arm64) k3s cluster managed with Flux in
[dylanwhitetech/k3s-infrastructure](https://github.com/dylanwhitetech/k3s-infrastructure).

## Decisions & why

| Area | Decision | Why |
|------|----------|-----|
| Frontend | React + Vite + TypeScript, Oxlint, Vitest | React is the most common UI library, so help and components are easy to find. Vite gives instant dev reloads and simple builds. TypeScript catches mistakes early. Oxlint and Vitest are fast and fit Vite. |
| Backend | FastAPI (Python 3.12), Ruff, pytest | Typed and fast, generates OpenAPI docs automatically, and Python keeps the API simple. Ruff and pytest are the standard fast lint/test tools. |
| Database | PostgreSQL via the CloudNativePG operator, SQLAlchemy + Alembic | Real relational data (recipes, ingredients, ratings) plus built-in full-text search. CNPG manages Postgres on Kubernetes (failover, backups, status) and can be reused by future apps. Alembic gives versioned migrations. |
| DB storage | `local-path` volume pinned to one node + nightly `pg_dump` to NFS | Running Postgres directly on NFS risks corruption. Local disk is safe and fast; the nightly dump on the NFS share is the backup. |
| Recipe format | YAML files in `recipes/`, checked by a JSON Schema | Recipes are code: reviewable in PRs, versioned, and easy for Copilot to write. The schema keeps the grid renderer simple and safe. |
| Recipe submissions | GitHub-native: form → issue → `recipe:approved` label → Copilot cloud agent opens a PR → CI → human merge | No admin UI or moderation queue to build. GitHub gives review, history and automation for free. |
| Feedback | Ratings and "I made this" in Postgres; app feedback opens an issue | Quick signals live with the data; real feedback lands where we work. |
| Accounts | None in v1; Cloudflare Turnstile + API rate limits | No passwords or personal data to protect. Turnstile blocks bots without annoying captchas. |
| Photos | Not in v1 | Keeps storage and moderation simple; a research issue covers it later. |
| Containers | Docker Desktop for local dev; multi-arch (amd64/arm64) images on GHCR; k3s runs them with containerd | The same images run on laptops, in CI and on the Pis. `docker compose` starts the whole stack locally with one command. |
| Hosting | Helm chart → OCI on GHCR → Flux in k3s-infrastructure; Cloudflare Tunnel → ingress-nginx | GitOps: the cluster state is in git and every change is a reviewed PR. The tunnel avoids opening home ports and Cloudflare handles TLS. |
| GitHub from the API | GitHub App `naileditkitchen-bot` (issues: write only) | Narrow permissions and short-lived tokens instead of a personal token. |
| Styling | Decided by @ArthurW2 (issue S14) | Our frontend expert picks the approach. |
| AI-first | `AGENTS.md` rules plus Copilot agents, skills and instructions in `.github/`; decisions in `guidance/` | Copilot follows the same rules as humans, and anyone can hand it an issue. |

## How recipe submission works

1. Someone fills in the **Submit a recipe** form in the app (free text is fine). Turnstile checks they're human.
2. The API (as `naileditkitchen-bot`) opens a GitHub issue labeled `recipe:submission` and locks it.
   *Submissions are public; the form says so.*
3. A maintainer reads it and adds the `recipe:approved` label.
4. A GitHub Action assigns the **Copilot cloud agent**, which uses the `recipe-grid-author` skill to turn the text into `recipes/<slug>.yaml` and opens a PR.
5. CI validates the YAML against the schema; a maintainer reviews and merges.
6. release-please ships a release; Flux deploys it; a pre-upgrade Job migrates the DB and seeds the new recipe.

## v1 scope

**In:** browse recipes, search + tag filter (Postgres full-text search), grid recipe view (mobile-friendly),
submit-a-recipe form, app feedback form, star ratings and "I made this".

**Out (Future):** photos, user accounts, comments, servings scaling, print view, in-browser AI recipe conversion.

## Run & test locally (Docker)

> **Placeholder:** the real commands land with issue **S15** (docker-compose). Keep this section accurate;
> S15 is only done when these commands work exactly as written.

**Do this before every push.**

1. Install and start **Docker Desktop**. Check it works: `docker compose version`.
2. Copy `.env.example` to `.env` (no real secrets needed locally).
3. Start everything: `docker compose up --build`
   - Web: http://localhost:8080
   - API: http://localhost:8000 (docs at http://localhost:8000/docs)
   - Postgres: `localhost:5432`
4. Run the tests (exact commands added in S12/S13/S16; the `local-preflight` skill runs them all).
5. Reset the database: `docker compose down -v`

## AI-first workflow

Everything Copilot needs is in the repo, so it works the same in VS Code, the GitHub Copilot app,
the Copilot CLI and the Copilot cloud agent on GitHub.

| File | What it does |
|------|--------------|
| `AGENTS.md` | Canonical rules for agents and humans (source of truth). `.github/copilot-instructions.md` points to it. |
| `guidance/` | Lasting decisions (architecture, stack, deployment). Check before new work; update in the same PR. |
| `.github/instructions/*.instructions.md` | Extra rules for certain paths (code review, Copilot authoring). |
| `.github/agents/naileditkitchen-main.agent.md` | **Main agent: start every session with it.** Plans, implements, and delegates. |
| `.github/agents/naileditkitchen-test.agent.md` | Writes and runs tests (background subagent or its own session). |
| `.github/agents/naileditkitchen-deploy.agent.md` | Releases, promotion PRs to k3s-infrastructure, read-only rollout checks. |
| `.github/skills/gh-issue-drafter/` | Drafts from the target repo's actual issue form and reconciles labels, epics, dependencies, and Project fields. |
| `.github/skills/gh-pr-drafter/` | Issue-prefixed branch/PR names, Conventional Commit messages, and the PR template. |
| `.github/skills/visual-explanation/` | Explains a topic with a concise visual or focused, accessible HTML artifact. |
| `.github/skills/field-notes/` | Records agentic learnings/blockers in the session folder (never the repo) for a curator. |
| `.github/skills/copilot-authoring/` | Standards for agents, skills, instructions and templates, plus the resource catalogue `references.md`. |

Code review uses the built-in Copilot code review on GitHub, guided by
`.github/instructions/code-review.instructions.md`.

[`AGENTS.md`](AGENTS.md) defines our shared engineering standards and sourced code-documentation
rules: Google-style Python docstrings, TSDoc for reusable TypeScript/React APIs, and intentional
FastAPI/Helm documentation.
Branch names and PR titles use `<type>/<issue-number>-<short-hyphenated-description>`
(e.g. `feat/1234-add-feature-x`), with only `feat`, `fix`, `cicd`, or `chore`.
Commit messages separately follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/).
Existing session-managed branches are not renamed. For squash merges, the human merger
must use a Conventional Commit message rather than the slash-form PR title.

### Selecting the main agent

No repository file can make `naileditkitchen-main` the automatic default; each surface starts
with its built-in agent until you pick one. The agent has `disable-model-invocation: true`, so
Copilot never picks it on its own. Select it per session:

| Surface | How |
|---------|-----|
| GitHub Copilot app | Agent picker in the prompt box, or type `/agent` and choose `naileditkitchen-main`. |
| Copilot CLI | `copilot --agent naileditkitchen-main`, or `/agent` inside a session. |
| VS Code | Agent dropdown in Copilot Chat. |
| Cloud agent on GitHub.com | Pick it from the agent dropdown in the agents panel/tab, or when assigning an issue to Copilot (only after the file is on the default branch). |

**New to agentic work? Try this:**

1. **VS Code:** open the repo, open Copilot Chat, pick **naileditkitchen-main** from the agent dropdown, and say
   "Work on issue #<n>". It reads the issue and guidance, writes code, and delegates tests to `naileditkitchen-test`.
2. **GitHub Copilot app / CLI:** open the repo, select the `naileditkitchen-main` agent (`/agent`), and give it the issue.
3. **Cloud agent on GitHub:** on an issue marked `Copilot-ready? yes`, assign it to **Copilot** and pick `naileditkitchen-main`. It opens a PR for you to review.
4. Always review the PR yourself. Copilot code review also comments automatically.
## Repo layout (planned)

```text
frontend/        React + Vite app
backend/         FastAPI app, Alembic migrations, recipe seeder
recipes/         Recipe YAML + JSON Schema
recipes/source/  Original recipes used as test fixtures
deploy/chart/    Helm chart
docs/            Architecture, operations, runbooks, API
guidance/        Lasting decisions (one record per decision)
observability/   Grafana dashboards
.github/         Copilot agents, skills, instructions, templates, workflows
```

## Related repos

- [dylanwhitetech/k3s-infrastructure](https://github.com/dylanwhitetech/k3s-infrastructure): cluster, Flux, Cloudflare Tunnel, CloudNativePG, secrets
