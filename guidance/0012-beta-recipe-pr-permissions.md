# 0012: GitHub App permissions for recipe-only PRs

## Status
Accepted

## Context
The verified App setup grants Issues write and Metadata read. It does not establish
permission to create recipe branches or open PRs, which the new beta flow requires.

## Decision
Supersede [0007](0007-github-app-for-api-github-access.md) as the target capability
contract, not as evidence that permissions have already changed. Require owner
approval of minimum Contents and Pull requests read/write permissions and the
installation update, restricted to this repository.

Use short-lived installation tokens and the existing secret-management process.
Do not grant workflow modification or administrative permissions. Remove unneeded
capabilities only after checking consumers.

Mocked publisher development can proceed without production permission changes.
The owner must verify a benign recipe-only PR under real repository restrictions
and codify actual results before enabling production submissions. Never disclose
credentials or automatically merge the verification PR.

## Consequences
- A distinct human settings/verification gate is required for launch.
- Preserve historical issue-lockdown evidence without presenting it as a PR test.
- Changing GitHub App settings does not require exposing or regenerating credentials
  unless the actual installation/key situation requires it.
- Software/config changes remain issue-scoped and human-merged.

## References
- [Human permission gate](https://github.com/dylanwhitetech/nailed-it-kitchen/issues/71)
- [Verified setup and planned gate](../docs/github-app.md)
- [Choosing App permissions](https://docs.github.com/en/apps/creating-github-apps/setting-up-a-github-app/choosing-permissions-for-a-github-app)
- [Approving updated permissions](https://docs.github.com/en/apps/using-github-apps/approving-updated-permissions-for-a-github-app)
