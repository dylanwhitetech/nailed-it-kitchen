# 0006: No user accounts in beta; Turnstile and rate limits

## Status
Accepted

## Context
Public write endpoints attract spam, but accounts would add passwords and personal data to protect.
Beta exposes recipe submissions; feedback and ratings are Post-beta.

## Decision
Ship beta without user accounts. Protect every public write endpoint with Cloudflare Turnstile and API rate limiting, and validate all public input on the server.

## Consequences
- No passwords or personal data to store.
- Turnstile blocks bots without captchas.
- Features that need identity (comments, accounts) stay Post-beta and need a superseding record.

## References
- [README "Decisions & why"](../README.md#decisions--why)
- [README "Beta scope"](../README.md#beta-scope)
