from __future__ import annotations

from dataclasses import dataclass

import cv2


WINDOW_NAME = "Face Detector Kiosk"


@dataclass
class OverlayStatus:
    camera_state: str = "LIVE"
    instruction: str = "Full-frame face detection active"
    recognition_state: str = "Waiting for face"
    recognition_level: str = "info"
    device_name: str = "unknown-device"


def render_status(message: str) -> None:
    print(f"[EDGE UI] {message}")


def render_frame(frame, status: OverlayStatus) -> bool:
    if frame is None:
        return False

    canvas = frame.copy()
    height, width = canvas.shape[:2]

    _draw_camera_state(canvas, status.camera_state)
    _draw_instruction(canvas, status.instruction)
    _draw_recognition_state(canvas, status.recognition_state, status.recognition_level, height)
    _draw_device_name(canvas, status.device_name, width, height)

    cv2.imshow(WINDOW_NAME, canvas)
    key = cv2.waitKey(1) & 0xFF
    return key in (ord("q"), 27)


def close_ui() -> None:
    cv2.destroyAllWindows()

def _draw_camera_state(canvas, camera_state: str) -> None:
    color = (0, 200, 0) if camera_state.upper() == "LIVE" else (0, 0, 255)
    cv2.rectangle(canvas, (12, 12), (250, 52), (20, 20, 20), -1)
    cv2.putText(
        canvas,
        f"Camera: {camera_state}",
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        color,
        2,
        cv2.LINE_AA,
    )


def _draw_instruction(canvas, instruction: str) -> None:
    cv2.rectangle(canvas, (12, 64), (770, 108), (20, 20, 20), -1)
    cv2.putText(
        canvas,
        instruction,
        (24, 94),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.74,
        (240, 240, 240),
        2,
        cv2.LINE_AA,
    )


def _draw_recognition_state(canvas, message: str, level: str, height: int) -> None:
    palette = {
        "success": (0, 170, 0),
        "warning": (0, 210, 255),
        "failed": (0, 0, 220),
        "error": (0, 0, 220),
        "info": (0, 150, 230),
    }
    color = palette.get(level, palette["info"])
    cv2.rectangle(canvas, (12, height - 66), (1000, height - 14), (20, 20, 20), -1)
    cv2.putText(
        canvas,
        message,
        (24, height - 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.78,
        color,
        2,
        cv2.LINE_AA,
    )


def _draw_device_name(canvas, device_name: str, width: int, height: int) -> None:
    cv2.putText(
        canvas,
        f"Device: {device_name}",
        (width - 320, height - 82),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (180, 180, 180),
        1,
        cv2.LINE_AA,
    )
