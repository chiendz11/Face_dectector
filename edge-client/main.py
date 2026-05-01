import os
import time

import requests

from core.camera import CameraStream
from core.face_detector import detect_and_crop_faces
from ui.display import OverlayStatus, close_ui, render_frame, render_status


def send_crops_to_backend(
    faces: list[bytes],
    api_base_url: str,
    device_name: str,
) -> tuple[str, str]:
    endpoint = f"{api_base_url.rstrip('/')}/api/vision/recognize"

    for index, face_bytes in enumerate(faces, start=1):
        try:
            response = requests.post(
                endpoint,
                data={"device_name": device_name},
                files={"file": (f"face-{index}.jpg", face_bytes, "image/jpeg")},
                timeout=5,
            )
            response.raise_for_status()
            payload = response.json()
            result = payload.get("result", {})
            status = payload.get("status", "unknown")
            employee_code = result.get("employee_code")

            if status == "granted" and employee_code:
                message = f"Verification success: {employee_code}"
                render_status(message)
                return "success", message

            if status == "granted":
                message = "Verification success"
                render_status(message)
                return "success", message

            render_status(f"Recognition response: {status}")
        except requests.RequestException as exc:
            message = f"Backend request failed: {exc}"
            render_status(message)
            return "error", message

    return "failed", "Verification failed. Please try again."


def main() -> None:
    api_base_url = os.getenv("API_BASE_URL", "http://localhost")
    device_name = os.getenv("EDGE_DEVICE_NAME", "main-gate-01")
    scan_interval_seconds = float(os.getenv("SCAN_INTERVAL_SECONDS", "1.0"))
    last_scan_time = 0.0

    overlay_status = OverlayStatus(
        camera_state="LIVE",
        instruction="Place your face inside the circle",
        recognition_state="Waiting for face",
        recognition_level="info",
        device_name=device_name,
    )

    try:
        camera = CameraStream()
    except Exception as exc:
        render_status(f"Unable to open edge camera: {exc}")
        return

    render_status(
        f"Starting edge kiosk for {device_name}. API target: {api_base_url}"
    )

    try:
        while True:
            frame = camera.read_frame()
            if frame is None:
                overlay_status.camera_state = "OFFLINE"
                overlay_status.recognition_state = "Camera frame unavailable"
                overlay_status.recognition_level = "error"
                time.sleep(0.1)
                continue

            overlay_status.camera_state = "LIVE"
            now = time.monotonic()

            if now - last_scan_time >= scan_interval_seconds:
                faces = detect_and_crop_faces(frame)
                last_scan_time = now

                if not faces:
                    overlay_status.recognition_state = "No face detected. Please align and retry."
                    overlay_status.recognition_level = "info"
                else:
                    level, message = send_crops_to_backend(faces, api_base_url, device_name)
                    overlay_status.recognition_state = message
                    overlay_status.recognition_level = level

            should_exit = render_frame(frame, overlay_status)
            if should_exit:
                render_status("Exit requested from kiosk UI")
                break
    finally:
        close_ui()


if __name__ == "__main__":
    main()
