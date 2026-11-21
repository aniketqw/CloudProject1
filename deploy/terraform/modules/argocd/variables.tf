variable "repository" {
  type        = string
  description = "Git repository Argo CD watches."
}

variable "revision" {
  type        = string
  description = "Git revision (branch, tag or commit) Argo CD syncs."
}

variable "source_path" {
  type        = string
  default     = "deploy/environments/team"
  description = "Folder inside the repository that holds the child Applications."
}

variable "directory_include" {
  type        = string
  default     = "applications.yaml"
  description = "File pattern Argo CD reads inside source_path. Null reads the whole folder."
}

variable "app_name" {
  type    = string
  default = "food-root"
}

variable "destination_namespace" {
  type    = string
  default = "argocd"
}

variable "argocd_cm_extra" {
  type        = map(string)
  default     = {}
  description = "Extra keys merged into the argocd-cm ConfigMap (used by the local test cluster)."
}
