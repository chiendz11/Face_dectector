from pathlib import Path

import cv2

try:
    import mediapipe as mp
except ImportError:
    mp = None

_face_detector = None
_opencv_face_detector = None

if mp is not None and hasattr(mp, "solutions") and hasattr(mp.solutions, "face_detection"):
    _face_detector = mp.solutions.face_detection.FaceDetection(
        model_selection=0,
        min_detection_confidence=0.5,
    )
else:
    cascade_path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
    candidate = cv2.CascadeClassifier(str(cascade_path))
    if not candidate.empty():
        _opencv_face_detector = candidate


def detect_and_crop_faces(frame) -> list[bytes]:
    if frame is None:
        return []

    if _face_detector is None:
        return _detect_and_crop_faces_with_opencv(frame)

    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = _face_detector.process(rgb_frame)
    if not results.detections:
        return []

    height, width = frame.shape[:2]
    boxes = []

    for detection in results.detections:
        bbox = detection.location_data.relative_bounding_box
        x1 = max(0, int(bbox.xmin * width))
        y1 = max(0, int(bbox.ymin * height))
        x2 = min(width, x1 + int(bbox.width * width))
        y2 = min(height, y1 + int(bbox.height * height))
        boxes.append((x1, y1, x2, y2))

    return _encode_crops(frame, boxes)


def _detect_and_crop_faces_with_opencv(frame) -> list[bytes]:
    if _opencv_face_detector is None:
        return []

    grayscale_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    detections = _opencv_face_detector.detectMultiScale(
        grayscale_frame,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(40, 40),
    )
    boxes = [(x, y, x + width, y + height) for x, y, width, height in detections]
    return _encode_crops(frame, boxes)


def _encode_crops(frame, boxes: list[tuple[int, int, int, int]]) -> list[bytes]:
    face_images: list[bytes] = []

    for x1, y1, x2, y2 in boxes:
        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            continue

        success, buffer = cv2.imencode(".jpg", crop)
        if not success:
            continue

        face_images.append(buffer.tobytes())

    return face_images
