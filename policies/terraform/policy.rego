package main

import rego.v1

warn contains msg if {
  modules := object.get(object.get(input, "module", {}), "eks", [])
  some idx
  module := modules[idx]
  object.get(module, "cluster_endpoint_public_access", false) == true
  not public_eks_endpoint_exception("eks")
  msg := "module.eks enables cluster_endpoint_public_access; require documented exception or private endpoint rollout"
}

warn contains msg if {
  buckets := object.get(object.get(input, "resource", {}), "aws_s3_bucket", {})
  some name
  instances := buckets[name]
  some idx
  bucket := instances[idx]
  object.get(bucket, "force_destroy", false) == true
  not force_destroy_bucket_exception(name)
  msg := sprintf("S3 bucket %s sets force_destroy=true; require lifecycle review or exception", [name])
}

warn contains msg if {
  databases := object.get(object.get(input, "resource", {}), "aws_db_instance", {})
  some name
  instances := databases[name]
  some idx
  database := instances[idx]
  object.get(database, "skip_final_snapshot", false) == true
  not skip_final_snapshot_exception(name)
  msg := sprintf("RDS instance %s skips final snapshots; require documented exception or deletion safeguard", [name])
}

warn contains msg if {
  groups := object.get(object.get(input, "resource", {}), "aws_security_group", {})
  some name
  instances := groups[name]
  some idx
  group := instances[idx]
  ingresses := object.get(group, "ingress", [])
  some ingress_idx
  ingress := ingresses[ingress_idx]
  cidr_blocks := object.get(ingress, "cidr_blocks", [])
  cidr_blocks[_] == "0.0.0.0/0"
  sensitive_ingress(ingress)
  not public_ingress_security_group_exception(name)
  msg := sprintf("Security group %s allows public ingress on a sensitive port range; require documented exception", [name])
}

sensitive_ingress(ingress) if {
  object.get(ingress, "protocol", "") == "tcp"
  from_port := object.get(ingress, "from_port", -1)
  to_port := object.get(ingress, "to_port", -1)
  from_port == 22
  to_port == 22
}

sensitive_ingress(ingress) if {
  object.get(ingress, "protocol", "") == "tcp"
  from_port := object.get(ingress, "from_port", -1)
  to_port := object.get(ingress, "to_port", -1)
  from_port == 5432
  to_port == 5432
}

sensitive_ingress(ingress) if {
  object.get(ingress, "protocol", "") == "tcp"
  from_port := object.get(ingress, "from_port", -1)
  to_port := object.get(ingress, "to_port", -1)
  from_port == 6379
  to_port == 6379
}

force_destroy_bucket_exception(name) if {
  some exception in data.exceptions.infra.force_destroy_buckets
  exception.resource_name == name
  exception_active(exception)
}

public_eks_endpoint_exception(name) if {
  some exception in data.exceptions.infra.public_eks_endpoints
  exception.module_name == name
  exception_active(exception)
}

public_ingress_security_group_exception(name) if {
  some exception in data.exceptions.infra.public_ingress_security_groups
  exception.resource_name == name
  exception_active(exception)
}

skip_final_snapshot_exception(name) if {
  some exception in data.exceptions.infra.skip_final_snapshots
  exception.resource_name == name
  exception_active(exception)
}

exception_active(exception) if {
  object.get(exception, "expires_on", "") == ""
}

exception_active(exception) if {
  expires_on := object.get(exception, "expires_on", "")
  expires_on != ""
  time.now_ns() <= time.parse_rfc3339_ns(sprintf("%sT00:00:00Z", [expires_on]))
}