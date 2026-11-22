# Installs Argo CD and the Applications that point it at the Git repository.
# Both are Helm releases so the whole thing works on a brand-new cluster in one
# apply: a kubernetes_manifest resource would need the cluster to exist at plan time.

resource "helm_release" "argocd" {
  name             = "argocd"
  namespace        = "argocd"
  create_namespace = true
  repository       = "https://argoproj.github.io/argo-helm"
  chart            = "argo-cd"
  version          = "10.18.0"
  wait             = true
  timeout          = 600

  values = [jsonencode({
    configs = {
      # A sync sometimes waits for a hook Job that has already completed and never notices. After 5 minutes the sync is
      # failed and the retry policy starts a fresh one, which passes; without this someone had to clear it by hand.
      params = { "server.insecure" = false, "controller.sync.timeout.seconds" = "300" }
      cm = merge({
        "resource.customizations.health.argoproj.io_Application" = "hs = {}\nhs.status = \"Progressing\"\nif obj.status ~= nil and obj.status.health ~= nil then\n hs.status = obj.status.health.status\n hs.message = obj.status.health.message\nend\nreturn hs"
      }, var.argocd_cm_extra)
      rbac = { "policy.default" = "role:readonly" }
    }
    server = {
      service   = { type = "ClusterIP" }
      resources = { requests = { cpu = "50m", memory = "96Mi" }, limits = { cpu = "500m", memory = "512Mi" } }
    }
    dex            = { enabled = false }
    notifications  = { enabled = false }
    applicationSet = { enabled = false }
    controller = {
      resources = { requests = { cpu = "100m", memory = "256Mi" }, limits = { cpu = "500m", memory = "1Gi" } }
    }
    repoServer = {
      resources = { requests = { cpu = "50m", memory = "128Mi" }, limits = { cpu = "500m", memory = "1Gi" } }
    }
    redis = {
      resources = { requests = { cpu = "50m", memory = "64Mi" }, limits = { cpu = "500m", memory = "512Mi" } }
    }
  })]
}

resource "helm_release" "applications" {
  name       = "argocd-applications"
  namespace  = "argocd"
  repository = "https://argoproj.github.io/argo-helm"
  chart      = "argocd-apps"
  version    = "2.0.8"
  wait       = true
  timeout    = 300

  values = [jsonencode({
    applications = {
      for name, app in var.applications : name => merge({
        namespace  = "argocd"
        finalizers = ["resources-finalizer.argocd.argoproj.io"]
        project    = "default"
      }, app)
    }
  })]

  depends_on = [helm_release.argocd]
}
