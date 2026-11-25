# 0014: Beta dependency and security checks

## Status
Accepted

## Context
The public beta has a small audience, but that is not a security boundary. Its
pip, npm, GitHub Actions and Docker dependencies need routine updates and a PR gate
without adding new services or noisy review load for a two-person team.

## Decision
Use GitHub-native tools only:

- Dependabot version updates run weekly for each manifest that exists, with minor and
  patch updates grouped per ecosystem and major updates kept as separate PRs.
- The dependency review action fails pull requests to `main` that introduce a
  runtime, development or unknown-scope dependency with a high or critical vulnerability.
- Workflows grant the minimum `GITHUB_TOKEN` permissions and pin third-party actions
  to full commit SHAs with a version comment; Dependabot proposes pin updates.
- CodeQL uses repository default setup rather than a committed workflow. Its settings
  are owner-controlled and verified by readback, not inferred from committed files.

## Consequences
- New manifests must be added to `.github/dependabot.yml` when they are introduced.
- Grouped minor/patch PRs still need normal review and passing checks before merge.
- Whether `dependency-review` becomes a required status check is an owner ruleset
  decision recorded in `docs/repo-settings.md`.
- No third-party scanners or extra services are adopted for beta.

## References
- [Essential dependency and security checks](https://github.com/dylanwhitetech/nailed-it-kitchen/issues/23)
- [Repository settings](../docs/repo-settings.md)
- [`.github/dependabot.yml`](../.github/dependabot.yml)
- [`.github/workflows/dependency-review.yml`](../.github/workflows/dependency-review.yml)
- [Usable beta scope](0009-usable-beta-scope.md)
