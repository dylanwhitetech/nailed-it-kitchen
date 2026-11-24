# Guidance index

Durable decisions for Nailed It Kitchen that should outlive a single pull request: architecture,
stack, deployment, and constraints. Keep one decision per file and link implementation or runbook
docs instead of copying procedures.

**Guidance rules**: check `guidance/README.md` before new scope; create/update a record when a change
introduces/replaces/retires a lasting decision (architecture, stack, deployment, constraints); ship it
in the same PR; supersede rather than delete.

## When to create or update a record

- A change introduces, replaces, or retires a lasting behavior or constraint.
- Future contributors need the rationale to avoid re-litigating the same trade-off.
- The decision affects more than one file, workflow, or runbook.

Do not create a record for routine edits, refactors, or one-off bug fixes. To change a decision, add
a new record and set the old one's status to `Superseded by <id>`.

## Record format

File name: `NNNN-short-kebab-title.md` (next free number).

```markdown
# <id>: <title>

## Status
Accepted | Proposed | Superseded by <id> | Deprecated

## Context
What problem or constraint required a decision?

## Decision
What did we choose?

## Consequences
- Positive and negative follow-on effects.

## References
- Repo docs, manifests, PRs, issues, and upstream docs that justify this record.
```

## Decision map

| Decision | Topic | Affected paths |
| --- | --- | --- |
| [0001-application-stack.md](0001-application-stack.md) | Application stack | `frontend/**`, `backend/**`, container and compose files |
| [0002-recipes-as-yaml-with-json-schema.md](0002-recipes-as-yaml-with-json-schema.md) | Recipes as YAML validated by a JSON Schema | `recipes/**` |
| [0003-github-native-recipe-submissions.md](0003-github-native-recipe-submissions.md) | GitHub-native recipe submissions | `backend/**`, `.github/workflows/**`, `recipes/**` |
| [0004-postgres-on-cloudnativepg.md](0004-postgres-on-cloudnativepg.md) | PostgreSQL on CloudNativePG with local storage and nightly dumps | `backend/**` (migrations), `deploy/chart/**` |
| [0005-gitops-hosting-through-k3s-infrastructure.md](0005-gitops-hosting-through-k3s-infrastructure.md) | GitOps hosting through k3s-infrastructure and Cloudflare Tunnel | `deploy/chart/**`, `.github/workflows/**`, `.github/agents/naileditkitchen-deploy.agent.md` |
| [0006-no-accounts-in-v1.md](0006-no-accounts-in-v1.md) | No user accounts in v1; Turnstile and rate limits | `backend/**`, `frontend/**` |
| [0007-github-app-for-api-github-access.md](0007-github-app-for-api-github-access.md) | GitHub App for API access to GitHub | `backend/**`, `deploy/chart/**` |
| [0008-lightweight-agentic-baseline.md](0008-lightweight-agentic-baseline.md) | Lightweight agentic baseline | `AGENTS.md`, `.github/**`, `guidance/**` |

## References

- Source: format adapted from
  [dylanwhitetech/k3s-infrastructure `guidance/README.md`](https://github.com/dylanwhitetech/k3s-infrastructure/blob/main/guidance/README.md);
  seed records summarize the README "Decisions & why" table (decided during planning; the
  application code is not built yet).
