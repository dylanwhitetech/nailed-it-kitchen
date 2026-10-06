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
| Issue creation | Collaborators only | Pending; setting has no documented repository REST API field |
| Pull-request creation | Collaborators only | Applied and read back via `pull_request_creation_policy` |
| Interaction limits | Collaborators only, six months | Applied; expires 2027-04-06 |
| `main` ruleset | Active, targets `refs/heads/main` only | Applied; exported to [`.github/rulesets/main.json`](../.github/rulesets/main.json) |
| Pull requests | Require one approval, CODEOWNERS review, and dismiss stale approvals on new pushes | Applied |
| Branch safety | Block force pushes and deletion | Applied |
| Copilot code review | `review_on_push=false`; `review_draft_pull_requests=false` (skip new-push and draft reviews; automatic reviews run on PR open/ready) | Active ruleset verified |
| Dependabot | Vulnerability alerts enabled | Applied |
| Secret scanning | Secret scanning and push protection enabled | Already enabled |
| GitHub Actions | Default `GITHUB_TOKEN` permissions are read-only; token cannot approve PR reviews; fork PR approval policy is all outside contributors; `allowed_actions=all` | Verified; action allowlisting was not requested or changed |

The active ruleset retains the existing CodeQL alert rule and repository-admin bypass.
The bypass preserves the repository owner's break-glass access. `CODEOWNERS` names
`@dylanwhitetech` and `@ArthurW2`; both have repository write access, so both remain
eligible to review. No required CI status checks are configured yet; the ruleset's
required-status-check list is intentionally empty until CI is added.

GitHub's repository API readback reports `pull_request_creation_policy=collaborators_only`.
The Actions fork-PR approval endpoint currently reports
`approval_policy=all_external_contributors`. The Actions permissions endpoint
separately reports `allowed_actions=all`; action allowlisting was not requested or
changed.

GitHub returned an interaction-limit expiry of `2027-04-06T18:59:05Z`. The
[`interaction-limit-reminder` workflow](../.github/workflows/interaction-limit-reminder.yml)
checks monthly and uses the live interaction-limit expiry to open one reminder a
month before it expires. It grants `administration: read` to read that expiry and
`issues: write` only to this scheduled/manual reminder job; the repository-wide
default token permission remains read-only. Close a reminder only after reapplying
the six-month setting. The renewed limit's expiry automatically moves the next
reminder date; the first reminder is due 2027-03-06.

## Pending administrator actions

These settings are **not represented as applied** here:

| Area | Required action | Status |
| --- | --- | --- |
| Issues | Settings → General → Features → Issues → set **Creation allowed by** to **Collaborators only** | Pending UI action |
| Copilot content exclusion | Add `package-lock.json`, `**/*.lock`, `recipes/*.yaml`, and the repository's generated-file paths under Settings → Copilot → Content exclusion; verify repository/plan eligibility | Pending UI action and eligibility check |
| Copilot cloud agent | Verify/enable repository access under Settings → Copilot → Cloud agent, subject to account eligibility | Pending UI action and eligibility check |

The collaborator-only issue-creation control is documented in GitHub's 2026
changelog, including a triage-role exception, but it is not present in the documented
repository update API schema. Check the UI setting and collaborator list when
applying it. The repository update API does support the collaborator-only PR
creation policy, which is now applied. The documented content-exclusion API is
organization-scoped; this is a personal-user repository, and no per-repository
content-exclusion API endpoint is documented. Content exclusion is documented for
Copilot Business and Enterprise and applies to Copilot code review, so verify
eligibility and effective policy in Settings. The repository cloud-agent
configuration API returned enabled tools, firewall, and automation settings, but
does not report whether account policy has enabled Copilot cloud agent access to
this repository. Verify that access in Settings.

An earlier fork-PR approval readback conflicted with the repository owner's
verification. The latest GET now reports `all_external_contributors`, so the
requested policy is currently verified as applied.

Until these pending UI settings are applied and verified, issue #11 is not complete
and must not be treated as unblocking #12.

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
- [GitHub Docs: GITHUB_TOKEN permissions](https://docs.github.com/en/actions/security-for-github-actions/security-guides/automatic-token-authentication)
- [GitHub Docs: Limiting interactions in your repository](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/limiting-interactions-in-your-repository)
- [GitHub Docs: Managing rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets)
- [GitHub Docs: Approving workflow runs from forks](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/approve-runs-from-forks)
- [GitHub Docs: Excluding content from GitHub Copilot](https://docs.github.com/en/copilot/how-tos/configure-content-exclusion/exclude-content-from-copilot)
- [GitHub Docs: Adding Copilot cloud agent to your organization](https://docs.github.com/en/copilot/how-tos/administer-copilot/manage-for-organization/add-copilot-cloud-agent)
- [GitHub Changelog: New repository settings for pull request access](https://github.blog/changelog/2026-02-13-new-repository-settings-for-configuring-pull-request-access/)
- [GitHub Changelog: Restrict issue creation to collaborators only](https://github.blog/changelog/2026-06-29-restrict-issue-creation-to-collaborators-only/)
- [GitHub Changelog: Triage role can bypass issue creation restrictions](https://github.blog/changelog/2026-08-03-triage-role-can-bypass-issue-creation-restrictions/)
