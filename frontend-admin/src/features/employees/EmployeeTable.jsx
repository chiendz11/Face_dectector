export default function EmployeeTable({
  departments,
  editEmployee,
  editingCode,
  employees,
  error,
  includeInactive,
  message,
  onDeactivate,
  onEditChange,
  onEditStart,
  onEditCancel,
  onOpenEnrollment,
  onIncludeInactiveChange,
  onRestore,
  onSubmitEdit,
}) {
  return (
    <section className="card">
      <div className="form-row">
        <h2>Registered employees</h2>
        <label className="toggle-row">
          <input
            type="checkbox"
            checked={includeInactive}
            onChange={(event) => onIncludeInactiveChange(event.target.checked)}
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
              <th>Face</th>
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
                      onChange={(event) => onEditChange({ ...editEmployee, full_name: event.target.value })}
                    />
                  ) : (
                    employee.full_name
                  )}
                </td>
                <td>
                  {editingCode === employee.employee_code ? (
                    <select
                      aria-label={`Department for ${employee.employee_code}`}
                      value={editEmployee.department_id}
                      onChange={(event) => onEditChange({ ...editEmployee, department_id: event.target.value })}
                    >
                      <option value="">Unassigned</option>
                      {departments.map((department) => (
                        <option key={department.id} value={department.id}>
                          {department.name}
                        </option>
                      ))}
                    </select>
                  ) : (
                    employee.department || "Unassigned"
                  )}
                </td>
                <td>
                  <span className={`state-pill ${employee.has_face_embedding ? "ok" : "warn"}`}>
                    {employee.has_face_embedding ? "enrolled" : "needed"}
                  </span>
                </td>
                <td>
                  <span className={`state-pill ${employee.active === false ? "warn" : "ok"}`}>
                    {employee.active === false ? "inactive" : "active"}
                  </span>
                </td>
                <td>
                  {editingCode === employee.employee_code ? (
                    <form className="button-row" onSubmit={(event) => onSubmitEdit(event, employee.employee_code)}>
                      <button type="submit" className="button button-small">
                        Save
                      </button>
                      <button type="button" className="button button-small button-secondary" onClick={onEditCancel}>
                        Cancel
                      </button>
                    </form>
                  ) : (
                    <div className="button-row">
                      {employee.active === false ? (
                        <button type="button" className="button button-small" onClick={() => onRestore(employee.employee_code)}>
                          Restore
                        </button>
                      ) : (
                        <>
                          <button
                            type="button"
                            className="button button-small"
                            onClick={() => onOpenEnrollment(employee)}
                          >
                            Enroll face
                          </button>
                          <button
                            type="button"
                            className="button button-small button-secondary"
                            onClick={() => onEditStart(employee)}
                          >
                            Edit
                          </button>
                          <button
                            type="button"
                            className="button button-small button-danger"
                            onClick={() => onDeactivate(employee.employee_code)}
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
  );
}
