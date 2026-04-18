from __future__ import annotations

import time
from functools import wraps
from threading import Lock


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        exceptions: tuple[type[BaseException], ...] = (Exception,),
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.exceptions = exceptions
        self.failure_count = 0
        self.state: str = "closed"
        self._reopened_at: float | None = None
        self._lock = Lock()

    def call(self, func, *args, **kwargs):
        with self._lock:
            now = time.monotonic()
            if self.state == "open":
                if self._reopened_at is not None and now < self._reopened_at + self.recovery_timeout:
                    raise RuntimeError("Circuit breaker is open; service temporarily unavailable")
                self.state = "half_open"

        try:
            result = func(*args, **kwargs)
        except self.exceptions as exc:
            with self._lock:
                self.failure_count += 1
                if self.failure_count >= self.failure_threshold:
                    self.state = "open"
                    self._reopened_at = now
            raise
        else:
            with self._lock:
                self.failure_count = 0
                self.state = "closed"
                self._reopened_at = None
            return result

    def __call__(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return self.call(func, *args, **kwargs)

        return wrapper


def retry_operation(
    max_attempts: int = 3,
    initial_delay: float = 0.5,
    multiplier: float = 2.0,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> callable:
    def decorate(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_error: BaseException | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_error = exc
                    if attempt == max_attempts:
                        raise
                    time.sleep(delay)
                    delay *= multiplier
            raise last_error  # pragma: no cover

        return wrapper

    return decorate
