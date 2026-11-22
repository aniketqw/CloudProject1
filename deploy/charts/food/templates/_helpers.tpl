{{/* Application image: imageRepository:imageTag when both are set (cloud, Terraform), else the full `image` value. */}}
{{- define "food.image" -}}
{{- if and .Values.imageRepository .Values.imageDigest -}}
{{ printf "%s@%s" .Values.imageRepository .Values.imageDigest }}
{{- else if and .Values.imageRepository .Values.imageTag -}}
{{ printf "%s:%s" .Values.imageRepository .Values.imageTag }}
{{- else -}}
{{ .Values.image }}
{{- end -}}
{{- end -}}
