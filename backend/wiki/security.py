import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.utils import timezone

from .models import LoginAttempt, PasswordHistory, SecurityAuditLog

security_logger = logging.getLogger("algowiki.security")


def get_security_value(key: str, default):
    values = getattr(settings, "AUTH_SECURITY", {}) or {}
    return values.get(key, default)


def get_client_ip(request):
    if not request:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    remote = request.META.get("REMOTE_ADDR", "")
    return remote.strip() or None


def _build_attempt_key(username: str, ip_address: str | None):
    identity = (username or "").strip().lower() or "<empty>"
    ip = (ip_address or "").strip().lower() or "-"
    return f"{identity}|{ip}", identity


def check_login_locked(username: str, ip_address: str | None):
    key, _ = _build_attempt_key(username, ip_address)
    attempt = LoginAttempt.objects.filter(key=key).first()
    if not attempt:
        return False, 0

    now = timezone.now()
    if attempt.locked_until and attempt.locked_until > now:
        wait_seconds = int((attempt.locked_until - now).total_seconds())
        return True, max(wait_seconds, 1)

    if attempt.locked_until and attempt.locked_until <= now:
        attempt.locked_until = None
        attempt.failure_count = 0
        attempt.save(update_fields=["locked_until", "failure_count", "updated_at"])

    return False, 0


def register_login_failure(username: str, ip_address: str | None):
    key, username_ci = _build_attempt_key(username, ip_address)
    now = timezone.now()
    max_failures = int(get_security_value("LOGIN_MAX_FAILURES", 5))
    failure_window_minutes = int(get_security_value("LOGIN_FAILURE_WINDOW_MINUTES", 15))
    lock_minutes = int(get_security_value("LOGIN_LOCK_MINUTES", 15))
    window_start = now - timedelta(minutes=max(1, failure_window_minutes))

    attempt, _ = LoginAttempt.objects.get_or_create(
        key=key,
        defaults={
            "username_ci": username_ci[:150],
            "ip_address": ip_address,
            "failure_count": 0,
        },
    )

    if attempt.last_failed_at is None or attempt.last_failed_at < window_start:
        attempt.failure_count = 0

    attempt.failure_count += 1
    attempt.username_ci = username_ci[:150]
    attempt.ip_address = ip_address
    attempt.last_failed_at = now

    if attempt.failure_count >= max(1, max_failures):
        attempt.locked_until = now + timedelta(minutes=max(1, lock_minutes))
    else:
        attempt.locked_until = None

    attempt.save(
        update_fields=[
            "username_ci",
            "ip_address",
            "failure_count",
            "last_failed_at",
            "locked_until",
            "updated_at",
        ]
    )

    return attempt


def clear_login_failures(username: str, ip_address: str | None):
    key, _ = _build_attempt_key(username, ip_address)
    LoginAttempt.objects.filter(key=key).delete()


def record_security_event(
    *,
    event_type: str,
    request=None,
    user=None,
    username: str = "",
    success: bool = True,
    detail: str = "",
    metadata=None,
):
    actor = user if user and getattr(user, "is_authenticated", False) else None
    resolved_username = (username or "").strip()
    if not resolved_username and actor is not None:
        resolved_username = actor.username

    user_agent = ""
    if request:
        user_agent = (request.META.get("HTTP_USER_AGENT", "") or "").strip()[:255]

    event = SecurityAuditLog.objects.create(
        event_type=event_type,
        user=actor,
        username=resolved_username[:150],
        ip_address=get_client_ip(request),
        user_agent=user_agent,
        success=bool(success),
        detail=(detail or "").strip()[:255],
        metadata=metadata or {},
    )
    log_method = security_logger.info if success else security_logger.warning
    log_method(
        "Security event type=%s username=%s success=%s ip=%s detail=%s",
        event.event_type,
        event.username or "-",
        event.success,
        event.ip_address or "-",
        event.detail or "-",
    )


def is_password_reused(user, raw_password: str):
    if not user or not raw_password:
        return False

    history_limit = int(get_security_value("PASSWORD_HISTORY_COUNT", 5))
    history_limit = max(history_limit, 1)
    if user.password and check_password(raw_password, user.password):
        return True

    historical_hashes = (
        PasswordHistory.objects.filter(user=user)
        .order_by("-created_at")
        .values_list("password_hash", flat=True)[:history_limit]
    )
    for password_hash in historical_hashes:
        if password_hash and check_password(raw_password, password_hash):
            return True
    return False


def record_password_history(user):
    if not user or not user.password:
        return

    latest = PasswordHistory.objects.filter(user=user).order_by("-created_at").first()
    if latest and latest.password_hash == user.password:
        return

    PasswordHistory.objects.create(user=user, password_hash=user.password)

    history_limit = int(get_security_value("PASSWORD_HISTORY_COUNT", 5))
    history_limit = max(history_limit, 1)
    stale_ids = list(
        PasswordHistory.objects.filter(user=user)
        .order_by("-created_at")
        .values_list("id", flat=True)[history_limit:]
    )
    if stale_ids:
        PasswordHistory.objects.filter(id__in=stale_ids).delete()
