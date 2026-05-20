export default function EmployeeForm({
  departments,
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
          <select
            value={employee.department_id}
            onChange={(event) => onChange({ ...employee, department_id: event.target.value })}
          >
            <option value="">Unassigned</option>
            {departments.map((department) => (
              <option key={department.id} value={department.id}>
                {department.name}
              </option>
            ))}
          </select>
        </label>
        <button type="submit" className="button">
          Add employee
        </button>
      </form>
      {error && <p className="status-error">{error}</p>}
    </section>
  );
}
