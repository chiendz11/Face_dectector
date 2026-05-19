import { useEffect, useRef, useState } from "react";
import { completeEnrollmentSession } from "./enrollmentApi";

const TARGET_SAMPLE_COUNT = 5;
const MIN_SAMPLE_COUNT = 3;
const DEVICE_NAME = "frontend-admin-camera";

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

export default function EnrollmentCapture({ session, onCancel, onComplete }) {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const [samples, setSamples] = useState([]);
  const [cameraState, setCameraState] = useState("starting");
  const [submitState, setSubmitState] = useState("ready");
  const [message, setMessage] = useState("");

  useEffect(() => {
    startCamera();
    return () => stopCamera();
  }, []);

  async function startCamera() {
    if (!navigator.mediaDevices?.getUserMedia) {
      setCameraState("unavailable");
      setMessage("Camera API is unavailable in this browser.");
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
      setMessage("");
    } catch (error) {
      setCameraState("blocked");
      setMessage(error instanceof Error ? error.message : "Camera permission denied.");
    }
  }

  function stopCamera() {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
  }

  function captureSample() {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || video.readyState < 2) {
      setSubmitState("error");
      setMessage("Camera frame is not ready.");
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
    if (samples.length < MIN_SAMPLE_COUNT) {
      setSubmitState("error");
      setMessage(`Capture at least ${MIN_SAMPLE_COUNT} face samples before enrolling.`);
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
      const { response, payload } = await completeEnrollmentSession({ token: session.token, formData });
      if (!response.ok) {
        throw new Error(payload.detail || "Enrollment failed.");
      }

      setSubmitState("success");
      setMessage(payload.message || "Enrollment completed.");
      setSamples([]);
      stopCamera();
      onComplete?.(payload);
    } catch (error) {
      setSubmitState("error");
      setMessage(error instanceof Error ? error.message : "Enrollment failed.");
    }
  }

  const canSubmit = samples.length >= MIN_SAMPLE_COUNT && submitState !== "submitting";

  return (
    <section className="capture-panel" aria-label="Face enrollment capture">
      <div className="capture-header">
        <div>
          <p className="eyebrow">Enrollment session</p>
          <h2>{session.employee_code}</h2>
          {session.full_name && <p className="muted">{session.full_name}</p>}
        </div>
        <div className="capture-actions">
          <span className={`state-pill ${cameraState === "live" ? "ok" : "warn"}`}>{cameraState}</span>
          {onCancel && (
            <button type="button" className="button button-secondary" onClick={onCancel}>
              Close
            </button>
          )}
        </div>
      </div>

      <div className="capture-workspace">
        <div className="capture-stage">
          <video ref={videoRef} autoPlay playsInline muted aria-label="Enrollment camera preview" />
          <canvas ref={canvasRef} hidden />
        </div>

        <form className="capture-controls" onSubmit={submitEnrollment}>
          <div className="sample-count">
            <strong>{samples.length}</strong>
            <span>samples captured</span>
          </div>
          <div className="button-row">
            <button type="button" className="button" onClick={captureSample} disabled={cameraState !== "live"}>
              Capture
            </button>
            <button
              type="button"
              className="button button-secondary"
              onClick={() => setSamples([])}
              disabled={!samples.length}
            >
              Clear
            </button>
          </div>
          <button type="submit" className="button" disabled={!canSubmit}>
            Complete enrollment
          </button>

          <div className="sample-grid" aria-label="Captured samples">
            {samples.map((sample, index) => (
              <img key={sample.id} src={sample.dataUrl} alt={`Captured sample ${index + 1}`} />
            ))}
          </div>

          {message && <p className={submitState === "success" ? "status-success" : "status-error"}>{message}</p>}
        </form>
      </div>
    </section>
  );
}
