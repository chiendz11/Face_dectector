variable "aws_region" {
  description = "AWS region for the EKS stack"
  type        = string
  default     = "ap-southeast-1"
}

variable "deployment_environment" {
  description = "Logical environment name used to select production-grade defaults"
  type        = string
  default     = "staging"
}

variable "environment_identity" {
  description = "Stable environment identity used for tagging resources (for example staging, production, pr-101)"
  type        = string
  default     = ""
}

variable "env_version" {
  description = "Point-in-time environment version used for AWS resource tags (for example main-<sha> or v1.2.0)"
  type        = string
  default     = ""
}

variable "resource_owner" {
  description = "Optional owner identifier used for cost-allocation tags on sandbox resources"
  type        = string
  default     = ""
}

variable "cluster_name" {
  description = "Name of the EKS cluster"
  type        = string
  default     = "face-detector-staging"
}

variable "cluster_version" {
  description = "Kubernetes version for the EKS control plane"
  type        = string
  default     = "1.30"
}

variable "vpc_cidr" {
  description = "CIDR block for the EKS VPC"
  type        = string
  default     = "10.42.0.0/16"
}

variable "node_instance_type" {
  description = "EC2 instance type for the EKS managed node group"
  type        = string
  default     = "t3.medium"
}

variable "node_min_size" {
  description = "Minimum number of nodes in the EKS managed node group"
  type        = number
  default     = 1
}

variable "node_max_size" {
  description = "Maximum number of nodes in the EKS managed node group"
  type        = number
  default     = 2
}

variable "node_desired_size" {
  description = "Desired number of nodes in the EKS managed node group"
  type        = number
  default     = 1
}

variable "snapshot_bucket_name" {
  description = "S3 bucket name used by the face detector application for archived snapshots"
  type        = string
  default     = "face-detector-employee-images-staging"
}

variable "argocd_namespace" {
  description = "Namespace where ArgoCD is installed"
  type        = string
  default     = "argocd"
}

variable "app_namespace" {
  description = "Namespace where the face detector application is deployed"
  type        = string
  default     = "facedetector"
}

variable "argocd_chart_version" {
  description = "Version of the ArgoCD Helm chart"
  type        = string
  default     = "7.6.12"
}

variable "metrics_server_chart_version" {
  description = "Version of the metrics-server Helm chart"
  type        = string
  default     = "3.13.0"
}

variable "enable_keda" {
  description = "Whether to install KEDA for queue-driven worker autoscaling"
  type        = bool
  default     = null
}

variable "keda_namespace" {
  description = "Namespace where KEDA is installed"
  type        = string
  default     = "keda"
}

variable "keda_chart_version" {
  description = "Version of the KEDA Helm chart"
  type        = string
  default     = "2.19.0"
}

variable "db_name" {
  description = "Application database name for the managed PostgreSQL instance"
  type        = string
}

variable "db_username" {
  description = "Master username for the managed PostgreSQL instance"
  type        = string
}

variable "db_password" {
  description = "Master password for the managed PostgreSQL instance"
  type        = string
  sensitive   = true
}

variable "db_port" {
  description = "TCP port for the managed PostgreSQL instance"
  type        = number
  default     = 5432
}

variable "db_instance_class" {
  description = "Optional RDS instance class override"
  type        = string
  default     = ""
}

variable "db_allocated_storage" {
  description = "Optional RDS allocated storage override in GiB"
  type        = number
  default     = null
}

variable "db_max_allocated_storage" {
  description = "Optional RDS max allocated storage override in GiB"
  type        = number
  default     = null
}

variable "db_engine_version" {
  description = "Engine version for the managed PostgreSQL instance"
  type        = string
  default     = "16"
}

variable "redis_auth_token" {
  description = "Auth token used by the managed Redis replication group"
  type        = string
  sensitive   = true
}

variable "redis_port" {
  description = "TCP port for the managed Redis replication group"
  type        = number
  default     = 6379
}

variable "redis_node_type" {
  description = "Optional ElastiCache node type override"
  type        = string
  default     = ""
}

variable "redis_num_cache_clusters" {
  description = "Optional ElastiCache node count override"
  type        = number
  default     = null
}

variable "redis_engine_version" {
  description = "Engine version for the managed Redis replication group"
  type        = string
  default     = "7.1"
}

variable "enable_cluster_autoscaler" {
  description = "Whether to install cluster-autoscaler for the EKS managed node group"
  type        = bool
  default     = null
}

variable "cluster_autoscaler_chart_version" {
  description = "Version of the cluster-autoscaler Helm chart"
  type        = string
  default     = "9.56.0"
}

variable "cluster_autoscaler_image_tag" {
  description = "Optional cluster-autoscaler image tag override; defaults to the EKS cluster minor"
  type        = string
  default     = ""
}
