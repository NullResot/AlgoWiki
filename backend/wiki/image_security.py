from __future__ import annotations

import io
import json
import warnings
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from django.conf import settings
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.utils import timezone
from PIL import Image, ImageOps, UnidentifiedImageError

from .security import get_client_ip


SUPPORTED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}
FORMAT_TO_EXTENSION = {
    "JPEG": ".jpg",
    "PNG": ".png",
    "WEBP": ".webp",
}
FORMAT_TO_CONTENT_TYPE = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}
SAFE_LABELS = {"nonlabel", "safe", "normal", "clean", "ok", "approved"}
MANUAL_LABEL_MARKERS = {
    "review",
    "manual",
    "uncertain",
    "suspicious",
    "unknown",
    "low_quality",
    "quality",
    "borderline",
}
REJECT_LABEL_MARKERS = {
    "porn",
    "sexual",
    "nude",
    "nudity",
    "violence",
    "violent",
    "blood",
    "gore",
    "weapon",
    "gun",
    "knife",
    "terror",
    "political",
    "illegal",
    "abuse",
    "harass",
    "harassment",
    "spam",
    "ads",
    "advert",
    "drug",
    "fraud",
    "malware",
    "scam",
}


@dataclass(slots=True)
class NormalizedImageUpload:
    original_name: str
    content_type: str
    size_bytes: int
    width: int
    height: int
    format: str
    extension: str
    file: ContentFile


@dataclass(slots=True)
class ImageDerivative:
    content_type: str
    size_bytes: int
    width: int
    height: int
    format: str
    extension: str
    file: ContentFile


@dataclass(slots=True)
class ImageModerationResult:
    provider: str
    decision: str
    risk_level: str = "unknown"
    categories: list[str] = field(default_factory=list)
    summary: str = ""
    user_notice: str = ""
    raw_response: dict[str, Any] = field(default_factory=dict)
    error_message: str = ""


def _setting(name: str, default):
    return getattr(settings, name, default)


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _plain_value(value: Any):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _plain_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_plain_value(item) for item in value]
    if isinstance(value, tuple):
        return [_plain_value(item) for item in value]
    if hasattr(value, "__dict__"):
        payload = {
            key: item
            for key, item in vars(value).items()
            if not key.startswith("_")
        }
        if payload:
            return {key: _plain_value(item) for key, item in payload.items()}
    return str(value)


def _response_value(value: Any, *names: str, default: Any = ""):
    if isinstance(value, dict):
        for name in names:
            if name in value and value[name] is not None:
                return value[name]
    for name in names:
        if hasattr(value, name):
            item = getattr(value, name)
            if item is not None:
                return item
    return default


def _response_items(value: Any):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, dict):
        for key in ("Result", "result", "items", "Items"):
            item = value.get(key)
            if isinstance(item, list):
                return item
            if isinstance(item, dict):
                return [item]
        return []
    for name in ("Result", "result", "items", "Items"):
        item = getattr(value, name, None)
        if isinstance(item, list):
            return item
        if isinstance(item, dict):
            return [item]
    return []


def _image_format_and_extension(image: Image.Image) -> tuple[str, str, str]:
    detected = str(image.format or "").upper()
    if detected not in SUPPORTED_IMAGE_FORMATS:
        raise ValueError("仅支持 JPG、PNG、WebP 图片。")
    return detected, FORMAT_TO_EXTENSION[detected], FORMAT_TO_CONTENT_TYPE[detected]


def _needs_alpha(image: Image.Image) -> bool:
    if image.mode in {"RGBA", "LA"}:
        return True
    transparency = image.info.get("transparency")
    return transparency is not None


