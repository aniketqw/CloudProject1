# Argo CD and the root Application, from the shared module, installed once the node pool exists.
module "argocd" {
  source     = "../modules/argocd"
  repository = var.git_repository
  revision   = var.git_revision

  depends_on = [google_container_node_pool.apps]
}
