---
applyTo: ".github/agents/**,.github/skills/**,.github/instructions/**,.github/ISSUE_TEMPLATE/**,.github/PULL_REQUEST_TEMPLATE/**,.github/PULL_REQUEST_TEMPLATE.md,.github/copilot-instructions.md,.github/pull_request_template.md,AGENTS.md"
excludeAgent: "code-review"
---

# Copilot authoring

Source: written from scratch as a pointer to the `copilot-authoring` skill.

When creating or editing an agent, skill, instruction file, `AGENTS.md`, issue form, or PR template,
follow `.github/skills/copilot-authoring/SKILL.md`: awesome-copilot prior art first, `Source:`
attribution, no invented frontmatter, least tools, and updated rosters. Prose customizations include
official docs under `## References`; cite form and template docs and attribution in the authoring
instructions or PR instead.
Repo-specific agent filenames and IDs use kebab-case with the `naileditkitchen-` prefix.

## References

- https://docs.github.com/en/copilot/how-tos/configure-custom-instructions/add-repository-instructions