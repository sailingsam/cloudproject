{{/* Base name for all resources. */}}
{{- define "url-shortener.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "url-shortener.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/* Image tag actually deployed: the git SHA from CI, or appVersion. */}}
{{- define "url-shortener.imageTag" -}}
{{- default .Chart.AppVersion .Values.image.tag -}}
{{- end -}}

{{- define "url-shortener.postgresName" -}}
{{- printf "%s-postgres" (include "url-shortener.fullname" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/* Labels shared by every resource. */}}
{{- define "url-shortener.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" }}
app.kubernetes.io/name: {{ include "url-shortener.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: url-shortener
{{- end -}}

{{/* Selector labels for the API pods (must never change between releases). */}}
{{- define "url-shortener.apiSelectorLabels" -}}
app.kubernetes.io/name: {{ include "url-shortener.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: api
{{- end -}}

{{- define "url-shortener.postgresSelectorLabels" -}}
app.kubernetes.io/name: {{ include "url-shortener.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: database
{{- end -}}

{{- define "url-shortener.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{- default (include "url-shortener.fullname" .) .Values.serviceAccount.name -}}
{{- else -}}
{{- default "default" .Values.serviceAccount.name -}}
{{- end -}}
{{- end -}}

{{/* True when Prometheus Operator CRDs exist and monitoring is enabled. */}}
{{- define "url-shortener.monitoringEnabled" -}}
{{- if and .Values.monitoring.enabled (.Capabilities.APIVersions.Has "monitoring.coreos.com/v1") -}}
true
{{- end -}}
{{- end -}}
