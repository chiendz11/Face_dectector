import { useEffect, useState } from "react";
import { listRecognitionEvents } from "./logApi";

const defaultFilters = {
  matched: "all",
  employee_code: "",
  device_name: "",
  limit: 50,
};

export default function RecognitionLogsPanel({ authHeaders, onUnauthorized }) {
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
      const { response, payload } = await listRecognitionEvents({ filters, authHeaders });
      if (response.status === 401) {
        onUnauthorized?.();
        return;
      }
      if (!response.ok) {
        throw new Error(payload.detail || "Failed to load recognition logs");
      }
      setEvents(payload.items || []);
      setStatus("loaded");
    } catch (err) {
      setStatus("error");
      setError(err instanceof Error ? err.message : "Failed to load recognition logs");
    }
  }

  return (
    <section className="console-section">
      <div className="section-header">
        <div>
          <p className="eyebrow">Face Recognition</p>
          <h2>Recognition Logs</h2>
        </div>
      </div>

      <section className="card">
        <form className="filter-bar" onSubmit={loadEvents}>
          <label>
            Match
            <select
              value={filters.matched}
              onChange={(event) => setFilters({ ...filters, matched: event.target.value })}
            >
              <option value="all">All</option>
              <option value="true">Matched</option>
              <option value="false">Rejected</option>
            </select>
          </label>
          <label>
            Staff code
            <input
              type="text"
              value={filters.employee_code}
              onChange={(event) => setFilters({ ...filters, employee_code: event.target.value })}
              placeholder="EMP-"
            />
          </label>
          <label>
            Device
            <input
              type="text"
              value={filters.device_name}
              onChange={(event) => setFilters({ ...filters, device_name: event.target.value })}
              placeholder="main-gate-01"
            />
          </label>
          <button type="submit" className="button">
            Refresh
          </button>
        </form>

        {events.length === 0 ? (
          <p className="muted">{status === "loading" ? "Loading recognition logs..." : "No recognition events found."}</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Time</th>
                <th>Result</th>
                <th>Staff</th>
                <th>Confidence</th>
                <th>Device</th>
                <th>Snapshot</th>
              </tr>
            </thead>
            <tbody>
              {events.map((item) => (
                <tr key={item.id}>
                  <td>{formatTimestamp(item.created_at)}</td>
                  <td>
                    <span className={`state-pill ${item.matched ? "ok" : "warn"}`}>
                      {item.matched ? "matched" : "rejected"}
                    </span>
                  </td>
                  <td>{item.employee_code || "Unknown"}</td>
                  <td>{formatConfidence(item.confidence)}</td>
                  <td>{item.device_name || "Unknown"}</td>
                  <td>
                    {item.snapshot_url ? (
                      <a href={item.snapshot_url} target="_blank" rel="noreferrer">
                        Open
                      </a>
                    ) : (
                      "None"
                    )}
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

function formatConfidence(value) {
  if (typeof value !== "number") {
    return "0.000";
  }
  return value.toFixed(3);
}
