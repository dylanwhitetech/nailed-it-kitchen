# 0014: Early CI and SHA-tagged multi-arch images

## Status
Accepted

## Context
Backend, frontend and recipe checks existed only as local commands, and nothing built the arm64
images the Raspberry Pi cluster needs. Waiting for the Helm chart before adding CI would delay
feedback, but a placeholder must not look like chart validation. Recipe pull requests carry
untrusted content, and the repository is public.

## Decision
- One `CI` workflow runs on `pull_request` and pushes to `main` without path filters: `Backend`
  (Ruff, pytest against a PostgreSQL service), `Frontend` (Oxlint, Vitest, build), `Recipes`
  (schema validation and tests), and `Image build (api|web)` (Buildx linux/amd64 + linux/arm64,
  not pushed).
- `Helm chart applicability` reports "not applicable" while `deploy/chart/` is absent and fails once
  it exists, until the chart work replaces it with real Helm lint/template/install checks under the
  same name.
- Trusted pushes to `main` in this repository publish
  `ghcr.io/dylanwhitetech/naileditkitchen-{api,web}:<full-commit-sha>` after all checks pass. No
  moving tags are pushed.
- Least privilege: workflow default `contents: read`; only publish jobs get `packages: write`. Never
  use `pull_request_target`; no repository secrets in check jobs; checkouts do not persist
  credentials; third-party Actions and service images are pinned to full SHAs/digests.
- The ruleset's required checks are applied by an owner in settings and then re-exported; the
  committed export always mirrors the live ruleset.

## Consequences
- Pull requests get feedback before the chart exists, and a chart cannot merge behind a green check
  that never linted it.
- Every `main` commit has immutable, reproducible image tags for promotion; storage grows with each
  push, and pruning old untagged/unused versions is an owner GHCR task if it becomes necessary.
- Pinned SHAs need updates; Dependabot's GitHub Actions ecosystem is expected to propose them.
- Multi-arch builds under QEMU make pull request checks slower than single-arch builds.

## References
- [CI guide](../docs/ci.md) and [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)
- [Repository settings: required CI checks](../docs/repo-settings.md#required-ci-checks)
- [0001: Application stack](0001-application-stack.md), [0005: GitOps hosting](0005-gitops-hosting-through-k3s-infrastructure.md)
- Issue #22 (this decision), #25 (chart checks), #28 (artifact visibility), #43 (owner settings)
- [GitHub Docs: Security hardening for GitHub Actions](https://docs.github.com/en/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions)
- [GitHub Docs: Connecting a repository to a package](https://docs.github.com/en/packages/learn-github-packages/connecting-a-repository-to-a-package)
