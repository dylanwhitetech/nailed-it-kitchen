# 0018: release-please and trusted promotion PRs

## Status
Accepted

## Context
CI publishes SHA-tagged multi-arch images for every passing `main` push, and the chart lives in
`deploy/chart/naileditkitchen`, but nothing turned a reviewed state of `main` into a versioned,
deployable artifact or proposed it to the cluster. Releases must stay human-gated, must not trust
pull request input, must not rebuild (and so silently replace) images, and must not mistake a
missing first-onboarding HelmRelease for a successful promotion.

## Decision
- release-please (manifest mode, one `simple` package, `vX.Y.Z` tags, first version `0.1.0`) owns
  every version. The repository, tag, GitHub Release and chart version are one number; there is no
  hand tagging.
- One trusted `Release` workflow runs only on a successful `CI` run for a push to `main` in this
  repository (`workflow_run`), or on manual dispatch on `main`. Each job has its own minimal
  permissions and the workflow default is none.
- Chart publication reuses CI's `naileditkitchen-{api,web}:<full SHA>` images: it verifies both
  platforms and the revision annotation, then packages the chart from the release commit with
  `appVersion` set to the full SHA and image tags and index digests pinned. It also creates
  `X.Y.Z` image aliases to the same indexes, refusing to overwrite conflicting aliases. It publishes
  `oci://ghcr.io/dylanwhitetech/charts/naileditkitchen:X.Y.Z`, never overwrites a published
  version, and reconciles every recent release whose chart is missing.
- Promotion uses `INFRA_PR_TOKEN` to open, never merge, a PR in
  `dylanwhitetech/k3s-infrastructure` that bumps `spec.chart.spec.version` in the HelmRelease
  file selected by the owner through `NIK_HELMRELEASE_PATH` after onboarding. An unset path or a
  missing file (first onboarding not merged) fails promotion; downgrades are refused. Rollback is a
  reviewed revert of the promotion PR plus the migration/backup recovery procedure.
- The repository owner owns `INFRA_PR_TOKEN` scope, expiry and renewal, verified at launch and at
  each renewal.
- The logic lives in a tested script (`scripts/release`), not inline workflow shell.

## Consequences
- Every deployed chart maps to a reviewed release PR, a tag and exact image digests; Flux pins an
  exact chart version.
- Release PRs opened with the workflow token need the owner's "Actions can create pull requests"
  setting and do not trigger CI automatically, so an owner must start their checks.
- Nothing can release while `main` CI is failing, and the first promotion waits for the reviewed
  first-onboarding change in k3s-infrastructure.
- Promotion depends on a long-lived token with an owner-tracked expiry; if it lapses, charts are
  published but not promoted until it is renewed.

## References
- [Releases and promotion](../docs/releases.md), [`.github/workflows/release.yml`](../.github/workflows/release.yml)
- [0005: GitOps hosting](0005-gitops-hosting-through-k3s-infrastructure.md), [0017: Early CI and SHA-tagged images](0017-early-ci-and-sha-tagged-images.md)
- Issue #26 (this decision), #25 (chart contract), #28 (artifact visibility), dylanwhitetech/k3s-infrastructure#36 (first onboarding)
- Prior art: [weatherapp release workflows](https://github.com/dylanwhitetech/weatherapp/tree/main/.github/workflows)
- [release-please manifest releaser](https://github.com/googleapis/release-please/blob/main/docs/manifest-releaser.md)
- [GitHub Docs: `workflow_run`](https://docs.github.com/en/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows#workflow_run)
- [Helm: OCI registries](https://helm.sh/docs/topics/registries/)
