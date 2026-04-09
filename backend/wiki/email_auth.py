import math
import secrets
import string
from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.core.mail import send_mail
from django.utils import timezone
from django.utils.crypto import salted_hmac
from rest_framework.exceptions import APIException, ValidationError

from .models import EmailVerificationTicket

EMAIL_TICKET_SIGNING_SALT = "wiki.email.ticket.v1"
EMAIL_CODE_DIGEST_SALT = "wiki.email.code.v1"


class EmailDeliveryError(APIException):
    status_code = 503
    default_detail = "Email service is temporarily unavailable. Please retry shortly."
    default_code = "email_delivery_failed"


def mask_email(value: str) -> str:
    email = str(value or "").strip()
    if "@" not in email:
        return email
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        local_masked = local[:1] + "*"
    else:
        local_masked = local[:2] + "*" * max(1, len(local) - 2)
    return f"{local_masked}@{domain}"


def build_email_ticket_token(ticket: EmailVerificationTicket) -> str:
    return signing.dumps({"ticket_id": ticket.id}, salt=EMAIL_TICKET_SIGNING_SALT, compress=True)


def load_email_ticket_from_token(token: str, *, purpose: str) -> EmailVerificationTicket:
    raw = str(token or "").strip()
    if not raw:
        raise ValidationError({"ticket_token": ["Please request a new verification code."]})

    try:
        payload = signing.loads(raw, salt=EMAIL_TICKET_SIGNING_SALT)
    except signing.BadSignature as exc:
        raise ValidationError({"ticket_token": ["Verification session is invalid."]}) from exc

    ticket_id = payload.get("ticket_id")
    try:
        ticket = EmailVerificationTicket.objects.get(id=ticket_id, purpose=purpose)
    except EmailVerificationTicket.DoesNotExist as exc:
        raise ValidationError({"ticket_token": ["Verification session is invalid."]}) from exc
    return ticket


def generate_email_code() -> str:
    alphabet = string.digits
    length = max(4, int(getattr(settings, "EMAIL_CODE_LENGTH", 6)))
    return "".join(secrets.choice(alphabet) for _ in range(length))


def send_transactional_email(*, subject: str, body: str, recipient_list: list[str]) -> None:
    backend_name = str(getattr(settings, "EMAIL_BACKEND", "") or "")
    if "smtp" in backend_name.lower():
        if not settings.EMAIL_HOST or not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
            raise EmailDeliveryError("SMTP configuration is incomplete. Please contact the site administrator.")

    try:
        sent = send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipient_list,
            fail_silently=False,
        )
    except Exception as exc:
        raise EmailDeliveryError() from exc

    if sent < 1:
        raise EmailDeliveryError()


def build_email_code_digest(ticket: EmailVerificationTicket, code: str) -> str:
    return salted_hmac(
        EMAIL_CODE_DIGEST_SALT,
        f"{ticket.id}:{ticket.purpose}:{ticket.email.lower()}:{code}",
        secret=settings.SECRET_KEY,
    ).hexdigest()


def validate_email_code(ticket: EmailVerificationTicket, code: str) -> None:
    now = timezone.now()
    if ticket.consumed_at is not None:
        raise ValidationError({"code": ["This verification code has already been used."]})
    if ticket.expires_at <= now:
        raise ValidationError({"code": ["Verification code expired. Please request a new one."]})

    max_attempts = max(1, int(getattr(settings, "EMAIL_CODE_MAX_VERIFY_ATTEMPTS", 5)))
    if ticket.verify_attempt_count >= max_attempts:
        raise ValidationError({"code": ["Too many incorrect attempts. Please request a new verification code."]})

    code_text = str(code or "").strip()
    if not code_text:
        raise ValidationError({"code": ["Please enter the verification code."]})

    expected = build_email_code_digest(ticket, code_text)
    if not secrets.compare_digest(expected, ticket.code_hash):
        ticket.verify_attempt_count += 1
        ticket.save(update_fields=["verify_attempt_count", "updated_at"])
        raise ValidationError({"code": ["Verification code is incorrect."]})


def get_email_code_send_wait_seconds(*, purpose: str, email: str, user=None) -> int:
    cooldown_seconds = max(0, int(getattr(settings, "EMAIL_CODE_RESEND_SECONDS", 60)))
    if cooldown_seconds <= 0:
        return 0

    queryset = EmailVerificationTicket.objects.filter(purpose=purpose, email__iexact=email)
    if user is not None:
        queryset = queryset.filter(user=user)
    latest = queryset.order_by("-created_at").first()
    if not latest:
        return 0

    elapsed = (timezone.now() - latest.created_at).total_seconds()
    wait_seconds = cooldown_seconds - int(elapsed)
    return wait_seconds if wait_seconds > 0 else 0


