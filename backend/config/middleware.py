import logging
import time
from uuid import uuid4

from django.conf import settings

from .request_context import normalize_request_id, reset_request_id, set_request_id

request_logger = logging.getLogger("algowiki.request")


class RequestContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = normalize_request_id(request.headers.get("X-Request-ID")) if request.headers else "-"
        if request_id == "-":
            request_id = uuid4().hex

        token = set_request_id(request_id)
        request.request_id = request_id
        started = time.perf_counter()

        try:
            response = self.get_response(request)
        except Exception:
            duration_ms = (time.perf_counter() - started) * 1000
            request_logger.exception(
                "Unhandled request exception method=%s path=%s duration_ms=%.2f user=%s remote=%s",
                request.method,
                request.get_full_path(),
                duration_ms,
                self._resolve_user(request),
                self._resolve_remote_addr(request),
            )
            raise
        else:
            response["X-Request-ID"] = request_id
            self._log_request(request, response, started)
            return response
        finally:
            reset_request_id(token)

    def _log_request(self, request, response, started):
        if not getattr(settings, "REQUEST_LOG_ENABLED", True):
            return
        if self._should_skip_path(request.path):
            return

        duration_ms = (time.perf_counter() - started) * 1000
        level = logging.INFO
        if response.status_code >= 500 or duration_ms >= float(getattr(settings, "SLOW_REQUEST_MS", 1500)):
            level = logging.WARNING

        request_logger.log(
            level,
            "Request completed method=%s path=%s status=%s duration_ms=%.2f user=%s remote=%s",
            request.method,
            request.get_full_path(),
            response.status_code,
            duration_ms,
            self._resolve_user(request),
            self._resolve_remote_addr(request),
        )

    def _should_skip_path(self, path: str) -> bool:
        path = path or "/"
        for prefix in getattr(settings, "REQUEST_LOG_EXCLUDE_PREFIXES", ()):
            prefix = str(prefix or "").strip()
            if prefix and path.startswith(prefix):
                return True
        return False

    @staticmethod
    def _resolve_user(request) -> str:
        user = getattr(request, "user", None)
        if user is not None and getattr(user, "is_authenticated", False):
            return getattr(user, "username", "") or str(getattr(user, "pk", "authenticated"))
        return "anonymous"

    @staticmethod
    def _resolve_remote_addr(request) -> str:
        forwarded = (request.META.get("HTTP_X_FORWARDED_FOR", "") or "").strip()
        if forwarded:
            return forwarded.split(",")[0].strip()
        return (request.META.get("REMOTE_ADDR", "") or "").strip() or "-"
