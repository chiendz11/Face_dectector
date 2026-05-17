from edge_client.config import EdgeClientConfig, parse_camera_source


def test_parse_camera_source_accepts_integer_index():
    assert parse_camera_source("0") == 0


def test_parse_camera_source_accepts_device_path():
    assert parse_camera_source("/dev/video0") == "/dev/video0"


def test_config_from_env_reads_web_kiosk_values(monkeypatch):
    monkeypatch.setenv("API_BASE_URL", "https://api.example.test")
    monkeypatch.setenv("EDGE_DEVICE_NAME", "gate-02")
    monkeypatch.setenv("SCAN_INTERVAL_SECONDS", "2.5")
    monkeypatch.setenv("EDGE_BACKEND_ENABLED", "false")
    monkeypatch.setenv("BACKEND_REQUEST_TIMEOUT_SECONDS", "0.5")
    monkeypatch.setenv("CAMERA_SOURCE", "/dev/video0")
    monkeypatch.setenv("EDGE_UI_MODE", "web")
    monkeypatch.setenv("EDGE_KIOSK_HOST", "127.0.0.1")
    monkeypatch.setenv("EDGE_KIOSK_PORT", "9090")
    monkeypatch.setenv("EDGE_STREAM_FPS", "8")

    config = EdgeClientConfig.from_env()

    assert config.api_base_url == "https://api.example.test"
    assert config.device_name == "gate-02"
    assert config.scan_interval_seconds == 2.5
    assert config.backend_enabled is False
    assert config.backend_request_timeout_seconds == 0.5
    assert config.camera_source == "/dev/video0"
    assert config.ui_mode == "web"
    assert config.kiosk_host == "127.0.0.1"
    assert config.kiosk_port == 9090
    assert config.stream_fps == 8
