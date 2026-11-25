# 0020: Hookless chart lifecycle and verified pg_dump backups

## Status
Accepted

## Context
Record 0004 requires CloudNativePG, an ordered migration/seed Job and nightly dumps, and notes
that a pre-install hook cannot depend on ordinary resources from the same install. A post-install
hook would also deadlock when API pods wait for the schema it creates. The release must stay
GitOps-friendly (Flux waits on resource health) and never serve a schema older than the API image.

## Decision
- The chart in `deploy/chart/naileditkitchen` uses no Helm hooks. Each revision applies an
  ordinary Job `<release>-migrate-<revision>` that waits for PostgreSQL, then migrates and seeds
  under a PostgreSQL advisory lock, and leaves a newer schema untouched on rollback.
- API pods have a `wait-for-schema` init container and roll with `maxUnavailable: 0`, so the old
  version serves until the schema and new pods are ready. All waits are bounded.
- CloudNativePG generates the database credentials; other credentials are existing Secrets
  referenced by name. Images render `repository@digest` or `repository:tag` (default
  `appVersion`), and an unreleased appVersion or `latest` fails rendering.
- CronJob `<release>-backup` writes custom-format `pg_dump` files to an immediately bound PVC,
  verifies each with `pg_restore --list` before an atomic rename, and prunes by age only after a
  successful dump. The Cluster and backup PVC are kept on uninstall.
- CI's existing `chart` job lints and renders with pinned Helm and runs a kind fresh install,
  upgrade and backup smoke test with a pinned CloudNativePG operator.

## Consequences
- Helm or Flux report success only after the migration Job and new pods are ready; a failed
  migration leaves the old pods serving and is retried by the next revision.
- Backup freshness alerting and restore drills are operated from
  `dylanwhitetech/k3s-infrastructure`.
- A `WaitForFirstConsumer` backup StorageClass needs `backup.storage.existingClaim`.

## References
- [Deployment guide](../docs/deployment.md)
- [0004: PostgreSQL on CloudNativePG](0004-postgres-on-cloudnativepg.md)
- [Helm chart hooks](https://helm.sh/docs/topics/charts_hooks/)
- [CloudNativePG documentation](https://cloudnative-pg.io/documentation/current/)
