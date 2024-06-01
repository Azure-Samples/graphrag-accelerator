{{/*
Expand the name of the chart.
*/}}
{{- define "graphrag.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "graphrag.fullname" -}}
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

{{/*
Create a graphrag-query fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "graphrag.query.fullname" -}}
{{- if .Values.query.fullnameOverride }}
{{- .Values.query.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- printf "%s-%s" .Release.Name .Values.query.name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s-%s" .Release.Name $name .Values.query.name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create a graphrag-index fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "graphrag.index.fullname" -}}
{{- if .Values.index.fullnameOverride }}
{{- .Values.index.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- printf "%s-%s" .Release.Name .Values.index.name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s-%s" .Release.Name $name .Values.index.name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "graphrag.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "graphrag.common.labels" -}}
azure.workload.identity/use: "true"
helm.sh/chart: {{ include "graphrag.chart" . }}
{{ include "graphrag.common.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "graphrag.labels" -}}
{{ include "graphrag.common.labels" . }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "graphrag.common.selectorLabels" -}}
app.kubernetes.io/name: {{ include "graphrag.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "graphrag.query.labels" -}}
{{ include "graphrag.common.labels" . }}
{{ include "graphrag.query.selectorLabels" . }}
{{- end -}}

{{- define "graphrag.query.selectorLabels" -}}
{{ include "graphrag.common.selectorLabels" . }}
component: {{ .Values.query.name | quote }}
{{- end -}}

{{- define "graphrag.index.labels" -}}
{{ include "graphrag.common.labels" . }}
{{ include "graphrag.index.selectorLabels" . }}
{{- end -}}

{{- define "graphrag.index.selectorLabels" -}}
{{ include "graphrag.common.selectorLabels" . }}
component: {{ .Values.index.name | quote }}
{{- end -}}

{{/*
Create the name of the service account to use
*/}}
{{- define "graphrag.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "graphrag.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}
