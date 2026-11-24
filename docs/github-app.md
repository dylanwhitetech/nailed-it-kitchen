# GitHub App

The API is intended to use `naileditkitchen-bot` to create and lock submission
and feedback issues without a personal token.

## Verified public app details

On 2026-11-24, GitHub's public app API returned:

| Property | Value |
| --- | --- |
| App | [`naileditkitchen-bot`](https://github.com/apps/naileditkitchen-bot), owned by `dylanwhitetech` |
| App ID | `5911275` |
| Repository permissions | Issues: read and write; Metadata: read |
| Subscribed events | None |

An empty event list does **not** establish that the webhook is disabled.

## Installation and key

The installation ID is `185542543`. On 2026-11-24, the app-authenticated API
confirmed that the installation uses selected repositories and has access only
to `dylanwhitetech/nailed-it-kitchen`. The owner reports that the webhook is
disabled and a private key is securely stored.

Never put the key or a token in this repository, an issue, a prompt, or a log.
Store the key with SOPS in `k3s-infrastructure`; delete any temporary local key
file once it has been stored there.

## Lockdown check

On 2026-11-24, an installation token successfully created, locked, and closed
a test issue under the repository's collaborator-only restrictions. For future
checks, use a short-lived token through a secure owner-controlled flow, ensure
the test issue is closed even if locking fails, and record the outcome without
credentials.

On 2026-11-24, the repository reported collaborator-only issue creation and
an active collaborator-only interaction limit expiring 2027-04-06 18:59:05 UTC.
These settings alone do not prove that the app can create or lock an issue.

## References

- [Registering a GitHub App](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/registering-a-github-app)
- [Generating an installation access token](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app)
- [GitHub App access decision](../guidance/0007-github-app-for-api-github-access.md)
