variable "aws_region" {
  description = "AWS region where the Terraform state backend will live"
  type        = string
  default     = "ap-southeast-1"
}

variable "state_bucket_name" {
  description = "S3 bucket name for Terraform remote state"
  type        = string
}

variable "lock_table_name" {
  description = "DynamoDB table name for Terraform state locking"
  type        = string
}
