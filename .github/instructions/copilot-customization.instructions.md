---
applyTo: ".github/agents/**,.github/skills/**,.github/instructions/**,.github/copilot-instructions.md,AGENTS.md"
excludeAgent: "code-review"
---

# Copilot customization rules

These rules apply whenever you create or edit an agent, skill or instructions file.

## Sourcing rule

1. **Search awesome-copilot first**: https://github.com/github/awesome-copilot
   (`agents/`, `skills/`, `instructions/`, or https://awesome-copilot.github.com/llms.txt).
2. If something fits, **copy it and adapt it**. Keep a `Source:` link to the exact upstream file
   (awesome-copilot is MIT-licensed; keep attribution).
3. If nothing fits, write from scratch and say so in the PR description.
4. Every file ends with a `## References` section linking the official GitHub docs it follows.

## File locations and format (official)

| Kind | Location | Frontmatter |
|------|----------|-------------|
| Repo-wide instructions | `.github/copilot-instructions.md` | none |
| Path-specific instructions | `.github/instructions/<name>.instructions.md` | `applyTo` (glob), optional `excludeAgent: "code-review"` or `"coding-agent"` |
| Custom agent | `.github/agents/<name>.agent.md` | `description` (required), `name`, `tools`, `model`, `target`, `disable-model-invocation`, `user-invocable` |
| Skill | `.github/skills/<name>/SKILL.md` | `name`, `description` (say *when* to use it) |

- `handoffs` and `argument-hint` work in VS Code only; the cloud agent ignores them.
- `model` is honored in VS Code and the CLI. Always write **why** that model was picked.
- Keep the agent prompt under 30,000 characters. Keep instructions short; long dev-only
  files should set `excludeAgent: "code-review"` so the reviewer doesn't load them.
- Use kebab-case file names. Prefix repo-specific agents with `naileditkitchen-`.

## Checklist

- [ ] Searched awesome-copilot and linked the `Source:` (or noted "written from scratch")
- [ ] `## References` lists the official docs
- [ ] Least tools needed; no secrets
- [ ] Updated the agent/skill table in `.github/copilot-instructions.md` and the README

## References

- https://docs.github.com/en/copilot/how-tos/configure-custom-instructions/add-repository-instructions
- https://docs.github.com/en/copilot/reference/custom-agents-configuration
- https://docs.github.com/en/copilot/how-tos/use-copilot-agents/coding-agent/create-custom-agents
- https://docs.github.com/en/copilot/concepts/agents/about-agent-skills
- https://docs.github.com/en/copilot/how-tos/use-copilot-agents/coding-agent/create-skills
