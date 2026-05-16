from edge_client.config import EdgeClientConfig
from edge_client.ui.web_kiosk import _mjpeg_frames, create_app


class DummyRuntime:
    def __init__(self) -> None:
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True

    def get_frame(self) -> bytes:
        return b"jpeg-bytes"

    def status_snapshot(self) -> dict:
        return {
            "cameraState": "LIVE",
            "recognitionState": "Waiting for face",
            "recognitionLevel": "info",
            "backendState": "idle",
            "faceCount": 0,
            "frameCount": 1,
            "lastFrameAt": 1.0,
            "lastScanAt": None,
            "deviceName": "gate-01",
            "backendEnabled": False,
        }


def make_config() -> EdgeClientConfig:
    return EdgeClientConfig(
        api_base_url="http://localhost",
        device_name="gate-01",
        scan_interval_seconds=1.0,
        backend_enabled=False,
        backend_request_timeout_seconds=1.0,
        camera_source=0,
        ui_mode="web",
        kiosk_host="127.0.0.1",
        kiosk_port=8080,
        stream_fps=12.0,
    )


def test_create_app_exposes_kiosk_routes():
    app = create_app(make_config(), DummyRuntime())

    paths = {route.path for route in app.routes}

    assert "/" in paths
    assert "/api/status" in paths
    assert "/healthz" in paths
    assert "/stream.mjpg" in paths
    assert "/static" in paths


def test_mjpeg_generator_yields_frame_boundary():
    frame = next(_mjpeg_frames(DummyRuntime(), make_config()))

    assert frame.startswith(b"--frame\r\nContent-Type: image/jpeg")
    assert b"jpeg-bytes" in frame
