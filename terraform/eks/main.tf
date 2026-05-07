terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 3.1"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.27"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = local.resource_tags
  }
}

data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  is_sandbox                    = var.deployment_environment == "sandbox"
  is_staging                    = var.deployment_environment == "staging"
  is_production                 = var.deployment_environment == "production"
  azs                           = slice(data.aws_availability_zones.available.names, 0, 2)
  resolved_environment_identity = trimspace(var.environment_identity) != "" ? trimspace(var.environment_identity) : var.deployment_environment
  resolved_env_version          = trimspace(var.env_version) != "" ? trimspace(var.env_version) : "${local.resolved_environment_identity}-unknown"
  sandbox_capacity_type         = local.is_sandbox ? "SPOT" : "ON_DEMAND"
  resource_tags = merge({
    "facedetector:managed-by"    = "terraform"
    "facedetector:environment"   = var.deployment_environment
    "facedetector:identity"      = local.resolved_environment_identity
    "facedetector:version"       = local.resolved_env_version
    "facedetector:lifecycle"     = local.is_sandbox ? "ephemeral" : "shared"
    "facedetector:cost-tier"     = local.is_sandbox ? "sandbox" : "shared"
    "facedetector:capacity-type" = local.sandbox_capacity_type
    "facedetector:cluster-name"  = var.cluster_name
    }, trimspace(var.resource_owner) != "" ? {
    "facedetector:owner" = trimspace(var.resource_owner)
  } : {})

  public_subnets = [
    for index, _ in local.azs : cidrsubnet(var.vpc_cidr, 4, index)
  ]

  private_subnets = [
    for index, _ in local.azs : cidrsubnet(var.vpc_cidr, 4, index + length(local.azs))
  ]

  use_private_worker_subnets = !local.is_sandbox

  enable_keda = var.enable_keda != null ? var.enable_keda : true

  db_instance_class        = trimspace(var.db_instance_class) != "" ? var.db_instance_class : local.is_production ? "db.t4g.small" : "db.t4g.micro"
  db_allocated_storage     = var.db_allocated_storage != null ? var.db_allocated_storage : local.is_production ? 100 : 20
  db_max_allocated_storage = var.db_max_allocated_storage != null ? var.db_max_allocated_storage : local.is_production ? 200 : 50

  redis_node_type          = trimspace(var.redis_node_type) != "" ? var.redis_node_type : local.is_production ? "cache.t4g.small" : "cache.t4g.micro"
  redis_num_cache_clusters = var.redis_num_cache_clusters != null ? var.redis_num_cache_clusters : local.is_production ? 2 : 1

  enable_cluster_autoscaler    = var.enable_cluster_autoscaler != null ? var.enable_cluster_autoscaler : true
  cluster_autoscaler_image_tag = trimspace(var.cluster_autoscaler_image_tag) != "" ? var.cluster_autoscaler_image_tag : "v${var.cluster_version}.0"

  postgres_identifier        = replace(substr("${var.cluster_name}-postgres", 0, 63), "_", "-")
  redis_replication_group_id = replace(substr("${var.cluster_name}-redis", 0, 40), "_", "-")

  autoscaler_tags = local.enable_cluster_autoscaler ? {
    "k8s.io/cluster-autoscaler/enabled"             = "true"
    "k8s.io/cluster-autoscaler/${var.cluster_name}" = "owned"
  } : {}

  eks_managed_node_groups = {
    default = {
      min_size      = var.node_min_size
      max_size      = var.node_max_size
      desired_size  = var.node_desired_size
      capacity_type = local.sandbox_capacity_type
      tags          = merge(local.resource_tags, local.autoscaler_tags)
    }
  }

  propagated_asg_tags = {
    for tag in flatten([
      for group_name, _ in local.eks_managed_node_groups : [
        for tag_key, tag_value in local.resource_tags : {
          key        = "${group_name}:${tag_key}"
          group_name = group_name
          tag_key    = tag_key
          tag_value  = tag_value
        }
      ]
    ]) : tag.key => tag
  }
}

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.8"

  name = "${var.cluster_name}-vpc"
  cidr = var.vpc_cidr
  azs  = local.azs

  public_subnets          = local.public_subnets
  private_subnets         = local.private_subnets
  map_public_ip_on_launch = local.is_sandbox

  enable_nat_gateway     = local.use_private_worker_subnets
  one_nat_gateway_per_az = local.is_production
  single_nat_gateway     = local.is_staging
  tags                   = local.resource_tags

  public_subnet_tags = merge(local.resource_tags, {
    "kubernetes.io/cluster/${var.cluster_name}" = "shared"
    "kubernetes.io/role/elb"                    = 1
  })

  private_subnet_tags = merge(local.resource_tags, {
    "kubernetes.io/cluster/${var.cluster_name}" = "shared"
    "kubernetes.io/role/internal-elb"           = 1
  })
}

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.13"

  cluster_name                             = var.cluster_name
  cluster_version                          = var.cluster_version
  cluster_endpoint_public_access           = true
  cluster_endpoint_private_access          = true
  enable_cluster_creator_admin_permissions = true
  enable_irsa                              = true
  tags                                     = local.resource_tags

  vpc_id     = module.vpc.vpc_id
  subnet_ids = local.use_private_worker_subnets ? module.vpc.private_subnets : module.vpc.public_subnets

  eks_managed_node_group_defaults = {
    ami_type       = "AL2023_x86_64_STANDARD"
    instance_types = [var.node_instance_type]
    disk_size      = 30
  }

  eks_managed_node_groups = local.eks_managed_node_groups

  cluster_addons = {
    coredns    = {}
    kube-proxy = {}
    vpc-cni    = {}
  }
}

