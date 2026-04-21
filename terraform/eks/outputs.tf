output "cluster_name" {
  description = "EKS cluster name"
  value       = module.eks.cluster_name
}

output "cluster_endpoint" {
  description = "EKS cluster endpoint"
  value       = module.eks.cluster_endpoint
}

output "app_namespace" {
  description = "Kubernetes namespace used for the face detector application"
  value       = kubernetes_namespace.application.metadata[0].name
}

output "argocd_namespace" {
  description = "Kubernetes namespace used for ArgoCD"
  value       = kubernetes_namespace.argocd.metadata[0].name
}

output "snapshot_bucket_name" {
  description = "S3 bucket name created for archived snapshots"
  value       = aws_s3_bucket.snapshots.id
}
