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
   For documentation-only changes, run available documentation/customization checks;
   do not claim unavailable application or Docker checks passed.
3. **PRs** use the `gh-pr-drafter` skill, the PR template, the naming convention below,
   and `Closes #N`. Commits follow Conventional Commits, not the PR-title format.
4. **Never merge to `main` yourself.** A human from CODEOWNERS approves and merges.
5. **No secrets** in code, issues, PRs or logs. Secrets live in SOPS in k3s-infrastructure
   or in GitHub repo secrets. Use placeholders in examples.
6. **Codify everything.** Any manual change (cluster, Cloudflare, GitHub settings) must end
   up as code or docs. If you or a human did something by hand, open an issue to codify it:
   cluster/platform → `dylanwhitetech/k3s-infrastructure`; app/chart → this repo.
7. **Public repo, private contributions.** Only collaborators open issues/PRs. The public sends
   recipes and feedback through the app, never directly on GitHub.

## Shared engineering standards

- Keep code, configuration, and workflow changes in Git. Use meaningful names and existing
  patterns/helpers before adding new ones.
- Prefer KISS, DRY, YAGNI, and separation of concerns: small, single-responsibility functions
  and classes, minimal duplication, and solutions that are easy to understand and maintain.
- Avoid speculative abstractions, premature optimization, and shared mutable/global state
  where practical. Update dependencies through focused security/compatibility work, not unrelated upgrades.
- Keep changes scoped to one concern where practical and reversible. Preserve existing contracts
  unless intentionally changing them; update user/operator docs alongside behavior or workflow changes.
- Add or update the smallest relevant tests for changed behavior. Relevant validation must pass
  before merge, and at least one human from CODEOWNERS must review; agents never merge.
- Handle errors explicitly with useful context and appropriate logging or user feedback.
  Do not mask root causes with broad catch-all handlers, silent failures, or success-shaped fallbacks.
- Never expose secrets, credentials, tokens, or sensitive personal data in source, prompts,
  examples, templates, or logs. Use placeholders and avoid private host details.
- Prefer readable code or refactoring over comments. Add concise comments for non-obvious intent,
  constraints, or tradeoffs, not narration of what the code already says.

## Branch, PR title, and commit conventions

New branch names and PR titles use **`<type>/<issue-number>-<short-hyphenated-description>`**,
for example `feat/1234-add-feature-x`. The issue number is the GitHub issue the work is based on,
not a roadmap/story label such as `S12`. Use only `feat` (features), `fix` (bugs),
`cicd` (CI/CD), or `chore` (other maintenance, including docs). Use lowercase kebab-case,
a positive issue number without `#`, and no spaces, underscores, or empty/consecutive hyphens.
The PR type mirrors the branch type, and the PR title matches the branch name when the branch
follows this convention. Existing session-managed branches are exempt from renaming; their
PR titles still follow the convention.

Commit messages follow [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/):
`<type>[optional scope][!]: <short imperative description>`, for example
`feat(api): add recipe search`. Use `feat` for features, `fix` for bug fixes, and appropriate
types such as `docs`, `refactor`, `test`, `build`, `ci`, or `chore` for other changes.
An optional body explains why; mark breaking changes with `!` before the colon or a
`BREAKING CHANGE: <description>` footer. Commit types are independent of the four branch/PR
types: a `cicd/...` branch can contain `ci: ...` commits. Copilot-authored commits include
`Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>` as a final trailer.

Release-please is planned, not configured yet. Slash-form PR titles are not Conventional Commits:
when configuring releases or preparing a squash merge, preserve a Conventional Commit message
on `main` rather than copying the PR title as the squash message. The human merger must set
that message when the merge UI defaults to the PR title.

## Code documentation

- **Python:** use Google-style docstrings and PEP 257 conventions for public modules, classes,
  functions, and non-obvious contracts. Include a summary and applicable `Args`, `Returns`/`Yields`,
  and `Raises` sections. Explain behavior, constraints, side effects, and meaningful exceptions;
  do not repeat type annotations or add boilerplate to trivial code.
- **FastAPI:** document endpoint purpose and public behavior in summaries/descriptions or
  handler docstrings. FastAPI can publish docstrings as OpenAPI descriptions; keep exposed text
  intentional and useful to API consumers, without internal implementation details or secrets.
- **TypeScript/React:** use TSDoc-style `/** ... */` comments for reusable exported components,
  hooks, utilities, and non-obvious props/contracts. Explain semantics, defaults, units,
  constraints, and side effects; use `@param`, `@returns`, `@remarks`, or examples when useful.
  Keep types in TypeScript declarations instead of duplicating JSDoc type declarations.
  React has no separate documentation-comment syntax; avoid boilerplate on trivial components.
- **Helm/YAML:** document each configurable `values.yaml` property with a comment beginning
  with its name. Use Helm template comments for implementation explanations, YAML comments
  only when useful in rendered output, and the recipe schema for recipe content.
- **SQL/migrations/configuration:** explain only non-obvious constraints, transformations,
  rollback assumptions, or operational decisions; do not invent docstrings for declarative files.
- Keep documentation accurate when behavior changes. Do not add documentation generators,
  dependencies, or lint plugins solely to enforce these conventions.

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
| `naileditkitchen-dev` | agent | Manually selected main developer; expanded tools where supported by the host |
| `copilot-author` | agent | Creating or updating agents, skills, instructions |
| `naileditkitchen-code-review` | agent | Local review before you push (cheap pinned model) |
| `naileditkitchen-k3s-ops` | agent | Read-only cluster triage for the app (local only, needs kubeconfig) |
| `gh-issue-drafter` | skill | Drafting and opening issues with our templates, labels, epics, dependencies |
| `gh-pr-drafter` | skill | Issue-prefixed branches/PR titles, Conventional Commit messages, and our PR template |

Planned (as issues): `local-preflight` skill (S16), `recipe-grid-author` skill (S18).

## References

- Repository custom instructions: https://docs.github.com/en/copilot/how-tos/configure-custom-instructions/add-repository-instructions
- Custom agents configuration: https://docs.github.com/en/copilot/reference/custom-agents-configuration
- About agent skills: https://docs.github.com/en/copilot/concepts/agents/about-agent-skills
- Conventional Commits 1.0.0: https://www.conventionalcommits.org/en/v1.0.0/
- Google Python docstrings: https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings
- PEP 257: https://peps.python.org/pep-0257/
- TSDoc: https://tsdoc.org/
- React with TypeScript: https://react.dev/learn/typescript
- FastAPI docstring descriptions: https://fastapi.tiangolo.com/tutorial/path-operation-configuration/#description-from-docstring
- Helm values documentation: https://helm.sh/docs/chart_best_practices/values/
- Helm template comments: https://helm.sh/docs/chart_best_practices/templates/
- Source: Git conventions adapted from awesome-copilot
  [conventional-branch](https://github.com/github/awesome-copilot/blob/main/skills/conventional-branch/SKILL.md)
  and [conventional-commit](https://github.com/github/awesome-copilot/blob/main/skills/conventional-commit/SKILL.md) (MIT).
- Structure adapted from awesome-copilot `skills/copilot-instructions-blueprint-generator`:
  https://github.com/github/awesome-copilot/tree/main/skills/copilot-instructions-blueprint-generator
