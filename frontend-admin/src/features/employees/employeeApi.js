export async function listEmployees({ includeInactive, authHeaders }) {
  const suffix = includeInactive ? "?include_inactive=true" : "";
  const response = await fetch(`/api/admin/employees${suffix}`, {
    method: "GET",
    headers: authHeaders,
  });
  const payload = await readJson(response);
  return { response, payload };
}

export async function createEmployee({ employee, jsonHeaders }) {
  const response = await fetch("/api/admin/employees", {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify(employee),
  });
  const payload = await readJson(response);
  return { response, payload };
}

export async function updateEmployee({ employeeCode, employee, jsonHeaders }) {
  const response = await fetch(`/api/admin/employees/${encodeURIComponent(employeeCode)}`, {
    method: "PATCH",
    headers: jsonHeaders,
    body: JSON.stringify(employee),
  });
  const payload = await readJson(response);
  return { response, payload };
}

export async function deactivateEmployee({ employeeCode, authHeaders }) {
  const response = await fetch(`/api/admin/employees/${encodeURIComponent(employeeCode)}`, {
    method: "DELETE",
    headers: authHeaders,
  });
  const payload = await readJson(response);
  return { response, payload };
}

export async function restoreEmployee({ employeeCode, authHeaders }) {
  const response = await fetch(`/api/admin/employees/${encodeURIComponent(employeeCode)}/restore`, {
    method: "POST",
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
