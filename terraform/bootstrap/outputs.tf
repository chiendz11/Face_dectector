output "state_bucket_name" {
  description = "Terraform remote state bucket name"
  value       = aws_s3_bucket.terraform_state.id
}

output "lock_table_name" {
  description = "Terraform state lock DynamoDB table name"
  value       = aws_dynamodb_table.terraform_lock.name
}
