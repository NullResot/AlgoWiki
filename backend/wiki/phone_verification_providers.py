import json
import re
from datetime import timedelta
from typing import Any
from uuid import uuid4

from django.conf import settings
from django.core import signing
from django.db import IntegrityError
from django.utils import timezone
from django.utils.crypto import salted_hmac
from rest_framework.exceptions import ValidationError

from alibabacloud_dypnsapi20170525.client import Client as DypnsapiClient
from alibabacloud_dypnsapi20170525 import models as dypnsapi_models
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_tea_util import models as util_models

from .models import PhoneVerification, PhoneVerificationTicket

PHONE_TICKET_SIGNING_SALT = "wiki.phone.ticket.v1"
PHONE_DIGEST_SALT = "wiki.phone.digest.v1"
MAINLAND_PHONE_RE = re.compile(r"^1[3-9]\d{9}$")


class PhoneVerificationProviderError(Exception):
    def __init__(self, message: str, *, status_code: int = 502):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _config() -> dict[str, Any]:
    return getattr(settings, "ALIYUN_PNVS", {}) or {}


def aliyun_phone_verification_is_configured() -> bool:
    cfg = _config()
    return bool(
        cfg.get("ENABLED")
        and cfg.get("ACCESS_KEY_ID")
        and cfg.get("ACCESS_KEY_SECRET")
        and cfg.get("SIGN_NAME")
        and cfg.get("TEMPLATE_CODE")
    )


def _require_config() -> dict[str, Any]:
    cfg = _config()
    if not cfg.get("ENABLED"):
        raise PhoneVerificationProviderError("短信验证服务尚未开启。", status_code=503)
    missing = [
        key
        for key in ("ACCESS_KEY_ID", "ACCESS_KEY_SECRET", "SIGN_NAME", "TEMPLATE_CODE")
        if not cfg.get(key)
    ]
    if missing:
        raise PhoneVerificationProviderError(
            f"短信验证服务配置不完整：{', '.join(missing)}。",
            status_code=503,
        )
    return cfg


def _timeout_ms(cfg: dict[str, Any]) -> int:
    return max(1, int(cfg.get("TIMEOUT_SECONDS") or 15)) * 1000


def _client(cfg: dict[str, Any], endpoint: str) -> DypnsapiClient:
    return DypnsapiClient(
        open_api_models.Config(
            access_key_id=str(cfg.get("ACCESS_KEY_ID") or ""),
            access_key_secret=str(cfg.get("ACCESS_KEY_SECRET") or ""),
            endpoint=endpoint,
        )
    )


def _runtime_options(cfg: dict[str, Any]) -> util_models.RuntimeOptions:
    timeout = _timeout_ms(cfg)
    return util_models.RuntimeOptions(connect_timeout=timeout, read_timeout=timeout)


def _call_with_failover(cfg: dict[str, Any], method_name: str, request_obj):
    endpoints = [str(item).strip() for item in cfg.get("ENDPOINTS") or [] if str(item).strip()]
    last_error: Exception | None = None
    for endpoint in endpoints:
        try:
            client = _client(cfg, endpoint)
            method = getattr(client, method_name)
            return method(request_obj, _runtime_options(cfg))
        except Exception as exc:  # SDK exceptions vary by provider response and transport.
            last_error = exc
    if last_error:
        error_text = str(last_error).lower()
        if any(
            marker in error_text
            for marker in (
                "forbidden.nopermission",
                "not authorized to perform this action",
                "accessdenied",
                "implicitdeny",
            )
        ):
            raise PhoneVerificationProviderError(
                "阿里云号码认证服务当前未授权给这组 AccessKey。请在 RAM 中给该 RAM 用户授予 AliyunDypnsFullAccess，"
                "或至少允许 dypns:SendSmsVerifyCode 和 dypns:CheckSmsVerifyCode。"
            ) from last_error
        if "function_not_opened" in error_text:
            raise PhoneVerificationProviderError(
                "阿里云号码认证服务尚未开通短信认证能力。"
            ) from last_error
        raise PhoneVerificationProviderError(
            f"短信验证服务调用失败：{last_error}"
        ) from last_error
    raise PhoneVerificationProviderError("短信验证服务没有可用 endpoint。", status_code=503)