resource "aws_autoscaling_group_tag" "cluster_autoscaler_enabled" {
  for_each = local.enable_cluster_autoscaler ? local.eks_managed_node_groups : {}

  autoscaling_group_name = module.eks.eks_managed_node_groups[each.key].node_group_autoscaling_group_names[0]

  tag {
    key                 = "k8s.io/cluster-autoscaler/enabled"
    value               = "true"
    propagate_at_launch = true
  }
}

resource "aws_autoscaling_group_tag" "cluster_autoscaler_cluster" {
  for_each = local.enable_cluster_autoscaler ? local.eks_managed_node_groups : {}

  autoscaling_group_name = module.eks.eks_managed_node_groups[each.key].node_group_autoscaling_group_names[0]

  tag {
    key                 = "k8s.io/cluster-autoscaler/${var.cluster_name}"
    value               = "owned"
    propagate_at_launch = true
  }
}

resource "aws_autoscaling_group_tag" "node_metadata" {
  for_each = local.propagated_asg_tags

  autoscaling_group_name = module.eks.eks_managed_node_groups[each.value.group_name].node_group_autoscaling_group_names[0]

  tag {
    key                 = each.value.tag_key
    value               = each.value.tag_value
    propagate_at_launch = true
  }
}

provider "kubernetes" {
  host                   = module.eks.cluster_endpoint
  cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)

  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    command     = "aws"
    args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_name]
  }
}

provider "helm" {
  kubernetes {
    host                   = module.eks.cluster_endpoint
    cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)

    exec {
      api_version = "client.authentication.k8s.io/v1beta1"
      command     = "aws"
      args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_name]
    }
  }
}

resource "aws_s3_bucket" "snapshots" {
  bucket        = var.snapshot_bucket_name
  force_destroy = true
}

