import base64
import hashlib
import hmac
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.core.cache import cache
from rest_framework.exceptions import APIException

from .models import CaptchaAuditLog

captcha_logger = logging.getLogger("algowiki.security")


class CaptchaError(APIException):
    status_code = 400
    default_detail = "验证码校验失败，请重试"
    default_code = "CAPTCHA_INVALID"

    def __init__(self, *, code: str, message: str, status_code: int = 400):
        self.status_code = status_code
        self.captcha_code = code
        super().__init__({"code": code, "message": message})


CAPTCHA_REQUIRED = ("CAPTCHA_REQUIRED", "请先完成人机验证", 400)
CAPTCHA_INVALID = ("CAPTCHA_INVALID", "验证码校验失败，请重试", 400)
CAPTCHA_DUPLICATED = ("CAPTCHA_DUPLICATED", "验证码已使用，请重新验证", 400)
CAPTCHA_RATE_LIMITED = ("CAPTCHA_RATE_LIMITED", "操作过于频繁，请稍后再试", 429)
CAPTCHA_PROVIDER_ERROR = ("CAPTCHA_PROVIDER_ERROR", "验证码服务暂时不可用，请稍后再试", 503)


@dataclass(frozen=True)
class CaptchaTarget:
    target_type: str = ""
    target_value: str = ""


def raise_captcha_error(error_tuple):
    code, message, status_code = error_tuple
    raise CaptchaError(code=code, message=message, status_code=status_code)


def bool_setting(name: str, default: bool = False) -> bool:
    return bool(getattr(settings, name, default))


def hash_text(value: str) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def stable_json_hash(value: Any) -> str:
    try:
        raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    except TypeError:
        raw = str(value)
    return hash_text(raw)


def get_client_ip(request) -> str:
    forwarded = str(request.META.get("HTTP_X_FORWARDED_FOR") or "").split(",")[0].strip()
    return forwarded or str(request.META.get("REMOTE_ADDR") or "").strip()


def get_user_agent(request) -> str:
    return str(request.META.get("HTTP_USER_AGENT") or "")[:1000]


def cache_add_once(key: str, timeout: int) -> bool:
    return cache.add(key, "1", timeout=timeout)


