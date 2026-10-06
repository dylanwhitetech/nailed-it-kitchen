# Copilot Instructions: Nailed It Kitchen

This file is the **source of truth** for how Copilot (and humans) work in this repo.
`AGENTS.md` only points here. Path-specific rules live in `.github/instructions/`.

## What this repo is

Nailed It Kitchen is a recipe app for the adulting millennial, served at
`https://naileditkitchen.dylanlabs.dev` from a Raspberry Pi k3s cluster (arm64).
Recipes are displayed as a "Cooking for Engineers" style **grid** (ingredients on the
left, actions combining them to the right).

Status: **planning complete, application code not started.** Work is tracked as
GitHub issues `[S00]`–`[S42]`, in order. Start at the pinned `[S00] Getting started roadmap` issue.

## Stack (decided, do not change without an issue)

| Area | Choice |
|------|--------|
| Frontend | React + Vite + TypeScript, npm, Oxlint, Vitest, served by `nginx-unprivileged` |
| Backend | FastAPI on Python 3.12, Ruff, pytest, SQLAlchemy + Alembic |
| Database | PostgreSQL via the CloudNativePG operator (one `Cluster` per app) |
| Recipes | YAML files in `recipes/*.yaml`, validated by a JSON Schema in CI |
| Containers | Multi-arch (amd64/arm64) images on GHCR; Docker Desktop + `docker compose` for local dev; k3s runs them with containerd |
| Deploy | Helm chart in `deploy/chart/`, released as OCI chart, promoted to `dylanwhitetech/k3s-infrastructure` (Flux) |
| Ingress | Cloudflare Tunnel → ingress-nginx. TLS ends at Cloudflare. |
| Spam control | Cloudflare Turnstile + API rate limiting. No user accounts in v1. |
| GitHub from API | GitHub App `naileditkitchen-bot` (issues: write only) |

## Repo layout (planned)

```text
frontend/        React + Vite app
backend/         FastAPI app, Alembic migrations, recipe seeder
recipes/         Recipe YAML (source of truth for content) + schema
recipes/source/  Original free-text recipes used as golden test fixtures
deploy/chart/    Helm chart
docs/            Architecture, operations, runbooks, API
observability/   Grafana dashboards
.github/         Copilot agents, skills, instructions, templates, workflows
```

## Working rules

1. **Issue first.** Every change maps to an issue. Use the `gh-issue-drafter` skill to create one.
2. **Test locally before pushing.** Follow the README section "Run & test locally (Docker)".
   Once the `local-preflight` skill exists (issue S16), run it before every PR.
3. **PRs** use the `gh-pr-drafter` skill: the PR template, a Conventional Commit title
   (`feat:`, `fix:`, `docs:`, `chore:`, `ci:` ...), `Closes #N`, and the trailer
   `Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>` on commits made by Copilot.
4. **Never merge to `main` yourself.** A human from CODEOWNERS approves and merges.
5. **No secrets** in code, issues, PRs or logs. Secrets live in SOPS in k3s-infrastructure
   or in GitHub repo secrets. Use placeholders in examples.
6. **Codify everything.** Any manual change (cluster, Cloudflare, GitHub settings) must end
   up as code or docs. If you or a human did something by hand, open an issue to codify it:
   cluster/platform → `dylanwhitetech/k3s-infrastructure`; app/chart → this repo.
7. **Public repo, private contributions.** Only collaborators open issues/PRs. The public sends
   recipes and feedback through the app, never directly on GitHub.

## Copilot customization rules (sourcing rule)

When creating or changing an agent, skill or instructions file:

1. Follow the official GitHub docs and list them under `## References` in the file.
2. Search [github/awesome-copilot](https://github.com/github/awesome-copilot) first. If something
   fits, copy and adapt it, and keep a `Source:` link to the upstream file (MIT, keep attribution).
   Only write from scratch if nothing fits, and say so in the PR.
3. Use the `copilot-author` agent for this work. Details: `.github/instructions/copilot-customization.instructions.md`.

## Agents and skills

| Name | Type | Use it for |
|------|------|-----------|
| `naileditkitchen-dev` | agent | Default for all development work |
| `copilot-author` | agent | Creating or updating agents, skills, instructions |
| `naileditkitchen-code-review` | agent | Local review before you push (cheap pinned model) |
| `naileditkitchen-k3s-ops` | agent | Read-only cluster triage for the app (local only, needs kubeconfig) |
| `gh-issue-drafter` | skill | Drafting and opening issues with our templates, labels, epics, dependencies |
| `gh-pr-drafter` | skill | Drafting and opening PRs with our template and conventions |

Planned (as issues): `local-preflight` skill (S16), `recipe-grid-author` skill (S18).

## References

- Repository custom instructions: https://docs.github.com/en/copilot/how-tos/configure-custom-instructions/add-repository-instructions
- Custom agents configuration: https://docs.github.com/en/copilot/reference/custom-agents-configuration
- About agent skills: https://docs.github.com/en/copilot/concepts/agents/about-agent-skills
- Structure adapted from awesome-copilot `skills/copilot-instructions-blueprint-generator`:
  https://github.com/github/awesome-copilot/tree/main/skills/copilot-instructions-blueprint-generator
