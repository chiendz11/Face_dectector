import cv2


class CameraStream:
    def __init__(self, source: int | str = 0) -> None:
        if isinstance(source, str) and source.isdigit():
            source = int(source)

        self.capture = cv2.VideoCapture(source)
        if not self.capture.isOpened():
            raise RuntimeError(f"Unable to open camera source: {source}")

    def read_frame(self):
        success, frame = self.capture.read()
        if not success:
            return None

        return frame

    def close(self) -> None:
        if self.capture.isOpened():
            self.capture.release()

    def __del__(self):
        if hasattr(self, "capture"):
            self.close()
