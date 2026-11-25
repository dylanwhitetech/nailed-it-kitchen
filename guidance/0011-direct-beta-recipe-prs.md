# 0011: Direct protected recipe PR submissions

## Status
Accepted

## Context
The former issue -> approval label -> Copilot conversion -> PR process in 0003 adds
moderation stages and agent credentials that are not needed for a plain recipe.
The owner chose a deterministic paste template and editable preview, not arbitrary
prose or AI extraction.

## Decision
Supersede [0003](0003-github-native-recipe-submissions.md). The planned app flow is:
paste one title/Ingredients/Instructions block -> editable preview -> confirmation ->
server validation/Turnstile/rate limits -> one recipe-file PR -> CI -> human review/merge
-> release/promotion -> Flux -> Postgres seeding.

Disclose public GitHub publication and request no submitter identity. Enforce a
32 KiB request cap, a 20,000-character recipe-content cap, bounded fields and both
per-client and aggregate rate limits before GitHub writes. Validate on the server;
ambiguous or malformed input is rejected rather than guessed. Safe serialization,
parameterized queries and escaped rendering prevent execution; no text scan proves
that a submission is harmless, so human review remains required.

The server generates safe paths/branches and adds exactly one new recipe file,
never workflows or overwrites. Recover partial/retried requests without duplicate
PRs. The success response links the actual created PR; external failures are explicit.

The original default-off switch decision is superseded by
[0021](0021-default-on-submission-switch.md). Helm/env configuration can disable submissions
without breaking reading/search; the UI reflects server availability. Implementation must
document in-flight request handling and the operator redeploy procedure.

## Consequences
- No issue creation, approval label, AI provider or Copilot conversion in beta.
- A dedicated recipe Markdown PR template includes actual validation and unchecked
  human review items. App-generated recipe-only PRs do not need a synthetic issue
  or software-change issue-prefix/Closes convention.
- That narrow exception never covers software, configuration or workflow changes.
- Keep ordinary CI and privileged release jobs isolated from untrusted recipe data.
- The template and endpoint are planned, not implemented by this scope decision.

## References
- [Submission contract](https://github.com/dylanwhitetech/nailed-it-kitchen/issues/39)
- [Protections and switch](https://github.com/dylanwhitetech/nailed-it-kitchen/issues/38)
- [Restricted publisher](https://github.com/dylanwhitetech/nailed-it-kitchen/issues/37)
- [Creating PR templates](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/creating-a-pull-request-template-for-your-repository)
- [No accounts; server protection](0006-no-accounts-in-v1.md)
