# 0003: GitHub-native recipe submissions

## Status
Accepted

## Context
The public must be able to submit recipes and feedback without accounts or direct GitHub access, and maintainers do not want to build an admin UI or moderation queue.

## Decision
App form, then the API (as `naileditkitchen-bot`) opens a locked issue labeled `recipe:submission`; a maintainer adds `recipe:approved`; a GitHub Action assigns the Copilot cloud agent, which opens a PR adding `recipes/<slug>.yaml`; CI validates; a human merges. App feedback also opens an issue; ratings and "I made this" are stored in Postgres.

## Consequences
- GitHub provides review, history, and automation for free.
- Submissions are public; the form must say so.
- Only collaborators open issues/PRs directly; the public goes through the app.

## References
- [README "How recipe submission works"](../README.md#how-recipe-submission-works)
- [README "Decisions & why"](../README.md#decisions--why)
