from __future__ import annotations

from contextlib import asynccontextmanager
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
import threading
import time
from typing import Callable, Iterator

import cv2
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
import numpy as np
import uvicorn

from edge_client.clients.backend import send_crops_to_backend
from edge_client.config import EdgeClientConfig
from edge_client.hardware.camera import CameraStream
from edge_client.vision.face_detector import detect_and_crop_faces


CameraFactory = Callable[[int | str], CameraStream]
Detector = Callable[[object], list[bytes]]
BackendSender = Callable[[list[bytes], str, str, float], tuple[str, str]]
STATIC_DIR = Path(__file__).resolve().parent / "static"


@dataclass
class KioskSnapshot:
    camera_state: str = "STARTING"
    recognition_state: str = "Starting camera"
    recognition_level: str = "info"
    backend_state: str = "idle"
    face_count: int = 0
    frame_count: int = 0
    last_frame_at: float | None = None
    last_scan_at: float | None = None


class WebKioskRuntime:
    def __init__(
        self,
        config: EdgeClientConfig,
        camera_factory: CameraFactory = CameraStream,
        detector: Detector = detect_and_crop_faces,
        backend_sender: BackendSender = send_crops_to_backend,
    ) -> None:
        self.config = config
        self.camera_factory = camera_factory
        self.detector = detector
        self.backend_sender = backend_sender
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._backend_executor = ThreadPoolExecutor(max_workers=1)
        self._backend_future: Future[tuple[str, str]] | None = None
        self._snapshot = KioskSnapshot()
        self._latest_jpeg = self._render_placeholder("Starting camera")

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="edge-kiosk", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._backend_future is not None:
            self._backend_future.cancel()
        if self._thread is not None:
            self._thread.join(timeout=2)
        self._backend_executor.shutdown(wait=False, cancel_futures=True)

    def get_frame(self) -> bytes:
        with self._lock:
            return self._latest_jpeg

    def status_snapshot(self) -> dict:
        with self._lock:
            snapshot = self._snapshot
            return {
                "cameraState": snapshot.camera_state,
                "recognitionState": snapshot.recognition_state,
                "recognitionLevel": snapshot.recognition_level,
                "backendState": snapshot.backend_state,
                "faceCount": snapshot.face_count,
                "frameCount": snapshot.frame_count,
                "lastFrameAt": snapshot.last_frame_at,
                "lastScanAt": snapshot.last_scan_at,
                "deviceName": self.config.device_name,
                "backendEnabled": self.config.backend_enabled,
            }

    def _run(self) -> None:
        camera = None
        last_scan_time = 0.0

        try:
            camera = self.camera_factory(self.config.camera_source)
            self._update_status(
                camera_state="LIVE",
                recognition_state="Scanning full camera view",
                recognition_level="info",
            )
        except Exception as exc:
            self._set_placeholder(f"Unable to open camera: {exc}")
            self._update_status(
                camera_state="OFFLINE",
                recognition_state=f"Unable to open camera: {exc}",
                recognition_level="error",
            )
            return

        try:
            while not self._stop_event.is_set():
                self._poll_backend_result()

                frame = camera.read_frame()
                if frame is None:
                    self._set_placeholder("Camera frame unavailable")
                    self._update_status(
                        camera_state="OFFLINE",
                        recognition_state="Camera frame unavailable",
                        recognition_level="error",
                    )
                    time.sleep(0.1)
                    continue

                now = time.monotonic()
                self._publish_frame(frame, now)

                if (
                    self._backend_future is None
                    and now - last_scan_time >= self.config.scan_interval_seconds
                ):
                    faces = self.detector(frame)
                    last_scan_time = now
                    self._handle_faces(faces, now)

                time.sleep(0.01)
        finally:
            if camera is not None:
                camera.close()

    def _handle_faces(self, faces: list[bytes], now: float) -> None:
        if not faces:
            self._update_status(
                camera_state="LIVE",
                recognition_state="No face detected in view",
                recognition_level="warning",
                backend_state="idle",
                face_count=0,
                last_scan_at=now,
            )
            return

        if not self.config.backend_enabled:
            self._update_status(
                camera_state="LIVE",
                recognition_state=f"UI test mode: {len(faces)} face(s) detected",
                recognition_level="success",
                backend_state="disabled",
                face_count=len(faces),
                last_scan_at=now,
            )
            return

        self._backend_future = self._backend_executor.submit(
            self.backend_sender,
            faces,
            self.config.api_base_url,
            self.config.device_name,
            self.config.backend_request_timeout_seconds,
        )
        self._update_status(
            camera_state="LIVE",
            recognition_state="Face detected. Verifying...",
            recognition_level="info",
            backend_state="verifying",
            face_count=len(faces),
            last_scan_at=now,
        )

    def _poll_backend_result(self) -> None:
        if self._backend_future is None or not self._backend_future.done():
            return

        try:
            level, message = self._backend_future.result()
        except Exception as exc:
            level = "error"
            message = f"Backend request failed: {exc}"

        self._backend_future = None
        self._update_status(
            recognition_state=message,
            recognition_level=level,
            backend_state="idle",
        )

    def _publish_frame(self, frame, now: float) -> None:
        success, buffer = cv2.imencode(".jpg", frame)
        if not success:
            return

        with self._lock:
            self._latest_jpeg = buffer.tobytes()
            self._snapshot.camera_state = "LIVE"
            self._snapshot.frame_count += 1
            self._snapshot.last_frame_at = now

    def _set_placeholder(self, message: str) -> None:
        with self._lock:
            self._latest_jpeg = self._render_placeholder(message)

    def _update_status(
        self,
        *,
        camera_state: str | None = None,
        recognition_state: str | None = None,
        recognition_level: str | None = None,
        backend_state: str | None = None,
        face_count: int | None = None,
        last_scan_at: float | None = None,
    ) -> None:
        with self._lock:
            if camera_state is not None:
                self._snapshot.camera_state = camera_state
            if recognition_state is not None:
                self._snapshot.recognition_state = recognition_state
            if recognition_level is not None:
                self._snapshot.recognition_level = recognition_level
            if backend_state is not None:
                self._snapshot.backend_state = backend_state
            if face_count is not None:
                self._snapshot.face_count = face_count
            if last_scan_at is not None:
                self._snapshot.last_scan_at = last_scan_at

    @staticmethod
    def _render_placeholder(message: str) -> bytes:
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.rectangle(frame, (0, 0), (640, 480), (24, 28, 35), -1)
        cv2.putText(
            frame,
            message[:44],
            (36, 250),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.72,
            (230, 238, 247),
            2,
            cv2.LINE_AA,
        )
        success, buffer = cv2.imencode(".jpg", frame)
        if not success:
            return b""
        return buffer.tobytes()


