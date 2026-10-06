---
applyTo: ".github/agents/**,.github/skills/**,.github/instructions/**,.github/ISSUE_TEMPLATE/**,.github/PULL_REQUEST_TEMPLATE/**,.github/copilot-instructions.md,.github/pull_request_template.md,AGENTS.md"
excludeAgent: "code-review"
---

# Copilot customization rules

These rules apply whenever you create or edit a Copilot agent, skill, instructions file, issue form,
or pull request template.

## Sourcing rule

1. **Search awesome-copilot first**: https://github.com/github/awesome-copilot
   (`agents/`, `skills/`, `instructions/`, or https://awesome-copilot.github.com/llms.txt).
2. If something fits, **copy it and adapt it**. Keep a `Source:` link to the exact upstream file
   (awesome-copilot is MIT-licensed; keep attribution).
3. If nothing fits, write from scratch and say so in the PR description.
4. Agent, skill, and instruction files end with a `## References` section linking the official
   GitHub docs they follow. For issue/PR forms, cite the official docs in the related authoring
   instructions or PR description; do not add unsupported form fields for references.

## File locations and format (official)

| Kind | Location | Frontmatter |
|------|----------|-------------|
| Repo-wide instructions | `.github/copilot-instructions.md` | none |
| Path-specific instructions | `.github/instructions/<name>.instructions.md` | `applyTo` (glob), optional `excludeAgent: "code-review"` or `"coding-agent"` |
| Custom agent | `.github/agents/<name>.agent.md` | `description` (required), `name`, `tools`, `model`, `target`, `disable-model-invocation`, `user-invocable` |
| Skill | `.github/skills/<name>/SKILL.md` | `name`, `description` (say *when* to use it) |
| Issue form | `.github/ISSUE_TEMPLATE/*.yml` | GitHub issue form schema |
| Pull request template | `.github/PULL_REQUEST_TEMPLATE/` or `.github/pull_request_template.md` | GitHub PR template format |

- `handoffs` and `argument-hint` work in VS Code only; the cloud agent ignores them.
- `model` is honored in VS Code and the CLI. Always write **why** that model was picked.
- Keep the agent prompt under 30,000 characters. Keep instructions short; long dev-only
  files should set `excludeAgent: "code-review"` so the reviewer doesn't load them.
- Use kebab-case file names. Prefix repo-specific agents with `naileditkitchen-`.

## Checklist

- [ ] Searched awesome-copilot and linked the `Source:` (or noted "written from scratch")
- [ ] Prose customization files have `## References`; a template PR cites its official docs
- [ ] Least tools needed; no secrets
- [ ] Updated the agent/skill table in `.github/copilot-instructions.md` and the README
- [ ] For a form/template change, preserved its user-facing purpose and required fields; changed
      labels deliberately and verified each against the target repository's existing labels

## References

- https://docs.github.com/en/copilot/how-tos/configure-custom-instructions/add-repository-instructions
- https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/creating-issue-forms
- https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/creating-a-pull-request-template-for-your-repository
- Source: this repository-specific instruction is written from scratch; its sourcing and format rules follow the official GitHub documentation above.
- https://docs.github.com/en/copilot/reference/custom-agents-configuration
- https://docs.github.com/en/copilot/how-tos/use-copilot-agents/coding-agent/create-custom-agents
- https://docs.github.com/en/copilot/concepts/agents/about-agent-skills
- https://docs.github.com/en/copilot/how-tos/use-copilot-agents/coding-agent/create-skills
