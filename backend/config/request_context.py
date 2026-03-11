import contextvars
import logging
import re

_request_id_var = contextvars.ContextVar("algowiki_request_id", default="-")
_request_id_pattern = re.compile(r"[^A-Za-z0-9._-]+")


def normalize_request_id(value: str | None) -> str:
    normalized = _request_id_pattern.sub("-", str(value or "").strip())[:64].strip("-.")
    return normalized or "-"


def set_request_id(value: str):
    return _request_id_var.set(normalize_request_id(value))


def get_request_id() -> str:
    return normalize_request_id(_request_id_var.get("-"))


def reset_request_id(token):
    _request_id_var.reset(token)


class RequestIdFilter(logging.Filter):
    def filter(self, record):
        record.request_id = get_request_id()
        return True