def normalize_uploaded_image(
    uploaded_file,
    *,
    allowed_extensions: set[str],
    allowed_content_types: set[str],
    max_bytes: int,
    max_pixels: int,
    max_width: int,
    max_height: int,
) -> NormalizedImageUpload:
    original_name = Path(getattr(uploaded_file, "name", "") or "image").name[:255]
    suffix = Path(original_name).suffix.lower()
    if allowed_extensions and suffix not in allowed_extensions:
        raise ValueError("仅支持 JPG、PNG、WebP 图片。")

    content_type = _normalize_text(getattr(uploaded_file, "content_type", "")).lower()
    if content_type and allowed_content_types and content_type not in allowed_content_types:
        raise ValueError("图片内容类型不在允许范围内。")

    size_bytes = int(getattr(uploaded_file, "size", 0) or 0)
    if size_bytes <= 0:
        raise ValueError("图片文件不能为空。")
    if max_bytes > 0 and size_bytes > max_bytes:
        limit_mb = max_bytes / 1024 / 1024
        raise ValueError(f"单张图片不能超过 {limit_mb:.1f}MB。")

    try:
        uploaded_file.seek(0)
    except Exception:
        pass

    normalized_width = 0
    normalized_height = 0
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(uploaded_file) as image:
                image.load()
                if getattr(image, "is_animated", False) or getattr(image, "n_frames", 1) > 1:
                    raise ValueError("不允许上传动图。")
                width, height = image.size
                if width <= 0 or height <= 0:
                    raise ValueError("图片尺寸无效。")
                if max_pixels > 0 and width * height > max_pixels:
                    raise ValueError("图片像素过大。")

                output_format, extension, output_content_type = _image_format_and_extension(image)
                image = ImageOps.exif_transpose(image)

                over_width = max_width > 0 and image.width > max_width
                over_height = max_height > 0 and image.height > max_height
                if over_width or over_height:
                    image.thumbnail((max_width or image.width, max_height or image.height), Image.Resampling.LANCZOS)

                if output_format == "JPEG":
                    if image.mode not in {"RGB", "L"}:
                        image = image.convert("RGB")
                    save_kwargs = {
                        "format": "JPEG",
                        "quality": 88,
                        "optimize": True,
                        "progressive": True,
                    }
                elif output_format == "PNG":
                    if image.mode not in {"RGB", "RGBA", "P", "L", "LA"}:
                        image = image.convert("RGBA" if _needs_alpha(image) else "RGB")
                    save_kwargs = {
                        "format": "PNG",
                        "optimize": True,
                    }
                else:
                    if image.mode not in {"RGB", "RGBA", "L", "LA"}:
                        image = image.convert("RGBA" if _needs_alpha(image) else "RGB")
                    save_kwargs = {
                        "format": "WEBP",
                        "quality": 88,
                        "method": 6,
                    }

                buffer = io.BytesIO()
                image.save(buffer, **save_kwargs)
                normalized_bytes = buffer.getvalue()
                normalized_width = image.width
                normalized_height = image.height
    except UnidentifiedImageError as exc:
        raise ValueError("不是有效的图片文件。") from exc
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError("图片像素过大。") from exc
    except OSError as exc:
        raise ValueError("图片文件损坏或无法处理。") from exc

    if max_bytes > 0 and len(normalized_bytes) > max_bytes:
        limit_mb = max_bytes / 1024 / 1024
        raise ValueError(f"处理后的图片仍然超过 {limit_mb:.1f}MB。")

    normalized_name = f"{Path(original_name).stem or 'image'}{extension}"
    return NormalizedImageUpload(
        original_name=original_name,
        content_type=output_content_type,
        size_bytes=len(normalized_bytes),
        width=normalized_width,
        height=normalized_height,
        format=output_format,
        extension=extension,
        file=ContentFile(normalized_bytes, name=normalized_name),
    )