def _normalize_country_code(value: str | int | None) -> str:
    text = re.sub(r"\D", "", str(value or "86"))
    return text or "86"


def _normalize_phone_number(value: str) -> str:
    text = re.sub(r"\D", "", str(value or ""))
    if text.startswith("86") and len(text) == 13:
        text = text[2:]
    return text


def normalize_phone_context(*, country_code: str | int | None, phone_number: str) -> tuple[str, str]:
    normalized_country_code = _normalize_country_code(country_code)
    normalized_phone_number = _normalize_phone_number(phone_number)
    if normalized_country_code != "86":
        raise ValidationError({"country_code": ["Only mainland China phone numbers are supported."]})
    if not MAINLAND_PHONE_RE.fullmatch(normalized_phone_number):
        raise ValidationError({"phone_number": ["Please enter a valid mainland China mobile number."]})
    return normalized_country_code, normalized_phone_number


def mask_phone_number(value: str) -> str:
    phone = _normalize_phone_number(value)
    if len(phone) < 7:
        return phone
    return f"{phone[:3]}****{phone[-4:]}"


def _build_phone_digest(country_code: str, phone_number: str) -> str:
    return salted_hmac(
        PHONE_DIGEST_SALT,
        f"{country_code}:{phone_number}",
        secret=settings.SECRET_KEY,
    ).hexdigest()


def build_phone_ticket_token(ticket: PhoneVerificationTicket) -> str:
    return signing.dumps({"ticket_id": ticket.id}, salt=PHONE_TICKET_SIGNING_SALT, compress=True)


def load_phone_ticket_from_token(token: str) -> PhoneVerificationTicket:
    raw = str(token or "").strip()
    if not raw:
        raise ValidationError({"ticket_token": ["Please request a new verification code."]})
    try:
        payload = signing.loads(raw, salt=PHONE_TICKET_SIGNING_SALT)
    except signing.BadSignature as exc:
        raise ValidationError({"ticket_token": ["Verification session is invalid."]}) from exc

    ticket_id = payload.get("ticket_id")
    try:
        return PhoneVerificationTicket.objects.select_related("user").get(id=ticket_id)
    except PhoneVerificationTicket.DoesNotExist as exc:
        raise ValidationError({"ticket_token": ["Verification session is invalid."]}) from exc


def build_phone_code_window_wait_seconds(*, country_code: str, phone_number: str, user=None) -> int:
    window_minutes = max(1, int(getattr(settings, "PHONE_VERIFICATION_WINDOW_MINUTES", 60)))
    max_sends = max(1, int(getattr(settings, "PHONE_VERIFICATION_MAX_SENDS_PER_WINDOW", 5)))
    window_start = timezone.now() - timedelta(minutes=window_minutes)
    queryset = PhoneVerificationTicket.objects.filter(
        phone_country_code=country_code,
        phone_digest=_build_phone_digest(country_code, phone_number),
        created_at__gte=window_start,
    ).order_by("created_at")
    if user is not None:
        queryset = queryset.filter(user=user)
    recent = list(queryset[:max_sends])
    if len(recent) < max_sends:
        return 0
    oldest = recent[0]
    wait_until = oldest.created_at + timedelta(minutes=window_minutes)
    wait_seconds = int((wait_until - timezone.now()).total_seconds())
    return wait_seconds if wait_seconds > 0 else 0


def build_phone_code_send_wait_seconds(*, country_code: str, phone_number: str, user=None) -> int:
    cooldown_seconds = max(0, int(getattr(settings, "PHONE_VERIFICATION_RESEND_SECONDS", 60)))
    if cooldown_seconds <= 0:
        return 0

    queryset = PhoneVerificationTicket.objects.filter(
        phone_country_code=country_code,
        phone_digest=_build_phone_digest(country_code, phone_number),
    )
    if user is not None:
        queryset = queryset.filter(user=user)
    latest = queryset.order_by("-created_at").first()
    if not latest:
        return 0
    elapsed = (timezone.now() - latest.created_at).total_seconds()
    wait_seconds = cooldown_seconds - int(elapsed)
    return wait_seconds if wait_seconds > 0 else 0


