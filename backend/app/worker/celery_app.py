from celery import Celery
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.core.config import settings


def _normalize_redis_ssl_url(redis_url: str) -> str:
    parts = urlsplit(redis_url)
    if parts.scheme != "rediss":
        return redis_url

    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    if "ssl_cert_reqs" in query:
        return redis_url

    query["ssl_cert_reqs"] = "CERT_REQUIRED"
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


celery_redis_url = _normalize_redis_ssl_url(settings.redis_url)

celery_app = Celery(
    "face_detector",
    broker=celery_redis_url,
    backend=celery_redis_url,
)

celery_app.conf.task_routes = {
    "app.worker.tasks.*": {"queue": "default"},
}