def normalize_uploaded_avatar(
    uploaded_file,
    *,
    allowed_extensions: set[str],
    allowed_content_types: set[str],
    max_bytes: int,
    output_size: int = 256,
    max_output_bytes: int = 96 * 1024,
) -> NormalizedImageUpload:
    original_name = Path(getattr(uploaded_file, "name", "") or "avatar").name[:255]
    suffix = Path(original_name).suffix.lower()
    if allowed_extensions and suffix not in allowed_extensions:
        raise ValueError("仅支持 JPG、PNG、WebP 头像。")

    content_type = _normalize_text(getattr(uploaded_file, "content_type", "")).lower()
    if content_type and allowed_content_types and content_type not in allowed_content_types:
        raise ValueError("头像图片类型不在允许范围内。")

    size_bytes = int(getattr(uploaded_file, "size", 0) or 0)
    if size_bytes <= 0:
        raise ValueError("头像文件不能为空。")
    if max_bytes > 0 and size_bytes > max_bytes:
        limit_mb = max_bytes / 1024 / 1024
        raise ValueError(f"头像图片不能超过 {limit_mb:.1f}MB。")

    try:
        uploaded_file.seek(0)
    except Exception:
        pass

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(uploaded_file) as image:
                image.load()
                if getattr(image, "is_animated", False) or getattr(image, "n_frames", 1) > 1:
                    raise ValueError("不允许上传动图头像。")
                if image.width <= 0 or image.height <= 0:
                    raise ValueError("头像图片尺寸无效。")
                if image.width * image.height > 8 * 1024 * 1024:
                    raise ValueError("头像图片像素过大。")

                _image_format_and_extension(image)
                image = ImageOps.exif_transpose(image)
                image = ImageOps.fit(
                    image,
                    (int(output_size), int(output_size)),
                    Image.Resampling.LANCZOS,
                    centering=(0.5, 0.5),
                )
                if image.mode not in {"RGB", "RGBA", "L", "LA"}:
                    image = image.convert("RGBA" if _needs_alpha(image) else "RGB")

                normalized_bytes = b""
                for quality in (82, 74, 66, 58, 50):
                    buffer = io.BytesIO()
                    image.save(buffer, format="WEBP", quality=quality, method=6)
                    normalized_bytes = buffer.getvalue()
                    if not max_output_bytes or len(normalized_bytes) <= max_output_bytes:
                        break
    except UnidentifiedImageError as exc:
        raise ValueError("不是有效的头像图片。") from exc
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError("头像图片像素过大。") from exc
    except OSError as exc:
        raise ValueError("头像图片损坏或无法处理。") from exc

    if max_output_bytes > 0 and len(normalized_bytes) > max_output_bytes:
        limit_kb = max_output_bytes / 1024
        raise ValueError(f"处理后的头像仍然超过 {limit_kb:.0f}KB。")

    normalized_name = f"{Path(original_name).stem or 'avatar'}.webp"
    return NormalizedImageUpload(
        original_name=original_name,
        content_type="image/webp",
        size_bytes=len(normalized_bytes),
        width=int(output_size),
        height=int(output_size),
        format="WEBP",
        extension=".webp",
        file=ContentFile(normalized_bytes, name=normalized_name),
    )


