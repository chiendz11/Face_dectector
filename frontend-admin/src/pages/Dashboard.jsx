import { useEffect, useMemo, useState } from "react";
import StatCard from "../components/StatCard";
import DepartmentPanel from "../features/departments/DepartmentPanel";
import {
  createDepartment as requestCreateDepartment,
  deactivateDepartment as requestDeactivateDepartment,
  listDepartments as requestDepartments,
  updateDepartment as requestUpdateDepartment,
} from "../features/departments/departmentApi";
import EmployeeForm from "../features/employees/EmployeeForm";
import EmployeeTable from "../features/employees/EmployeeTable";
import {
  createEmployee as requestCreateEmployee,
  deactivateEmployee as requestDeactivateEmployee,
  listEmployees as requestEmployees,
  restoreEmployee as requestRestoreEmployee,
  updateEmployee as requestUpdateEmployee,
} from "../features/employees/employeeApi";
import FaceEnrollmentPage from "../features/enrollment/FaceEnrollmentPage";

const defaultSession = {
  status: "ready",
};

export default function Dashboard() {
  const [token, setToken] = useState(() => localStorage.getItem("admin_token") || "");
  const [employees, setEmployees] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [status, setStatus] = useState(defaultSession.status);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [includeInactive, setIncludeInactive] = useState(false);
  const [credentials, setCredentials] = useState({ username: "admin", password: "admin" });
  const [newEmployee, setNewEmployee] = useState({ full_name: "", department_id: "" });
  const [newDepartment, setNewDepartment] = useState({ name: "" });
  const [editingCode, setEditingCode] = useState("");
  const [editEmployee, setEditEmployee] = useState({ full_name: "", department_id: "" });
  const [editingDepartmentId, setEditingDepartmentId] = useState("");
  const [editDepartment, setEditDepartment] = useState({ name: "" });
  const [activeSection, setActiveSection] = useState("directory");
  const [enrollmentQuerySeed, setEnrollmentQuerySeed] = useState("");

  const authHeaders = useMemo(() => (token ? { Authorization: `Bearer ${token}` } : {}), [token]);
  const jsonHeaders = useMemo(() => ({ "Content-Type": "application/json", ...authHeaders }), [authHeaders]);
  const activeEmployees = employees.filter((employee) => employee.active !== false);
  const inactiveEmployees = employees.filter((employee) => employee.active === false);

  useEffect(() => {
    if (token) {
      fetchEmployees();
      fetchDepartments();
    }
  }, [token, includeInactive]);

  function employeePayload(employee) {
    return {
      full_name: employee.full_name,
      department_id: employee.department_id ? Number(employee.department_id) : null,
    };
  }

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

  async function fetchDepartments() {
    try {
      const { response, payload } = await requestDepartments({ includeInactive: false, authHeaders });

      if (response.status === 401) {
        handleLogout();
        return;
      }

      if (!response.ok) {
        throw new Error(payload.detail || "Failed to load departments");
      }

      setDepartments(payload.items || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load departments");
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
    setDepartments([]);
    setEditingCode("");
    setEditingDepartmentId("");
    setActiveSection("directory");
    setEnrollmentQuerySeed("");
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
        employee: employeePayload(newEmployee),
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
      setNewEmployee({ full_name: "", department_id: "" });
      setMessage(`Employee ${payload.employee_code} created.`);
      setStatus("loaded");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create failed");
      setStatus("error");
    }
  }

  async function handleCreateDepartment(event) {
    event.preventDefault();
    setStatus("loading");
    setError("");
    setMessage("");

    try {
      const { response, payload } = await requestCreateDepartment({
        department: newDepartment,
        jsonHeaders,
      });

      if (response.status === 401) {
        handleLogout();
        return;
      }

      if (!response.ok) {
        throw new Error(payload.detail || "Create department failed");
      }

      await fetchDepartments();
      setNewDepartment({ name: "" });
      setMessage(`Department ${payload.name} created.`);
      setStatus("loaded");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create department failed");
      setStatus("error");
    }
  }

  function startEdit(employee) {
    setEditingCode(employee.employee_code);
    setEditEmployee({
      full_name: employee.full_name || "",
      department_id: employee.department_id ? String(employee.department_id) : "",
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
        employee: employeePayload(editEmployee),
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

  function startDepartmentEdit(department) {
    setEditingDepartmentId(department.id);
    setEditDepartment({ name: department.name || "" });
    setError("");
    setMessage("");
  }

  async function submitDepartmentEdit(event, departmentId) {
    event.preventDefault();
    setStatus("loading");
    setError("");
    setMessage("");

    try {
      const { response, payload } = await requestUpdateDepartment({
        departmentId,
        department: editDepartment,
        jsonHeaders,
      });

      if (response.status === 401) {
        handleLogout();
        return;
      }

      if (!response.ok) {
        throw new Error(payload.detail || "Update department failed");
      }

      setEditingDepartmentId("");
      await fetchDepartments();
      await fetchEmployees();
      setMessage(`Department ${payload.name} updated.`);
      setStatus("loaded");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update department failed");
      setStatus("error");
    }
  }

  async function deactivateDepartment(departmentId) {
    setStatus("loading");
    setError("");
    setMessage("");

    try {
      const { response, payload } = await requestDeactivateDepartment({ departmentId, authHeaders });

      if (response.status === 401) {
        handleLogout();
        return;
      }

      if (!response.ok) {
        throw new Error(payload.detail || "Deactivate department failed");
      }

      await fetchDepartments();
      setMessage(`Department ${payload.id} deactivated.`);
      setStatus("loaded");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Deactivate department failed");
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

  function openEnrollment(employee) {
    setEnrollmentQuerySeed(employee.employee_code);
    setActiveSection("enrollment");
    setError("");
    setMessage("");
  }

  function handleEnrollmentComplete() {
    setMessage("Enrollment saved.");
    fetchEmployees();
  }

  return (
    <main className="page-shell">
      <section className="hero">
        <p className="eyebrow">Face Access Control</p>
        <h1>Admin workspace for a practical office access-control system.</h1>
        <p className="lead">
          {token
            ? "Operate the local directory, face enrollment, recognition logs, audit logs, and edge devices from one console."
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
          <nav className="console-nav" aria-label="Admin console sections">
            <button
              type="button"
              className={`nav-button ${activeSection === "directory" ? "active" : ""}`}
              onClick={() => setActiveSection("directory")}
            >
              Directory
            </button>
            <button
              type="button"
              className={`nav-button ${activeSection === "enrollment" ? "active" : ""}`}
              onClick={() => setActiveSection("enrollment")}
            >
              Face Enrollment
            </button>
            <button
              type="button"
              className={`nav-button ${activeSection === "recognition-logs" ? "active" : ""}`}
              onClick={() => setActiveSection("recognition-logs")}
            >
              Recognition Logs
            </button>
            <button
              type="button"
              className={`nav-button ${activeSection === "audit-logs" ? "active" : ""}`}
              onClick={() => setActiveSection("audit-logs")}
            >
              Audit Logs
            </button>
            <button
              type="button"
              className={`nav-button ${activeSection === "devices" ? "active" : ""}`}
              onClick={() => setActiveSection("devices")}
            >
              Devices
            </button>
          </nav>

          <section className="grid">
            <StatCard title="Active employees" value={activeEmployees.length.toString()} hint="Available for access checks" />
            <StatCard title="Inactive records" value={inactiveEmployees.length.toString()} hint="Soft-deleted audit records" />
            <StatCard title="Status" value={status} hint="Backend API session state" />
          </section>

          {activeSection === "directory" && (
            <>
              <EmployeeForm
                departments={departments}
                employee={newEmployee}
                error={error}
                onChange={setNewEmployee}
                onLogout={handleLogout}
                onSubmit={handleCreateEmployee}
              />

              <DepartmentPanel
                departments={departments}
                editingDepartmentId={editingDepartmentId}
                editDepartment={editDepartment}
                newDepartment={newDepartment}
                onCreateDepartment={handleCreateDepartment}
                onDeactivateDepartment={deactivateDepartment}
                onEditDepartmentCancel={() => setEditingDepartmentId("")}
                onEditDepartmentChange={setEditDepartment}
                onEditDepartmentStart={startDepartmentEdit}
                onNewDepartmentChange={setNewDepartment}
                onSubmitDepartmentEdit={submitDepartmentEdit}
              />

              <EmployeeTable
                departments={departments}
                editEmployee={editEmployee}
                editingCode={editingCode}
                employees={employees}
                error={error}
                includeInactive={includeInactive}
                message={message}
                onDeactivate={deactivateEmployee}
                onEditCancel={() => setEditingCode("")}
                onEditChange={setEditEmployee}
                onEditStart={startEdit}
                onIncludeInactiveChange={setIncludeInactive}
                onOpenEnrollment={openEnrollment}
                onRestore={restoreEmployee}
                onSubmitEdit={submitEdit}
              />
            </>
          )}

          {activeSection === "enrollment" && (
            <FaceEnrollmentPage
              authHeaders={authHeaders}
              querySeed={enrollmentQuerySeed}
              onEnrollmentComplete={handleEnrollmentComplete}
              onUnauthorized={handleLogout}
            />
          )}

          {activeSection === "recognition-logs" && (
            <section className="card form-card">
              <p className="eyebrow">Face Recognition</p>
              <h2>Recognition Logs</h2>
              <p className="muted">No recognition events loaded yet.</p>
            </section>
          )}

          {activeSection === "audit-logs" && (
            <section className="card form-card">
              <p className="eyebrow">Governance</p>
              <h2>Audit Logs</h2>
              <p className="muted">No audit events loaded yet.</p>
            </section>
          )}

          {activeSection === "devices" && (
            <section className="card form-card">
              <p className="eyebrow">Edge</p>
              <h2>Devices</h2>
              <p className="muted">No devices registered yet.</p>
            </section>
          )}
        </>
      )}
    </main>
  );
}
