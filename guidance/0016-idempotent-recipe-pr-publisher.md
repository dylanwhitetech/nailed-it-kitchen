# 0016: Idempotent recipe PR publisher contract

## Status
Accepted

## Context
[0011](0011-direct-beta-recipe-prs.md) requires one new recipe file per submission,
no overwrites and retry recovery without duplicate PRs. [0012](0012-beta-recipe-pr-permissions.md)
requires short-lived, minimum-permission installation tokens. The publisher needed
concrete rules for naming, collisions, retries, credentials and its caller interface.

## Decision
- Reserve one branch per slug: `recipe/<slug>`. The file is always
  `recipes/<slug>.yaml`, added without a blob SHA so GitHub atomically refuses an
  overwrite. Only identical canonical YAML resumes the branch and open PR.
- Reject a slug that exists on the base branch or has different content on its
  submission branch, whether or not a PR is open. Verify the branch adds exactly
  one file before opening or returning a PR.
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
- Concurrent different-content submissions cannot both publish: GitHub's create-only
  file operation on the shared branch selects one content without an overwrite.
  Identical requests recover via that file and GitHub's unique open head/base PR.
- Partial and closed submissions reserve their content until maintainers close any
  PR and delete the branch with no publisher requests in flight. No shared database
  lock or process-local synchronization is needed.
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
