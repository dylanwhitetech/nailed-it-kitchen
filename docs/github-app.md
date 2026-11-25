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

## Recipe PR publisher

`backend/app/github_publisher.py` implements the publisher. It has been tested only
against a mocked GitHub API; it has **not** been run with the real App, so the
permissions below are its requirement, not a verified capability.

### Permission contract

Each installation token is requested for only the configured repository with only
`contents: write` and `pull_requests: write` (`metadata: read` is implicit). If
the installation lacks either permission, GitHub refuses the token and the
publisher fails with a permission error before any repository write; a token that
comes back with fewer permissions or other repositories is also refused. The
issues-only setup above therefore cannot publish.

| Call | Permission |
| --- | --- |
| `POST /app/installations/{id}/access_tokens` | App JWT |
| `GET /repos/{repo}/git/ref/heads/{base}`, `contents`, `compare`, `GET pulls` | Contents/Pull requests read |
| `POST /repos/{repo}/git/refs` (new branch) | Contents write |
| `PUT /repos/{repo}/contents/recipes/<slug>.yaml` without `sha` (add only) | Contents write |
| `POST /repos/{repo}/pulls` | Pull requests write |

The publisher never calls issue, label, assignment, workflow, merge or update-file
endpoints. Contents write could technically change other files, so repository rules
and the human review remain the enforcement for anything outside the publisher.

### Behavior

- The branch is `recipe/<slug>` and the
  file is `recipes/<slug>.yaml`; the PR title is `Add recipe: <slug>`. Public input
  cannot choose the repository, base, branch, path or title.
- A slug already on the base branch is rejected. All submissions for a slug share
  one branch; GitHub's atomic create-only file write reserves it for the first
  content, rejecting different content without overwriting, even across processes.
  Concurrent identical submissions reuse the file and GitHub's unique open PR for
  the same head/base. No process-local lock is needed.
- A partial or closed submission's branch continues to reserve that content.
  To release a rejected slug for different content, a maintainer must close its PR
  and delete the branch after ensuring no publisher request is still in flight.
- Before opening the PR, the branch's diff against the base must add exactly that one
  file. A retry resumes an existing branch/file and returns the existing open PR.
- Transport errors, timeouts and HTTP 500/502/503/504 get three attempts with short
  exponential backoff (10-second request timeout). Rate limits wait for GitHub's
  `retry-after` or reset time only if it is at most 30 seconds; otherwise the
  publisher raises an error carrying the wait. Other errors fail immediately.
- The caller supplies the complete Markdown PR body; the publisher sends it verbatim.

### Configuration

| Variable | Meaning |
| --- | --- |
| `GITHUB_APP_ID` | App ID |
| `GITHUB_APP_INSTALLATION_ID` | Installation ID |
| `GITHUB_APP_PRIVATE_KEY_FILE` | Path to the mounted PEM private key (a secret file, never an environment value) |
| `GITHUB_REPOSITORY` | `owner/name`; defaults to `dylanwhitetech/nailed-it-kitchen` |
| `GITHUB_BASE_BRANCH` | PR base; defaults to `main` |

Supply the key from the existing secret-management process. Installation tokens
are kept only in memory and refreshed five minutes before expiry; App JWTs live
nine minutes.

### Secure diagnostics

Publisher errors and logs contain the operation, HTTP status, attempt number and
GitHub's `x-github-request-id`, never the key, JWT, token, recipe text or PR body.
Use the request ID when asking GitHub support. Permission errors name the missing
Contents and Pull requests write permissions.

### Real verification

After the permission update, the owner can open one benign verification PR from a
trusted shell that has the configuration above:

```bash
python -m backend.app.github_publisher path/to/benign-recipe.yaml --confirm-real-pr
```

It prints only `created` or `reused` and the PR URL. Use a slug that is not on the
base branch, since an existing slug is rejected. Inspect the entire diff, close
the PR without merging unless it is the real launch submission, and delete its
branch. Then record the verified capabilities in this document.

## References

- [Registering a GitHub App](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/registering-a-github-app)
- [Generating an installation access token](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app)
- [Beta GitHub App access decision](../guidance/0012-beta-recipe-pr-permissions.md)
- [Choosing GitHub App permissions](https://docs.github.com/en/apps/creating-github-apps/setting-up-a-github-app/choosing-permissions-for-a-github-app)
