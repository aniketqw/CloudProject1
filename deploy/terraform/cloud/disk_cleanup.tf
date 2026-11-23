# Deleting a GKE cluster does not delete the persistent disks its volume claims created (the ZooKeeper claims keep their
# volumes by design). Five runs of this platform left 24 orphaned 2 GB disks behind. This resource is created before the
# cluster and destroyed after it (the cluster depends on it), and removes the disks created for the `food` namespace.
resource "terraform_data" "pvc_disk_cleanup" {
  input = {
    project = var.project_id
  }

  provisioner "local-exec" {
    when        = destroy
    interpreter = ["bash", "-c"]
    command     = <<-EOT
      export CLOUDSDK_AUTH_ACCESS_TOKEN="$(gcloud auth application-default print-access-token 2>/dev/null || gcloud auth print-access-token)"
      gcloud compute disks list --project '${self.input.project}' --filter='name~^pvc- AND NOT users:*' --format='csv[no-heading](name,zone.basename())' |
        while IFS=, read -r name zone; do
          gcloud compute disks delete "$name" --zone "$zone" --project '${self.input.project}' --quiet || true
        done
    EOT
  }
}
