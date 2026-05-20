import { useEffect, useState } from "react";
import { listAuditEvents } from "./logApi";

const defaultFilters = {
  actor: "",
  action: "",
  resource_type: "",
  limit: 50,
};

export default function AuditLogsPanel({ authHeaders, onUnauthorized }) {
  const [filters, setFilters] = useState(defaultFilters);
  const [events, setEvents] = useState([]);
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState("");

  useEffect(() => {
    loadEvents();
  }, []);

  async function loadEvents(event) {
    event?.preventDefault();
    setStatus("loading");
    setError("");

    try {
      const { response, payload } = await listAuditEvents({ filters, authHeaders });
      if (response.status === 401) {
        onUnauthorized?.();
        return;
      }
      if (!response.ok) {
        throw new Error(payload.detail || "Failed to load audit logs");
      }
      setEvents(payload.items || []);
      setStatus("loaded");
    } catch (err) {
      setStatus("error");
      setError(err instanceof Error ? err.message : "Failed to load audit logs");
    }
  }

  return (
    <section className="console-section">
      <div className="section-header">
        <div>
          <p className="eyebrow">Governance</p>
          <h2>Audit Logs</h2>
        </div>
      </div>

      <section className="card">
        <form className="filter-bar" onSubmit={loadEvents}>
          <label>
            Actor
            <input
              type="text"
              value={filters.actor}
              onChange={(event) => setFilters({ ...filters, actor: event.target.value })}
              placeholder="admin"
            />
          </label>
          <label>
            Action
            <input
              type="text"
              value={filters.action}
              onChange={(event) => setFilters({ ...filters, action: event.target.value })}
              placeholder="face.enroll"
            />
          </label>
          <label>
            Resource
            <input
              type="text"
              value={filters.resource_type}
              onChange={(event) => setFilters({ ...filters, resource_type: event.target.value })}
              placeholder="employee"
            />
          </label>
          <button type="submit" className="button">
            Refresh
          </button>
        </form>

        {events.length === 0 ? (
          <p className="muted">{status === "loading" ? "Loading audit logs..." : "No audit events found."}</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Time</th>
                <th>Actor</th>
                <th>Action</th>
                <th>Resource</th>
                <th>Metadata</th>
              </tr>
            </thead>
            <tbody>
              {events.map((item) => (
                <tr key={item.id}>
                  <td>{formatTimestamp(item.created_at)}</td>
                  <td>{item.actor}</td>
                  <td>{item.action}</td>
                  <td>
                    {item.resource_type}
                    {item.resource_id ? `:${item.resource_id}` : ""}
                  </td>
                  <td>
                    <code>{formatMetadata(item.metadata)}</code>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {error && <p className="status-error">{error}</p>}
      </section>
    </section>
  );
}

function formatTimestamp(value) {
  if (!value) {
    return "Unknown";
  }
  return new Date(value).toLocaleString();
}

function formatMetadata(value) {
  if (!value || Object.keys(value).length === 0) {
    return "{}";
  }
  return JSON.stringify(value);
}