def _build_response_payload(body) -> dict[str, Any]:
    model = getattr(body, "model", None)
    payload = {
        "request_id": getattr(body, "request_id", "") or "",
        "code": getattr(body, "code", "") or "",
        "message": getattr(body, "message", "") or "",
        "success": getattr(body, "success", None),
    }
    if model:
        payload.update(
            {
                "biz_id": getattr(model, "biz_id", "") or "",
                "out_id": getattr(model, "out_id", "") or "",
                "verify_code_returned": bool(getattr(model, "verify_code", "") or ""),
                "verify_result": getattr(model, "verify_result", "") or "",
            }
        )
    return payload


def _is_success_code(value: str) -> bool:
    return str(value or "").strip() in {"200", "OK", "Success"}


def _is_passed(value: str) -> bool:
    normalized = str(value or "").strip().upper()
    return normalized in {"PASS", "TRUE", "T", "YES", "Y", "1"}


def _get_phone_verification(user) -> PhoneVerification | None:
    if not user or not user.is_authenticated:
        return None
    try:
        return user.phone_verification
    except PhoneVerification.DoesNotExist:
        return None


def _update_phone_verification(
    *,
    user,
    status: str,
    country_code: str,
    phone_number: str,
    provider: str,
    provider_out_id: str = "",
    provider_biz_id: str = "",
    provider_request_id: str = "",
    provider_status_message: str = "",
    provider_result: dict[str, Any] | None = None,
    provider_started_at=None,
    provider_checked_at=None,
    provider_expires_at=None,
    submitted_at=None,
    verified_at=None,
    revoked_at=None,
    review_note: str = "",
    reviewer=None,
) -> PhoneVerification:
    digest = _build_phone_digest(country_code, phone_number)
    now = timezone.now()
    masked = mask_phone_number(phone_number)
    last4 = phone_number[-4:]
    instance, _ = PhoneVerification.objects.get_or_create(user=user)
    instance.status = status
    instance.phone_country_code = country_code
    instance.phone_masked = masked[:32]
    instance.phone_last4 = last4
    instance.phone_digest = digest
    instance.provider = provider
    instance.provider_out_id = provider_out_id[:120]
    instance.provider_biz_id = provider_biz_id[:120]
    instance.provider_request_id = provider_request_id[:120]
    instance.provider_status_message = provider_status_message[:300]
    instance.provider_result = provider_result or {}
    instance.provider_started_at = provider_started_at or now
    instance.provider_checked_at = provider_checked_at
    instance.provider_expires_at = provider_expires_at
    instance.submitted_at = submitted_at or now
    instance.verified_at = verified_at
    instance.revoked_at = revoked_at
    instance.reviewer = reviewer
    instance.review_note = review_note[:300]
    instance.save()
    return instance