def build_webp_thumbnail(
    source_file,
    *,
    original_name: str = "",
    max_side: int = 480,
    max_bytes: int = 180 * 1024,
) -> ImageDerivative:
    max_side = max(96, int(max_side or 480))
    max_bytes = max(0, int(max_bytes or 0))
    best_bytes = b""
    best_width = 0
    best_height = 0
    try:
        source_file.seek(0)
    except Exception:
        pass

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(source_file) as image:
                image.load()
                if getattr(image, "is_animated", False) or getattr(image, "n_frames", 1) > 1:
                    raise ValueError("Animated images are not supported.")
                if image.width <= 0 or image.height <= 0:
                    raise ValueError("Invalid image dimensions.")

                image = ImageOps.exif_transpose(image)
                if image.mode not in {"RGB", "RGBA", "L", "LA"}:
                    image = image.convert("RGBA" if _needs_alpha(image) else "RGB")

                side_candidates = []
                for side in (max_side, 420, 360, 300, 240, 180):
                    side = min(int(side), max_side)
                    if side >= 96 and side not in side_candidates:
                        side_candidates.append(side)

                for side in side_candidates:
                    candidate = image.copy()
                    candidate.thumbnail((side, side), Image.Resampling.LANCZOS)
                    for quality in (78, 70, 62, 54, 46, 38):
                        buffer = io.BytesIO()
                        candidate.save(buffer, format="WEBP", quality=quality, method=6)
                        payload = buffer.getvalue()
                        if not best_bytes or len(payload) < len(best_bytes):
                            best_bytes = payload
                            best_width = candidate.width
                            best_height = candidate.height
                        if not max_bytes or len(payload) <= max_bytes:
                            stem = Path(original_name or getattr(source_file, "name", "") or "image").stem or "image"
                            return ImageDerivative(
                                content_type="image/webp",
                                size_bytes=len(payload),
                                width=candidate.width,
                                height=candidate.height,
                                format="WEBP",
                                extension=".webp",
                                file=ContentFile(payload, name=f"{stem}-thumb.webp"),
                            )
    except UnidentifiedImageError as exc:
        raise ValueError("Invalid image file.") from exc
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError("Image dimensions are too large.") from exc
    except OSError as exc:
        raise ValueError("Image file is corrupted or cannot be processed.") from exc
    finally:
        try:
            source_file.seek(0)
        except Exception:
            pass

    if not best_bytes:
        raise ValueError("Image thumbnail could not be generated.")
    stem = Path(original_name or getattr(source_file, "name", "") or "image").stem or "image"
    return ImageDerivative(
        content_type="image/webp",
        size_bytes=len(best_bytes),
        width=best_width,
        height=best_height,
        format="WEBP",
        extension=".webp",
        file=ContentFile(best_bytes, name=f"{stem}-thumb.webp"),
    )


def _format_time_wait(seconds: int) -> str:
    seconds = max(1, int(seconds or 1))
    if seconds >= 60:
        minutes = max(1, round(seconds / 60))
        return f"{minutes} 分钟"
    return f"{seconds} 秒"


def _check_cache_window_limit(
    *,
    key: str,
    amount: int,
    limit: int,
    window_seconds: int,
    exceeded_message: str,
) -> None:
    if amount <= 0 or limit <= 0 or window_seconds <= 0:
        return
    now = timezone.now()
    state = cache.get(key)
    if not isinstance(state, dict):
        state = {}
    window_start = float(state.get("window_start") or now.timestamp())
    used = int(state.get("count") or 0)
    elapsed = now.timestamp() - window_start
    if elapsed >= window_seconds:
        window_start = now.timestamp()
        used = 0
        elapsed = 0
    if used + amount > limit:
        wait = window_seconds - int(elapsed)
        raise ValueError(f"{exceeded_message} Try again in {_format_time_wait(wait)}.")
    cache.set(
        key,
        {"window_start": window_start, "count": used + amount},
        timeout=window_seconds,
    )


