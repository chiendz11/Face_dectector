import { useEffect, useMemo, useRef, useState } from "react";

const TARGET_SAMPLE_COUNT = 5;
const DEVICE_NAME = "local-enrollment-station";

const emptyCredentials = {
  username: "admin",
  password: "",
};

function dataUrlToBlob(dataUrl) {
  const [metadata, base64] = dataUrl.split(",");
  const contentType = metadata.match(/data:(.*);base64/)?.[1] || "image/jpeg";
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return new Blob([bytes], { type: contentType });
}

export default function App() {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const [token, setToken] = useState(() => localStorage.getItem("enrollment_token") || "");
  const [credentials, setCredentials] = useState(emptyCredentials);
  const [employeeCode, setEmployeeCode] = useState("");
  const [samples, setSamples] = useState([]);
  const [cameraState, setCameraState] = useState("idle");
  const [submitState, setSubmitState] = useState("ready");
  const [message, setMessage] = useState("");

  const authHeaders = useMemo(() => (token ? { Authorization: `Bearer ${token}` } : {}), [token]);
  const canEnroll = token && employeeCode.trim() && samples.length >= 3 && submitState !== "submitting";

  useEffect(() => {
    if (!token) {
      stopCamera();
      return undefined;
    }

    startCamera();
    return () => stopCamera();
  }, [token]);

  async function handleLogin(event) {
    event.preventDefault();
    setSubmitState("submitting");
    setMessage("");

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
      localStorage.setItem("enrollment_token", payload.access_token);
      setToken(payload.access_token);
      setCredentials(emptyCredentials);
      setSubmitState("ready");
    } catch (error) {
      setSubmitState("error");
      setMessage(error instanceof Error ? error.message : "Login failed");
    }
  }

  async function startCamera() {
    if (!navigator.mediaDevices?.getUserMedia) {
      setCameraState("Camera API unavailable");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: "user",
          width: { ideal: 1280 },
          height: { ideal: 720 },
        },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }
      setCameraState("live");
    } catch (error) {
      setCameraState("blocked");
      setMessage(error instanceof Error ? error.message : "Camera permission denied");
    }
  }

  function stopCamera() {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
  }

  function handleLogout() {
    localStorage.removeItem("enrollment_token");
    setToken("");
    setSamples([]);
    setEmployeeCode("");
    setSubmitState("ready");
    setMessage("");
  }

  function captureSample() {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || video.readyState < 2) {
      setSubmitState("error");
      setMessage("Camera frame is not ready");
      return;
    }

    const width = video.videoWidth || 1280;
    const height = video.videoHeight || 720;
    canvas.width = width;
    canvas.height = height;
    const context = canvas.getContext("2d");
    context.drawImage(video, 0, 0, width, height);
    const dataUrl = canvas.toDataURL("image/jpeg", 0.9);
    setSamples((current) => [
      ...current.slice(Math.max(0, current.length - TARGET_SAMPLE_COUNT + 1)),
      {
        id: crypto.randomUUID?.() || `${Date.now()}-${current.length}`,
        dataUrl,
      },
    ]);
    setSubmitState("ready");
    setMessage("");
  }

  async function submitEnrollment(event) {
    event.preventDefault();
    if (!canEnroll) {
      setSubmitState("error");
      setMessage("Capture at least 3 face samples before enrolling");
      return;
    }

    setSubmitState("submitting");
    setMessage("");

    const formData = new FormData();
    formData.append("device_name", DEVICE_NAME);
    samples.forEach((sample, index) => {
      formData.append("files", dataUrlToBlob(sample.dataUrl), `sample-${index + 1}.jpg`);
    });

    try {
      const response = await fetch(
        `/api/admin/employees/${encodeURIComponent(employeeCode.trim())}/enroll-samples`,
        {
          method: "POST",
          headers: authHeaders,
          body: formData,
        },
      );

      if (response.status === 401) {
        handleLogout();
        throw new Error("Session expired");
      }

      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail || "Enrollment failed");
      }

      setSubmitState("success");
      setMessage(payload.message || "Enrollment completed");
      setSamples([]);
    } catch (error) {
      setSubmitState("error");
      setMessage(error instanceof Error ? error.message : "Enrollment failed");
    }
  }

  if (!token) {
    return (
      <main className="auth-shell">
        <section className="auth-panel">
          <p className="eyebrow">Enrollment Station</p>
          <h1>Controlled face enrollment</h1>
          <form onSubmit={handleLogin} className="auth-form">
            <label>
              Username
              <input
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
            <button type="submit" disabled={submitState === "submitting"}>
              Sign in
            </button>
            {message && <p className="status-error">{message}</p>}
          </form>
        </section>
      </main>
    );
  }

  return (
    <main className="station-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Enrollment Station</p>
          <h1>Live sample capture</h1>
        </div>
        <div className="topbar-actions">
          <span className={`state-pill ${cameraState === "live" ? "ok" : "warn"}`}>{cameraState}</span>
          <button type="button" className="secondary" onClick={handleLogout}>
            Log out
          </button>
        </div>
      </header>

      <section className="workspace">
        <div className="camera-stage">
          <video ref={videoRef} autoPlay playsInline muted aria-label="Enrollment camera preview" />
          <canvas ref={canvasRef} hidden />
        </div>

        <aside className="control-panel">
          <form onSubmit={submitEnrollment}>
            <label>
              Employee code
              <input
                value={employeeCode}
                onChange={(event) => setEmployeeCode(event.target.value)}
                placeholder="EMP-001"
                required
              />
            </label>

            <div className="sample-count">
              <span>{samples.length}</span>
              <p>samples captured</p>
            </div>

            <div className="button-row">
              <button type="button" onClick={captureSample} disabled={cameraState !== "live"}>
                Capture
              </button>
              <button type="button" className="secondary" onClick={() => setSamples([])} disabled={!samples.length}>
                Clear
              </button>
            </div>

            <button type="submit" disabled={!canEnroll}>
              Enroll face
            </button>
          </form>

          <div className="sample-grid" aria-label="Captured samples">
            {samples.map((sample, index) => (
              <img key={sample.id} src={sample.dataUrl} alt={`Captured sample ${index + 1}`} />
            ))}
          </div>

          {message && <p className={submitState === "success" ? "status-success" : "status-error"}>{message}</p>}
        </aside>
      </section>
    </main>
  );
}
