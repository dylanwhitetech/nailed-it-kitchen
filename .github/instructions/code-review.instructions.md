---
applyTo: "**"
excludeAgent: "coding-agent"
---

# Code review rules

Be brief. Only comment when it matters.

## Comment on

- Correctness bugs and broken edge cases
- Security: secrets, injection, missing input validation, unsafe auth/token handling, missing Turnstile/rate limit on public endpoints
- Contract breaks: API shape, recipe YAML schema, DB migrations without a downgrade
- Missing or wrong tests for changed behavior
- Manual steps that are not codified (see "Codify everything" in `.github/copilot-instructions.md`)

## Do not comment on

- Style or formatting (Ruff and Oxlint handle this)
- Naming preferences, or anything already passing CI
- Generated files, lockfiles, `recipes/*.yaml` content (CI validates the schema)

## Format

- At most ~10 comments per PR, most important first.
- Each comment: file + line, the problem, a concrete fix.
- No PR summary essays.

## References

- https://docs.github.com/en/copilot/tutorials/customize-code-review
- https://docs.github.com/en/copilot/how-tos/configure-custom-instructions/add-repository-instructions
