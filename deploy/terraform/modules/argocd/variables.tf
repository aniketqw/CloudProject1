variable "applications" {
  type        = any
  description = "Argo CD Applications to create, keyed by name (argocd-apps chart format: source, destination, syncPolicy, optional additionalAnnotations)."
}

variable "argocd_cm_extra" {
  type        = map(string)
  default     = {}
  description = "Extra keys merged into the argocd-cm ConfigMap (used by the local test cluster)."
}
