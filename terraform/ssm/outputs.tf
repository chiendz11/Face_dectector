output "ssm_parameter_names" {
  description = "List of created or updated SSM parameter names"
  value       = [for p in aws_ssm_parameter.env : p.name]
}

output "ssm_parameter_count" {
  description = "Number of SSM parameters created or updated"
  value       = length(aws_ssm_parameter.env)
}
