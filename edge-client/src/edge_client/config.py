from __future__ import annotations

from dataclasses import dataclass
import os


def parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


def parse_camera_source(value: str) -> int | str:
    value = value.strip()
    if value.isdigit():
        return int(value)

    return value


@dataclass(frozen=True)
class EdgeClientConfig:
    api_base_url: str
    device_name: str
    scan_interval_seconds: float
    backend_enabled: bool
    backend_request_timeout_seconds: float
    camera_source: int | str
    ui_mode: str
    kiosk_host: str
    kiosk_port: int
    stream_fps: float

    @classmethod
    def from_env(cls) -> "EdgeClientConfig":
        return cls(
            api_base_url=os.getenv("API_BASE_URL", "http://localhost"),
            device_name=os.getenv("EDGE_DEVICE_NAME", "main-gate-01"),
            scan_interval_seconds=float(os.getenv("SCAN_INTERVAL_SECONDS", "1.0")),
            backend_enabled=parse_bool(os.getenv("EDGE_BACKEND_ENABLED"), default=True),
            backend_request_timeout_seconds=float(
                os.getenv("BACKEND_REQUEST_TIMEOUT_SECONDS", "1.0")
            ),
            camera_source=parse_camera_source(os.getenv("CAMERA_SOURCE", "0")),
            ui_mode=os.getenv("EDGE_UI_MODE", "web").strip().lower(),
            kiosk_host=os.getenv("EDGE_KIOSK_HOST", "0.0.0.0"),
            kiosk_port=int(os.getenv("EDGE_KIOSK_PORT", "8080")),
            stream_fps=float(os.getenv("EDGE_STREAM_FPS", "12.0")),
        )
