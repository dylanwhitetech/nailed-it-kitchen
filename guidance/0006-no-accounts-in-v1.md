# 0006: No user accounts in v1; Turnstile and rate limits

## Status
Accepted

## Context
Public write endpoints (recipe submissions, feedback, ratings) attract spam, but accounts would add passwords and personal data to protect.

## Decision
Ship v1 without user accounts. Protect every public write endpoint with Cloudflare Turnstile and API rate limiting, and validate all public input on the server.

## Consequences
- No passwords or personal data to store.
- Turnstile blocks bots without captchas.
- Features that need identity (comments, accounts) stay out of v1 and need a superseding record.

## References
- [README "Decisions & why"](../README.md#decisions--why)
- [README "v1 scope"](../README.md#v1-scope)
