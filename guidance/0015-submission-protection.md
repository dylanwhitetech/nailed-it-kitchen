# 0015: Beta submission protection and off switch

## Status
Accepted

## Context
Beta has no accounts ([0006](0006-no-accounts-in-v1.md)) and turns public submissions into
recipe PRs ([0011](0011-direct-beta-recipe-prs.md)). Protections must hold on the server before
expensive parsing or GitHub writes, must fail closed, and must never take browsing down.

## Decision
- `SUBMISSIONS_ENABLED` defaults false. Submissions are available only when the switch is on,
  the Turnstile keys are configured and a publisher is installed; otherwise the API refuses them
  before reading the body. A minimal public availability endpoint drives the UI notice.
- Exact limits: request body 32 KiB (32,768 bytes) and recipe content 20,000 characters.
- Cheap checks run first: switch, content type, declared size, client identity, rate limit,
  bounded body read, strict JSON, validation, Turnstile, then publishing.
- `CF-Connecting-IP` is trusted only from configured proxy CIDRs; `X-Forwarded-For` is ignored
  and Uvicorn runs with `--no-proxy-headers`.
- Per-client and aggregate sliding-window limits live in process memory, keyed by hashed
  networks. This is a deliberate beta simplicity trade-off: no new datastore is introduced.
- Turnstile is verified server-side with a bounded timeout; only explicit success passes.
- Unsafe controls and executable-looking markup are rejected; human review remains required.

## Consequences
- Limits multiply with replicas and reset on restart; beta runs one API process or lowers limits.
  Shared limits would need a new decision and datastore.
- Enabling the switch publishes nothing until the publisher is wired in.
- Changing the switch is a GitOps config rollout; in-flight requests finish.

## References
- [Submission protection issue](https://github.com/dylanwhitetech/nailed-it-kitchen/issues/38)
- [Recipe submissions guide](../docs/submissions.md)
- [Cloudflare Turnstile server-side validation](https://developers.cloudflare.com/turnstile/get-started/server-side-validation/)
- [Uvicorn proxy settings](https://www.uvicorn.org/deployment/#proxies-and-forwarded-headers)
