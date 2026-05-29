import json
import secrets
from datetime import timedelta
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from uuid import uuid4

from django.conf import settings
from django.utils import timezone

from alibabacloud_cloudauth20190307.client import Client as CloudauthClient
from alibabacloud_cloudauth20190307 import models as cloudauth_models
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_tea_util import models as util_models

from .models import RealNameVerification


class RealNameProviderError(Exception):
    def __init__(self, message: str, *, status_code: int = 502):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _config() -> dict[str, Any]:
    return getattr(settings, "ALIYUN_IDVERIFY", {}) or {}


def aliyun_real_name_is_configured() -> bool:
    cfg = _config()
    return bool(
        cfg.get("ENABLED")
        and cfg.get("ACCESS_KEY_ID")
        and cfg.get("ACCESS_KEY_SECRET")
        and cfg.get("SCENE_ID")
        and cfg.get("ENDPOINTS")
    )


def _require_config() -> dict[str, Any]:
    cfg = _config()
    if not cfg.get("ENABLED"):
        raise RealNameProviderError("实名认证服务尚未开启。", status_code=503)
    missing = [
        key
        for key in ("ACCESS_KEY_ID", "ACCESS_KEY_SECRET", "SCENE_ID", "ENDPOINTS")
        if not cfg.get(key)
    ]
    if missing:
        raise RealNameProviderError(
            f"实名认证服务配置不完整：{', '.join(missing)}。",
            status_code=503,
        )
    try:
        int(str(cfg["SCENE_ID"]).strip())
    except (TypeError, ValueError) as exc:
        raise RealNameProviderError("实名认证 Scene ID 配置无效。", status_code=503) from exc
    return cfg


def _timeout_ms(cfg: dict[str, Any]) -> int:
    return max(1, int(cfg.get("TIMEOUT_SECONDS") or 15)) * 1000


