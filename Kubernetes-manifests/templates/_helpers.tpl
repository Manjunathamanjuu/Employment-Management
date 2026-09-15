{{/*
Chart name.
*/}}
{{- define "employment-management.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Fully qualified application name.
*/}}
{{- define "employment-management.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name (include "employment-management.name" .) | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}

{{/*
PostgreSQL resource name.
*/}}
{{- define "employment-management.postgresName" -}}
{{- printf "%s-postgres" .Release.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels.
*/}}
{{- define "employment-management.labels" -}}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version | replace "+" "_" }}
app.kubernetes.io/name: {{ include "employment-management.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Application selector labels.
*/}}
{{- define "employment-management.selectorLabels" -}}
app.kubernetes.io/name: {{ include "employment-management.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}