def get_email_code_window_wait_seconds(*, purpose: str, email: str, user=None) -> int:
    window_minutes = max(1, int(getattr(settings, "EMAIL_CODE_WINDOW_MINUTES", 60)))
    max_sends = max(1, int(getattr(settings, "EMAIL_CODE_MAX_SENDS_PER_WINDOW", 5)))
    window_start = timezone.now() - timedelta(minutes=window_minutes)
    queryset = EmailVerificationTicket.objects.filter(
        purpose=purpose,
        email__iexact=email,
        created_at__gte=window_start,
    ).order_by("created_at")
    if user is not None:
        queryset = queryset.filter(user=user)

    recent = list(queryset[:max_sends])
    if len(recent) < max_sends:
        return 0

    oldest = recent[0]
    wait_until = oldest.created_at + timedelta(minutes=window_minutes)
    wait_seconds = math.ceil((wait_until - timezone.now()).total_seconds())
    return wait_seconds if wait_seconds > 0 else 0


def create_email_verification_ticket(
    *,
    purpose: str,
    email: str,
    user=None,
    username_snapshot: str = "",
    school_name_snapshot: str = "",
    password_hash_snapshot: str = "",
    created_ip: str | None = None,
) -> tuple[EmailVerificationTicket, str]:
    code = generate_email_code()
    ticket = EmailVerificationTicket.objects.create(
        purpose=purpose,
        user=user,
        email=(email or "").strip(),
        username_snapshot=(username_snapshot or "").strip()[:150],
        school_name_snapshot=(school_name_snapshot or "").strip()[:120],
        password_hash_snapshot=(password_hash_snapshot or "").strip()[:128],
        code_hash="",
        created_ip=created_ip,
        expires_at=timezone.now() + timedelta(seconds=max(60, settings.EMAIL_CODE_TTL_SECONDS)),
    )
    ticket.code_hash = build_email_code_digest(ticket, code)
    ticket.save(update_fields=["code_hash", "updated_at"])
    return ticket, code


def send_email_code(ticket: EmailVerificationTicket, code: str) -> None:
    expires_minutes = max(1, math.ceil(settings.EMAIL_CODE_TTL_SECONDS / 60))
    purpose = ticket.purpose
    if purpose == EmailVerificationTicket.Purpose.CHANGE_PASSWORD:
        subject = f"{settings.EMAIL_SUBJECT_PREFIX}修改密码验证码"
        body = "\n".join(
            [
                "你正在修改 AlgoWiki 账号密码。",
                "",
                f"验证码：{code}",
                f"有效期：{expires_minutes} 分钟",
                "",
                "如果这不是你的操作，请忽略此邮件。",
            ]
        )
        send_transactional_email(subject=subject, body=body, recipient_list=[ticket.email])
        return
    if purpose == EmailVerificationTicket.Purpose.REGISTER:
        subject = f"{settings.EMAIL_SUBJECT_PREFIX}注册验证码"
        intro = "你正在注册 AlgoWiki 账号。"
    elif purpose == EmailVerificationTicket.Purpose.RESET_PASSWORD:
        subject = f"{settings.EMAIL_SUBJECT_PREFIX}找回密码验证码"
        intro = "你正在重置 AlgoWiki 账号密码。"
    else:
        subject = f"{settings.EMAIL_SUBJECT_PREFIX}邮箱验证验证码"
        intro = "你正在变更或验证 AlgoWiki 账号邮箱。"

    body = "\n".join(
        [
            f"{intro}",
            "",
            f"验证码：{code}",
            f"有效期：{expires_minutes} 分钟",
            "",
            "如果这不是你的操作，请忽略此邮件。",
        ]
    )

    send_transactional_email(subject=subject, body=body, recipient_list=[ticket.email])


def send_email_change_notice(*, old_email: str, new_email: str) -> None:
    old_email = str(old_email or "").strip()
    new_email = str(new_email or "").strip()
    if not old_email or not new_email or old_email.lower() == new_email.lower():
        return

    subject = f"{settings.EMAIL_SUBJECT_PREFIX}邮箱已变更提醒"
    body = "\n".join(
        [
            "你的 AlgoWiki 账号邮箱刚刚发生了变更。",
            "",
            f"原邮箱：{old_email}",
            f"新邮箱：{new_email}",
            "",
            "如果这不是你的操作，请立即联系站点管理员并尽快修改密码。",
        ]
    )
    send_transactional_email(subject=subject, body=body, recipient_list=[old_email])
