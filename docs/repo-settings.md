# Repository settings

This document records the repository settings for `dylanwhitetech/nailed-it-kitchen`.
Settings marked **Applied** were read back from GitHub after configuration on 2026-10-06.
Settings marked **Pending** are available in GitHub but could not be applied or verified
through the documented repository API; they require an administrator to use the web UI.

## Applied settings

| Area | Setting | Live state |
| --- | --- | --- |
| Repository features | Wiki and Projects disabled | Applied |
| Repository features | Discussions disabled | Already disabled |
| Interaction limits | Collaborators only, six months | Applied; expires 2027-04-06 |
| `main` ruleset | Active, targets `refs/heads/main` only | Applied; exported to [`.github/rulesets/main.json`](../.github/rulesets/main.json) |
| Pull requests | Require one approval, CODEOWNERS review, and dismiss stale approvals on new pushes | Applied |
| Branch safety | Block force pushes and deletion | Applied |
| Copilot code review | `review_on_push=false`; `review_draft_pull_requests=false` (skip new-push and draft reviews; automatic reviews run on PR open/ready) | Active ruleset verified |
| Dependabot | Vulnerability alerts enabled | Applied |
| Secret scanning | Secret scanning and push protection enabled | Already enabled |
| GitHub Actions | Default `GITHUB_TOKEN` permissions are read-only; token cannot approve PR reviews; `allowed_actions=all` | Verified; action allowlisting was not requested or changed |

The active ruleset retains the existing CodeQL alert rule and repository-admin bypass.
The bypass preserves the repository owner's break-glass access. `CODEOWNERS` names
`@dylanwhitetech` and `@ArthurW2`; both have repository write access, so both remain
eligible to review. No required CI status checks are configured yet; the ruleset's
required-status-check list is intentionally empty until CI is added.

GitHub returned an interaction-limit expiry of `2027-04-06T18:59:05Z`. The
[`interaction-limit-reminder` workflow](../.github/workflows/interaction-limit-reminder.yml)
checks monthly and uses the live interaction-limit expiry to open one reminder a
month before it expires. It grants `administration: read` to read that expiry and
`issues: write` only to this scheduled/manual reminder job; the repository-wide
default token permission remains read-only. Close a reminder only after reapplying
the six-month setting. The renewed limit's expiry automatically moves the next
reminder date; the first reminder is due 2027-03-06.

## Pending administrator actions

These settings are supported by GitHub's web UI, but no documented repository REST
API control was available to set/read them in this run. They are **not represented as
applied** here:

| Area | Required action | Status |
| --- | --- | --- |
| Issues | Settings → General → Features → Issues → set **Creation allowed by** to **Collaborators only** | Pending UI action |
| Pull requests | Settings → General → Features → Pull requests → set **Creation allowed by** to **Collaborators only** | Pending UI action |
| Copilot content exclusion | Add `package-lock.json`, `**/*.lock`, `recipes/*.yaml`, and the repository's generated-file paths under Settings → Copilot → Content exclusion; verify repository/plan eligibility | Pending UI action and eligibility check |
| Copilot cloud agent | Enable repository access under Settings → Copilot → Cloud agent, subject to the account/organization policy | Pending UI action and policy check |
| Actions fork approval | Set workflow approval to require approval for all outside contributors under Settings → Actions → General | Pending UI action |

The collaborator-only issue and pull-request controls are documented as repository
settings in GitHub's 2026 changelog. The issue-creation control has a documented
triage-role exception; check the resulting UI state and collaborator list when
applying it. Copilot content exclusion is documented for Copilot Business and
Enterprise and applies to Copilot code review, but availability and effective
repository policy were not exposed by the repository API. Copilot cloud-agent
availability can also depend on organization or enterprise policy. Fork workflow
approval policy is distinct from the already-verified read-only default token
permission.

Until these pending UI settings are applied and verified, issue #11 is not complete
and must not be treated as unblocking #12.

The repository Actions API currently reports `allowed_actions=all`. This controls
which Actions may run and is separate from the requested default token permission
and fork-workflow approval policy; it was not changed by this task.

The ruleset export includes GitHub-generated ruleset and bypass-actor identifiers.
They are non-secret metadata; the admin-role bypass is retained intentionally so the
repository owner can recover from a ruleset lockout.

## Official references

- [GitHub REST API: Update a repository](https://docs.github.com/en/rest/repos/repos#update-a-repository)
- [GitHub REST API: Set interaction restrictions for a repository](https://docs.github.com/en/rest/interactions/repos#set-interaction-restrictions-for-a-repository)
- [GitHub REST API: Update a repository ruleset](https://docs.github.com/en/rest/repos/rules#update-a-repository-ruleset)
- [GitHub REST API: Enable vulnerability alerts](https://docs.github.com/en/rest/dependabot/alerts#enable-dependabot-alerts-for-a-repository)
- [GitHub REST API: Actions permissions](https://docs.github.com/en/rest/actions/permissions)
- [GitHub Docs: GITHUB_TOKEN permissions](https://docs.github.com/en/actions/security-for-github-actions/security-guides/automatic-token-authentication)
- [GitHub Docs: Limiting interactions in your repository](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/limiting-interactions-in-your-repository)
- [GitHub Docs: Managing rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets)
- [GitHub Docs: Approving workflow runs from forks](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/approve-runs-from-forks)
- [GitHub Docs: Excluding content from GitHub Copilot](https://docs.github.com/en/copilot/how-tos/configure-content-exclusion/exclude-content-from-copilot)
- [GitHub Docs: Adding Copilot cloud agent to your organization](https://docs.github.com/en/copilot/how-tos/administer-copilot/manage-for-organization/add-copilot-cloud-agent)
- [GitHub Changelog: New repository settings for pull request access](https://github.blog/changelog/2026-02-13-new-repository-settings-for-configuring-pull-request-access/)
- [GitHub Changelog: Restrict issue creation to collaborators only](https://github.blog/changelog/2026-06-29-restrict-issue-creation-to-collaborators-only/)
- [GitHub Changelog: Triage role can bypass issue creation restrictions](https://github.blog/changelog/2026-08-03-triage-role-can-bypass-issue-creation-restrictions/)
