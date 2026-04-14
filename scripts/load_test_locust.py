from __future__ import annotations

import os
import random
from pathlib import Path

from locust import HttpUser, task, between

IMAGE_DIR = Path(os.getenv("LOCUST_IMAGE_DIR", "scripts/load_test_images")).expanduser()
DEVICE_NAMES = [
    "gate-entrance-01",
    "gate-entrance-02",
    "gate-side-01",
    "gate-side-02",
    "mobile-checkin-01",
    "mobile-checkin-02",
]


class FaceRecognitionUser(HttpUser):
    wait_time = between(0.1, 0.4)

    def on_start(self) -> None:
        if not IMAGE_DIR.exists() or not IMAGE_DIR.is_dir():
            raise RuntimeError(
                f"Image directory not found: {IMAGE_DIR}. Please set LOCUST_IMAGE_DIR to a folder with sample images."
            )

        self.images = [
            path
            for path in IMAGE_DIR.iterdir()
            if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png"}
        ]
        if not self.images:
            raise RuntimeError(f"No images found in {IMAGE_DIR}. Add JPG/PNG files for request payloads.")

    @task
    def post_recognition_request(self) -> None:
        image_path = random.choice(self.images)
        device_name = random.choice(DEVICE_NAMES)

        with image_path.open("rb") as image_file:
            files = {"file": (image_path.name, image_file, "image/jpeg")}
            data = {"device_name": device_name}
            with self.client.post(
                "/api/vision/recognize",
                files=files,
                data=data,
                timeout=30,
                catch_response=True,
            ) as response:
                if response.status_code == 429:
                    response.failure("rate limited by Nginx")
                elif response.status_code != 200:
                    response.failure(f"unexpected status {response.status_code}")
