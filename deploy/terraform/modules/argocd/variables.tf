variable "applications" {
  type        = any
  description = "Argo CD Applications to create, keyed by name (argocd-apps chart format: source, destination, syncPolicy, optional additionalAnnotations)."
}

variable "argocd_cm_extra" {
  type        = map(string)
  default     = {}
  description = "Extra keys merged into the argocd-cm ConfigMap (used by the local test cluster)."
}

variable "admin_password_bcrypt" {
  type        = string
  default     = ""
  sensitive   = true
  description = "bcrypt hash of the Argo CD admin password. Empty keeps Argo CD's generated initial admin secret."
}

variable "admin_password_mtime" {
  type        = string
  default     = ""
  description = "RFC3339 time the admin password was set (Argo CD uses it to invalidate older sessions)."
}
