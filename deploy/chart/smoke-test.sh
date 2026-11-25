#!/usr/bin/env bash
# Fresh-install and upgrade smoke test for deploy/chart/naileditkitchen on a disposable cluster.
#
# Requires kubectl, helm and KUBE_CONTEXT naming a throwaway cluster that already runs the CloudNativePG
# operator, and API/web images available to it under two tags (FIRST_TAG, SECOND_TAG) so the
# upgrade rolls every pod. Never point this at a real cluster: it installs and deletes a release.
set -euo pipefail

: "${KUBE_CONTEXT:?}" "${API_REPOSITORY:?}" "${WEB_REPOSITORY:?}" "${FIRST_TAG:?}" "${SECOND_TAG:?}"
RELEASE="${RELEASE:-naileditkitchen}"
NAMESPACE="${NAMESPACE:-naileditkitchen-smoke}"
STORAGE_CLASS="${STORAGE_CLASS:-standard}"
CHART="$(dirname "$0")/naileditkitchen"

kc() { kubectl --context "$KUBE_CONTEXT" --namespace "$NAMESPACE" "$@"; }

diagnose() {
  echo "::group::Diagnostics"
  kc get all,cluster.postgresql.cnpg.io,pvc,secret -o wide || true
  kc get events --sort-by=.lastTimestamp | tail -n 60 || true
  for pod in $(kc get pods -o name); do
    kc logs "$pod" --all-containers --tail=80 || true
  done
  echo "::endgroup::"
}
trap 'status=$?; if [ "$status" -ne 0 ]; then diagnose; fi; kill $(jobs -p) 2>/dev/null || true' EXIT

install() {
  # Same wait semantics as the GitOps release: workloads ready and the migration Job complete.
  helm upgrade --install "$RELEASE" "$CHART" --kube-context "$KUBE_CONTEXT" --namespace "$NAMESPACE" \
    --wait --wait-for-jobs --timeout 15m \
    --set api.image.repository="$API_REPOSITORY" --set api.image.tag="$1" \
    --set web.image.repository="$WEB_REPOSITORY" --set web.image.tag="$1" \
    --set api.image.pullPolicy=Never --set web.image.pullPolicy=Never \
    --set database.storage.storageClass="$STORAGE_CLASS" --set database.storage.size=1Gi \
    --set backup.storage.existingClaim=smoke-backups \
    --set monitoring.serviceMonitor.enabled=false
}

check_app() {
  # Distinct local ports per phase, so a slow-exiting forwarder cannot shadow the next check.
  local PORT=$1 API_PORT=$2
  kubectl --context "$KUBE_CONTEXT" --namespace "$NAMESPACE" \
    port-forward "svc/$RELEASE-web" "$PORT:8080" >/dev/null &
  local web=$!
  kubectl --context "$KUBE_CONTEXT" --namespace "$NAMESPACE" \
    port-forward "svc/$RELEASE-api" "$API_PORT:8000" >/dev/null &
  local api=$!
  sleep 3
  curl --fail --silent --show-error --max-time 10 --retry 5 --retry-all-errors "http://127.0.0.1:$PORT/" | grep -q '<div id="root">'
  curl --fail --silent --show-error --max-time 10 --retry 5 --retry-all-errors "http://127.0.0.1:$API_PORT/api/readyz"
  echo
  local count
  count="$(curl --fail --silent --show-error --max-time 10 "http://127.0.0.1:$API_PORT/api/recipes?limit=100" | grep -o '"slug":' | wc -l)"
  local expected
  expected="$(find "$(dirname "$0")/../../recipes" -maxdepth 1 -name '*.yaml' | wc -l)"
  kill "$web" "$api" 2>/dev/null || true
  wait "$web" "$api" 2>/dev/null || true
  echo "recipes served: $count (expected $expected)"
  [ "$count" -eq "$expected" ]
}

echo "== Fresh install =="
# Helm --wait waits for chart PVCs to bind; kind's WaitForFirstConsumer class only binds when the
# backup Job runs, so the smoke test supplies the backup volume as an existing claim.
kubectl --context "$KUBE_CONTEXT" create namespace "$NAMESPACE"
kc apply -f - <<EOF
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: smoke-backups
spec:
  accessModes: [ReadWriteOnce]
  storageClassName: $STORAGE_CLASS
  resources:
    requests:
      storage: 1Gi
