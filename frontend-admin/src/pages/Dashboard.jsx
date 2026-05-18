import { useEffect, useMemo, useState } from "react";
import EnrollmentCapture from "../components/EnrollmentCapture";
import StatCard from "../components/StatCard";

const defaultSession = {
  status: "ready",
};

export default function Dashboard() {
  const [token, setToken] = useState(() => localStorage.getItem("admin_token") || "");
  const [employees, setEmployees] = useState([]);
  const [status, setStatus] = useState(defaultSession.status);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [includeInactive, setIncludeInactive] = useState(false);
  const [credentials, setCredentials] = useState({ username: "admin", password: "admin" });
  const [newEmployee, setNewEmployee] = useState({ employee_code: "", full_name: "", department: "" });
  const [editingCode, setEditingCode] = useState("");
  const [editEmployee, setEditEmployee] = useState({ full_name: "", department: "" });
  const [enrollmentSession, setEnrollmentSession] = useState(null);

  const authHeaders = useMemo(() => (token ? { Authorization: `Bearer ${token}` } : {}), [token]);
  const jsonHeaders = useMemo(() => ({ "Content-Type": "application/json", ...authHeaders }), [authHeaders]);
  const activeEmployees = employees.filter((employee) => employee.active !== false);
  const inactiveEmployees = employees.filter((employee) => employee.active === false);

  useEffect(() => {
    if (token) {
      fetchEmployees();
    }
  }, [token, includeInactive]);

  async function fetchEmployees() {
    setStatus("loading");
    setError("");

    try {
      const suffix = includeInactive ? "?include_inactive=true" : "";
      const response = await fetch(`/api/admin/employees${suffix}`, {
        method: "GET",
        headers: authHeaders,
      });

      if (response.status === 401) {
        handleLogout();
        return;
      }

      if (!response.ok) {
        throw new Error("Failed to load employees");
      }

      const payload = await response.json();
      setEmployees(payload.items || []);
      setStatus("loaded");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
      setStatus("error");
    }
  }

  async function handleLogin(event) {
    event.preventDefault();
    setStatus("loading");
    setError("");

    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(credentials),
      });

      if (!response.ok) {
        throw new Error("Invalid username or password");
      }

      const payload = await response.json();
      localStorage.setItem("admin_token", payload.access_token);
      setToken(payload.access_token);
      setStatus("loaded");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
      setStatus("error");
    }
  }

  function handleLogout() {
    localStorage.removeItem("admin_token");
    setToken("");
    setEmployees([]);
    setEditingCode("");
    setEnrollmentSession(null);
    setMessage("");
    setStatus(defaultSession.status);
    setError("");
  }

  async function handleCreateEmployee(event) {
    event.preventDefault();
    setStatus("loading");
    setError("");
    setMessage("");

    try {
      const response = await fetch("/api/admin/employees", {
        method: "POST",
        headers: jsonHeaders,
        body: JSON.stringify(newEmployee),
      });

      if (response.status === 401) {
        handleLogout();
        return;
      }

      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail || "Create employee failed");
      }

      await fetchEmployees();
      setNewEmployee({ employee_code: "", full_name: "", department: "" });
      setMessage(`Employee ${payload.employee_code} created.`);
      setStatus("loaded");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create failed");
      setStatus("error");
    }
  }

  function startEdit(employee) {
    setEditingCode(employee.employee_code);
    setEditEmployee({
      full_name: employee.full_name || "",
      department: employee.department || "",
    });
    setError("");
    setMessage("");
  }

  async function submitEdit(event, employeeCode) {
    event.preventDefault();
    setStatus("loading");
    setError("");
    setMessage("");

    try {
      const response = await fetch(`/api/admin/employees/${encodeURIComponent(employeeCode)}`, {
        method: "PATCH",
        headers: jsonHeaders,
        body: JSON.stringify(editEmployee),
      });

      if (response.status === 401) {
        handleLogout();
        return;
      }

      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail || "Update employee failed");
      }

      setEditingCode("");
      await fetchEmployees();
      setMessage(`Employee ${payload.employee_code} updated.`);
      setStatus("loaded");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed");
      setStatus("error");
    }
  }

  async function deactivateEmployee(employeeCode) {
    setStatus("loading");
    setError("");
    setMessage("");

    try {
      const response = await fetch(`/api/admin/employees/${encodeURIComponent(employeeCode)}`, {
        method: "DELETE",
        headers: authHeaders,
      });

      if (response.status === 401) {
        handleLogout();
        return;
      }

      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail || "Deactivate employee failed");
      }

      await fetchEmployees();
      setMessage(`Employee ${payload.employee_code} deactivated.`);
      setStatus("loaded");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Deactivate failed");
      setStatus("error");
    }
  }

  async function restoreEmployee(employeeCode) {
    setStatus("loading");
    setError("");
    setMessage("");

    try {
      const response = await fetch(`/api/admin/employees/${encodeURIComponent(employeeCode)}/restore`, {
        method: "POST",
        headers: authHeaders,
      });

      if (response.status === 401) {
        handleLogout();
        return;
      }

      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail || "Restore employee failed");
      }

      await fetchEmployees();
      setMessage(`Employee ${payload.employee_code} restored.`);
      setStatus("loaded");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Restore failed");
      setStatus("error");
    }
  }

  async function createEnrollmentSession(employee) {
    setStatus("loading");
    setError("");
    setMessage("");

    try {
      const response = await fetch(
        `/api/admin/employees/${encodeURIComponent(employee.employee_code)}/enrollment-sessions`,
        {
          method: "POST",
          headers: authHeaders,
        },
      );

      if (response.status === 401) {
        handleLogout();
        return;
      }

      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail || "Create enrollment session failed");
      }

      setEnrollmentSession({
        ...payload,
        full_name: employee.full_name,
        department: employee.department,
      });
      setStatus("loaded");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create enrollment session failed");
      setStatus("error");
    }
  }

  function handleEnrollmentComplete(payload) {
    setMessage(payload.message || "Enrollment completed.");
    setEnrollmentSession(null);
    fetchEmployees();
  }

  return (
    <main className="page-shell">
      <section className="hero">
        <p className="eyebrow">Face Access Control</p>
        <h1>Admin workspace for a practical office access-control system.</h1>
        <p className="lead">
          {token
            ? "Manage staff identities, edit employee records, and issue token-bound face enrollment sessions."
            : "Log in to connect this admin UI to the backend API and manage employees."}
        </p>
      </section>

      {!token ? (
        <section className="card form-card">
          <h2>Sign in</h2>
          <form onSubmit={handleLogin}>
            <label>
              Username
              <input
                type="text"
                value={credentials.username}
                onChange={(event) => setCredentials({ ...credentials, username: event.target.value })}
                required
              />
            </label>
            <label>
              Password
              <input
                type="password"
                value={credentials.password}
                onChange={(event) => setCredentials({ ...credentials, password: event.target.value })}
                required
              />
            </label>
            <button type="submit" className="button">
              Sign in
            </button>
            {error && <p className="status-error">{error}</p>}
          </form>
        </section>
      ) : (
        <>
          <section className="grid">
            <StatCard title="Active employees" value={activeEmployees.length.toString()} hint="Available for access checks" />
            <StatCard title="Inactive records" value={inactiveEmployees.length.toString()} hint="Soft-deleted audit records" />
            <StatCard title="Status" value={status} hint="Backend API session state" />
          </section>

          <section className="card form-card">
            <div className="form-row">
              <h2>New employee</h2>
              <button type="button" className="button button-secondary" onClick={handleLogout}>
                Log out
              </button>
            </div>
            <form onSubmit={handleCreateEmployee}>
              <label>
                Employee code
                <input
                  type="text"
                  value={newEmployee.employee_code}
                  onChange={(event) => setNewEmployee({ ...newEmployee, employee_code: event.target.value })}
                  required
                />
              </label>
              <label>
                Full name
                <input
                  type="text"
                  value={newEmployee.full_name}
                  onChange={(event) => setNewEmployee({ ...newEmployee, full_name: event.target.value })}
                  required
                />
              </label>
              <label>
                Department
                <input
                  type="text"
                  value={newEmployee.department}
                  onChange={(event) => setNewEmployee({ ...newEmployee, department: event.target.value })}
                />
              </label>
              <button type="submit" className="button">
                Add employee
              </button>
            </form>
          </section>

          {enrollmentSession && (
            <EnrollmentCapture
              session={enrollmentSession}
              onCancel={() => setEnrollmentSession(null)}
              onComplete={handleEnrollmentComplete}
            />
          )}

          <section className="card">
            <div className="form-row">
              <h2>Registered employees</h2>
              <label className="toggle-row">
                <input
                  type="checkbox"
                  checked={includeInactive}
                  onChange={(event) => setIncludeInactive(event.target.checked)}
                />
                Show inactive
              </label>
            </div>

            {employees.length === 0 ? (
              <p>No employees registered yet.</p>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>Code</th>
                    <th>Full name</th>
                    <th>Department</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {employees.map((employee) => (
                    <tr key={employee.employee_code} className={employee.active === false ? "inactive-row" : ""}>
                      <td>{employee.employee_code}</td>
                      <td>
                        {editingCode === employee.employee_code ? (
                          <input
                            aria-label={`Full name for ${employee.employee_code}`}
                            value={editEmployee.full_name}
                            onChange={(event) => setEditEmployee({ ...editEmployee, full_name: event.target.value })}
                          />
                        ) : (
                          employee.full_name
                        )}
                      </td>
                      <td>
                        {editingCode === employee.employee_code ? (
                          <input
                            aria-label={`Department for ${employee.employee_code}`}
                            value={editEmployee.department}
                            onChange={(event) => setEditEmployee({ ...editEmployee, department: event.target.value })}
                          />
                        ) : (
                          employee.department || "None"
                        )}
                      </td>
                      <td>
                        <span className={`state-pill ${employee.active === false ? "warn" : "ok"}`}>
                          {employee.active === false ? "inactive" : "active"}
                        </span>
                      </td>
                      <td>
                        {editingCode === employee.employee_code ? (
                          <form className="button-row" onSubmit={(event) => submitEdit(event, employee.employee_code)}>
                            <button type="submit" className="button button-small">
                              Save
                            </button>
                            <button
                              type="button"
                              className="button button-small button-secondary"
                              onClick={() => setEditingCode("")}
                            >
                              Cancel
                            </button>
                          </form>
                        ) : (
                          <div className="button-row">
                            {employee.active === false ? (
                              <button
                                type="button"
                                className="button button-small"
                                onClick={() => restoreEmployee(employee.employee_code)}
                              >
                                Restore
                              </button>
                            ) : (
                              <>
                                <button
                                  type="button"
                                  className="button button-small"
                                  onClick={() => createEnrollmentSession(employee)}
                                >
                                  Open camera
                                </button>
                                <button
                                  type="button"
                                  className="button button-small button-secondary"
                                  onClick={() => startEdit(employee)}
                                >
                                  Edit
                                </button>
                                <button
                                  type="button"
                                  className="button button-small button-danger"
                                  onClick={() => deactivateEmployee(employee.employee_code)}
                                >
                                  Deactivate
                                </button>
                              </>
                            )}
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {message && <p className="status-success">{message}</p>}
            {error && <p className="status-error">{error}</p>}
          </section>
        </>
      )}
    </main>
  );
}
