variable "aws_region" {
  description = "AWS region where the SSM parameters are stored"
  type        = string
  default     = "ap-southeast-1"
}

variable "environment" {
  description = "Target environment name for the SSM parameter path (staging or production)"
  type        = string
}

variable "env_file_path" {
  description = "Optional path to a backend runtime env file. When unset, the committed example template for the selected environment is used."
  type        = string
  default     = null
}

variable "parameter_type" {
  description = "SSM parameter type used for synced runtime configuration. SecureString is the recommended default for deployed environments."
  type        = string
  default     = "SecureString"

  validation {
    condition     = contains(["String", "SecureString"], var.parameter_type)
    error_message = "parameter_type must be either String or SecureString."
  }
}

variable "kms_key_id" {
  description = "Optional KMS key ID or ARN used when parameter_type is SecureString. Leave unset to use the AWS managed SSM key."
  type        = string
  default     = null
}
