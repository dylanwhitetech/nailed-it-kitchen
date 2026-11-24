# 0007: GitHub App for API access to GitHub

## Status
Accepted

## Context
The API must open issues for submissions and feedback without a long-lived personal token.

## Decision
Use the GitHub App `naileditkitchen-bot` with only issues: write permission. Its credentials live in SOPS in k3s-infrastructure or in GitHub repo secrets, never in code.

## Consequences
- Narrow permissions and short-lived installation tokens.
- Any new GitHub capability needs a permission change, an issue, and an updated record.

## References
- [README "Decisions & why"](../README.md#decisions--why)
- [About creating GitHub Apps](https://docs.github.com/en/apps/creating-github-apps/about-creating-github-apps/about-creating-github-apps)
