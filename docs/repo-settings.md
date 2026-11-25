# Repository settings

This document records the repository settings for `dylanwhitetech/nailed-it-kitchen`.
Settings marked **Applied** were read back from GitHub after configuration on 2026-10-06.
Settings marked **Pending** need an administrator UI action or confirmation before
they can be considered complete.

## Applied settings

| Area | Setting | Live state |
| --- | --- | --- |
| Repository features | Wiki and Projects disabled | Applied |
| Repository features | Discussions disabled | Already disabled |
| Issue creation | Collaborators only | Applied; verified via GraphQL `issueCreationPolicy=COLLABORATORS_ONLY` |
| Pull-request creation | Collaborators only | Applied and read back via `pull_request_creation_policy` |
| Interaction limits | Collaborators only, six months | Applied; expires 2027-04-06 |
| `main` ruleset | Active, targets `refs/heads/main` only | Applied; exported to [`.github/rulesets/main.json`](../.github/rulesets/main.json) |
| Pull requests | Require one approval, CODEOWNERS review, and dismiss stale approvals on new pushes | Applied |
| Branch safety | Block force pushes and deletion | Applied |
| Copilot code review | `review_on_push=false`; `review_draft_pull_requests=false` (skip new-push and draft reviews; automatic reviews run on PR open/ready) | Active ruleset verified |
| Dependabot | Vulnerability alerts enabled | Applied |
| Secret scanning | Secret scanning and push protection enabled | Already enabled |
| Code scanning | CodeQL default setup, `default` query suite, weekly schedule, languages detected by GitHub | Applied 2026-11-25; agent-collected read-only API readback at 2026-11-25 07:09 UTC reports `state=configured` with `actions`, `javascript-typescript` (also reported as `javascript` and `typescript`) and `python`; the latest `main` analyses (commit `ca03afb`) for those three categories report 0 results, with 0 open alerts. Owner verification of the Python and JavaScript/TypeScript results is pending (see below) |
| GitHub Actions | Default `GITHUB_TOKEN` permissions are read-only; token cannot approve PR reviews; fork PR approval policy is all outside contributors; `allowed_actions=all` | Verified; action allowlisting was not requested or changed |

