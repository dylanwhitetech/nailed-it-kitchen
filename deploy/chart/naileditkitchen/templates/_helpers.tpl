{{- define "naileditkitchen.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "naileditkitchen.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/* Common labels; call with (dict "root" $ "component" "api"). */}}
{{- define "naileditkitchen.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .root.Chart.Name .root.Chart.Version | replace "+" "_" }}
{{ include "naileditkitchen.selectorLabels" . }}
app.kubernetes.io/version: {{ .root.Chart.AppVersion | trunc 63 | quote }}
app.kubernetes.io/managed-by: {{ .root.Release.Service }}
app.kubernetes.io/part-of: naileditkitchen
{{- end }}

{{- define "naileditkitchen.selectorLabels" -}}
app.kubernetes.io/name: {{ include "naileditkitchen.name" .root }}
app.kubernetes.io/instance: {{ .root.Release.Name }}
app.kubernetes.io/component: {{ .component }}
{{- end }}

{{/*
Image reference; call with (dict "root" $ "image" .Values.api.image).
repository@digest when a digest is set, otherwise repository:tag with tag defaulting to appVersion.
*/}}
{{- define "naileditkitchen.image" -}}
{{- $image := .image }}
{{- if $image.digest }}
{{- printf "%s@%s" $image.repository $image.digest }}
{{- else }}
{{- $tag := toString (default .root.Chart.AppVersion $image.tag) }}
{{- if eq $tag "unreleased" }}
{{- fail (printf "%s: set a tag or digest; this chart has no released appVersion" $image.repository) }}
{{- end }}
{{- if eq $tag "latest" }}
{{- fail (printf "%s: the latest tag is not allowed; use a commit SHA tag or digest" $image.repository) }}
{{- end }}
{{- printf "%s:%s" $image.repository $tag }}
{{- end }}
{{- end }}

{{- define "naileditkitchen.dbCluster" -}}
{{- printf "%s-db" (include "naileditkitchen.fullname" .) }}
{{- end }}

{{/* Database environment from the CloudNativePG-generated app Secret; the password stays out of the URL. */}}
{{- define "naileditkitchen.databaseEnv" -}}
- name: PGPASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ include "naileditkitchen.dbCluster" . }}-app
      key: password
- name: DATABASE_URL
  value: {{ printf "postgresql+psycopg://%s@%s-rw:5432/%s" .Values.database.name (include "naileditkitchen.dbCluster" .) .Values.database.name | quote }}
{{- end }}

{{/* Shared installation identity and revision for migration and API readiness. */}}
{{- define "naileditkitchen.lifecycleEnv" -}}
- name: LIFECYCLE_INSTALLATION_ID
  valueFrom:
    configMapKeyRef:
      name: {{ include "naileditkitchen.fullname" . }}-lifecycle
      key: installation-id
- name: LIFECYCLE_REVISION
  value: {{ .Release.Revision | quote }}
{{- end }}

{{- define "naileditkitchen.containerSecurityContext" -}}
allowPrivilegeEscalation: false
readOnlyRootFilesystem: true
capabilities:
  drop: ["ALL"]
{{- end }}

{{/* Pod security context; call with a numeric user id. */}}
{{- define "naileditkitchen.podSecurityContext" -}}
runAsNonRoot: true
runAsUser: {{ . }}
runAsGroup: {{ . }}
fsGroup: {{ . }}
seccompProfile:
  type: RuntimeDefault
{{- end }}
