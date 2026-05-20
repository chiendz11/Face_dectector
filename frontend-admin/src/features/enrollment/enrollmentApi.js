export async function createEnrollmentSession({ employeeCode, authHeaders }) {
  const response = await fetch(`/api/admin/employees/${encodeURIComponent(employeeCode)}/enrollment-sessions`, {
    method: "POST",
    headers: authHeaders,
  });
  const payload = await readJson(response);
  return { response, payload };
}

export async function getEnrollmentSession({ token }) {
  const response = await fetch(`/api/admin/enrollment-sessions/${encodeURIComponent(token)}`);
  const payload = await readJson(response);
  return { response, payload };
}

export async function completeEnrollmentSession({ token, formData }) {
  const response = await fetch(`/api/admin/enrollment-sessions/${encodeURIComponent(token)}/complete`, {
    method: "POST",
    body: formData,
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
