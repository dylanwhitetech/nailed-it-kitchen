---
name: copilot-authoring
description: "Creates and updates Copilot customizations (custom agents, skills, instruction files, AGENTS.md, issue forms, PR templates) using official GitHub formats, Anthropic skill best practices, and awesome-copilot prior art. Use when adding, changing, or removing any of these files, or when a field note proposes a change to one."
---

# Copilot authoring

Standards for agents, skills, instructions, `AGENTS.md`, issue forms, and PR templates. Keep each
change small, grounded in official docs, and backed by a real need.

## Authoring standards

**Authoring standards** (copilot-authoring skill): official GitHub formats/locations; Anthropic skill
rules; create a skill only after a field note/failure shows the need; prefer editing an existing
agent/skill; awesome-copilot reference-first (existing rule kept); cite sources; least tools.

## Process

1. **Confirm the need.** Name the failure, field note, or user request that drives the change.
   Prefer editing an existing agent, skill, or `AGENTS.md` over adding a file.
2. **Search awesome-copilot first**: https://github.com/github/awesome-copilot (`agents/`, `skills/`,
   `instructions/`, https://awesome-copilot.github.com/llms.txt; list with
   `gh api repos/github/awesome-copilot/contents/<dir>`). If something fits, copy and adapt it and
   keep a `Source:` link to the exact upstream file (MIT; keep attribution). If nothing fits, write
   from scratch and say so in the PR.
3. **Check the official docs** in [references.md](references.md) for current frontmatter and
   locations. Never invent frontmatter fields.
4. **Write the file** (table below), then update every roster that lists it (`AGENTS.md`, README).
   Nothing may point to a removed or renamed file.
5. **Validate**: frontmatter parses as YAML, links resolve, and stale names are gone (`grep`).
6. **Open the PR** with the `gh-pr-drafter` skill, listing the upstream source and docs used.

## File locations and format

| Kind | Location | Frontmatter |
|------|----------|-------------|
| Agent instructions (canonical rules) | `AGENTS.md` | none |
| Repo-wide instructions | `.github/copilot-instructions.md` | none |
| Path-specific instructions | `.github/instructions/<name>.instructions.md` | `applyTo` (glob); optional `excludeAgent: "code-review"` or `"coding-agent"` |
| Custom agent | `.github/agents/<name>.agent.md` | `description` (required); `name`, `tools`, `model`, `target`, `disable-model-invocation`, `user-invocable`, `mcp-servers`, `metadata` |
| Skill | `.github/skills/<name>/SKILL.md` | `name` (matches folder), `description` (required); optional `license`, `allowed-tools` |
| Issue form | `.github/ISSUE_TEMPLATE/*.yml` | GitHub issue form schema |
| PR template | `.github/pull_request_template.md` or `.github/PULL_REQUEST_TEMPLATE/` | none |

## Rules

- **Agents:** state scope, priorities, constraints, and output. Least tools; read-only agents get
  no `edit`. Set `model` only with a written "Why this model" comment and a supported model name.
  `infer` is retired; use `disable-model-invocation` (not auto-picked) and `user-invocable`.
  `handoffs` and `argument-hint` are VS Code only. CLI-only `include-custom-instructions: true` gives
  a subagent `AGENTS.md`. Prompt under 30,000 characters. The file name (without `.agent.md`) is
  the agent ID; use kebab-case with the repo prefix.
- **One hop:** subagents cannot create subagents. Delegation prompts carry complete context.
- **Skills:** `name` is lowercase letters, numbers, and hyphens (max 64). `description` is third
  person, says what it does and when to use it (max 1,024). Keep `SKILL.md` under 500 lines; put
  detail in files one level deep. Only add what the model does not already know.
- **Instructions:** short, self-contained, broadly applicable. Keep only rules an agent cannot work
  out from the code or README; overviews add cost without helping. Long dev-only path instructions
  set `excludeAgent: "code-review"`.
- **Sources:** agent, skill, and instruction files end with `## References` (official docs) and a
  `Source:` line. Issue forms and PR templates cite docs and attribution in the PR description, not
  in the user-facing template. Preserve their purpose and required fields; verify labels exist.
- **New resources:** when the user shares a new agentic resource, append it to
  [references.md](references.md) in the same PR.
- No secrets, private host details, or personal data in any customization.

## Checklist

- [ ] Need is named (field note, failure, or request); existing file edited where possible
- [ ] awesome-copilot searched; `Source:` link or "written from scratch"
- [ ] Frontmatter fields are all in the official docs; YAML parses
- [ ] `## References` present (prose files); rosters in `AGENTS.md` and README updated
- [ ] No dangling links or stale names; least tools; no secrets

## References

- Resource catalogue: [references.md](references.md)
- Source: folds in the previous `copilot-author` agent (adapted from awesome-copilot
  [`agents/custom-agent-foundry.agent.md`](https://github.com/github/awesome-copilot/blob/main/agents/custom-agent-foundry.agent.md) and the
  [`skills/suggest-awesome-github-copilot-agents`](https://github.com/github/awesome-copilot/tree/main/skills/suggest-awesome-github-copilot-agents),
  [`-skills`](https://github.com/github/awesome-copilot/tree/main/skills/suggest-awesome-github-copilot-skills),
  [`-instructions`](https://github.com/github/awesome-copilot/tree/main/skills/suggest-awesome-github-copilot-instructions) skills, MIT)
  and the previous `copilot-customization` instructions (written from scratch from the official docs).
