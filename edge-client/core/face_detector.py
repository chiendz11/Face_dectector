import cv2
import mediapipe as mp

_face_detector = mp.solutions.face_detection.FaceDetection(
    model_selection=0,
    min_detection_confidence=0.5,
)


def detect_and_crop_faces(frame) -> list[bytes]:
    if frame is None:
        return []

    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = _face_detector.process(rgb_frame)
    if not results.detections:
        return []

    height, width = frame.shape[:2]
    face_images: list[bytes] = []

    for detection in results.detections:
        bbox = detection.location_data.relative_bounding_box
        x1 = max(0, int(bbox.xmin * width))
        y1 = max(0, int(bbox.ymin * height))
        x2 = min(width, x1 + int(bbox.width * width))
        y2 = min(height, y1 + int(bbox.height * height))

        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            continue

        success, buffer = cv2.imencode(".jpg", crop)
        if not success:
            continue

        face_images.append(buffer.tobytes())

    return face_images
