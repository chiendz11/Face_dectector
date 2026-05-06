package main

import rego.v1

trusted_pull_request_target_workflows := {
  "Sandbox Auto Apply",
  "Sandbox Auto Destroy",
  "Terraform PR Plan",
}

deny contains msg if {
  not has_top_level_permissions
  msg := "Workflow must declare top-level permissions"
}

deny contains msg if {
  pair := walk(input)[_]
  path := pair[0]
  value := pair[1]
  is_uses_field(path, value)
  uses_mutable_ref(value)
  not mutable_ref_exception(value)
  msg := sprintf("Mutable action reference %q is not allowed", [value])
}

deny contains msg if {
  workflow := workflow_name
  trusted_pull_request_target_workflows[workflow]
  has_event("pull_request")
  not trust_boundary_exception("trusted-workflow-pull-request-event", workflow)
  msg := sprintf("Trusted workflow %q must not declare pull_request; keep production semantics anchored to the default branch or use the workflow R&D lane with a time-boxed exception", [workflow])
}

deny contains msg if {
  workflow := workflow_name
  trusted_pull_request_target_workflows[workflow]
  not has_event("pull_request_target")
  not trust_boundary_exception("trusted-workflow-missing-pull_request_target", workflow)
  msg := sprintf("Trusted workflow %q must declare pull_request_target; keep production semantics anchored to the default branch or use the workflow R&D lane with a time-boxed exception", [workflow])
}

deny contains msg if {
  workflow := workflow_name
  has_event("pull_request")
  has_permission_write("id-token")
  not trust_boundary_exception("pull-request-id-token-write", workflow)
  msg := sprintf("Workflow %q must not request id-token: write on pull_request; move OIDC usage to a trusted event or add a time-boxed exception", [workflow])
}

workflow_name := object.get(input, "name", "<unnamed workflow>")

workflow_triggers := object.get(input, "on", object.get(input, "true", object.get(input, true, {})))

has_top_level_permissions if {
  permissions := object.get(input, "permissions", null)
  valid_permissions(permissions)
}

has_event(event) if {
  triggers := workflow_triggers
  type_name(triggers) == "string"
  lower(triggers) == event
}

has_event(event) if {
  triggers := workflow_triggers
  type_name(triggers) == "array"
  some index
  item := triggers[index]
  type_name(item) == "string"
  lower(item) == event
}

has_event(event) if {
  triggers := workflow_triggers
  type_name(triggers) == "object"
  object.get(triggers, event, null) != null
}

has_permission_write(permission_name) if {
  permissions := object.get(input, "permissions", {})
  permission_is_write(permissions, permission_name)
}

has_permission_write(permission_name) if {
  jobs := object.get(input, "jobs", {})
  some job_name
  job := jobs[job_name]
  permissions := object.get(job, "permissions", {})
  permission_is_write(permissions, permission_name)
}

valid_permissions(permissions) if {
  type_name(permissions) == "object"
}

valid_permissions(permissions) if {
  type_name(permissions) == "string"
}

permission_is_write(permissions, permission_name) if {
  type_name(permissions) == "object"
  lower(object.get(permissions, permission_name, "")) == "write"
}

permission_is_write(permissions, _) if {
  type_name(permissions) == "string"
  lower(permissions) == "write-all"
}

is_uses_field(path, value) if {
  count(path) > 0
  path[count(path) - 1] == "uses"
  type_name(value) == "string"
}

uses_mutable_ref(uses) if {
  not startswith(uses, "./")
  contains(uses, "@")
  parts := split(uses, "@")
  ref := lower(parts[count(parts) - 1])
  ref == "main"
}

uses_mutable_ref(uses) if {
  not startswith(uses, "./")
  contains(uses, "@")
  parts := split(uses, "@")
  ref := lower(parts[count(parts) - 1])
  ref == "master"
}

uses_mutable_ref(uses) if {
  not startswith(uses, "./")
  contains(uses, "@")
  parts := split(uses, "@")
  ref := lower(parts[count(parts) - 1])
  ref == "head"
}

uses_mutable_ref(uses) if {
  not startswith(uses, "./")
  contains(uses, "@")
  parts := split(uses, "@")
  ref := lower(parts[count(parts) - 1])
  ref == "latest"
}

uses_mutable_ref(uses) if {
  not startswith(uses, "./")
  contains(uses, "@")
  parts := split(uses, "@")
  ref := parts[count(parts) - 1]
  regex.match(`^v\d+(\.\d+)*$`, ref)
}

mutable_ref_exception(uses) if {
  some exception in data.exceptions.github.mutable_refs
  exception.subject == uses
  exception_active(exception)
}

trust_boundary_exception(rule, workflow) if {
  some exception in object.get(object.get(data.exceptions, "github", {}), "trust_boundary_changes", [])
  exception.rule == rule
  exception.workflow == workflow
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