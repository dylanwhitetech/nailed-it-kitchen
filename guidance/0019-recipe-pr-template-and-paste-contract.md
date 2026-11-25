# 0019: Recipe PR template and shared paste contract

## Status
Accepted

## Context
[0011](0011-direct-beta-recipe-prs.md) chose a deterministic paste template, an editable
preview and app-opened recipe PRs reviewed with a dedicated Markdown template.
[0016](0016-idempotent-recipe-pr-publisher.md) left the PR body to the submission endpoint.
The browser preview must agree with the server parser, and untrusted recipe text must not
become Markdown, mentions or HTML in the PR.

## Decision
- `.github/PULL_REQUEST_TEMPLATE/recipe.md` is the single review template. The API renders
  every recipe PR body from it, replacing the `<!-- nik:recipe -->` and `<!-- nik:checks -->`
  markers, each required exactly once. Recipe text goes inside a code fence longer than any
  backtick run in it. Reviewer checkboxes stay unchecked and there is no `Closes #N`.
- The API image ships the template. A missing or malformed template, or incomplete publisher
  settings, leaves the publisher unset so submissions stay unavailable.
- The browser parser in `frontend/src/submission/recipeText.ts` mirrors `recipes/validate.py`.
  Golden cases generated from the Python parser (`recipes/tests/paste_cases.json`) run in
  both test suites. The server stays authoritative.
- A slug that is taken returns HTTP 409 `recipe_conflict`, so the submitter changes the title;
  other publisher failures keep `publish_failed` with `retryable`.

## Consequences
- Changing the paste format means updating both parsers and regenerating the golden cases.
- Template edits must keep both markers; tests and startup checks enforce this.
- GitHub shows the template in its UI only after it is merged to the default branch; the API
  reads its own packaged copy.
- Production submissions stay off until the App permissions are verified
  ([github-app.md](../docs/github-app.md#beta-permission-gate)).

## References
- [Submission page, PR body and API](../docs/submissions.md)
- [Submission flow and PR template](https://github.com/dylanwhitetech/nailed-it-kitchen/issues/39)
- [Creating a pull request template](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/creating-a-pull-request-template-for-your-repository)
- [Using query parameters to create a pull request](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/using-query-parameters-to-create-a-pull-request)
- Prior art: [awesome-copilot PR template](https://github.com/github/awesome-copilot/blob/main/.github/pull_request_template.md)
