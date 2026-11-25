# Deployment (Helm chart)

The `naileditkitchen` Helm chart in [`deploy/chart/naileditkitchen`](../deploy/chart/naileditkitchen)
deploys the API, web app, ingress, a CloudNativePG PostgreSQL cluster, the migration/seed Job and
the nightly backup CronJob. Production releases are installed by Flux from
`dylanwhitetech/k3s-infrastructure`; this page documents the chart contract, ordering, recovery
and the local smoke test. [`values.yaml`](../deploy/chart/naileditkitchen/values.yaml) documents
every value.

## Prerequisites

- Kubernetes with ingress-nginx and the CloudNativePG operator and CRDs (`postgresql.cnpg.io/v1`).
  CI uses CloudNativePG chart 0.29.2 (operator 1.30.2).
- The release namespace exists; the chart does not create it.
- A StorageClass for the database volume (`database.storage.storageClass`, default `local-path`).
- For the backup PVC created by the chart (`backup.storage.storageClass`, default `ssd-nfs`), a
  StorageClass that binds immediately. Helm `--wait` and Flux wait for chart PVCs to bind, so a
  `WaitForFirstConsumer` class blocks the release until the first backup runs. Otherwise supply
  `backup.storage.existingClaim`.
- Optional existing Secrets, referenced by name and never stored in values:

| Secret | Keys | Used when |
| --- | --- | --- |
| `submissions.turnstile.existingSecret` (default `naileditkitchen-turnstile`) | `submissions.turnstile.secretKey` (default `secret-key`) | Always referenced as optional; required before enabling submissions |
| `githubApp.existingSecret` (default `naileditkitchen-github-app`) | `app-id`, `installation-id`, `private-key` | `githubApp.enabled=true` |

CloudNativePG generates the database credentials in Secret `<release>-db-app`; the chart reads
`password` from it. No database password is set in values.

## Names and images

With release name `naileditkitchen`, resources are named `naileditkitchen-*`: Deployments and
Services `-api` (port 8000) and `-web` (port 8080), Cluster `-db` (services `-db-rw`), Job
`-migrate-<revision>`, CronJob `-backup` and PVC `-db-backups`. Every resource carries
`app.kubernetes.io/name`, `app.kubernetes.io/instance` and `app.kubernetes.io/component`.

Images come from `api.image` and `web.image` (`repository`, `tag`, `digest`). A digest renders
`repository@digest`; otherwise `repository:tag`, with an empty tag defaulting to the chart
`appVersion`. The committed chart has `appVersion: unreleased`, so it renders only after a release
sets the appVersion or tags; `latest` is rejected. The migration Job uses the API image. The
`Chart.yaml` `version` line carries the release-please marker.

## Install and upgrade ordering

The chart uses no Helm hooks. A pre-install hook cannot wait for the Cluster created by the same
release, and a post-install hook would deadlock with API pods that wait for the schema. Instead,
every install and upgrade applies these ordinary resources together:

1. CloudNativePG creates the Cluster and its `-db-app` Secret.
2. Job `<release>-migrate-<revision>` waits up to `migration.databaseWaitSeconds` for PostgreSQL,
   then runs Alembic `upgrade head` and the recipe seed under a PostgreSQL advisory lock. If the
   database schema is newer than the image (a rollback), it leaves the database untouched.
3. Each new API pod's `wait-for-schema` init container waits up to `api.schemaWaitSeconds` until the
   schema is at or beyond its image's head. The API rolls with `maxUnavailable: 0`, so old pods
   keep serving until new ones are ready on `/api/readyz`.

Helm `--wait --wait-for-jobs` (and Flux's default health checks) therefore succeed only after the database,
the migration Job and the new pods are ready. Jobs are immutable, so each revision has a new Job
and Helm deletes the previous revision's Job.

## Recovery

- **Migration Job failed or timed out:** read `kubectl logs job/<release>-migrate-<revision>`.
  New API pods stay in `Init` and old pods keep serving. Fix the cause and apply a new revision
  (for example a Flux reconcile or `helm upgrade`); the next revision creates a new Job.
- **API pod stuck in `Init`:** the init container fails after `api.schemaWaitSeconds` and is
  retried; check the migration Job first.
- **Rollback to an older image:** the Job skips migration and seeding because the schema is newer;
  the older API starts if its code is compatible with the newer schema. Schema downgrades are a
  deliberate manual recovery with a tested backup (see the [backend guide](backend.md)).
- **Uninstall:** the Cluster and the backup PVC have `helm.sh/resource-policy: keep`, so
  uninstalling never deletes the database or backups. Delete them deliberately.

## Backups

CronJob `<release>-backup` (`backup.schedule`, default `30 3 * * *`, `concurrencyPolicy: Forbid`)
runs `pg_dump --format=custom` with the PostgreSQL operand image into the backup PVC as
`naileditkitchen-<UTC yyyymmddThhmmssZ>.dump`. It writes `.partial`, verifies the file with
`pg_restore --list`, then renames it and logs `wrote /backups/<file>`. Only after a successful
dump does it delete dumps older than `backup.retentionDays` (default 14, `find -mtime`) and stale
`.partial` files. Failed Jobs are kept (`backup.failedJobsHistoryLimit`) for inspection; backup
freshness alerting and the restore runbook live in `dylanwhitetech/k3s-infrastructure`. A Job
created manually from the CronJob does not update the CronJob's last successful time.

Restore a dump into an empty database with `pg_restore --clean --if-exists --no-owner
--dbname=<target> <file>`; always rehearse against a disposable database first.

## Monitoring

`monitoring.serviceMonitor.enabled` (default `true`) renders a ServiceMonitor for
`/api/metrics` only when the `monitoring.coreos.com/v1` API is available. Add
`monitoring.serviceMonitor.labels` if your Prometheus selects ServiceMonitors by label.

## Smoke test

[`deploy/chart/smoke-test.sh`](../deploy/chart/smoke-test.sh) runs in CI (`Helm chart
applicability` job, see [CI](ci.md)) against a disposable kind cluster with CloudNativePG. It
installs the chart, checks the Cluster, the completed migration Job, the web page, `/api/readyz`
and the seeded recipe count, upgrades to a second image tag (new Job, old Job removed, rollout),
then runs a backup Job and checks its output. To run it locally against a disposable cluster with
the images loaded, always target an explicit context and never a shared cluster:

```bash
KUBE_CONTEXT=kind-nik-chart API_REPOSITORY=naileditkitchen-api WEB_REPOSITORY=naileditkitchen-web \
  FIRST_TAG=smoke-1 SECOND_TAG=smoke-2 bash deploy/chart/smoke-test.sh
```

The script creates namespace `naileditkitchen-smoke` and fails if it already exists; delete the
namespace between runs.
