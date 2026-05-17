from concurrent.futures import Future, ThreadPoolExecutor
from importlib.metadata import PackageNotFoundError, version
import time

from edge_client.clients.backend import send_crops_to_backend
from edge_client.config import EdgeClientConfig
from edge_client.hardware.camera import CameraStream
from edge_client.ui.opencv_display import (
    OverlayStatus,
    close_ui,
    render_frame,
    render_status,
)
from edge_client.vision.face_detector import detect_and_crop_faces


def ensure_web_runtime_dependencies() -> None:
    try:
        starlette_version = version("starlette")
    except PackageNotFoundError as exc:
        raise SystemExit(
            "Missing web runtime dependency: starlette. "
            "Run .\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt "
            "from edge-client/."
        ) from exc

    if _version_at_least(starlette_version, (0, 48, 0)):
        raise SystemExit(
            f"Incompatible starlette {starlette_version} for edge-client web mode. "
            "Use the dedicated edge-client venv: .\\.venv\\Scripts\\python.exe main.py"
        )


def _version_at_least(raw_version: str, minimum: tuple[int, int, int]) -> bool:
    parts = []
    for part in raw_version.replace("-", ".").split("."):
        if not part.isdigit():
            break
        parts.append(int(part))

    while len(parts) < 3:
        parts.append(0)

    return tuple(parts[:3]) >= minimum


def run_opencv_kiosk(config: EdgeClientConfig) -> None:
    last_scan_time = 0.0
    backend_executor = ThreadPoolExecutor(max_workers=1)
    backend_future: Future[tuple[str, str]] | None = None

    overlay_status = OverlayStatus(
        camera_state="LIVE",
        instruction="Full-frame face detection active",
        recognition_state="Waiting for face",
        recognition_level="info",
        device_name=config.device_name,
    )

    try:
        camera = CameraStream(config.camera_source)
    except Exception as exc:
        render_status(f"Unable to open edge camera: {exc}")
        return

    render_status(
        f"Starting OpenCV edge kiosk for {config.device_name}. "
        f"API target: {config.api_base_url}. Backend enabled: {config.backend_enabled}"
    )

    try:
        while True:
            if backend_future is not None and backend_future.done():
                try:
                    level, message = backend_future.result()
                except Exception as exc:
                    level = "error"
                    message = f"Backend request failed: {exc}"

                overlay_status.recognition_state = message
                overlay_status.recognition_level = level
                backend_future = None

            frame = camera.read_frame()
            if frame is None:
                overlay_status.camera_state = "OFFLINE"
                overlay_status.recognition_state = "Camera frame unavailable"
                overlay_status.recognition_level = "error"
                time.sleep(0.1)
                continue

            overlay_status.camera_state = "LIVE"
            now = time.monotonic()

            if (
                backend_future is None
                and now - last_scan_time >= config.scan_interval_seconds
            ):
                faces = detect_and_crop_faces(frame)
                last_scan_time = now

                if not faces:
                    overlay_status.recognition_state = "No face detected in view"
                    overlay_status.recognition_level = "warning"
                else:
                    if not config.backend_enabled:
                        face_count = len(faces)
                        overlay_status.recognition_state = (
                            f"UI test mode: {face_count} face(s) detected"
                        )
                        overlay_status.recognition_level = "success"
                    else:
                        overlay_status.recognition_state = "Face detected. Verifying..."
                        overlay_status.recognition_level = "info"
                        backend_future = backend_executor.submit(
                            send_crops_to_backend,
                            faces,
                            config.api_base_url,
                            config.device_name,
                            config.backend_request_timeout_seconds,
                        )

            should_exit = render_frame(frame, overlay_status)
            if should_exit:
                render_status("Exit requested from kiosk UI")
                break
    finally:
        if backend_future is not None:
            backend_future.cancel()
        backend_executor.shutdown(wait=False, cancel_futures=True)
        close_ui()


def main() -> None:
    config = EdgeClientConfig.from_env()
    if config.ui_mode == "opencv":
        run_opencv_kiosk(config)
        return

    ensure_web_runtime_dependencies()

    from edge_client.ui.web_kiosk import run_web_kiosk

    run_web_kiosk(config)


if __name__ == "__main__":
    main()
