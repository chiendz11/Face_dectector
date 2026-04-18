from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a simple concurrency test against the recognition API.")
    parser.add_argument("--host", required=True, help="Base URL for the backend, e.g. http://localhost")
    parser.add_argument("--image-path", required=True, help="Path to the sample image file")
    parser.add_argument("--workers", type=int, default=2, help="Number of concurrent requests")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    image_path = Path(args.image_path)
    if not image_path.exists():
        raise SystemExit(f"Image path not found: {image_path}")

    url = f"{args.host}/api/vision/recognize"
    print(f"Sending {args.workers} concurrent requests to {url}")

    def send_request(index: int) -> tuple[int, str]:
        with image_path.open("rb") as image_file:
            files = {"file": (image_path.name, image_file, "image/jpeg")}
            data = {"device_name": f"concurrency-test-{index}"}
            response = httpx.post(url, files=files, data=data, timeout=20)
            return response.status_code, response.text[:200]

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(send_request, i) for i in range(args.workers)]
        for future in as_completed(futures):
            status, body = future.result()
            print(f"  status={status}, body={body}")

    print("Concurrency test completed. Check the recognition event table for duplicate entries if the same face arrived simultaneously.")


if __name__ == "__main__":
    main()