def start_aliyun_phone_verification(
    *,
    user,
    phone_number: str,
    country_code: str,
    request,
) -> tuple[PhoneVerification, PhoneVerificationTicket, dict[str, Any]]:
    cfg = _require_config()
    normalized_country_code, normalized_phone_number = normalize_phone_context(
        country_code=country_code,
        phone_number=phone_number,
    )
    if _get_phone_verification(user) and _get_phone_verification(user).status == PhoneVerification.Status.VERIFIED:
        verification = _get_phone_verification(user)
        if verification and verification.phone_digest == _build_phone_digest(
            normalized_country_code, normalized_phone_number
        ):
            return verification, None, {
                "ticket_token": "",
                "masked_phone": verification.phone_masked,
                "expires_in_seconds": 0,
            }
        raise PhoneVerificationProviderError("你已经完成手机号验证。", status_code=400)

    digest = _build_phone_digest(normalized_country_code, normalized_phone_number)
    existing = PhoneVerification.objects.filter(phone_digest=digest).exclude(user=user).first()
    if existing and existing.status == PhoneVerification.Status.VERIFIED:
        raise PhoneVerificationProviderError("该手机号已绑定其他账号。", status_code=400)

    wait_seconds = build_phone_code_send_wait_seconds(
        country_code=normalized_country_code,
        phone_number=normalized_phone_number,
        user=user,
    )
    if wait_seconds:
        raise PhoneVerificationProviderError(
            "请稍后再发送验证码。",
            status_code=429,
        )

    window_wait_seconds = build_phone_code_window_wait_seconds(
        country_code=normalized_country_code,
        phone_number=normalized_phone_number,
        user=user,
    )
    if window_wait_seconds:
        raise PhoneVerificationProviderError(
            "验证码发送过于频繁，请稍后再试。",
            status_code=429,
        )

    scheme_name = str(cfg.get("SCHEME_NAME") or "AlgoWiki").strip() or "AlgoWiki"
    template_param = str(cfg.get("TEMPLATE_PARAM") or "").strip() or "{\"code\":\"##code##\",\"min\":\"5\"}"
    out_id = str(cfg.get("OUT_ID_PREFIX") or "algowiki")[:40] + "-" + uuid4().hex
    request_obj = dypnsapi_models.SendSmsVerifyCodeRequest(
        auto_retry=int(cfg.get("AUTO_RETRY") or 0),
        code_length=int(cfg.get("CODE_LENGTH") or 6),
        code_type=int(cfg.get("CODE_TYPE") or 1),
        country_code=normalized_country_code,
        duplicate_policy=int(cfg.get("DUPLICATE_POLICY") or 1),
        interval=int(cfg.get("INTERVAL_SECONDS") or 60),
        out_id=out_id,
        owner_id=None,
        phone_number=normalized_phone_number,
        return_verify_code=bool(cfg.get("RETURN_VERIFY_CODE")),
        scheme_name=scheme_name,
        sign_name=str(cfg.get("SIGN_NAME") or "").strip(),
        sms_up_extend_code=str(cfg.get("SMS_UP_EXTEND_CODE") or "").strip() or None,
        template_code=str(cfg.get("TEMPLATE_CODE") or "").strip(),
        template_param=template_param,
        valid_time=int(cfg.get("VALID_TIME_SECONDS") or 300),
    )
    response = _call_with_failover(cfg, "send_sms_verify_code_with_options", request_obj)
    body = getattr(response, "body", None)
    if not body or not _is_success_code(getattr(body, "code", "")):
        message = getattr(body, "message", "") or "短信验证码发送失败。"
        raise PhoneVerificationProviderError(message)

    now = timezone.now()
    expires_seconds = max(60, int(cfg.get("VALID_TIME_SECONDS") or 300))
    response_payload = _build_response_payload(body)
    provider_out_id = str(response_payload.get("out_id") or out_id)
    provider_biz_id = str(response_payload.get("biz_id") or "")
    provider_request_id = str(response_payload.get("request_id") or "")
    try:
        verification = _update_phone_verification(
            user=user,
            status=PhoneVerification.Status.PENDING,
            country_code=normalized_country_code,
            phone_number=normalized_phone_number,
            provider="aliyun_pnvs",
            provider_out_id=provider_out_id,
            provider_biz_id=provider_biz_id,
            provider_request_id=provider_request_id,
            provider_status_message=str(getattr(body, "message", "") or "")[:300],
            provider_result=response_payload,
            provider_started_at=now,
            provider_checked_at=None,
            provider_expires_at=now + timedelta(seconds=expires_seconds),
            submitted_at=now,
            verified_at=None,
            revoked_at=None,
            review_note="已发送短信验证码，等待用户校验。",
        )
    except IntegrityError as exc:
        raise PhoneVerificationProviderError("该手机号已被其他账号使用。", status_code=400) from exc

    ticket = PhoneVerificationTicket.objects.create(
        user=user,
        phone_country_code=normalized_country_code,
        phone_masked=verification.phone_masked,
        phone_last4=verification.phone_last4,
        phone_digest=digest,
        provider="aliyun_pnvs",
        provider_out_id=provider_out_id,
        provider_biz_id=provider_biz_id,
        provider_request_id=provider_request_id,
        provider_response=response_payload,
        created_ip=str(getattr(request, "META", {}).get("REMOTE_ADDR") or "").strip() or None,
        expires_at=now + timedelta(seconds=expires_seconds),
    )
    return verification, ticket, {
        "ticket_token": build_phone_ticket_token(ticket),
        "masked_phone": verification.phone_masked,
        "expires_in_seconds": expires_seconds,
    }


