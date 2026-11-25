# Recipe submissions

The backend owns every submission protection. The web app only explains when submissions are
paused; hiding the form is never the protection. **Submissions stay unavailable until a GitHub
publisher is configured in the application**, so enabling the switch alone does not publish
anything.

## API contract

`GET /api/submissions/availability` returns `{"enabled": true|false, "turnstile_site_key": ...}`.
The public Turnstile site key is returned only while submissions are available; otherwise it is
`null`. Availability is cheap, touches no database or GitHub and never affects
`/api/healthz` or `/api/readyz`.

`POST /api/submissions` accepts `Content-Type: application/json`:

```json
{
  "recipe": {
    "title": "Recipe title",
    "ingredients": ["First ingredient"],
    "instructions": ["First cooking instruction."],
    "source": "Optional source",
    "notes": ["Optional note"]
  },
  "turnstile_token": "token from the Turnstile widget"
}
```

The server generates the slug from the title; unknown fields, including `slug`, are rejected. Text
is normalized and validated with the shared recipe contract ([recipe format](recipe-format.md)),
including the 20,000-character content limit. Success returns HTTP 201 with
`{"status": "submitted", "pull_request_url": "..."}`.

Errors return `{"detail": {"code": ..., "message": ...}}`; messages are safe to show and never
contain secrets. Checks run in this order, so cheap refusals happen before expensive work:

| Order | Status | `code` | Meaning |
| --- | --- | --- | --- |
| 1 | 503 | `submissions_disabled` | Switch off, configuration invalid/incomplete, or no publisher; the body is not read |
| 2 | 415 | `unsupported_media_type` | Not `application/json` |
| 3 | 400 / 413 | `invalid_content_length` / `request_too_large` | Declared length invalid or above 32,768 bytes |
| 4 | 400 | `client_unidentified` | The client address cannot be determined safely |
| 5 | 429 | `rate_limited` | Per-client or aggregate limit reached; honour `Retry-After` |
| 6 | 413 | `request_too_large` | Streamed body above 32,768 bytes (exactly 32,768 is accepted) |
| 7 | 400 | `invalid_json` | Not UTF-8 JSON, duplicate keys, `NaN`/`Infinity` or excessive nesting |
| 8 | 422 | `invalid_request` / `invalid_recipe` | Wrong shape or invalid recipe; `errors` lists every problem |
| 9 | 403 | `turnstile_failed` | Token invalid, expired or already used; get a new token |
| 10 | 503 | `turnstile_unavailable` | Verification could not complete; nothing is published |
| 11 | 503 / 502 | `publish_failed` | Publisher failed; `retryable` says whether to try again later |

Every request that reaches the rate limiter consumes a slot, even if a later check fails.

### Untrusted text stays data

Text fields reject control characters (including line breaks inside a field), invisible
formatting characters other than the emoji zero-width joiner, HTML-like tags, `javascript:`,
`vbscript:` and `data:` URLs and `${{` expressions. Plain symbols such as `1 < 2 cups` and emoji
are allowed. This scan is **not** a guarantee that content is harmless: the publisher must
serialize YAML safely, the database layer parameterizes SQL, the web app renders text as text,
nothing ever passes user text to a shell or `eval`, and a human reviews every recipe PR.

## Configuration

Settings are read from the environment on every request. Invalid values are logged without
their contents and make submissions unavailable; they never break browsing or readiness.

| Variable | Default | Purpose |
| --- | --- | --- |
| `SUBMISSIONS_ENABLED` | `false` | Server-side switch |
| `TURNSTILE_SITE_KEY` | empty | Public widget key; required when enabled |
| `TURNSTILE_SECRET_KEY` | empty | Secret verification key; required when enabled; never logged |
| `TURNSTILE_TIMEOUT_SECONDS` | `5` | Siteverify timeout, above 0 and at most 30 |
| `TRUSTED_PROXY_CIDRS` | empty | Comma-separated peer networks allowed to set `CF-Connecting-IP` |
| `SUBMISSION_RATE_LIMIT_PER_CLIENT` | `3` | Attempts per client network per window |
| `SUBMISSION_RATE_LIMIT_AGGREGATE` | `20` | Attempts across all clients per window |
| `SUBMISSION_RATE_LIMIT_WINDOW_SECONDS` | `3600` | Sliding window length |

For local development use Cloudflare's test keys from the
[new developer setup](new-dev-setup.md#turnstile-configuration); never use production secrets
locally. Production secrets come from SOPS in `dylanwhitetech/k3s-infrastructure`.

### Client identity and proxies

Run the API with `--no-proxy-headers` (the image does) so Uvicorn does not rewrite the client
address. `X-Forwarded-For` is always ignored. `CF-Connecting-IP` is used only when the direct
peer is inside `TRUSTED_PROXY_CIDRS`; such a request must carry exactly one valid address or it
is refused with `client_unidentified`. Any other peer is limited by its own address, so a
spoofed header cannot evade limits. Set the CIDRs to the in-cluster ingress networks only.
IPv6 clients are grouped by `/64`.

### Rate-limit scope

Limits are in memory per process: they reset on restart and each replica or worker has its own
counters, so total capacity is the limit multiplied by the process count. Keep one API process
in beta or lower the limits accordingly. Client keys are keyed hashes, so raw addresses are not
stored.

### Turnstile fails closed

The server posts the token and secret to Cloudflare's siteverify endpoint with the configured
timeout. Only an explicit success passes. Invalid, expired or reused tokens return 403; timeouts,
network errors, unexpected responses and secret or Cloudflare errors return 503. Nothing is
published in either case.

## Turning submissions on or off

Change `SUBMISSIONS_ENABLED` through Git: update the Helm values or environment in the
deployment repository and let Flux roll out the change; manual cluster edits are reverted. The
Helm chart is not implemented yet, so the exact values key is defined with it.

- **In-flight requests:** each request reads the switch once, when it starts. A request that has
  already passed the switch continues through validation, Turnstile and publishing; new requests
  are refused immediately. A rollout replaces pods with graceful shutdown, which lets running
  requests finish.
- **What keeps working:** browsing, search, health and readiness do not depend on the switch,
  Turnstile or GitHub.
- To pause quickly during an incident, set the switch to `false` and let the rollout complete;
  then confirm `GET /api/submissions/availability` returns `"enabled": false`.

## Integration points

- **Publisher:** set `app.state.recipe_publisher` to an object with
  `async publish(recipe: dict) -> str` that returns the PR URL and raises
  `PublishError(message, retryable=...)` with a user-safe message. The recipe is already
  validated and normalized. Duplicate-submission protection belongs to the publisher and form.
- **Web form:** wrap it in `SubmissionAvailability` and render `TurnstileWidget` with the site key
  it provides; send a fresh token with each attempt. See the [frontend guide](frontend.md).
