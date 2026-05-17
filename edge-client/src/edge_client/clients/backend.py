import requests


def send_crops_to_backend(
    faces: list[bytes],
    api_base_url: str,
    device_name: str,
    timeout_seconds: float = 5.0,
) -> tuple[str, str]:
    endpoint = f"{api_base_url.rstrip('/')}/api/vision/recognize"

    for index, face_bytes in enumerate(faces, start=1):
        try:
            response = requests.post(
                endpoint,
                data={"device_name": device_name},
                files={"file": (f"face-{index}.jpg", face_bytes, "image/jpeg")},
                timeout=timeout_seconds,
            )
            if response.status_code >= 500:
                return (
                    "error",
                    f"Backend error {response.status_code}. Please retry or use manual check.",
                )
            if response.status_code >= 400:
                return (
                    "failed",
                    f"Recognition request rejected ({response.status_code}). Please try again.",
                )

            response.raise_for_status()
            payload = response.json()
            result = payload.get("result", {})
            status = payload.get("status", "unknown")
            employee_code = result.get("employee_code")

            if status == "granted" and employee_code:
                return "success", f"Verification success: {employee_code}"

            if status == "granted":
                return "success", "Verification success"

        except requests.RequestException as exc:
            return "error", f"Backend unavailable. Please retry. Detail: {exc}"

    return "failed", "Verification failed. Please try again."
