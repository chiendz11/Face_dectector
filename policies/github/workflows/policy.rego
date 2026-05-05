package main

import rego.v1

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

has_top_level_permissions if {
  permissions := object.get(input, "permissions", null)
  valid_permissions(permissions)
}

valid_permissions(permissions) if {
  type_name(permissions) == "object"
}

valid_permissions(permissions) if {
  type_name(permissions) == "string"
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

exception_active(exception) if {
  object.get(exception, "expires_on", "") == ""
}

exception_active(exception) if {
  expires_on := object.get(exception, "expires_on", "")
  expires_on != ""
  time.now_ns() <= time.parse_rfc3339_ns(sprintf("%sT00:00:00Z", [expires_on]))
}