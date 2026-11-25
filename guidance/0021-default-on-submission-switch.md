# 0021: Default-on submission switch

## Status
Accepted

## Context
The recipe submission feature is intended to be available when its dependencies are ready.
The previous default-off switch required an additional opt-in even after configuration.

## Decision
Supersede the default-off decision in [0015](0015-submission-protection.md). The API and local
Compose default `SUBMISSIONS_ENABLED` to `true`; setting it to `false` still pauses submissions.
All other protections in 0015 remain in force: missing or invalid Turnstile configuration or a
publisher keeps submissions unavailable, and server-side validation, rate limits and human
review are still required.

The current Helm chart separately sets `submissions.enabled` to `false`, overriding the API
default. Aligning that chart setting requires the chart owner's confirmed change. Do not change
a live deployment as part of this decision; the production verification gates still apply.

## Consequences
- Configured environments can accept submissions without an extra switch opt-in.
- Unconfigured environments fail closed; an explicit `false` preserves the operational pause.
- API/local and chart defaults differ until the chart setting is aligned.

## References
- [Submission protection](0015-submission-protection.md)
- [Direct recipe submissions](0011-direct-beta-recipe-prs.md)
- [Submission guide](../docs/submissions.md)
