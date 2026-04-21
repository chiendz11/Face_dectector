variable "aws_region" {
  description = "AWS region for the EKS stack"
  type        = string
  default     = "ap-southeast-1"
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
