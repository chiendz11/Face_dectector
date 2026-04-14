import os
import time

import requests

from core.camera import CameraStream
from core.face_detector import detect_and_crop_faces
from ui.display import render_status


def send_crops_to_backend(
    faces: list[bytes],
    backend_base_url: str,
    device_name: str,
) -> None:
    endpoint = f"{backend_base_url.rstrip('/')}/api/vision/recognize"

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
            render_status(
                "Recognition response: "
                f"{payload.get('status', 'unknown')} for {payload.get('filename')}"
            )
        except requests.RequestException as exc:
            render_status(f"Backend request failed: {exc}")


def main() -> None:
    backend_base_url = os.getenv("BACKEND_BASE_URL", "http://localhost")
    device_name = os.getenv("EDGE_DEVICE_NAME", "main-gate-01")
    scan_interval_seconds = float(os.getenv("SCAN_INTERVAL_SECONDS", "1.0"))

    camera = CameraStream()
    render_status(
        f"Starting edge kiosk for {device_name}. Backend target: {backend_base_url}"
    )

    while True:
        frame = camera.read_frame()
        faces = detect_and_crop_faces(frame)

        if not faces:
            render_status("No face detected. Waiting for the next frame.")
            time.sleep(scan_interval_seconds)
            continue

        render_status(
            f"Detected {len(faces)} face(s). Sending cropped face(s) to the backend."
        )
        send_crops_to_backend(faces, backend_base_url, device_name)
        time.sleep(scan_interval_seconds)


if __name__ == "__main__":
    main()