def create_app(
    config: EdgeClientConfig | None = None,
    runtime: WebKioskRuntime | None = None,
) -> FastAPI:
    config = config or EdgeClientConfig.from_env()
    runtime = runtime or WebKioskRuntime(config)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        runtime.start()
        try:
            yield
        finally:
            runtime.stop()

    app = FastAPI(title="Edge Kiosk", lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return _INDEX_HTML

    @app.get("/api/status")
    def status() -> JSONResponse:
        return JSONResponse(runtime.status_snapshot())

    @app.get("/healthz")
    def healthz() -> JSONResponse:
        snapshot = runtime.status_snapshot()
        healthy = snapshot["cameraState"] != "OFFLINE"
        return JSONResponse(
            {
                "ok": healthy,
                "cameraState": snapshot["cameraState"],
                "backendState": snapshot["backendState"],
                "deviceName": snapshot["deviceName"],
            },
            status_code=200 if healthy else 503,
        )

    @app.get("/stream.mjpg")
    def stream() -> StreamingResponse:
        return StreamingResponse(
            _mjpeg_frames(runtime, config),
            media_type="multipart/x-mixed-replace; boundary=frame",
        )

    return app


def _mjpeg_frames(runtime: WebKioskRuntime, config: EdgeClientConfig) -> Iterator[bytes]:
    delay = 1.0 / max(config.stream_fps, 1.0)
    while True:
        frame = runtime.get_frame()
        yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
        time.sleep(delay)


def run_web_kiosk(config: EdgeClientConfig | None = None) -> None:
    config = config or EdgeClientConfig.from_env()
    uvicorn.run(
        create_app(config),
        host=config.kiosk_host,
        port=config.kiosk_port,
        log_level="info",
    )


_INDEX_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Edge Kiosk</title>
  <link rel="stylesheet" href="/static/kiosk.css">
</head>
<body>
  <div class="shell">
    <header>
      <div class="brand">Edge Kiosk</div>
      <div class="topline">
        <div id="device" class="device">Device</div>
        <div id="camera" class="pill">STARTING</div>
      </div>
    </header>
    <main>
      <img class="stream" src="/stream.mjpg" alt="camera stream">
      <div class="vignette"></div>
      <div class="overlay">
        <div id="recognition" class="status-panel info">
          <div class="status-title">Recognition</div>
          <div id="recognition-message" class="status-message">Starting camera</div>
          <div id="recognition-detail" class="status-detail">Scanning the full camera view</div>
        </div>
        <div class="metric-row">
          <div id="backend" class="metric">Backend: idle</div>
          <div id="faces" class="metric">Faces: 0</div>
        </div>
      </div>
    </main>
  </div>
  <script>
    function detailFor(status) {
      if (status.recognitionLevel === 'warning') {
        return 'Detection runs across the entire camera frame.';
      }
      if (status.recognitionLevel === 'error') {
        return 'The kiosk remains online while the backend or camera recovers.';
      }
      if (status.backendEnabled === false) {
        return 'Backend is disabled for UI testing.';
      }
      return 'Camera feed is active.';
    }

    async function refreshStatus() {
      try {
        const response = await fetch('/api/status', { cache: 'no-store' });
        const status = await response.json();
        const recognition = document.getElementById('recognition');
        recognition.className = 'status-panel ' + status.recognitionLevel;
        document.getElementById('recognition-message').textContent = status.recognitionState;
        document.getElementById('recognition-detail').textContent = detailFor(status);
        document.getElementById('camera').textContent = status.cameraState;
        document.getElementById('device').textContent = status.deviceName;
        document.getElementById('backend').textContent = 'Backend: ' + status.backendState;
        document.getElementById('faces').textContent = 'Faces: ' + status.faceCount;
      } catch (error) {
        const recognition = document.getElementById('recognition');
        recognition.className = 'status-panel error';
        document.getElementById('recognition-message').textContent = 'Local kiosk service unavailable';
        document.getElementById('recognition-detail').textContent = 'Check the edge-client service on this device.';
      }
    }
    refreshStatus();
    setInterval(refreshStatus, 500);
  </script>
</body>
</html>
"""