The active ruleset retains the existing CodeQL alert rule and repository-admin bypass.
That rule blocks merges until CodeQL has analysed the pull request, so CodeQL default
setup must stay enabled; without it, pull requests stay blocked unless an admin bypasses.
Default setup scans pull requests when they are opened or pushed to. A pull request
opened before setup was enabled needs a new push to get a scan; closing and reopening
it does not start one. GitHub added Python and JavaScript/TypeScript automatically after
that code landed; the code-scanning analyses API shows `main` analyses for
`/language:python`, `/language:javascript-typescript` and `/language:actions` at
2026-11-25 05:57 UTC, each with zero results.
The bypass preserves the repository owner's break-glass access. `CODEOWNERS` names
`@dylanwhitetech` and `@ArthurW2`; both have repository write access, so both remain
eligible to review. No required CI status checks are configured yet; the ruleset's
required-status-check list stays empty until an owner applies the
[required CI checks](#required-ci-checks) below.

GitHub's repository API readback reports `pull_request_creation_policy=collaborators_only`.
The Actions fork-PR approval endpoint currently reports
`approval_policy=all_external_contributors`. The Actions permissions endpoint
separately reports `allowed_actions=all`; action allowlisting was not requested or
changed.

GitHub returned an interaction-limit expiry of `2027-04-06T18:59:05Z`. The
[`interaction-limit-reminder` workflow](../.github/workflows/interaction-limit-reminder.yml)
checks monthly on the 6th (15:00 UTC) and can also be dispatched manually. It uses
the recorded initial set date, **2026-10-06**, to open the first reminder when five
calendar months have elapsed: **2027-03-06**, one month before the recorded expiry.
Subsequent reminders become due five calendar months after the latest reminder
closure date (UTC), clamping the day to the last day of the target month if needed.
The monthly schedule creates the issue on the first check on or after its due date;
this can leave less than a month's notice. Run it manually when due if an earlier
reminder is needed, and renew promptly before the actual expiry. Scheduled runs
depend on GitHub Actions remaining enabled and may be delayed.

The workflow uses only the built-in `GITHUB_TOKEN` with `issues: write`; all other
workflow token permissions are disabled, and the repository-wide default remains
read-only. It does **not** call the interaction-limit endpoint or need an
Administration-capable App/token (`administration` is not a supported workflow
permission). It lists all issue pages directly rather than relying on search
indexing, ignores PRs, and leaves any existing open reminder alone. If a run fails,
rerun it: an issue already created will suppress another reminder.

Close a reminder **only after reapplying the six-month setting, on the same UTC
date**. Keep its exact title, `Renew repository interaction limit`, and do not
delete it; its closure timestamp records the renewal date. This is a recorded-date
reminder, not live renewal/expiry tracking: early closure, renaming, or deletion
breaks that record. If renewal happens outside this reminder process, update this
document's initial set date and the workflow's `initial_set_date`; existing later
closure dates still take precedence. Reopen a mistakenly closed reminder until
renewal is complete. Missed checks recover on the next run without skipping an
overdue reminder.

## Required CI checks

**Pending owner action.** The [CI workflow](ci.md) reports these job names on every pull request.
After they have run on GitHub at least once, an owner adds them to the `main` ruleset's
required status checks (source: GitHub Actions), reads the ruleset back and re-exports
[`.github/rulesets/main.json`](../.github/rulesets/main.json). Until then the export correctly
shows an empty list, and these checks are informative rather than enforced.

| Required check | Purpose |
| --- | --- |
| `Backend` | Ruff and pytest against PostgreSQL |
| `Frontend` | Oxlint, Vitest, type check and build |
| `Recipes` | Plain recipe schema validation and validator/fixture tests |
| `Helm chart applicability` | Not applicable without a chart; blocks a chart that lacks Helm checks |
| `Image build (api)` | amd64/arm64 API image builds |
| `Image build (web)` | amd64/arm64 web image builds |

The publish jobs run only on `main` and are not required checks. The existing strict
"up to date before merging" policy and CodeQL rule are unchanged. Dependency review runs
separately; whether to require it is an owner decision recorded below.

## Automated dependency checks (committed configuration)

These are defined in code. Their presence in the repository is not evidence that a
repository setting changed.

| File | Behavior |
| --- | --- |
| [`.github/dependabot.yml`](../.github/dependabot.yml) | Weekly version updates for pip (`/backend`, `/recipes`), npm (`/frontend`), GitHub Actions (`/`), Docker (`/backend`, `/frontend`) and Docker Compose (`/compose.yaml`). Minor and patch updates are grouped per ecosystem; major updates open separate PRs. Docker tags that are not version-like, such as `stable-alpine`, are not updated. |
| [`.github/workflows/dependency-review.yml`](../.github/workflows/dependency-review.yml) | Runs `actions/dependency-review-action` (pinned to a commit SHA) on pull requests to `main` and fails when a change introduces a runtime, development or unknown-scope dependency with a high or critical vulnerability. The job token has only `contents: read` and the workflow does not check out code. |
| [`.github/workflows/trivy.yml`](../.github/workflows/trivy.yml) | On pushes and pull requests to `main` and weekly, builds the API and web images and uploads Trivy high/critical image findings to code scanning (`trivy-backend`, `trivy-frontend`). Actions are pinned to commit SHAs; the job token has only `contents: read` and `security-events: write`. The `main` ruleset's code-scanning rule covers CodeQL only, so Trivy findings are reported but do not block merges. |
Dependabot version updates depend on the dependency graph, which GitHub enables for
public repositories. The repository readback on 2026-11-25 reports Dependabot
security updates as `disabled`; this change does not alter that setting, and
Dependabot alerts remain enabled as recorded above.

An agent-collected read-only readback at 2026-11-25 17:20 UTC (commit `a267af6`) reports
CodeQL default setup `state=configured` with 0 results for `/language:python`,
`/language:javascript-typescript` and `/language:actions`, 0 open Dependabot alerts,
and 74 open Trivy alerts: 54 high in `trivy-backend`, 15 high and 5 critical in
`trivy-frontend`. Recent `Dependency review` pull-request runs succeeded. This is
evidence, not owner verification or triage of those findings.

## Unsupported controls and pending administrator actions

These settings are **not represented as applied** here:

| Area | Required action | Status |
| --- | --- | --- |
| Copilot custom content exclusion | Requested paths: `package-lock.json`, `**/*.lock`, `recipes/*.yaml`, and generated files | Unavailable in the current repository Settings UI, reported by the administrator; follow-up [#57](https://github.com/dylanwhitetech/nailed-it-kitchen/issues/57) |
| Copilot cloud agent | Verify/enable repository access under Settings → Copilot → Cloud agent, subject to account eligibility | Pending UI action and eligibility check |
| CodeQL default setup | Owner confirms Python and JavaScript/TypeScript in Settings → Code security → Code scanning and reviews their analyses; record the date and result here | Pending owner verification; API readback above is agent-collected |
| Trivy image scanning | Decide whether to keep the Trivy workflow, which [guidance 0014](../guidance/0014-beta-dependency-and-security-checks.md) did not adopt, and record or supersede that decision; triage its open image findings | Pending owner decision and triage |
| Required status checks | After the `dependency-review` check has run on `main` pull requests, decide whether to add it to the `main` ruleset's required checks, then re-export `.github/rulesets/main.json` | Pending owner decision; the required-check list is still empty |

The collaborator-only issue-creation control is documented in GitHub's 2026
changelog, including a triage-role exception. Its GraphQL readback now confirms
`COLLABORATORS_ONLY`; the repository update REST schema does not expose this field.
The repository update API also confirms the collaborator-only PR creation policy.
The documented content-exclusion API is organization-scoped; this is a
personal-user repository, and no per-repository content-exclusion API endpoint is
documented. Custom content exclusion is documented for Copilot Business and
Enterprise and applies to Copilot code review. On 2026-10-06, the administrator
reported that the Content exclusion menu is absent. Treat this as an unavailable
control in the current setup, not as a setting still waiting to be saved. The
account's exact subscription has not been independently verified. Follow-up #57
tracks the maintainer decision about deferring the requirement or using an eligible
configuration; no subscription or repository ownership changes were made.

Separately, GitHub's built-in code-review exclusions already include
`package-lock.json`, `**/*.lock`, and common generated-file locations such as
`**/generated/**/*` and `**/generated-sources/**/*`. These defaults are not a custom
policy we configured. They do not establish exclusion of `recipes/*.yaml` or every
generated file. An instructions file or an invented ignore file is not an
equivalent enforced exclusion.

The repository cloud-agent configuration API returned enabled tools,
firewall, and automation settings, but does not report whether account policy has
enabled Copilot cloud agent access to this repository. Verify that access in
Settings.

An earlier fork-PR approval readback conflicted with the repository owner's
verification. The latest GET now reports `all_external_contributors`, so the
requested policy is currently verified as applied.

Issue #11 is not complete and must not be treated as unblocking #12 until the
remaining cloud-agent access check is resolved and the maintainer accepts a
disposition for the unavailable custom-exclusion control tracked in #57.

The repository Actions API reports `allowed_actions=all`. This controls which
Actions may run and is separate from the verified default token permission and
fork-workflow approval policy; it was not changed by this task.

The ruleset export includes GitHub-generated ruleset and bypass-actor identifiers.
They are non-secret metadata; the admin-role bypass is retained intentionally so the
repository owner can recover from a ruleset lockout.

## Official references

- [GitHub REST API: Update a repository](https://docs.github.com/en/rest/repos/repos#update-a-repository)
- [GitHub REST API: Set interaction restrictions for a repository](https://docs.github.com/en/rest/interactions/repos#set-interaction-restrictions-for-a-repository)
- [GitHub REST API: Update a repository ruleset](https://docs.github.com/en/rest/repos/rules#update-a-repository-ruleset)
- [GitHub REST API: Enable vulnerability alerts](https://docs.github.com/en/rest/dependabot/alerts#enable-dependabot-alerts-for-a-repository)
- [GitHub REST API: Actions permissions](https://docs.github.com/en/rest/actions/permissions)
- [GitHub REST API: Fork PR contributor approval policy](https://docs.github.com/en/rest/actions/permissions#get-fork-pr-contributor-approval-permissions-for-a-repository)
- [GitHub REST API: Copilot cloud agent configuration](https://docs.github.com/en/rest/copilot/copilot-cloud-agent-management#get-copilot-cloud-agent-configuration-for-a-repository)
- [GitHub REST API: Copilot content exclusion](https://docs.github.com/en/rest/copilot/copilot-content-exclusion)
- [GitHub REST API: Update a code scanning default setup configuration](https://docs.github.com/en/rest/code-scanning/code-scanning#update-a-code-scanning-default-setup-configuration)
- [GitHub Docs: Dependabot options reference](https://docs.github.com/en/code-security/dependabot/working-with-dependabot/dependabot-options-reference)
- [GitHub Docs: Configuring the dependency review action](https://docs.github.com/en/code-security/supply-chain-security/understanding-your-software-supply-chain/configuring-the-dependency-review-action)
- [GitHub Docs: Security hardening for GitHub Actions (pinning actions)](https://docs.github.com/en/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions#using-third-party-actions)
- [GitHub Docs: Editing your configuration of default setup](https://docs.github.com/en/code-security/how-tos/find-and-fix-code-vulnerabilities/manage-your-configuration/edit-default-setup)
- [GitHub Docs: GITHUB_TOKEN permissions](https://docs.github.com/en/actions/security-for-github-actions/security-guides/automatic-token-authentication)
- [GitHub Docs: Limiting interactions in your repository](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/limiting-interactions-in-your-repository)
- [GitHub Docs: Managing rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets)
- [GitHub Docs: Approving workflow runs from forks](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/approve-runs-from-forks)
- [GitHub Docs: Excluding content from GitHub Copilot](https://docs.github.com/en/copilot/how-tos/configure-content-exclusion/exclude-content-from-copilot)
- [GitHub Docs: Content-exclusion plan support](https://docs.github.com/en/copilot/concepts/security-governance-and-network-settings/content-exclusion)
- [GitHub Docs: Files automatically excluded from code review](https://docs.github.com/en/copilot/reference/review-excluded-files)
- [GitHub Docs: Adding Copilot cloud agent to your organization](https://docs.github.com/en/copilot/how-tos/administer-copilot/manage-for-organization/add-copilot-cloud-agent)
- [GitHub Changelog: New repository settings for pull request access](https://github.blog/changelog/2026-02-13-new-repository-settings-for-configuring-pull-request-access/)
- [GitHub Changelog: Restrict issue creation to collaborators only](https://github.blog/changelog/2026-06-29-restrict-issue-creation-to-collaborators-only/)
- [GitHub Changelog: Triage role can bypass issue creation restrictions](https://github.blog/changelog/2026-08-03-triage-role-can-bypass-issue-creation-restrictions/)
