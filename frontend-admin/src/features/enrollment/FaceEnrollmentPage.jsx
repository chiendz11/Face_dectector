import { useEffect, useState } from "react";
import { listEmployees as requestEmployees } from "../employees/employeeApi";
import EnrollmentCapture from "./EnrollmentCapture";
import { createEnrollmentSession as requestEnrollmentSession } from "./enrollmentApi";

const SEARCH_DEBOUNCE_MS = 300;
const MIN_SEARCH_LENGTH = 2;

export default function FaceEnrollmentPage({
  authHeaders,
  querySeed = "",
  onEnrollmentComplete,
  onUnauthorized,
}) {
  const [query, setQuery] = useState(querySeed);
  const [results, setResults] = useState([]);
  const [selectedStaff, setSelectedStaff] = useState(null);
  const [session, setSession] = useState(null);
  const [status, setStatus] = useState("idle");
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (querySeed) {
      setQuery(querySeed);
      setSelectedStaff(null);
      setSession(null);
      setMessage("");
    }
  }, [querySeed]);

  useEffect(() => {
    const normalizedQuery = query.trim();
    if (normalizedQuery.length < MIN_SEARCH_LENGTH) {
      setResults([]);
      setStatus("idle");
      return undefined;
    }

    const timeoutId = window.setTimeout(() => {
      searchStaff(normalizedQuery);
    }, SEARCH_DEBOUNCE_MS);

    return () => window.clearTimeout(timeoutId);
  }, [query, authHeaders]);

  async function searchStaff(searchQuery) {
    setStatus("searching");
    setMessage("");

    try {
      const { response, payload } = await requestEmployees({
        query: searchQuery,
        limit: 10,
        authHeaders,
      });

      if (response.status === 401) {
        onUnauthorized?.();
        return;
      }

      if (!response.ok) {
        throw new Error(payload.detail || "Staff search failed");
      }

      setResults(payload.items || []);
      setStatus("loaded");
    } catch (error) {
      setResults([]);
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "Staff search failed");
    }
  }

  function selectStaff(staff) {
    setSelectedStaff(staff);
    setSession(null);
    setMessage("");
  }

  async function startEnrollment() {
    if (!selectedStaff) {
      return;
    }

    setStatus("creating-session");
    setMessage("");

    try {
      const { response, payload } = await requestEnrollmentSession({
        employeeCode: selectedStaff.employee_code,
        authHeaders,
      });

      if (response.status === 401) {
        onUnauthorized?.();
        return;
      }

      if (!response.ok) {
        throw new Error(payload.detail || "Create enrollment session failed");
      }

      setSession({
        ...payload,
        full_name: selectedStaff.full_name,
        department: selectedStaff.department,
      });
      setStatus("session-ready");
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "Create enrollment session failed");
    }
  }

  function completeEnrollment(payload) {
    setSession(null);
    setSelectedStaff((current) => (current ? { ...current, has_face_embedding: true } : current));
    setMessage(payload.message || "Enrollment saved.");
    setStatus("completed");
    onEnrollmentComplete?.();
  }

  return (
    <section className="console-section">
      <div className="section-header">
        <div>
          <p className="eyebrow">Face Recognition</p>
          <h2>Face enrollment</h2>
        </div>
      </div>

      <section className="card form-card">
        <label>
          Search staff
          <input
            type="text"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Name or staff code"
            autoComplete="off"
          />
        </label>

        {query.trim().length < MIN_SEARCH_LENGTH ? (
          <p className="muted">Enter at least {MIN_SEARCH_LENGTH} characters.</p>
        ) : (
          <div className="search-results" aria-label="Staff search results">
            {status === "searching" && <p className="muted">Searching...</p>}
            {status === "loaded" && results.length === 0 && <p className="muted">No matching staff found.</p>}
            {results.map((staff) => (
              <button
                key={staff.employee_code}
                type="button"
                className={`search-result ${selectedStaff?.employee_code === staff.employee_code ? "selected" : ""}`}
                onClick={() => selectStaff(staff)}
              >
                <span>
                  <strong>{staff.full_name}</strong>
                  <small>
                    {staff.employee_code} {staff.department ? `- ${staff.department}` : "- Unassigned"}
                  </small>
                </span>
                <span className={`state-pill ${staff.has_face_embedding ? "ok" : "warn"}`}>
                  {staff.has_face_embedding ? "enrolled" : "needed"}
                </span>
              </button>
            ))}
          </div>
        )}
      </section>

      {selectedStaff && (
        <section className="card staff-selection">
          <div>
            <p className="eyebrow">Selected staff</p>
            <h3>{selectedStaff.full_name}</h3>
            <p className="muted">
              {selectedStaff.employee_code} {selectedStaff.department ? `- ${selectedStaff.department}` : "- Unassigned"}
            </p>
          </div>
          <button
            type="button"
            className="button"
            onClick={startEnrollment}
            disabled={status === "creating-session"}
          >
            Scan face
          </button>
        </section>
      )}

      {session && <EnrollmentCapture session={session} onCancel={() => setSession(null)} onComplete={completeEnrollment} />}
      {message && <p className={status === "completed" ? "status-success" : "status-error"}>{message}</p>}
    </section>
  );
}
