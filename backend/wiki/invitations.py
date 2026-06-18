import secrets

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone
from django.utils.crypto import salted_hmac

from .models import (
    InvitationCode,
    InvitationContributionEvent,
    InvitationRecord,
    PhoneVerification,
    User,
)
from .security import get_client_ip


INVITATION_REWARD_DELTA = 1
INVITATION_CODE_LENGTH = 8


def normalize_invitation_code(value: str) -> str:
    return "".join(ch for ch in str(value or "").upper().strip() if ch.isalnum())[:32]


def generate_invitation_code() -> str:
    alphabet = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
    return "".join(secrets.choice(alphabet) for _ in range(INVITATION_CODE_LENGTH))


def get_or_create_invitation_code(user: User) -> InvitationCode:
    try:
        return user.invitation_code
    except InvitationCode.DoesNotExist:
        pass

    for _ in range(20):
        code = generate_invitation_code()
        try:
            return InvitationCode.objects.create(user=user, code=code)
        except IntegrityError:
            continue
    raise RuntimeError("Unable to generate a unique invitation code.")


def get_active_invitation_code(value: str) -> InvitationCode | None:
    code = normalize_invitation_code(value)
    if not code:
        return None
    return (
        InvitationCode.objects.select_related("user")
        .filter(code=code, is_active=True, user__is_active=True, user__is_banned=False)
        .first()
    )


def hash_invitation_context(value: str, *, salt: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return salted_hmac(salt, text).hexdigest()


def build_invitation_request_metadata(request) -> dict:
    if request is None:
        return {}
    user_agent = str(request.META.get("HTTP_USER_AGENT") or "")[:300]
    return {
        "ip_hash": hash_invitation_context(get_client_ip(request) or "", salt="invitation-ip"),
        "user_agent_hash": hash_invitation_context(user_agent, salt="invitation-user-agent"),
    }


def create_pending_invitation_record(*, invitee: User, code_value: str, request=None) -> InvitationRecord | None:
    invitation_code = get_active_invitation_code(code_value)
    if invitation_code is None or invitation_code.user_id == invitee.id:
        return None

    metadata = build_invitation_request_metadata(request)
    with transaction.atomic():
        record, created = InvitationRecord.objects.get_or_create(
            invitee=invitee,
            defaults={
                "inviter": invitation_code.user,
                "invitation_code": invitation_code,
                "code_snapshot": invitation_code.code,
                "reward_delta": INVITATION_REWARD_DELTA,
                "registration_ip_hash": metadata.get("ip_hash", ""),
                "user_agent_hash": metadata.get("user_agent_hash", ""),
                "metadata": {"source": "register"},
            },
        )
        if created:
            invitation_code.used_count = F("used_count") + 1
            invitation_code.last_used_at = timezone.now()
            invitation_code.save(update_fields=["used_count", "last_used_at", "updated_at"])
        return record


def _create_invitation_score_event(
    *,
    user: User,
    actor: User | None,
    record: InvitationRecord | None,
    action_type: str,
    delta: int,
    is_rollback: bool,
    event_key: str,
    metadata: dict | None = None,
) -> InvitationContributionEvent:
    if event_key:
        existing = InvitationContributionEvent.objects.filter(event_key=event_key).first()
        if existing is not None:
            return existing
    User.objects.filter(pk=user.pk).update(invitation_score=F("invitation_score") + delta)
    user.refresh_from_db(fields=["invitation_score"])
    return InvitationContributionEvent.objects.create(
        user=user,
        actor=actor if actor and getattr(actor, "is_authenticated", False) else None,
        invitation_record=record,
        action_type=action_type,
        delta=delta,
        balance_after=user.invitation_score,
        is_rollback=is_rollback,
        event_key=event_key,
        metadata=metadata or {},
    )


def activate_invitation_for_user(*, invitee: User, actor: User | None = None) -> InvitationRecord | None:
    try:
        record = InvitationRecord.objects.select_related("inviter", "invitee").get(invitee=invitee)
    except InvitationRecord.DoesNotExist:
        return None
    if record.status != InvitationRecord.Status.PENDING:
        return record

    try:
        phone = invitee.phone_verification
    except PhoneVerification.DoesNotExist:
        return record
    if phone.status != PhoneVerification.Status.VERIFIED:
        return record

    now = timezone.now()
    with transaction.atomic():
        locked = (
            InvitationRecord.objects.select_for_update()
            .select_related("inviter", "invitee")
            .get(pk=record.pk)
        )
        if locked.status != InvitationRecord.Status.PENDING:
            return locked
        locked.status = InvitationRecord.Status.EFFECTIVE
        locked.effective_at = now
        locked.rolled_back_at = None
        locked.rejected_at = None
        locked.reviewed_by = actor if actor and getattr(actor, "is_authenticated", False) else None
        locked.save(
            update_fields=[
                "status",
                "effective_at",
                "rolled_back_at",
                "rejected_at",
                "reviewed_by",
                "updated_at",
            ]
        )
        try:
            _create_invitation_score_event(
                user=locked.inviter,
                actor=actor,
                record=locked,
                action_type=InvitationContributionEvent.ActionType.INVITATION_EFFECTIVE,
                delta=locked.reward_delta,
                is_rollback=False,
                event_key=f"invitation-effective:{locked.id}",
                metadata={"invitee_id": locked.invitee_id},
            )
        except IntegrityError:
            pass
        return locked


def rollback_invitation_record(
    *,
    record: InvitationRecord,
    actor: User | None = None,
    note: str = "",
    status: str = InvitationRecord.Status.ROLLED_BACK,
) -> InvitationRecord:
    now = timezone.now()
    with transaction.atomic():
        locked = (
            InvitationRecord.objects.select_for_update()
            .select_related("inviter", "invitee")
            .get(pk=record.pk)
        )
        previous_status = locked.status
        if previous_status == InvitationRecord.Status.EFFECTIVE:
            try:
                _create_invitation_score_event(
                    user=locked.inviter,
                    actor=actor,
                    record=locked,
                    action_type=InvitationContributionEvent.ActionType.INVITATION_ROLLBACK,
                    delta=-abs(locked.reward_delta),
                    is_rollback=True,
                    event_key=f"invitation-rollback:{locked.id}",
                    metadata={"invitee_id": locked.invitee_id, "note": note[:300]},
                )
            except IntegrityError:
                pass
        locked.status = status
        locked.reviewed_by = actor if actor and getattr(actor, "is_authenticated", False) else None
        locked.review_note = note[:300]
        if status == InvitationRecord.Status.ROLLED_BACK:
            locked.rolled_back_at = now
        elif status == InvitationRecord.Status.REJECTED:
            locked.rejected_at = now
        locked.save(
            update_fields=[
                "status",
                "reviewed_by",
                "review_note",
                "rolled_back_at",
                "rejected_at",
                "updated_at",
            ]
        )
        return locked


def rollback_invitation_for_user(*, invitee: User, actor: User | None = None, note: str = "") -> None:
    try:
        record = InvitationRecord.objects.select_related("inviter", "invitee").get(invitee=invitee)
    except InvitationRecord.DoesNotExist:
        return
    rollback_invitation_record(record=record, actor=actor, note=note)
