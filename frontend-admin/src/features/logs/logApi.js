export async function listRecognitionEvents({ filters = {}, authHeaders }) {
  const params = new URLSearchParams();
  if (filters.matched && filters.matched !== "all") {
    params.set("matched", filters.matched);
  }
  if (filters.employee_code?.trim()) {
    params.set("employee_code", filters.employee_code.trim());
  }
  if (filters.device_name?.trim()) {
    params.set("device_name", filters.device_name.trim());
  }
  params.set("limit", String(filters.limit || 50));
  const response = await fetch(`/api/admin/recognition-events?${params.toString()}`, {
    headers: authHeaders,
  });
  const payload = await readJson(response);
  return { response, payload };
}

export async function listAuditEvents({ filters = {}, authHeaders }) {
  const params = new URLSearchParams();
  if (filters.actor?.trim()) {
    params.set("actor", filters.actor.trim());
  }
  if (filters.action?.trim()) {
    params.set("action", filters.action.trim());
  }
  if (filters.resource_type?.trim()) {
    params.set("resource_type", filters.resource_type.trim());
  }
  params.set("limit", String(filters.limit || 50));
  const response = await fetch(`/api/admin/audit-events?${params.toString()}`, {
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