def enforce_image_upload_rate_limit(
    *,
    request,
    user,
    purpose: str,
    upload_count: int,
    upload_bytes: int = 0,
    model_cls=None,
    burst_limit: int | None = None,
    burst_window_seconds: int | None = None,
    min_interval_seconds: int | None = None,
    hourly_limit: int | None = None,
    daily_limit: int | None = None,
    ip_hourly_limit: int | None = None,
    ip_daily_limit: int | None = None,
    ip_hourly_bytes: int | None = None,
    ip_daily_bytes: int | None = None,
) -> None:
    now = timezone.now()
    user_key = getattr(user, "pk", None) or "anon"
    ip_key = get_client_ip(request) or "unknown"
    scope = f"image-upload:{purpose}:{user_key}:{ip_key}"

    burst_limit = int(
        burst_limit if burst_limit is not None else _setting("IMAGE_UPLOAD_BURST_LIMIT", 3)
    )
    burst_window_seconds = int(
        burst_window_seconds
        if burst_window_seconds is not None
        else _setting("IMAGE_UPLOAD_BURST_WINDOW_SECONDS", 60)
    )
    min_interval_seconds = int(
        min_interval_seconds
        if min_interval_seconds is not None
        else _setting("IMAGE_UPLOAD_MIN_INTERVAL_SECONDS", 10)
    )
    hourly_limit = int(
        hourly_limit if hourly_limit is not None else _setting("IMAGE_UPLOAD_HOURLY_LIMIT", 30)
    )
    daily_limit = int(
        daily_limit if daily_limit is not None else _setting("IMAGE_UPLOAD_DAILY_LIMIT", 100)
    )
    ip_hourly_limit = int(
        ip_hourly_limit
        if ip_hourly_limit is not None
        else _setting("IMAGE_UPLOAD_IP_HOURLY_LIMIT", 120)
    )
    ip_daily_limit = int(
        ip_daily_limit
        if ip_daily_limit is not None
        else _setting("IMAGE_UPLOAD_IP_DAILY_LIMIT", 400)
    )
    ip_hourly_bytes = int(
        ip_hourly_bytes
        if ip_hourly_bytes is not None
        else _setting("IMAGE_UPLOAD_IP_HOURLY_BYTES", 128 * 1024 * 1024)
    )
    ip_daily_bytes = int(
        ip_daily_bytes
        if ip_daily_bytes is not None
        else _setting("IMAGE_UPLOAD_IP_DAILY_BYTES", 512 * 1024 * 1024)
    )

    burst_key = f"{scope}:burst"
    burst_state = cache.get(burst_key)
    if not isinstance(burst_state, dict):
        burst_state = {}
    window_start = float(burst_state.get("window_start") or now.timestamp())
    count = int(burst_state.get("count") or 0)
    if now.timestamp() - window_start >= burst_window_seconds:
        window_start = now.timestamp()
        count = 0
    if count + upload_count > burst_limit:
        wait = burst_window_seconds - int(now.timestamp() - window_start)
        raise ValueError(f"上传过快，请等待 {_format_time_wait(wait)} 后再试。")
    burst_state = {
        "window_start": window_start,
        "count": count + upload_count,
    }
    cache.set(burst_key, burst_state, timeout=burst_window_seconds)

    last_key = f"{scope}:last"
    last_ts = cache.get(last_key)
    if last_ts is not None:
        try:
            last_ts = float(last_ts)
        except (TypeError, ValueError):
            last_ts = None
    if last_ts is not None and now.timestamp() - last_ts < min_interval_seconds:
        wait = min_interval_seconds - int(now.timestamp() - last_ts)
        raise ValueError(f"上传过于频繁，请等待 {_format_time_wait(wait)}。")
    cache.set(last_key, now.timestamp(), timeout=max(min_interval_seconds * 2, 60))

    ip_scope = f"image-upload-ip:{purpose}:{ip_key}"
    _check_cache_window_limit(
        key=f"{ip_scope}:count:hour",
        amount=int(upload_count or 0),
        limit=ip_hourly_limit,
        window_seconds=3600,
        exceeded_message="Too many image uploads from this network.",
    )
    _check_cache_window_limit(
        key=f"{ip_scope}:count:day",
        amount=int(upload_count or 0),
        limit=ip_daily_limit,
        window_seconds=86400,
        exceeded_message="Too many image uploads from this network.",
    )
    _check_cache_window_limit(
        key=f"{ip_scope}:bytes:hour",
        amount=int(upload_bytes or 0),
        limit=ip_hourly_bytes,
        window_seconds=3600,
        exceeded_message="Image upload traffic from this network is too high.",
    )
    _check_cache_window_limit(
        key=f"{ip_scope}:bytes:day",
        amount=int(upload_bytes or 0),
        limit=ip_daily_bytes,
        window_seconds=86400,
        exceeded_message="Daily image upload traffic from this network is too high.",
    )

    if model_cls is None or not hourly_limit and not daily_limit:
        return

    hour_cutoff = now - timedelta(hours=1)
    day_cutoff = now - timedelta(days=1)
    base_queryset = model_cls.objects.filter(uploaded_by=user)
    if hourly_limit > 0:
        hourly_count = base_queryset.filter(created_at__gte=hour_cutoff).count()
        if hourly_count + upload_count > hourly_limit:
            raise ValueError("最近一小时图片上传次数过多，请稍后再试。")
    if daily_limit > 0:
        daily_count = base_queryset.filter(created_at__gte=day_cutoff).count()
        if daily_count + upload_count > daily_limit:
            raise ValueError("今日图片上传次数已达上限。")


