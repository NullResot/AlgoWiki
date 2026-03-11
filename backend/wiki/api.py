import logging

from rest_framework.views import exception_handler

from config.request_context import get_request_id

api_logger = logging.getLogger("algowiki.api")


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    request = context.get("request")
    request_id = get_request_id()

    if response is None:
        return None

    if hasattr(response, "data") and isinstance(response.data, dict) and "request_id" not in response.data:
        response.data["request_id"] = request_id

    if response.status_code >= 500:
        api_logger.error(
            "API response error status=%s method=%s path=%s request_id=%s",
            response.status_code,
            getattr(request, "method", "-"),
            request.get_full_path() if request else "-",
            request_id,
        )
    elif response.status_code in {401, 403, 429}:
        api_logger.warning(
            "API access issue status=%s method=%s path=%s request_id=%s",
            response.status_code,
            getattr(request, "method", "-"),
            request.get_full_path() if request else "-",
            request_id,
        )

    return response
