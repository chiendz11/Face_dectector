package main

import rego.v1

deny contains msg if {
  not non_empty_string(object.get(input, "name", ""))
  msg := "Composite action must declare name"
}

deny contains msg if {
  not non_empty_string(object.get(input, "description", ""))
  msg := "Composite action must declare description"
}

deny contains msg if {
  runs := object.get(input, "runs", {})
  not non_empty_string(object.get(runs, "using", ""))
  msg := "Composite action is missing runs.using"
}

deny contains msg if {
  runs := object.get(input, "runs", {})
  lower(object.get(runs, "using", "")) == "composite"
  steps := object.get(runs, "steps", [])
  some idx
  step := steps[idx]
  object.get(step, "run", "") != ""
  object.get(step, "shell", "") == ""
  msg := sprintf("Composite action run step #%d must declare shell", [idx + 1])
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

non_empty_string(value) if {
  type_name(value) == "string"
  value != ""
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