def _load_aliyun_green_sdk():
    from alibabacloud_green20220302.client import Client as GreenClient
    from alibabacloud_green20220302 import models as green_models
    from alibabacloud_tea_openapi import models as open_api_models
    from alibabacloud_tea_util import models as util_models

    return GreenClient, green_models, open_api_models, util_models


def _aliyun_green_config() -> dict[str, Any]:
    return getattr(settings, "ALIYUN_IMAGE_MODERATION", {}) or {}


def aliyun_green_image_moderation_is_configured() -> bool:
    cfg = _aliyun_green_config()
    return bool(
        cfg.get("ENABLED")
        and cfg.get("ACCESS_KEY_ID")
        and cfg.get("ACCESS_KEY_SECRET")
        and cfg.get("ENDPOINTS")
    )


def _aliyun_runtime_options(cfg: dict[str, Any], util_models):
    timeout = max(1, int(cfg.get("TIMEOUT_SECONDS") or 15)) * 1000
    return util_models.RuntimeOptions(connect_timeout=timeout, read_timeout=timeout)


def _classify_aliyun_image_result(labels: list[str], risk_level: str, suggestions: list[str]):
    normalized_labels = [str(item or "").strip().lower() for item in labels if str(item or "").strip()]
    normalized_suggestions = [
        str(item or "").strip().lower()
        for item in suggestions
        if str(item or "").strip()
    ]
    risk = str(risk_level or "").strip().lower()

    if any(marker in risk for marker in {"reject", "block", "high", "danger"}):
        return "reject"
    if any(
        any(marker in label for marker in REJECT_LABEL_MARKERS)
        for label in normalized_labels
    ):
        return "reject"
    if any(suggestion in {"reject", "block"} for suggestion in normalized_suggestions):
        return "reject"

    if not normalized_labels or all(label in SAFE_LABELS for label in normalized_labels):
        return "approve"

    if risk in {"review", "manual", "suspicious", "medium"}:
        return "manual"
    if any(any(marker in label for marker in MANUAL_LABEL_MARKERS) for label in normalized_labels):
        return "manual"
    if any(suggestion in {"review", "manual"} for suggestion in normalized_suggestions):
        return "manual"
    return "manual"


def _summarize_aliyun_result(decision: str, labels: list[str], risk_level: str) -> str:
    label_text = ", ".join(labels[:5]) if labels else "nonLabel"
    if decision == "approve":
        return "阿里云图片审核通过。"
    if decision == "reject":
        return f"阿里云图片审核拒绝：{label_text}"
    if risk_level and risk_level != "unknown":
        return f"阿里云图片审核需要人工复核：{label_text}（{risk_level}）"
    return f"阿里云图片审核需要人工复核：{label_text}"


