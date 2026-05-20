export default function EmployeeForm({
  employee,
  error,
  onChange,
  onLogout,
  onSubmit,
}) {
  return (
    <section className="card form-card">
      <div className="form-row">
        <h2>New employee</h2>
        <button type="button" className="button button-secondary" onClick={onLogout}>
          Log out
        </button>
      </div>
      <form onSubmit={onSubmit}>
        <label>
          Employee code
          <input
            type="text"
            value={employee.employee_code}
            onChange={(event) => onChange({ ...employee, employee_code: event.target.value })}
            required
          />
        </label>
        <label>
          Full name
          <input
            type="text"
            value={employee.full_name}
            onChange={(event) => onChange({ ...employee, full_name: event.target.value })}
            required
          />
        </label>
        <label>
          Department
          <input
            type="text"
            value={employee.department}
            onChange={(event) => onChange({ ...employee, department: event.target.value })}
          />
        </label>
        <button type="submit" className="button">
          Add employee
        </button>
      </form>
      {error && <p className="status-error">{error}</p>}
    </section>
  );
}
