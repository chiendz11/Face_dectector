export default function DepartmentPanel({
  departments,
  editingDepartmentId,
  editDepartment,
  newDepartment,
  onCreateDepartment,
  onDeactivateDepartment,
  onEditDepartmentCancel,
  onEditDepartmentChange,
  onEditDepartmentStart,
  onNewDepartmentChange,
  onSubmitDepartmentEdit,
}) {
  return (
    <section className="card">
      <div className="form-row">
        <div>
          <h2>Departments</h2>
          <p className="muted">Create department records once, then assign employees from a controlled dropdown.</p>
        </div>
      </div>

      <form className="compact-form" onSubmit={onCreateDepartment}>
        <label>
          Department name
          <input
            type="text"
            value={newDepartment.name}
            onChange={(event) => onNewDepartmentChange({ ...newDepartment, name: event.target.value })}
            placeholder="Security"
            required
          />
        </label>
        <button type="submit" className="button">
          Add department
        </button>
      </form>

      {departments.length === 0 ? (
        <p>No departments created yet.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Code</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {departments.map((department) => (
              <tr key={department.id}>
                <td>
                  {editingDepartmentId === department.id ? (
                    <input
                      aria-label={`Department name for ${department.name}`}
                      value={editDepartment.name}
                      onChange={(event) => onEditDepartmentChange({ ...editDepartment, name: event.target.value })}
                    />
                  ) : (
                    department.name
                  )}
                </td>
                <td>{department.code}</td>
                <td>
                  <span className={`state-pill ${department.active === false ? "warn" : "ok"}`}>
                    {department.active === false ? "inactive" : "active"}
                  </span>
                </td>
                <td>
                  {editingDepartmentId === department.id ? (
                    <form className="button-row" onSubmit={(event) => onSubmitDepartmentEdit(event, department.id)}>
                      <button type="submit" className="button button-small">
                        Save
                      </button>
                      <button type="button" className="button button-small button-secondary" onClick={onEditDepartmentCancel}>
                        Cancel
                      </button>
                    </form>
                  ) : (
                    <div className="button-row">
                      <button
                        type="button"
                        className="button button-small button-secondary"
                        onClick={() => onEditDepartmentStart(department)}
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        className="button button-small button-danger"
                        onClick={() => onDeactivateDepartment(department.id)}
                      >
                        Deactivate
                      </button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