def _moderate_with_aliyun(image_url: str, *, data_id: str) -> ImageModerationResult:
    cfg = _aliyun_green_config()
    GreenClient, green_models, open_api_models, util_models = _load_aliyun_green_sdk()
    endpoints = [
        str(item).strip()
        for item in cfg.get("ENDPOINTS") or []
        if str(item).strip()
    ]
    last_error: Exception | None = None
    for endpoint in endpoints:
        try:
            client = GreenClient(
                open_api_models.Config(
                    access_key_id=str(cfg.get("ACCESS_KEY_ID") or ""),
                    access_key_secret=str(cfg.get("ACCESS_KEY_SECRET") or ""),
                    endpoint=endpoint,
                )
            )
            request = green_models.ImageModerationRequest(
                service="baselineCheck",
                service_parameters=json.dumps(
                    {
                        "imageUrl": image_url,
                        "dataId": data_id or str(uuid4()),
                    },
                    ensure_ascii=False,
                ),
            )
            runtime = _aliyun_runtime_options(cfg, util_models)
            response = client.image_moderation_with_options(request, runtime)
            body = _plain_value(getattr(response, "body", response))
            code = _response_value(body, "code", "Code", default=0)
            message = _response_value(body, "msg", "Msg", default="")
            data = _response_value(body, "data", "Data", default={})
            results = _response_items(_response_value(data, "result", "Result", default=[]))

            labels: list[str] = []
            suggestions: list[str] = []
            risk_level = _normalize_text(
                _response_value(data, "riskLevel", "risk_level", "RiskLevel", default="")
            ).lower()
            for item in results:
                label = _normalize_text(
                    _response_value(item, "Label", "label", "name", default="")
                )
                sub_label = _normalize_text(
                    _response_value(item, "SubLabel", "subLabel", "sub_label", default="")
                )
                suggestion = _normalize_text(
                    _response_value(item, "Suggestion", "suggestion", "action", default="")
                )
                item_risk = _normalize_text(
                    _response_value(item, "RiskLevel", "riskLevel", "risk_level", default="")
                ).lower()
                if label:
                    labels.append(label)
                if sub_label:
                    labels.append(sub_label)
                if suggestion:
                    suggestions.append(suggestion)
                if item_risk and not risk_level:
                    risk_level = item_risk

            if int(code or 0) != 200:
                raise RuntimeError(message or f"Aliyun image moderation returned code {code}.")

            decision = _classify_aliyun_image_result(labels, risk_level, suggestions)
            summary = _summarize_aliyun_result(decision, labels, risk_level)
            raw_response = {
                "endpoint": endpoint,
                "code": code,
                "message": message,
                "data": _plain_value(data),
                "results": _plain_value(results),
            }
            return ImageModerationResult(
                provider="aliyun_green",
                decision=decision,
                risk_level=risk_level or ("safe" if decision == "approve" else "manual"),
                categories=[str(item or "").strip() for item in labels[:10]],
                summary=summary,
                raw_response=raw_response,
            )
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"阿里云图片审核调用失败：{last_error}") from last_error


def moderate_image_url(image_url: str, *, data_id: str = "") -> ImageModerationResult:
    provider = _normalize_text(_setting("IMAGE_MODERATION_PROVIDER", "disabled")).lower() or "disabled"
    if provider in {"disabled", "off", "false", "0", "none"}:
        return ImageModerationResult(
            provider="disabled",
            decision="manual",
            risk_level="unknown",
            summary="图像内容审核未启用。",
        )
    if provider in {"aliyun", "aliyun_green", "green"}:
        if not aliyun_green_image_moderation_is_configured():
            return ImageModerationResult(
                provider="aliyun_green",
                decision="manual",
                risk_level="unknown",
                summary="阿里云图片审核未配置完成。",
            )
        try:
            return _moderate_with_aliyun(image_url, data_id=data_id)
        except ImportError as exc:
            return ImageModerationResult(
                provider="aliyun_green",
                decision="manual",
                risk_level="unknown",
                summary="阿里云图片审核 SDK 未安装。",
                error_message=str(exc),
            )
        except Exception as exc:
            return ImageModerationResult(
                provider="aliyun_green",
                decision="manual",
                risk_level="unknown",
                summary="阿里云图片审核暂时不可用。",
                error_message=str(exc),
            )
    return ImageModerationResult(
        provider=provider,
        decision="manual",
        risk_level="unknown",
        summary="图像内容审核未启用。",
    )


def resolve_moderation_status(result: ImageModerationResult, *, actor_is_manager: bool) -> tuple[str, str]:
    if result.decision == "reject":
        return "rejected", result.summary or "图片未通过审核。"
    if result.decision == "approve":
        return "approved", result.summary or "图片审核通过。"
    if actor_is_manager:
        note = result.summary or "管理员已确认上传。"
        return "approved", note
    note = result.summary or "等待人工图片审核。"
    return "pending", note
