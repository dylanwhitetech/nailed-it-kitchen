# 0008: Lightweight agentic baseline

## Status
Accepted

## Context
Copilot customizations had grown into several agents and a long instruction file. Research shows repository overviews in context files do not help agents and add cost, and full Agentic Context Engineering is too heavy for this team.

## Decision
`AGENTS.md` is canonical and holds only rules an agent cannot work out from the code or README; `.github/copilot-instructions.md` points to it. Three agents: `naileditkitchen-main` (entry, plans and delegates, one hop), `naileditkitchen-test`, and `naileditkitchen-deploy`. Code review uses built-in Copilot code review. Learnings are captured as field notes in the session folder (never the repo) for a curator; new skills are created only when a field note or failure shows the need; lasting decisions live in `guidance/`.

## Consequences
- Smaller always-loaded context and fewer files to maintain.
- The main agent is selected per session; no repo file enforces it (README "Selecting the main agent").
- Improvements arrive as small curator PRs instead of ad hoc rewrites.

## References
- [AGENTS.md](../AGENTS.md)
- [copilot-authoring references](../.github/skills/copilot-authoring/references.md)
- [Evaluating AGENTS.md](https://arxiv.org/html/2602.11988v3)
- [Agentic Context Engineering](https://arxiv.org/html/2510.04618v3)
- Issue [#63](https://github.com/dylanwhitetech/nailed-it-kitchen/issues/63)
