export async function listDepartments({ includeInactive, authHeaders }) {
  const suffix = includeInactive ? "?include_inactive=true" : "";
  const response = await fetch(`/api/admin/departments${suffix}`, {
    headers: authHeaders,
  });
  const payload = await readJson(response);
  return { response, payload };
}

export async function createDepartment({ department, jsonHeaders }) {
  const response = await fetch("/api/admin/departments", {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify(department),
  });
  const payload = await readJson(response);
  return { response, payload };
}

export async function updateDepartment({ departmentId, department, jsonHeaders }) {
  const response = await fetch(`/api/admin/departments/${encodeURIComponent(departmentId)}`, {
    method: "PATCH",
    headers: jsonHeaders,
    body: JSON.stringify(department),
  });
  const payload = await readJson(response);
  return { response, payload };
}

export async function deactivateDepartment({ departmentId, authHeaders }) {
  const response = await fetch(`/api/admin/departments/${encodeURIComponent(departmentId)}`, {
    method: "DELETE",
    headers: authHeaders,
  });
  const payload = await readJson(response);
  return { response, payload };
}

async function readJson(response) {
  try {
    return await response.json();
  } catch {
    return {};
  }
}
