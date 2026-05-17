import numpy as np

from edge_client.ui import opencv_display as display


class Calls:
    def __init__(self) -> None:
        self.imshow_count = 0
        self.destroy_called = False


def test_render_frame_returns_true_on_quit_key(monkeypatch):
    calls = Calls()

    monkeypatch.setattr(display.cv2, "imshow", lambda *args, **kwargs: setattr(calls, "imshow_count", calls.imshow_count + 1))
    monkeypatch.setattr(display.cv2, "waitKey", lambda _ms: ord("q"))

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    status = display.OverlayStatus(device_name="gate-01")

    should_exit = display.render_frame(frame, status)

    assert should_exit is True
    assert calls.imshow_count == 1


def test_render_frame_returns_false_without_exit_key(monkeypatch):
    monkeypatch.setattr(display.cv2, "imshow", lambda *args, **kwargs: None)
    monkeypatch.setattr(display.cv2, "waitKey", lambda _ms: -1)

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    status = display.OverlayStatus(device_name="gate-01")

    should_exit = display.render_frame(frame, status)

    assert should_exit is False


def test_close_ui_calls_destroy(monkeypatch):
    calls = Calls()

    def fake_destroy():
        calls.destroy_called = True

    monkeypatch.setattr(display.cv2, "destroyAllWindows", fake_destroy)

    display.close_ui()

    assert calls.destroy_called is True
