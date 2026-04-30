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

output "keda_namespace" {
  description = "Kubernetes namespace used for KEDA when enabled"
  value       = local.enable_keda ? kubernetes_namespace.keda[0].metadata[0].name : null
}

output "snapshot_bucket_name" {
  description = "S3 bucket name created for archived snapshots"
  value       = aws_s3_bucket.snapshots.id
}

output "database_endpoint" {
  description = "Managed PostgreSQL writer endpoint"
  value       = aws_db_instance.postgres.address
}

output "database_port" {
  description = "Managed PostgreSQL port"
  value       = aws_db_instance.postgres.port
}

output "database_name" {
  description = "Application database name"
  value       = aws_db_instance.postgres.db_name
}

output "database_username" {
  description = "Application database username"
  value       = aws_db_instance.postgres.username
}

output "redis_primary_endpoint" {
  description = "Managed Redis primary endpoint"
  value       = aws_elasticache_replication_group.redis.primary_endpoint_address
}

output "redis_reader_endpoint" {
  description = "Managed Redis reader endpoint when multiple cache clusters are enabled"
  value       = aws_elasticache_replication_group.redis.reader_endpoint_address
}

output "redis_port" {
  description = "Managed Redis port"
  value       = aws_elasticache_replication_group.redis.port
}

output "cluster_autoscaler_enabled" {
  description = "Whether cluster-autoscaler is installed for this environment"
  value       = local.enable_cluster_autoscaler
}