class CaptchaRateLimiter:
    BASE_RULES = {
        "ip": [(60, 5), (3600, 30), (86400, 100)],
        "user": [(60, 5), (3600, 20), (86400, 50)],
        "phone": [(60, 1), (3600, 5), (86400, 10)],
        "email": [(60, 1), (3600, 5), (86400, 10)],
    }
    SCENE_RULES = {
        "school_survey_submit": {
            "ip": [(60, 2), (3600, 10), (86400, 30)],
            "user": [(60, 2), (3600, 10), (86400, 20)],
            "school_survey": [(3600, 5), (86400, 20)],
        },
        "school_survey_update": {
            "ip": [(60, 3), (3600, 20)],
            "user": [(60, 3), (3600, 20)],
            "school_survey": [(60, 3), (3600, 10)],
        },
        "school_survey_delete": {
            "ip": [(60, 2), (3600, 10)],
            "user": [(60, 2), (3600, 10)],
            "school_survey": [(60, 2), (3600, 10)],
        },
        "school_survey_upload": {
            "ip": [(60, 3), (3600, 20)],
            "user": [(60, 5), (3600, 30)],
        },
        "school_survey_feedback": {
            "ip": [(60, 3), (3600, 20)],
            "user": [(60, 3), (3600, 20)],
            "school_survey": [(3600, 10)],
        },
        "school_survey_report": {
            "ip": [(60, 3), (3600, 20)],
            "user": [(60, 3), (3600, 20)],
            "school_survey": [(3600, 10)],
        },
        "school_survey_correction": {
            "ip": [(60, 3), (3600, 20)],
            "user": [(60, 3), (3600, 20)],
            "school_survey": [(3600, 10)],
        },
        "upload_image": {
            "ip": [(60, 3), (3600, 20)],
            "user": [(60, 5), (3600, 30)],
        },
    }

    def check_or_raise(self, *, request, scene: str, target: CaptchaTarget | None = None):
        checks = [("ip", get_client_ip(request))]
        if getattr(request.user, "is_authenticated", False):
            checks.append(("user", str(request.user.id)))
        if target and target.target_value:
            checks.append((target.target_type, target.target_value))

        rules = dict(self.BASE_RULES)
        for key, value in self.SCENE_RULES.get(scene, {}).items():
            rules[key] = value

        for scope, raw_value in checks:
            if not raw_value:
                continue
            for window_seconds, limit in rules.get(scope, []):
                self._increment_or_raise(
                    scene=scene,
                    scope=scope,
                    value=raw_value,
                    window_seconds=window_seconds,
                    limit=limit,
                )

    def _increment_or_raise(self, *, scene, scope, value, window_seconds, limit):
        bucket = int(time.time() // int(window_seconds))
        key = f"captcha:rate:{scene}:{scope}:{window_seconds}:{bucket}:{hash_text(value)}"
        current = int(cache.get(key) or 0)
        if current >= int(limit):
            raise_captcha_error(CAPTCHA_RATE_LIMITED)
        cache.set(key, current + 1, timeout=int(window_seconds) + 10)


class CaptchaFailureLimiter:
    RULES = {
        "ip": (5, 600),
        "user": (5, 600),
        "phone": (5, 1800),
        "email": (5, 1800),
        "school_survey": (5, 1800),
    }

    def check_or_raise(self, *, request, target: CaptchaTarget | None = None):
        for scope, value in self._subjects(request=request, target=target):
            lock_key = self._lock_key(scope, value)
            if cache.get(lock_key):
                raise_captcha_error(CAPTCHA_RATE_LIMITED)

    def record_failure(self, *, request, target: CaptchaTarget | None = None):
        for scope, value in self._subjects(request=request, target=target):
            limit, lock_seconds = self.RULES.get(scope, (5, 600))
            key = f"captcha:fail:{scope}:{hash_text(value)}"
            count = int(cache.get(key) or 0) + 1
            cache.set(key, count, timeout=lock_seconds)
            if count >= limit:
                cache.set(self._lock_key(scope, value), "1", timeout=lock_seconds)

    def record_success(self, *, request, target: CaptchaTarget | None = None):
        for scope, value in self._subjects(request=request, target=target):
            cache.delete(f"captcha:fail:{scope}:{hash_text(value)}")

    def _subjects(self, *, request, target):
        ip = get_client_ip(request)
        if ip:
            yield "ip", ip
        if getattr(request.user, "is_authenticated", False):
            yield "user", str(request.user.id)
        if target and target.target_value and target.target_type in self.RULES:
            yield target.target_type, target.target_value

    def _lock_key(self, scope, value):
        return f"captcha:fail-lock:{scope}:{hash_text(value)}"


class TurnstileValidator:
    def verify(self, *, token: str, remote_ip: str | None = None) -> dict:
        secret = str(getattr(settings, "TURNSTILE_SECRET_KEY", "") or "").strip()
        if not secret:
            raise_captcha_error(CAPTCHA_PROVIDER_ERROR)
        payload = {
            "secret": secret,
            "response": str(token or "").strip(),
        }
        if remote_ip:
            payload["remoteip"] = remote_ip
        request = urllib.request.Request(
            str(getattr(settings, "TURNSTILE_VERIFY_URL", "") or "").strip(),
            data=urllib.parse.urlencode(payload).encode("utf-8"),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=8) as response:
                body = response.read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            captcha_logger.warning("turnstile_provider_error error=%s", exc)
            raise_captcha_error(CAPTCHA_PROVIDER_ERROR)
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            raise_captcha_error(CAPTCHA_PROVIDER_ERROR)
        if not data.get("success"):
            captcha_logger.info(
                "turnstile_invalid errors=%s hostname=%s action=%s cdata=%s",
                data.get("error-codes"),
                data.get("hostname"),
                data.get("action"),
                data.get("cdata"),
            )
            raise_captcha_error(CAPTCHA_INVALID)
        return data


class GeeTestValidator:
    REQUIRED_FIELDS = ("lot_number", "captcha_output", "pass_token", "gen_time")

    def verify(self, *, payload: dict, remote_ip: str | None = None) -> dict:
        captcha_id = str(getattr(settings, "GEETEST_CAPTCHA_ID", "") or "").strip()
        captcha_key = str(getattr(settings, "GEETEST_CAPTCHA_KEY", "") or "").strip()
        if not captcha_id or not captcha_key:
            raise_captcha_error(CAPTCHA_PROVIDER_ERROR)
        if not isinstance(payload, dict) or any(not payload.get(field) for field in self.REQUIRED_FIELDS):
            raise_captcha_error(CAPTCHA_INVALID)

        lot_number = str(payload.get("lot_number") or "")
        sign_token = hmac.new(
            captcha_key.encode("utf-8"),
            lot_number.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).hexdigest()
        request_payload = {
            "lot_number": lot_number,
            "captcha_output": str(payload.get("captcha_output") or ""),
            "pass_token": str(payload.get("pass_token") or ""),
            "gen_time": str(payload.get("gen_time") or ""),
            "captcha_id": captcha_id,
            "sign_token": sign_token,
        }
        if remote_ip:
            request_payload["remote_ip"] = remote_ip
        request = urllib.request.Request(
            str(getattr(settings, "GEETEST_VERIFY_URL", "") or "").strip(),
            data=urllib.parse.urlencode(request_payload).encode("utf-8"),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=8) as response:
                body = response.read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            captcha_logger.warning("geetest_provider_error error=%s", exc)
            raise_captcha_error(CAPTCHA_PROVIDER_ERROR)
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            raise_captcha_error(CAPTCHA_PROVIDER_ERROR)
        result = str(data.get("result") or data.get("status") or "").lower()
        if result not in {"success", "pass", "true"} and data.get("success") is not True:
            captcha_logger.info("geetest_invalid result=%s data=%s", result, data)
            raise_captcha_error(CAPTCHA_INVALID)
        return data


class SecondaryCaptchaValidator:
    def verify(self, *, provider: str, payload: dict, remote_ip: str | None = None) -> dict:
        normalized = str(provider or "").strip().lower()
        if normalized == "geetest":
            return GeeTestValidator().verify(payload=payload, remote_ip=remote_ip)
        raise_captcha_error(CAPTCHA_PROVIDER_ERROR)


class CaptchaService:
    def __init__(self):
        self.rate_limiter = CaptchaRateLimiter()
        self.failure_limiter = CaptchaFailureLimiter()

    def verify_or_raise(
        self,
        *,
        request,
        captcha: dict | None,
        scene: str,
        target: CaptchaTarget | None = None,
    ) -> None:
        if not bool_setting("CAPTCHA_ENABLED", False):
            return
        if (
            getattr(request.user, "is_authenticated", False)
            and not bool_setting("CAPTCHA_REQUIRED_FOR_AUTHENTICATED_USERS", True)
        ):
            return

        target = target or CaptchaTarget()
        audit_kwargs = self._audit_base(request=request, scene=scene, target=target)
        turnstile_success = False
        secondary_success = False
        secondary_provider = ""
        try:
            if not isinstance(captcha, dict):
                raise_captcha_error(CAPTCHA_REQUIRED)
            if str(captcha.get("scene") or "") != scene:
                raise_captcha_error(CAPTCHA_INVALID)

            self.rate_limiter.check_or_raise(request=request, scene=scene, target=target)
            self.failure_limiter.check_or_raise(request=request, target=target)

            token = str(captcha.get("turnstile_token") or "").strip()
            if not token:
                raise_captcha_error(CAPTCHA_REQUIRED)
            token_hash = hash_text(token)
            if not cache_add_once(
                f"captcha:used:turnstile:{token_hash}",
                int(getattr(settings, "CAPTCHA_TOKEN_TTL", 300)),
            ):
                raise_captcha_error(CAPTCHA_DUPLICATED)
            TurnstileValidator().verify(token=token, remote_ip=get_client_ip(request))
            turnstile_success = True

            if bool_setting("SECONDARY_CAPTCHA_ENABLED", False):
                secondary_provider = str(captcha.get("secondary_provider") or "").strip().lower()
                if secondary_provider != str(getattr(settings, "SECONDARY_CAPTCHA_PROVIDER", "geetest")).lower():
                    raise_captcha_error(CAPTCHA_INVALID)
                secondary_payload = captcha.get("secondary_payload")
                if not isinstance(secondary_payload, dict):
                    raise_captcha_error(CAPTCHA_REQUIRED)
                secondary_hash = stable_json_hash(secondary_payload)
                if not cache_add_once(
                    f"captcha:used:secondary:{secondary_provider}:{secondary_hash}",
                    int(getattr(settings, "CAPTCHA_TOKEN_TTL", 300)),
                ):
                    raise_captcha_error(CAPTCHA_DUPLICATED)
                SecondaryCaptchaValidator().verify(
                    provider=secondary_provider,
                    payload=secondary_payload,
                    remote_ip=get_client_ip(request),
                )
                secondary_success = True

            self.failure_limiter.record_success(request=request, target=target)
            CaptchaAuditLog.objects.create(
                **audit_kwargs,
                turnstile_success=turnstile_success,
                secondary_provider=secondary_provider,
                secondary_success=secondary_success,
                result="success",
            )
        except CaptchaError as exc:
            code = getattr(exc, "captcha_code", "CAPTCHA_INVALID")
            self.failure_limiter.record_failure(request=request, target=target)
            CaptchaAuditLog.objects.create(
                **audit_kwargs,
                turnstile_success=turnstile_success,
                secondary_provider=secondary_provider,
                secondary_success=secondary_success,
                result="failed",
                error_code=code,
                error_message=str(exc.detail)[:1000],
            )
            raise

    def _audit_base(self, *, request, scene: str, target: CaptchaTarget):
        user = request.user if getattr(request.user, "is_authenticated", False) else None
        return {
            "scene": scene,
            "user": user,
            "ip_address": get_client_ip(request) or None,
            "user_agent": get_user_agent(request),
            "target_type": str(target.target_type or "")[:32],
            "target_hash": hash_text(target.target_value) if target.target_value else "",
        }


def get_public_captcha_config() -> dict:
    return {
        "enabled": bool_setting("CAPTCHA_ENABLED", False),
        "required_for_authenticated_users": bool_setting(
            "CAPTCHA_REQUIRED_FOR_AUTHENTICATED_USERS",
            True,
        ),
        "turnstile_site_key": str(getattr(settings, "TURNSTILE_SITE_KEY", "") or "").strip(),
        "secondary_enabled": bool_setting("SECONDARY_CAPTCHA_ENABLED", False),
        "secondary_provider": str(
            getattr(settings, "SECONDARY_CAPTCHA_PROVIDER", "geetest") or "geetest"
        )
        .strip()
        .lower(),
        "geetest_captcha_id": str(getattr(settings, "GEETEST_CAPTCHA_ID", "") or "").strip(),
        "token_ttl_seconds": int(getattr(settings, "CAPTCHA_TOKEN_TTL", 300)),
    }


def captcha_target(target_type: str, value: Any) -> CaptchaTarget:
    return CaptchaTarget(
        target_type=str(target_type or "")[:32],
        target_value=str(value or "").strip(),
    )


def extract_email_target(data: dict, key: str = "email") -> CaptchaTarget:
    return captcha_target("email", str((data or {}).get(key) or "").strip().lower())


def extract_phone_target(data: dict) -> CaptchaTarget:
    country = str((data or {}).get("country_code") or "86").strip()
    phone = str((data or {}).get("phone_number") or (data or {}).get("phone") or "").strip()
    return captcha_target("phone", f"{country}:{phone}")


def extract_school_survey_target(form_data: dict) -> CaptchaTarget:
    payload = form_data if isinstance(form_data, dict) else {}
    school_name = str(payload.get("school_name") or "").strip()
    contact = str(payload.get("submitter_contact") or "").strip().lower()
    return captcha_target("school_survey", f"{school_name}:{contact}")


def normalize_captcha_payload(value: Any) -> dict | None:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def extract_captcha_payload(data) -> dict | None:
    if not hasattr(data, "get"):
        return None
    return normalize_captcha_payload(data.get("captcha"))


def strip_captcha_payload(data):
    if hasattr(data, "copy") and hasattr(data, "pop"):
        clone = data.copy()
        try:
            clone.pop("captcha", None)
        except TypeError:
            if "captcha" in clone:
                clone.pop("captcha")
        return clone
    if isinstance(data, dict):
        return {key: value for key, value in data.items() if key != "captcha"}
    return data
