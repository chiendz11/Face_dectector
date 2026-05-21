from app.worker.celery_app import _normalize_redis_ssl_url


def test_normalize_redis_ssl_url_adds_cert_required_for_rediss() -> None:
    assert (
        _normalize_redis_ssl_url("rediss://:secret@redis.example:6379/0")
        == "rediss://:secret@redis.example:6379/0?ssl_cert_reqs=CERT_REQUIRED"
    )


def test_normalize_redis_ssl_url_keeps_existing_ssl_policy() -> None:
    assert (
        _normalize_redis_ssl_url("rediss://:secret@redis.example:6379/0?ssl_cert_reqs=CERT_NONE")
        == "rediss://:secret@redis.example:6379/0?ssl_cert_reqs=CERT_NONE"
    )


def test_normalize_redis_ssl_url_leaves_plain_redis_unchanged() -> None:
    assert _normalize_redis_ssl_url("redis://redis:6379/0") == "redis://redis:6379/0"
