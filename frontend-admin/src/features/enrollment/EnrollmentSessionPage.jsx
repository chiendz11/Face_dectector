import { useEffect, useState } from "react";
import EnrollmentCapture from "./EnrollmentCapture";
import { getEnrollmentSession } from "./enrollmentApi";

export default function EnrollmentSessionPage({ token }) {
  const [session, setSession] = useState(null);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState("");

  useEffect(() => {
    loadSession();
  }, [token]);

  async function loadSession() {
    setStatus("loading");
    setError("");
    try {
      const { response, payload } = await getEnrollmentSession({ token });
      if (!response.ok) {
        throw new Error(payload.detail || "Enrollment session unavailable.");
      }
      setSession({ ...payload, token });
      setStatus(payload.status);
    } catch (err) {
      setStatus("error");
      setError(err instanceof Error ? err.message : "Enrollment session unavailable.");
    }
  }

  return (
    <main className="page-shell">
      {session && session.status === "pending" ? (
        <EnrollmentCapture
          session={session}
          onComplete={() => {
            setSession((current) => (current ? { ...current, status: "completed" } : current));
            setStatus("completed");
          }}
        />
      ) : (
        <section className="card form-card">
          <p className="eyebrow">Enrollment session</p>
          <h1>{status === "completed" ? "Enrollment completed" : "Session unavailable"}</h1>
          {error && <p className="status-error">{error}</p>}
          {session && session.status !== "pending" && <p className="muted">Status: {session.status}</p>}
        </section>
      )}
    </main>
  );
}
