# 0014: Idempotent recipe PR publisher contract

## Status
Accepted

## Context
[0011](0011-direct-beta-recipe-prs.md) requires one new recipe file per submission,
no overwrites and retry recovery without duplicate PRs. [0012](0012-beta-recipe-pr-permissions.md)
requires short-lived, minimum-permission installation tokens. The publisher needed
concrete rules for naming, collisions, retries, credentials and its caller interface.

## Decision
- Derive the branch from the content: `recipe/<slug>/<SHA-256 prefix of canonical YAML>`.
  The same recipe always resumes the same branch and open PR; the file is always
  `recipes/<slug>.yaml`, added without a blob SHA so GitHub refuses an overwrite.
- Reject a slug that exists on the base branch or has another open submission PR.
  Branches without an open PR do not block. Verify the branch adds exactly one file
  before opening or returning a PR.
- Request each installation token for only the configured repository with only
  Contents and Pull requests write, and refuse tokens that come back broader in
  repositories or narrower in permissions. Read the private key only from a mounted
  file named in settings.
- Retry only transport errors and HTTP 500/502/503/504, three attempts with short
  backoff; honor rate-limit waits up to 30 seconds, otherwise fail with the wait.
- The submission endpoint renders the complete Markdown PR body from the recipe PR
  template and passes it as `pr_body`; the publisher sends it verbatim and fixes the
  title as `Add recipe: <slug>`. The publisher does not depend on the template.
- Errors and logs carry operation, status and GitHub request ID only.

## Consequences
- Two different submissions for the same new slug racing each other can both open
  PRs; the second merge conflicts instead of overwriting, and review decides.
- A closed submission leaves its branch; maintainers delete branches after closing.
- Mocked tests cannot prove real App permissions; production stays disabled until the
  owner verification in [github-app.md](../docs/github-app.md) is recorded.

## References
- [Publisher configuration, permissions and diagnostics](../docs/github-app.md#recipe-pr-publisher)
- [Restricted publisher](https://github.com/dylanwhitetech/nailed-it-kitchen/issues/37)
- [Submission flow and PR template](https://github.com/dylanwhitetech/nailed-it-kitchen/issues/39)
- [Human permission gate](https://github.com/dylanwhitetech/nailed-it-kitchen/issues/71)
- [Creating an installation access token](https://docs.github.com/en/rest/apps/apps#create-an-installation-access-token-for-an-app)
- [Create or update file contents](https://docs.github.com/en/rest/repos/contents#create-or-update-file-contents)
- [Rate limits for the REST API](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)
