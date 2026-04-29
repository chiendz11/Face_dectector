terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = local.resource_tags
  }
}

locals {
  default_env_file = "${path.module}/../../deploy/runtime/backend.${var.environment}.env.example"
  env_file         = coalesce(var.env_file_path, local.default_env_file)
  resolved_kms_key = var.kms_key_id == null ? "" : trimspace(var.kms_key_id)
  resolved_environment_identity = trimspace(var.environment_identity) != "" ? trimspace(var.environment_identity) : var.environment
  resolved_env_version         = trimspace(var.env_version) != "" ? trimspace(var.env_version) : "${local.resolved_environment_identity}-unknown"
  resource_tags = merge({
    "facedetector:managed-by"  = "terraform"
    "facedetector:environment" = var.environment
    "facedetector:identity"    = local.resolved_environment_identity
    "facedetector:version"     = local.resolved_env_version
    "facedetector:lifecycle"   = startswith(var.environment, "sandbox/") ? "ephemeral" : "shared"
    "facedetector:cost-tier"   = startswith(var.environment, "sandbox/") ? "sandbox" : "shared"
    "facedetector:parameter-set" = "/facedetector/${var.environment}"
  }, trimspace(var.resource_owner) != "" ? {
    "facedetector:owner" = trimspace(var.resource_owner)
  } : {})

  raw_lines = split("\n", trimspace(file(local.env_file)))

  parsed_entries = [
    for line in local.raw_lines : {
      key   = trimspace(split("=", line)[0])
      value = trimspace(join("=", slice(split("=", line), 1, length(split("=", line)))))
    }
    if length(trimspace(line)) > 0 && !startswith(trimspace(line), "#") && length(regexall("=", line)) > 0
  ]

  ssm_parameters = {
    for entry in local.parsed_entries : entry.key => entry.value
    if length(entry.key) > 0 && length(entry.value) > 0
  }
}

resource "aws_ssm_parameter" "env" {
  for_each = local.ssm_parameters

  name        = "/facedetector/${var.environment}/${each.key}"
  description = "Face detector ${var.environment} environment variable"
  type        = var.parameter_type
  value       = each.value
  overwrite   = true
  key_id      = var.parameter_type == "SecureString" && local.resolved_kms_key != "" ? local.resolved_kms_key : null
}
