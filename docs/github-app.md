# GitHub App

The beta API is intended to use `naileditkitchen-bot` to create a branch adding one
validated recipe file and open a PR for human review, without a personal token.
The permissions below are historical verified setup, **not** proof that recipe PR
publishing is authorized or implemented.

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

For the former issue-based workflow, on 2026-11-24 an installation token successfully created, locked, and closed
a test issue under the repository's collaborator-only restrictions. For future
checks, use a short-lived token through a secure owner-controlled flow, ensure
the test issue is closed even if locking fails, and record the outcome without
credentials.

On 2026-11-24, the repository reported collaborator-only issue creation and
an active collaborator-only interaction limit expiring 2027-04-06 18:59:05 UTC.
These settings alone do not prove that the app can create or lock an issue.

## Beta permission gate

The direct recipe PR workflow needs human-approved repository Contents and Pull
requests read/write permissions and an accepted installation update. Keep access
restricted to this repository; do not grant workflow-modification or administrative
permissions. Remove capabilities no longer needed only after checking their consumers.

The owner must verify the implemented publisher using a benign recipe-only PR under
the actual repository restrictions, then record the verified capabilities here.
Until that happens, the issues-only setup remains the last verified state and
production submissions must stay disabled.

The server must generate safe branch/path names, add only one new validated recipe
file, avoid overwrites, recover retries without duplicate PRs and never merge.
Credentials continue to use the existing secret-management process.

## References

- [Registering a GitHub App](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/registering-a-github-app)
- [Generating an installation access token](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app)
- [Beta GitHub App access decision](../guidance/0012-beta-recipe-pr-permissions.md)
- [Choosing GitHub App permissions](https://docs.github.com/en/apps/creating-github-apps/setting-up-a-github-app/choosing-permissions-for-a-github-app)