def check_aliyun_phone_verification(
    *,
    ticket: PhoneVerificationTicket,
    phone_number: str,
    verify_code: str,
) -> PhoneVerification:
    cfg = _require_config()
    if ticket.consumed_at is not None:
        raise ValidationError({"ticket_token": ["This verification session has already been used."]})
    if ticket.expires_at <= timezone.now():
        raise ValidationError({"ticket_token": ["Verification code expired. Please request a new one."]})

    normalized_phone_number = _normalize_phone_number(phone_number)
    normalized_country_code = ticket.phone_country_code or "86"
    digest = _build_phone_digest(normalized_country_code, normalized_phone_number)
    if digest != ticket.phone_digest:
        raise ValidationError({"phone_number": ["The phone number does not match the verification session."]})
    code_text = str(verify_code or "").strip()
    if not code_text:
        raise ValidationError({"verify_code": ["Please enter the verification code."]})
    max_attempts = max(1, int(getattr(settings, "PHONE_VERIFICATION_MAX_VERIFY_ATTEMPTS", 5)))
    if ticket.verify_attempt_count >= max_attempts:
        raise ValidationError({"verify_code": ["Too many incorrect attempts. Please request a new verification code."]})

    scheme_name = str(cfg.get("SCHEME_NAME") or "AlgoWiki").strip() or "AlgoWiki"
    request_obj = dypnsapi_models.CheckSmsVerifyCodeRequest(
        case_auth_policy=1,
        country_code=normalized_country_code,
        out_id=ticket.provider_out_id or None,
        phone_number=normalized_phone_number,
        scheme_name=scheme_name,
        verify_code=code_text,
    )
    response = _call_with_failover(cfg, "check_sms_verify_code_with_options", request_obj)
    body = getattr(response, "body", None)
    if not body or not _is_success_code(getattr(body, "code", "")):
        ticket.verify_attempt_count += 1
        ticket.save(update_fields=["verify_attempt_count", "updated_at"])
        message = getattr(body, "message", "") or "验证码校验失败。"
        raise PhoneVerificationProviderError(message)

    model = getattr(body, "model", None)
    verify_result = str(getattr(model, "verify_result", "") or "").strip().upper()
    payload = _build_response_payload(body)
    now = timezone.now()
    if not _is_passed(verify_result):
        ticket.verify_attempt_count += 1
        ticket.save(update_fields=["verify_attempt_count", "updated_at"])
        raise ValidationError({"verify_code": ["Verification code is incorrect or expired."]})

    verification = _update_phone_verification(
        user=ticket.user,
        status=PhoneVerification.Status.VERIFIED,
        country_code=normalized_country_code,
        phone_number=normalized_phone_number,
        provider="aliyun_pnvs",
        provider_out_id=str(payload.get("out_id") or ticket.provider_out_id or ""),
        provider_biz_id=str(payload.get("biz_id") or ticket.provider_biz_id or ""),
        provider_request_id=str(payload.get("request_id") or ticket.provider_request_id or ""),
        provider_status_message=str(getattr(body, "message", "") or "")[:300],
        provider_result=payload,
        provider_started_at=ticket.created_at,
        provider_checked_at=now,
        provider_expires_at=ticket.expires_at,
        submitted_at=ticket.created_at,
        verified_at=now,
        revoked_at=None,
        review_note="短信验证码校验通过。",
    )
    ticket.mark_consumed()
    return verification