resource "aws_s3_bucket_versioning" "snapshots" {
  bucket = aws_s3_bucket.snapshots.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "snapshots" {
  bucket = aws_s3_bucket.snapshots.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "snapshots" {
  bucket                  = aws_s3_bucket.snapshots.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_db_subnet_group" "postgres" {
  name       = "${var.cluster_name}-postgres"
  subnet_ids = module.vpc.private_subnets
}

resource "aws_security_group" "postgres" {
  name_prefix = "${var.cluster_name}-postgres-"
  description = "Allow PostgreSQL access from EKS worker nodes"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port       = var.db_port
    to_port         = var.db_port
    protocol        = "tcp"
    security_groups = [module.eks.node_security_group_id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_db_instance" "postgres" {
  identifier                 = local.postgres_identifier
  engine                     = "postgres"
  engine_version             = var.db_engine_version
  instance_class             = local.db_instance_class
  allocated_storage          = local.db_allocated_storage
  max_allocated_storage      = local.db_max_allocated_storage
  storage_type               = "gp3"
  db_name                    = var.db_name
  username                   = var.db_username
  password                   = var.db_password
  port                       = var.db_port
  db_subnet_group_name       = aws_db_subnet_group.postgres.name
  vpc_security_group_ids     = [aws_security_group.postgres.id]
  parameter_group_name       = "default.postgres16"
  backup_retention_period    = local.is_production ? 7 : 1
  storage_encrypted          = true
  multi_az                   = local.is_production
  publicly_accessible        = false
  auto_minor_version_upgrade = true
  apply_immediately          = !local.is_production
  skip_final_snapshot        = true
}

resource "aws_elasticache_subnet_group" "redis" {
  name       = "${var.cluster_name}-redis"
  subnet_ids = module.vpc.private_subnets
}

resource "aws_security_group" "redis" {
  name_prefix = "${var.cluster_name}-redis-"
  description = "Allow Redis access from EKS worker nodes"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port       = var.redis_port
    to_port         = var.redis_port
    protocol        = "tcp"
    security_groups = [module.eks.node_security_group_id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_elasticache_replication_group" "redis" {
  replication_group_id       = local.redis_replication_group_id
  description                = "Managed Redis for ${var.cluster_name}"
  engine                     = "redis"
  engine_version             = var.redis_engine_version
  node_type                  = local.redis_node_type
  num_cache_clusters         = local.redis_num_cache_clusters
  port                       = var.redis_port
  parameter_group_name       = "default.redis7"
  subnet_group_name          = aws_elasticache_subnet_group.redis.name
  security_group_ids         = [aws_security_group.redis.id]
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  auth_token                 = var.redis_auth_token
  automatic_failover_enabled = local.redis_num_cache_clusters > 1
  multi_az_enabled           = local.redis_num_cache_clusters > 1
  snapshot_retention_limit   = local.is_production ? 1 : 0
  apply_immediately          = true
}

data "aws_iam_policy_document" "cluster_autoscaler_assume_role" {
  count = local.enable_cluster_autoscaler ? 1 : 0

  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [module.eks.oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${module.eks.oidc_provider}:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "${module.eks.oidc_provider}:sub"
      values   = ["system:serviceaccount:kube-system:cluster-autoscaler"]
    }
  }
}

data "aws_iam_policy_document" "cluster_autoscaler" {
  count = local.enable_cluster_autoscaler ? 1 : 0

  statement {
    effect = "Allow"
    actions = [
      "autoscaling:DescribeAutoScalingGroups",
      "autoscaling:DescribeAutoScalingInstances",
      "autoscaling:DescribeLaunchConfigurations",
      "autoscaling:DescribeScalingActivities",
      "autoscaling:DescribeTags",
      "autoscaling:DescribeWarmPool",
      "autoscaling:SetDesiredCapacity",
      "autoscaling:TerminateInstanceInAutoScalingGroup",
      "ec2:DescribeAvailabilityZones",
      "ec2:DescribeImages",
      "ec2:DescribeInstanceTypeOfferings",
      "ec2:DescribeInstanceTypes",
      "ec2:DescribeLaunchTemplateVersions",
      "ec2:DescribeSubnets",
      "ec2:DescribeTags",
      "eks:DescribeNodegroup",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role" "cluster_autoscaler" {
  count = local.enable_cluster_autoscaler ? 1 : 0

  name               = "${var.cluster_name}-cluster-autoscaler"
  assume_role_policy = data.aws_iam_policy_document.cluster_autoscaler_assume_role[0].json
}

resource "aws_iam_policy" "cluster_autoscaler" {
  count = local.enable_cluster_autoscaler ? 1 : 0

  name   = "${var.cluster_name}-cluster-autoscaler"
  policy = data.aws_iam_policy_document.cluster_autoscaler[0].json
}

resource "aws_iam_role_policy_attachment" "cluster_autoscaler" {
  count = local.enable_cluster_autoscaler ? 1 : 0

  role       = aws_iam_role.cluster_autoscaler[0].name
  policy_arn = aws_iam_policy.cluster_autoscaler[0].arn
}

resource "kubernetes_namespace" "argocd" {
  metadata {
    name = var.argocd_namespace
  }

  depends_on = [module.eks]
}

resource "kubernetes_namespace" "application" {
  metadata {
    name = var.app_namespace
  }

  timeouts {
    delete = local.is_sandbox ? "15m" : "5m"
  }

  depends_on = [module.eks]
}

resource "kubernetes_namespace" "keda" {
  count = local.enable_keda ? 1 : 0

  metadata {
    name = var.keda_namespace
  }

  depends_on = [module.eks]
}

resource "helm_release" "argocd" {
  name             = "argocd"
  repository       = "https://argoproj.github.io/argo-helm"
  chart            = "argo-cd"
  version          = var.argocd_chart_version
  namespace        = kubernetes_namespace.argocd.metadata[0].name
  create_namespace = false
  wait             = true
  timeout          = local.is_production ? 900 : 1200

  values = [
    yamlencode({
      global = {
        domain = "argocd.${var.cluster_name}.local"
      }
      configs = {
        params = {
          "server.insecure" = true
        }
      }
      server = {
        service = {
          type = "ClusterIP"
        }
        resources = local.is_production ? {} : {
          requests = { cpu = "50m", memory = "128Mi" }
          limits   = { cpu = "300m", memory = "256Mi" }
        }
      }
      repoServer = {
        resources = local.is_production ? {} : {
          requests = { cpu = "50m", memory = "128Mi" }
          limits   = { cpu = "300m", memory = "256Mi" }
        }
      }
      controller = {
        resources = local.is_production ? {} : {
          requests = { cpu = "100m", memory = "256Mi" }
          limits   = { cpu = "500m", memory = "512Mi" }
        }
      }
      redis = {
        resources = local.is_production ? {} : {
          requests = { cpu = "25m", memory = "64Mi" }
          limits   = { cpu = "100m", memory = "128Mi" }
        }
      }
      dex = {
        enabled = false
        resources = local.is_production ? {} : {
          requests = { cpu = "10m", memory = "32Mi" }
          limits   = { cpu = "50m", memory = "64Mi" }
        }
      }
      applicationSet = {
        enabled = false
        resources = local.is_production ? {} : {
          requests = { cpu = "25m", memory = "64Mi" }
          limits   = { cpu = "100m", memory = "128Mi" }
        }
      }
      notifications = {
        enabled = false
        resources = local.is_production ? {} : {
          requests = { cpu = "10m", memory = "32Mi" }
          limits   = { cpu = "50m", memory = "64Mi" }
        }
      }
    })
  ]

  depends_on = [module.eks, kubernetes_namespace.argocd]
}

resource "helm_release" "metrics_server" {
  name             = "metrics-server"
  repository       = "https://kubernetes-sigs.github.io/metrics-server/"
  chart            = "metrics-server"
  version          = var.metrics_server_chart_version
  namespace        = "kube-system"
  create_namespace = false
  wait             = true
  timeout          = 600

  values = [
    yamlencode({
      apiService = {
        insecureSkipTLSVerify = true
      }
    })
  ]

  depends_on = [module.eks]
}

resource "helm_release" "keda" {
  count            = local.enable_keda ? 1 : 0
  name             = "keda"
  repository       = "https://kedacore.github.io/charts"
  chart            = "keda"
  version          = var.keda_chart_version
  namespace        = kubernetes_namespace.keda[0].metadata[0].name
  create_namespace = false
  wait             = !local.is_sandbox
  timeout          = 600

  depends_on = [module.eks, kubernetes_namespace.keda]
}

resource "helm_release" "cluster_autoscaler" {
  count            = local.enable_cluster_autoscaler ? 1 : 0
  name             = "cluster-autoscaler"
  repository       = "https://kubernetes.github.io/autoscaler"
  chart            = "cluster-autoscaler"
  version          = var.cluster_autoscaler_chart_version
  namespace        = "kube-system"
  create_namespace = false
  wait             = true
  timeout          = 600

  values = [
    yamlencode({
      cloudProvider = "aws"
      awsRegion     = var.aws_region
      autoDiscovery = {
        clusterName = var.cluster_name
      }
      fullnameOverride = "cluster-autoscaler"
      image = {
        tag = local.cluster_autoscaler_image_tag
      }
      rbac = {
        serviceAccount = {
          create = true
          name   = "cluster-autoscaler"
          annotations = {
            "eks.amazonaws.com/role-arn" = aws_iam_role.cluster_autoscaler[0].arn
          }
        }
      }
      extraArgs = {
        "balance-similar-node-groups"   = true
        expander                        = "least-waste"
        "skip-nodes-with-local-storage" = false
      }
    })
  ]

  depends_on = [
    module.eks,
    aws_iam_role_policy_attachment.cluster_autoscaler,
    aws_autoscaling_group_tag.cluster_autoscaler_enabled,
    aws_autoscaling_group_tag.cluster_autoscaler_cluster,
  ]
}
