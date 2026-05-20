import { useEffect, useMemo, useState } from "react";
import StatCard from "../components/StatCard";
import EmployeeForm from "../features/employees/EmployeeForm";
import EmployeeTable from "../features/employees/EmployeeTable";
import {
  createEmployee as requestCreateEmployee,
  deactivateEmployee as requestDeactivateEmployee,
  listEmployees as requestEmployees,
  restoreEmployee as requestRestoreEmployee,
  updateEmployee as requestUpdateEmployee,
} from "../features/employees/employeeApi";
import EnrollmentCapture from "../features/enrollment/EnrollmentCapture";
import { createEnrollmentSession as requestEnrollmentSession } from "../features/enrollment/enrollmentApi";

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
      const { response, payload } = await requestEmployees({ includeInactive, authHeaders });

      if (response.status === 401) {
        handleLogout();
        return;
      }

      if (!response.ok) {
        throw new Error("Failed to load employees");
      }

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
      const { response, payload } = await requestCreateEmployee({
        employee: newEmployee,
        jsonHeaders,
      });

      if (response.status === 401) {
        handleLogout();
        return;
      }

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
      const { response, payload } = await requestUpdateEmployee({
        employeeCode,
        employee: editEmployee,
        jsonHeaders,
      });

      if (response.status === 401) {
        handleLogout();
        return;
      }

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
      const { response, payload } = await requestDeactivateEmployee({ employeeCode, authHeaders });

      if (response.status === 401) {
        handleLogout();
        return;
      }

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
      const { response, payload } = await requestRestoreEmployee({ employeeCode, authHeaders });

      if (response.status === 401) {
        handleLogout();
        return;
      }

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
      const { response, payload } = await requestEnrollmentSession({
        employeeCode: employee.employee_code,
        authHeaders,
      });

      if (response.status === 401) {
        handleLogout();
        return;
      }

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

          <EmployeeForm
            employee={newEmployee}
            error={error}
            onChange={setNewEmployee}
            onLogout={handleLogout}
            onSubmit={handleCreateEmployee}
          />

          {enrollmentSession && (
            <EnrollmentCapture
              session={enrollmentSession}
              onCancel={() => setEnrollmentSession(null)}
              onComplete={handleEnrollmentComplete}
            />
          )}

          <EmployeeTable
            editEmployee={editEmployee}
            editingCode={editingCode}
            employees={employees}
            error={error}
            includeInactive={includeInactive}
            message={message}
            onCreateEnrollmentSession={createEnrollmentSession}
            onDeactivate={deactivateEmployee}
            onEditCancel={() => setEditingCode("")}
            onEditChange={setEditEmployee}
            onEditStart={startEdit}
            onIncludeInactiveChange={setIncludeInactive}
            onRestore={restoreEmployee}
            onSubmitEdit={submitEdit}
          />
        </>
      )}
    </main>
  );
}