def _client(cfg: dict[str, Any], endpoint: str) -> CloudauthClient:
    return CloudauthClient(
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
        except Exception as exc:  # SDK exceptions vary by transport and provider response.
            last_error = exc
    if last_error:
        raise RealNameProviderError(f"实名认证服务调用失败：{last_error}") from last_error
    raise RealNameProviderError("实名认证服务没有可用 endpoint。", status_code=503)


def _append_query(url: str, **params: str) -> str:
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    for key, value in params.items():
        if value:
            query[key] = value
    return urlunparse(parsed._replace(query=urlencode(query)))


def _build_return_url(request) -> str:
    configured = str(_config().get("RETURN_URL") or "").strip()
    if configured:
        return _append_query(configured, real_name_return="1")
    if request is None:
        raise RealNameProviderError("缺少实名认证回跳地址。", status_code=503)
    return request.build_absolute_uri("/moments?real_name_return=1")


def _request_ip(request) -> str:
    if request is None:
        return ""
    forwarded = str(request.META.get("HTTP_X_FORWARDED_FOR") or "").split(",", 1)[0].strip()
    return forwarded or str(request.META.get("REMOTE_ADDR") or "").strip()


def _meta_info_to_string(value) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return ""


def mask_real_name(value: str) -> str:
    name = str(value or "").strip()
    if not name:
        return ""
    if len(name) <= 2:
        return f"{name[:1]}*"
    return f"{name[:1]}{'*' * (len(name) - 2)}{name[-1:]}"


def _safe_body_map(body) -> dict[str, Any]:
    if not body:
        return {}
    return {
        "request_id": getattr(body, "request_id", "") or "",
        "code": getattr(body, "code", "") or "",
        "message": getattr(body, "message", "") or "",
    }


def _safe_describe_result(body) -> dict[str, Any]:
    result = getattr(body, "result_object", None)
    payload = _safe_body_map(body)
    if not result:
        return payload
    payload.update(
        {
            "success": getattr(result, "success", "") or "",
            "passed": getattr(result, "passed", "") or "",
            "sub_code": getattr(result, "sub_code", "") or "",
            "device_risk": getattr(result, "device_risk", "") or "",
        }
    )
    return payload


def _is_success_code(value: str) -> bool:
    return str(value or "").strip() in {"200", "OK", "Success"}


def _is_passed(value: str) -> bool | None:
    normalized = str(value or "").strip().lower()
    if normalized in {"t", "true", "y", "yes", "1", "pass", "passed"}:
        return True
    if normalized in {"f", "false", "n", "no", "0", "fail", "failed"}:
        return False
    return None


def start_aliyun_real_name_verification(
    *,
    user,
    real_name: str,
    id_number: str,
    meta_info,
    certify_url_type: str,
    request,
) -> tuple[RealNameVerification, dict[str, Any]]:
    cfg = _require_config()
    meta_info_text = _meta_info_to_string(meta_info)
    if not meta_info_text:
        raise RealNameProviderError("缺少浏览器实名认证环境信息，请刷新页面后重试。", status_code=400)

    url_type = str(certify_url_type or cfg.get("CERTIFY_URL_TYPE") or "H5").strip().upper()
    if url_type not in {"H5", "WEB"}:
        url_type = str(cfg.get("CERTIFY_URL_TYPE") or "H5").strip().upper()
    if url_type not in {"H5", "WEB"}:
        url_type = "H5"

    scene_id = int(str(cfg["SCENE_ID"]).strip())
    outer_order_no = uuid4().hex
    callback_token = secrets.token_urlsafe(32)[:80]
    return_url = _build_return_url(request)
    callback_url = str(cfg.get("CALLBACK_URL") or "").strip()
    request_obj = cloudauth_models.InitFaceVerifyRequest(
        scene_id=scene_id,
        outer_order_no=outer_order_no,
        product_code=str(cfg.get("PRODUCT_CODE") or "ID_PRO"),
        model=str(cfg.get("MODEL") or "MOVE_ACTION"),
        cert_type=str(cfg.get("CERT_TYPE") or "IDENTITY_CARD"),
        cert_name=real_name,
        cert_no=id_number,
        meta_info=meta_info_text,
        return_url=return_url,
        callback_url=callback_url or None,
        callback_token=callback_token if callback_url else None,
        certify_url_type=url_type,
        certify_url_style=str(cfg.get("CERTIFY_URL_STYLE") or "") or None,
        procedure_priority=str(cfg.get("PROCEDURE_PRIORITY") or "url"),
        user_id=str(user.id),
        ip=_request_ip(request),
    )
    response = _call_with_failover(cfg, "init_face_verify_with_options", request_obj)
    body = getattr(response, "body", None)
    result = getattr(body, "result_object", None)
    if not body or not _is_success_code(getattr(body, "code", "")):
        message = getattr(body, "message", "") or "实名认证初始化失败。"
        raise RealNameProviderError(message)
    certify_id = str(getattr(result, "certify_id", "") or "").strip()
    certify_url = str(getattr(result, "certify_url", "") or "").strip()
    if not certify_id or not certify_url:
        raise RealNameProviderError("实名认证服务未返回认证链接，请稍后重试。")

    now = timezone.now()
    instance, _ = RealNameVerification.objects.get_or_create(user=user)
    instance.status = RealNameVerification.Status.PENDING
    instance.real_name_masked = mask_real_name(real_name)[:40]
    instance.id_number_last4 = str(id_number or "")[-4:]
    instance.provider = "aliyun"
    instance.provider_trace_id = certify_id
    instance.provider_order_no = outer_order_no
    instance.provider_certify_id = certify_id
    instance.provider_scene_id = str(scene_id)
    instance.provider_sub_code = ""
    instance.provider_status_message = str(getattr(body, "message", "") or "")[:300]
    instance.provider_device_risk = ""
    instance.provider_result = _safe_body_map(body)
    instance.provider_callback_token = callback_token if callback_url else ""
    instance.provider_started_at = now
    instance.provider_checked_at = None
    instance.provider_expires_at = now + timedelta(minutes=30)
    instance.submitted_at = now
    instance.verified_at = None
    instance.revoked_at = None
    instance.reviewer = None
    instance.review_note = "已发起阿里云金融级实人认证，等待用户完成认证并回查结果。"
    instance.save()
    return instance, {
        "certify_id": certify_id,
        "certify_url": certify_url,
        "expires_at": instance.provider_expires_at,
    }


def sync_aliyun_real_name_verification(instance: RealNameVerification) -> RealNameVerification:
    cfg = _require_config()
    certify_id = str(instance.provider_certify_id or instance.provider_trace_id or "").strip()
    if not certify_id:
        raise RealNameProviderError("该实名记录没有第三方认证流水。", status_code=400)
    scene_id = int(str(cfg["SCENE_ID"]).strip())
    request_obj = cloudauth_models.DescribeFaceVerifyRequest(
        scene_id=scene_id,
        certify_id=certify_id,
        picture_return_type="0",
    )
    response = _call_with_failover(cfg, "describe_face_verify_with_options", request_obj)
    body = getattr(response, "body", None)
    if not body or not _is_success_code(getattr(body, "code", "")):
        message = getattr(body, "message", "") or "实名认证结果查询失败。"
        raise RealNameProviderError(message)

    result_payload = _safe_describe_result(body)
    passed = _is_passed(result_payload.get("passed"))
    now = timezone.now()
    instance.provider = "aliyun"
    instance.provider_trace_id = certify_id
    instance.provider_certify_id = certify_id
    instance.provider_scene_id = str(scene_id)
    instance.provider_sub_code = str(result_payload.get("sub_code") or "")[:80]
    instance.provider_status_message = str(result_payload.get("message") or "")[:300]
    instance.provider_device_risk = str(result_payload.get("device_risk") or "")[:120]
    instance.provider_result = result_payload
    instance.provider_checked_at = now

    if passed is True:
        instance.status = RealNameVerification.Status.VERIFIED
        instance.verified_at = now
        instance.revoked_at = None
        instance.review_note = "阿里云金融级实人认证通过。"
    elif passed is False:
        instance.status = RealNameVerification.Status.REJECTED
        instance.verified_at = None
        instance.review_note = (
            f"阿里云金融级实人认证未通过：{instance.provider_sub_code or instance.provider_status_message or '未通过'}"
        )[:300]
    else:
        instance.status = RealNameVerification.Status.PENDING
        instance.review_note = "阿里云金融级实人认证尚未完成，请完成认证后刷新状态。"

    instance.save()
    return instance
