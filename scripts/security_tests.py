from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import time

import httpx


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run security tests against the face recognition backend.")
    parser.add_argument("--host", required=True, help="Base URL for the backend, e.g. http://localhost")
    parser.add_argument("--image-path", required=True, help="Sample image to send in rate limit tests")
    parser.add_argument("--rate-requests", type=int, default=100, help="Number of requests to send during rate-limit test")
    parser.add_argument("--rate-workers", type=int, default=20, help="Number of concurrent workers to use")
    return parser.parse_args()


def run_rate_limit_test(host: str, image_path: Path, total_requests: int, workers: int) -> None:
    url = f"{host}/api/vision/recognize"
    print(f"Running rate-limit test: {total_requests} requests to {url}")

    def send_request(index: int) -> int:
        with image_path.open("rb") as image_file:
            files = {"file": (image_path.name, image_file, "image/jpeg")}
            data = {"device_name": f"rate-limit-test-{index % 10}"}
            try:
                response = httpx.post(url, files=files, data=data, timeout=20)
                return response.status_code
            except Exception as exc:
                print(f"Request {index} failed: {exc}")
                return 0

    statuses: dict[int, int] = {}
    start = time.time()
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(send_request, i) for i in range(total_requests)]
        for future in as_completed(futures):
            status = future.result()
            statuses[status] = statuses.get(status, 0) + 1
    duration = time.time() - start

    print(f"Completed {total_requests} requests in {duration:.2f}s")
    for status, count in sorted(statuses.items()):
        print(f"  {status}: {count}")
    print("Expect a large number of 429 responses if Nginx rate limiting is active.")


def run_auth_tests(host: str) -> None:
    client = httpx.Client(timeout=20)
    admin_url = f"{host}/api/admin/employees"

    print("Testing admin endpoint without token...")
    response = client.get(admin_url)
    print(f"  no-token status: {response.status_code}")

    print("Testing admin endpoint with invalid token...")
    headers = {"Authorization": "Bearer invalid-token"}
    response = client.get(admin_url, headers=headers)
    print(f"  invalid-token status: {response.status_code}")

    if response.status_code not in {401, 403}:
        print("Warning: invalid token did not produce an authorization error.")
    else:
        print("Authorization protection is working for admin endpoints.")


def main() -> None:
    args = parse_args()
    image_path = Path(args.image_path)
    if not image_path.exists():
        raise SystemExit(f"Image path not found: {image_path}")

    run_rate_limit_test(args.host, image_path, args.rate_requests, args.rate_workers)
    print("\nRunning authentication tests...\n")
    run_auth_tests(args.host)


if __name__ == "__main__":
    main()