EOF
install "$FIRST_TAG"
installation_id="$(kc get configmap "$RELEASE-lifecycle" -o jsonpath='{.data.installation-id}')"
[ -n "$installation_id" ]
kc wait --for=condition=Ready "cluster.postgresql.cnpg.io/$RELEASE-db" --timeout=60s
kc wait --for=condition=Complete "job/$RELEASE-migrate-1" --timeout=60s
kc get secret "$RELEASE-db-app" >/dev/null
kc get "cronjob/$RELEASE-backup" "ingress/$RELEASE" >/dev/null
check_app 18080 18000

echo "== Upgrade =="
install "$SECOND_TAG"
if [ "$(kc get configmap "$RELEASE-lifecycle" -o jsonpath='{.data.installation-id}')" != "$installation_id" ]; then
  echo "lifecycle installation identity changed during upgrade" >&2
  exit 1
fi
kc wait --for=condition=Complete "job/$RELEASE-migrate-2" --timeout=60s
if kc get "job/$RELEASE-migrate-1" >/dev/null 2>&1; then
  echo "previous revision's migration Job was not removed" >&2
  exit 1
fi
for component in api web; do
  image="$(kc get "deployment/$RELEASE-$component" -o jsonpath='{.spec.template.spec.containers[0].image}')"
  case "$image" in *":$SECOND_TAG") ;; *) echo "$component not upgraded: $image" >&2; exit 1 ;; esac
  kc rollout status "deployment/$RELEASE-$component" --timeout=60s
done
check_app 18081 18001

echo "== Backup =="
kc create job --from="cronjob/$RELEASE-backup" smoke-backup
kc wait --for=condition=Complete job/smoke-backup --timeout=300s
backup_logs="$(kc logs job/smoke-backup)"
printf '%s\n' "$backup_logs" >&2
printf '%s\n' "$backup_logs" | grep -Eq '^wrote /backups/naileditkitchen-[0-9]{8}T[0-9]{6}Z\.dump$'

echo "== Rollback with migration blocked =="
# Recreating revision 1 reuses its historical marker; the new Job must still finish.
kc exec "$RELEASE-db-1" -c postgres -- psql -d naileditkitchen -c \
  'SELECT pg_advisory_lock(7412025); SELECT pg_sleep(120);' >/dev/null 2>&1 &
lock_pid=$!
for attempt in $(seq 1 30); do
  held="$(kc exec "$RELEASE-db-1" -c postgres -- psql -d naileditkitchen -tAc \
    "SELECT EXISTS (SELECT 1 FROM pg_locks WHERE locktype='advisory' AND objid=7412025 AND granted);")"
  [ "$held" = "t" ] && break
  sleep 1
done
[ "$held" = "t" ]
helm rollback "$RELEASE" 1 --kube-context "$KUBE_CONTEXT" --namespace "$NAMESPACE" \
  --wait --wait-for-jobs --timeout 5m &
rollback_pid=$!
for attempt in $(seq 1 45); do
  api_pods="$(kc get pods -l "app.kubernetes.io/instance=$RELEASE,app.kubernetes.io/component=api" \
    -o jsonpath='{range .items[*]}{.spec.containers[0].image}{" "}{.status.containerStatuses[0].ready}{" "}{.status.containerStatuses[0].state.waiting.reason}{"\n"}{end}')"
  if printf '%s\n' "$api_pods" | grep -Fq "$API_REPOSITORY:$FIRST_TAG false PodInitializing" &&
     printf '%s\n' "$api_pods" | grep -Fq "$API_REPOSITORY:$SECOND_TAG true "; then
    break
  fi
  sleep 2
done
printf '%s\n' "$api_pods" | grep -Fq "$API_REPOSITORY:$FIRST_TAG false PodInitializing"
printf '%s\n' "$api_pods" | grep -Fq "$API_REPOSITORY:$SECOND_TAG true "
kc exec "$RELEASE-db-1" -c postgres -- psql -d naileditkitchen -tAc \
  "SELECT pg_terminate_backend(pid) FROM pg_locks WHERE locktype='advisory' AND objid=7412025 AND granted AND pid<>pg_backend_pid();" | grep -qx t
wait "$lock_pid" || true
wait "$rollback_pid"
kc wait --for=condition=Complete "job/$RELEASE-migrate-1" --timeout=60s
kc rollout status "deployment/$RELEASE-api" --timeout=60s
check_app 18082 18002

echo "Chart fresh install, upgrade, backup and rollback smoke test passed."
