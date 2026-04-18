import { useEffect, useMemo, useState } from "react";
import StatCard from "../components/StatCard";

const defaultSession = {
  employees: [],
  status: "ready",
  error: "",
};

export default function Dashboard() {
  const [token, setToken] = useState(() => localStorage.getItem("admin_token") || "");
  const [employees, setEmployees] = useState([]);
  const [status, setStatus] = useState(defaultSession.status);
  const [error, setError] = useState("");
  const [credentials, setCredentials] = useState({ username: "admin", password: "admin" });
  const [newEmployee, setNewEmployee] = useState({ employee_code: "", full_name: "", department: "" });

  const headers = useMemo(
    () => ({
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    }),
    [token],
  );

  useEffect(() => {
    if (token) {
      fetchEmployees();
    }
  }, [token]);

  const fetchEmployees = async () => {
    setStatus("loading");
    setError("");

    try {
      const response = await fetch("/api/admin/employees", {
        method: "GET",
        headers,
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
  };

  const handleLogin = async (event) => {
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
  };

  const handleLogout = () => {
    localStorage.removeItem("admin_token");
    setToken("");
    setEmployees([]);
    setStatus(defaultSession.status);
    setError("");
  };

  const handleCreateEmployee = async (event) => {
    event.preventDefault();
    setStatus("loading");
    setError("");

    try {
      const response = await fetch("/api/admin/employees", {
        method: "POST",
        headers,
        body: JSON.stringify(newEmployee),
      });

      if (response.status === 401) {
        handleLogout();
        return;
      }

      if (!response.ok) {
        const payload = await response.json();
        throw new Error(payload.detail || "Create employee failed");
      }

      await fetchEmployees();
      setNewEmployee({ employee_code: "", full_name: "", department: "" });
      setStatus("loaded");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create failed");
      setStatus("error");
    }
  };

  return (
    <main className="page-shell">
      <section className="hero">
        <p className="eyebrow">Face Access Control</p>
        <h1>Admin workspace for a practical office access-control system.</h1>
        <p className="lead">
          {token
            ? "Manage your staff list and watch the kiosk recognition pipeline."
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
            <StatCard title="Employees" value={employees.length.toString()} hint="Registered staff identities" />
            <StatCard title="Gates" value="1" hint="Primary kiosk connection" />
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
            {error && <p className="status-error">{error}</p>}
          </section>

          <section className="card">
            <h2>Registered employees</h2>
            {employees.length === 0 ? (
              <p>No employees registered yet.</p>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>Code</th>
                    <th>Full name</th>
                    <th>Department</th>
                  </tr>
                </thead>
                <tbody>
                  {employees.map((employee) => (
                    <tr key={employee.employee_code}>
                      <td>{employee.employee_code}</td>
                      <td>{employee.full_name}</td>
                      <td>{employee.department || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        </>
      )}
    </main>
  );
}
