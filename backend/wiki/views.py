import re
import csv
import json
import io
import logging
import os
import shutil
import zipfile
from uuid import uuid4
from datetime import date, datetime, time, timedelta
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlparse

from django.conf import settings
from django.http import HttpResponse
from django.core.files.storage import FileSystemStorage
from django.db import DatabaseError, IntegrityError, connection, transaction
from django.db.models import (
    Case,
    Count,
    Exists,
    F,
    IntegerField,
    Max,
    OuterRef,
    Prefetch,
    PROTECT,
    Q,
    Sum,
    Value,
    When,
)
from django.db.models.functions import TruncDate
from django.utils.dateparse import parse_date, parse_datetime
from django.utils import timezone
from rest_framework import generics, mixins, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    Announcement,
    AnnouncementRead,
    Answer,
    AssistantProviderConfig,
    Article,
    ArticleComment,
    ArticleStar,
    Category,
    CompetitionCalendarEvent,
    CompetitionNotice,
    CompetitionPracticeLink,
    CompetitionPracticeLinkProposal,
    CompetitionScheduleEntry,
    CompetitionZoneSection,
    ContributionEvent,
    DeletedContentArchive,
    DocumentPageSection,
    ExtensionPage,
    FriendlyLink,
    HeaderNavigationItem,
    IssueTicket,
    Question,
    RevisionProposal,
    SecurityAuditLog,
    SiteVisitDailyStat,
    TeamMember,
    TrickEntry,
    TrickEntryLike,
    TrickTerm,
    TrickTermSuggestion,
    UserNotification,
    User,
)
from .permissions import (
    AuthenticatedAndNotBanned,
    AdminOrSuperAdmin,
    SuperAdminOnly,
    can_moderate_category,
)
from .security import record_password_history, record_security_event
from .trick_terms import FIXED_TRICK_TERM_DEFINITIONS, FIXED_TRICK_TERM_SLUGS
from .throttles import (
    AssistantAnonRateThrottle,
    AssistantUserRateThrottle,
    ContentCreateRateThrottle,
    ContentDeleteRateThrottle,
    ContentUpdateRateThrottle,
    EmailChangeConfirmRateThrottle,
    EmailChangeRequestRateThrottle,
    LoginRateThrottle,
    PasswordChangeConfirmRateThrottle,
    PasswordChangeRequestRateThrottle,
    PasswordResetConfirmRateThrottle,
    PasswordResetRequestRateThrottle,
    ProfileUpdateRateThrottle,
    RegisterChallengeRateThrottle,
    RegisterRateThrottle,
    RegisterVerifyRateThrottle,
)
from .serializers import (
    AnnouncementSerializer,
    AnswerSerializer,
    ArticleCommentSerializer,
    ArticleDetailSerializer,
    ArticleSerializer,
    CategorySerializer,
    CompetitionCalendarEventSerializer,
    CompetitionNoticeSerializer,
    CompetitionPracticeLinkProposalSerializer,
    CompetitionPracticeLinkSerializer,
    CompetitionScheduleEntrySerializer,
    CompetitionZoneSectionSerializer,
    ContributionEventSerializer,
    DeletedContentArchiveSerializer,
    DocumentPageSectionSerializer,
    PasswordChangeCodeSerializer,
    EmailChangeCodeSerializer,
    EmailChangeSerializer,
    ExtensionPageSerializer,
    FriendlyLinkSerializer,
    HeaderNavigationItemSerializer,
    ImageUploadSerializer,
    IssueTicketSerializer,
    LoginSerializer,
    PasswordChangeSerializer,
    PasswordResetCodeSerializer,
    PasswordResetSerializer,
    QuestionSerializer,
    RegisterEmailCodeSerializer,
    RegisterSerializer,
    build_register_challenge,
    RevisionProposalSerializer,
    TrickEntrySerializer,
    SelfSecurityAuditLogSerializer,
    SecurityAuditLogSerializer,
    TeamMemberSerializer,
    TeamMemberUpsertSerializer,
    UserNotificationSerializer,
    TrickTermSerializer,
    TrickTermSuggestionSerializer,
    UserAdminSerializer,
    UserProfileSettingsSerializer,
    UserProfileUpdateSerializer,
    UserPublicSerializer,
    AssistantChatRequestSerializer,
    AssistantInteractionLogSerializer,
    AssistantProviderConfigSerializer,
    AssistantPublicConfigSerializer,
)
from .assistant import (
    AssistantProviderError,
    append_source_hint_to_answer,
    apply_brattish_tone_to_answer,
    strip_assistant_self_reference,
    build_competition_format_digest,
    build_original_problem_site_digest,
    build_recent_competition_digest,
    build_trick_digest,
    check_daily_limits,
    clear_public_corpus_cache,
    create_interaction_log,
    get_active_assistant_config,
    get_public_assistant_payload,
    invoke_assistant_completion,
    search_public_corpus,
)
from .merge import build_snapshot, merge_article_revision, snapshot_article

api_logger = logging.getLogger("algowiki.api")


def is_manager(user) -> bool:
    return bool(
        user
        and user.is_authenticated
        and user.role in {User.Role.ADMIN, User.Role.SUPERADMIN}
    )


def build_fixed_trick_term_order_expression():
    return Case(
        *[
            When(slug=item["slug"], then=Value(index))
            for index, item in enumerate(FIXED_TRICK_TERM_DEFINITIONS)
        ],
        default=Value(len(FIXED_TRICK_TERM_DEFINITIONS)),
        output_field=IntegerField(),
    )


def build_question_auto_close_at(base_time=None):
    return (base_time or timezone.now()) + Question.AUTO_CLOSE_AFTER


def sync_question_auto_close_state(question, reference_time=None):
    if not question:
        return False
    return question.maybe_auto_close(reference_time=reference_time)


def sync_question_auto_close_states(queryset, reference_time=None):
    now = reference_time or timezone.now()
    due_ids = list(
        queryset.filter(
            status=Question.Status.OPEN,
            auto_close_at__isnull=False,
            auto_close_at__lte=now,
        ).values_list("id", flat=True)
    )
    if not due_ids:
        return []
    Question.objects.filter(id__in=due_ids).update(
        status=Question.Status.CLOSED,
        auto_close_at=None,
        updated_at=now,
    )
    return due_ids


def can_manage_competition(user) -> bool:
    return bool(
        user
        and user.is_authenticated
        and user.role in {User.Role.SCHOOL, User.Role.ADMIN, User.Role.SUPERADMIN}
    )


def log_event(user, event_type: str, target, payload=None):
    if not user or not user.is_authenticated:
        return
    ContributionEvent.objects.create(
        user=user,
        event_type=event_type,
        target_type=target.__class__.__name__,
        target_id=target.pk,
        payload=payload or {},
    )


def create_notification(
    *,
    user,
    title: str,
    content: str = "",
    link: str = "",
    actor=None,
    target=None,
    level: str = UserNotification.Level.INFO,
):
    if not user or not user.is_active or user.is_banned:
        return None
    target_type = target.__class__.__name__ if target is not None else ""
    target_id = target.pk if target is not None else None
    return UserNotification.objects.create(
        user=user,
        actor=actor if actor and actor.is_authenticated else None,
        title=(title or "").strip()[:200],
        content=(content or "").strip()[:500],
        link=(link or "").strip()[:255],
        level=(
            level
            if level in dict(UserNotification.Level.choices)
            else UserNotification.Level.INFO
        ),
        target_type=target_type[:80],
        target_id=target_id,
    )


def normalize_review_note(raw_note) -> str:
    return str(raw_note or "").strip()


def increment_site_visit_count():
    today = timezone.localdate()
    try:
        SiteVisitDailyStat.objects.get_or_create(date=today, defaults={"page_views": 0})
    except IntegrityError:
        pass
    SiteVisitDailyStat.objects.filter(date=today).update(page_views=F("page_views") + 1)


def build_site_visit_stats_payload():
    today = timezone.localdate()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    totals = SiteVisitDailyStat.objects.aggregate(total=Sum("page_views"))

    def aggregate_from(start_date):
        return (
            SiteVisitDailyStat.objects.filter(date__gte=start_date).aggregate(
                total=Sum("page_views")
            )["total"]
            or 0
        )

    today_views = (
        SiteVisitDailyStat.objects.filter(date=today)
        .values_list("page_views", flat=True)
        .first()
        or 0
    )

    recent_days = []
    start_day = today - timedelta(days=6)
    rows = {
        item["date"]: item["page_views"]
        for item in SiteVisitDailyStat.objects.filter(date__gte=start_day)
        .values("date", "page_views")
        .order_by("date")
    }
    cursor = start_day
    while cursor <= today:
        recent_days.append(
            {
                "date": cursor.isoformat(),
                "page_views": int(rows.get(cursor, 0) or 0),
            }
        )
        cursor += timedelta(days=1)

    return {
        "generated_at": timezone.localtime(timezone.now()).isoformat(),
        "today": int(today_views),
        "week": int(aggregate_from(week_start)),
        "month": int(aggregate_from(month_start)),
        "total": int(totals["total"] or 0),
        "recent_days": recent_days,
    }


def _normalize_archive_value(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, dict):
        return {
            str(key): _normalize_archive_value(item) for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [_normalize_archive_value(item) for item in value]
    return str(value)


def _compact_archive_text(value, max_length=500):
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= max_length:
        return text
    return f"{text[: max_length - 3].rstrip()}..."


def _get_archive_user(instance):
    for field_name in ("author", "created_by", "proposer", "user"):
        user = getattr(instance, field_name, None)
        if isinstance(user, User):
            return user
    return None


def _build_deleted_content_snapshot(instance):
    snapshot = {}
    for field in instance._meta.fields:
        try:
            snapshot[field.name] = _normalize_archive_value(field.value_from_object(instance))
        except Exception:
            snapshot[field.name] = _normalize_archive_value(getattr(instance, field.name, None))

    if instance.pk:
        for field in instance._meta.many_to_many:
            related_items = []
            try:
                for related in getattr(instance, field.name).all():
                    related_items.append(
                        {
                            "id": related.pk,
                            "label": str(related),
                        }
                    )
            except Exception:
                related_items = []
            snapshot[field.name] = related_items

    snapshot["model"] = instance.__class__.__name__
    return snapshot


def _build_deleted_content_title(instance):
    if isinstance(instance, Answer):
        question_title = _compact_archive_text(getattr(instance.question, "title", ""), 80)
        return question_title or f"回答 #{instance.pk}"
    if isinstance(instance, CompetitionScheduleEntry):
        return _compact_archive_text(instance.competition_type, 120)
    if isinstance(instance, CompetitionPracticeLink):
        return _compact_archive_text(
            instance.short_name or instance.official_name or f"补题链接 #{instance.pk}",
            120,
        )
    for field_name in ("title", "short_name", "official_name", "competition_type", "name"):
        value = getattr(instance, field_name, "")
        if str(value or "").strip():
            return _compact_archive_text(value, 120)
    return f"{instance.__class__.__name__} #{instance.pk}"


def _build_deleted_content_summary(instance):
    if isinstance(instance, CompetitionScheduleEntry):
        end_date = instance.end_date or instance.event_date
        parts = [
            f"{instance.event_date} - {end_date}" if instance.event_date else "",
            instance.competition_time_range,
            instance.location,
            instance.qq_group,
        ]
        return _compact_archive_text(" ".join(str(part or "") for part in parts), 500)
    if isinstance(instance, CompetitionPracticeLink):
        parts = [
            instance.year,
            getattr(instance, "get_series_display", lambda: "")(),
            getattr(instance, "get_stage_display", lambda: "")(),
            instance.official_name,
            instance.organizer,
            instance.practice_links_note,
        ]
        return _compact_archive_text(" ".join(str(part or "") for part in parts), 500)
    if isinstance(instance, Answer):
        parts = [getattr(instance.question, "title", ""), instance.content_md]
        return _compact_archive_text(" ".join(str(part or "") for part in parts), 500)
    for field_name in (
        "content_md",
        "content",
        "description",
        "resolution_note",
        "review_note",
        "location",
    ):
        value = getattr(instance, field_name, "")
        if str(value or "").strip():
            return _compact_archive_text(value, 500)
    return ""


def _build_deleted_content_body(instance):
    if isinstance(instance, CompetitionPracticeLink):
        links_payload = json.dumps(instance.practice_links or [], ensure_ascii=False)
        body = " ".join(
            str(part or "")
            for part in [
                instance.official_name,
                instance.practice_links_note,
                links_payload,
            ]
        )
        return _compact_archive_text(body, 5000)
    for field_name in ("content_md", "content"):
        value = getattr(instance, field_name, "")
        if str(value or "").strip():
            return str(value)
    return ""


def archive_deleted_content(*, instance, operator, delete_action):
    original_author = _get_archive_user(instance)
    return DeletedContentArchive.objects.create(
        target_type=instance.__class__.__name__,
        target_id=instance.pk,
        delete_action=delete_action,
        title=_build_deleted_content_title(instance),
        summary=_build_deleted_content_summary(instance),
        content_md=_build_deleted_content_body(instance),
        snapshot=_build_deleted_content_snapshot(instance),
        original_author=original_author,
        original_author_name=getattr(original_author, "username", "") or "",
        deleted_by=operator if operator and operator.is_authenticated else None,
        deleted_by_name=getattr(operator, "username", "") or "",
    )


def build_review_notification_content(
    *,
    action: str,
    review_note: str,
    approved_fallback: str,
    rejected_fallback: str,
) -> str:
    note = normalize_review_note(review_note)
    if note:
        prefix = "驳回批注" if action == "reject" else "审核备注"
        return f"{prefix}：{note[:180]}"
    return rejected_fallback if action == "reject" else approved_fallback


def bulk_notify_users(
    *,
    users,
    title: str,
    content: str = "",
    link: str = "",
    actor=None,
    target=None,
    level: str = UserNotification.Level.INFO,
):
    target_type = target.__class__.__name__ if target is not None else ""
    target_id = target.pk if target is not None else None
    actor_id = actor.id if actor and actor.is_authenticated else None
    now = timezone.now()
    items = []
    valid_level = (
        level
        if level in dict(UserNotification.Level.choices)
        else UserNotification.Level.INFO
    )

    for user in users:
        if not user.is_active or user.is_banned:
            continue
        items.append(
            UserNotification(
                user=user,
                actor_id=actor_id,
                title=(title or "").strip()[:200],
                content=(content or "").strip()[:500],
                link=(link or "").strip()[:255],
                level=valid_level,
                target_type=target_type[:80],
                target_id=target_id,
                is_read=False,
                read_at=None,
                created_at=now,
                updated_at=now,
            )
        )

    if items:
        UserNotification.objects.bulk_create(items, batch_size=500)
    return len(items)


def append_review_note_to_instance(instance, reviewer, raw_note, *, field_name="review_note"):
    note = str(raw_note or "").strip()
    if not note:
        return None, "note is required."
    if not hasattr(instance, field_name):
        return None, "This item does not support review notes."

    existing = str(getattr(instance, field_name, "") or "").strip()
    timestamp = timezone.localtime(timezone.now()).strftime("%Y-%m-%d %H:%M")
    username = getattr(reviewer, "username", "") or "admin"
    entry = f"[{timestamp} {username}] {note}"
    setattr(instance, field_name, f"{existing}\n{entry}" if existing else entry)
    instance.save(update_fields=[field_name, "updated_at"])
    return instance, ""


class ReviewNoteActionMixin:
    review_note_field_name = "review_note"

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[AdminOrSuperAdmin],
        url_path="append-review-note",
    )
    def append_review_note(self, request, pk=None):
        item = self.get_object()
        item, detail = append_review_note_to_instance(
            item,
            request.user,
            request.data.get("note", request.data.get("review_note", "")),
            field_name=self.review_note_field_name,
        )
        if not item:
            return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)
        log_event(
            request.user,
            ContributionEvent.EventType.ADMIN,
            item,
            {"action": "append_review_note"},
        )
        return Response(self.get_serializer(item).data)


DELETED_USER_PLACEHOLDER_USERNAME = "system_deleted_user"


def is_deleted_user_placeholder(user) -> bool:
    return bool(
        user and getattr(user, "username", "") == DELETED_USER_PLACEHOLDER_USERNAME
    )


def get_deleted_user_placeholder():
    placeholder, _ = User.objects.get_or_create(
        username=DELETED_USER_PLACEHOLDER_USERNAME,
        defaults={
            "email": "",
            "role": User.Role.NORMAL,
            "is_active": False,
            "school_name": "",
            "bio": "System placeholder for permanently deleted accounts.",
            "avatar_url": "",
            "is_staff": False,
            "is_superuser": False,
        },
    )

    update_fields = []
    normalized_values = {
        "email": "",
        "role": User.Role.NORMAL,
        "is_active": False,
        "school_name": "",
        "bio": "System placeholder for permanently deleted accounts.",
        "avatar_url": "",
        "is_staff": False,
        "is_superuser": False,
    }
    for field_name, expected in normalized_values.items():
        if getattr(placeholder, field_name) != expected:
            setattr(placeholder, field_name, expected)
            update_fields.append(field_name)

    if placeholder.has_usable_password():
        placeholder.set_unusable_password()
        update_fields.append("password")

    if update_fields:
        placeholder.save(update_fields=update_fields)
    return placeholder


def reassign_protected_user_relations(*, source_user, placeholder_user) -> None:
    for relation in User._meta.related_objects:
        field = relation.field
        if getattr(field.remote_field, "on_delete", None) is not PROTECT:
            continue
        if relation.related_model is User:
            continue
        relation.related_model.objects.filter(**{field.name: source_user}).update(
            **{field.name: placeholder_user}
        )


UNSET = object()


def schema_outdated_response(exc):
    return Response(
        {
            "detail": "\u6570\u636e\u5e93\u7ed3\u6784\u7248\u672c\u8fc7\u65e7\uff0c\u8bf7\u5148\u6267\u884c\u6570\u636e\u5e93\u8fc1\u79fb\uff1apython backend/manage.py migrate",
            "code": "schema_outdated",
            "error": str(exc),
        },
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


def parse_datetime_query(value: str, *, end_of_day: bool = False):
    if not value:
        return None
    value = value.strip()
    if not value:
        return None

    dt = parse_datetime(value)
    if dt is None:
        date_value = parse_date(value)
        if date_value is None:
            return None
        dt = datetime.combine(date_value, time.max if end_of_day else time.min)

    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def parse_move_direction(request):
    direction = str(request.data.get("direction", "") or "").strip().lower()
    if direction not in {"up", "down"}:
        return None
    return direction


NON_PUBLIC_DETAIL_ACTIONS = {"retrieve", "update", "partial_update", "destroy", "move"}


def can_access_non_public_items(
    *, user, action: str, explicit_include: bool, permission_check
) -> bool:
    if not permission_check(user):
        return False
    return bool(explicit_include or action in NON_PUBLIC_DETAIL_ACTIONS)


def get_next_order_value(queryset, field_name: str) -> int:
    max_value = queryset.aggregate(max_value=Max(field_name)).get("max_value") or 0
    return int(max_value) + 1


def move_ordered_instance(
    *, instance, queryset, order_field: str, direction: str
) -> bool:
    items = list(queryset.order_by(order_field, "id"))
    current_index = next(
        (index for index, item in enumerate(items) if item.pk == instance.pk), None
    )
    if current_index is None:
        return False

    target_index = current_index - 1 if direction == "up" else current_index + 1
    if target_index < 0 or target_index >= len(items):
        return False

    items[current_index], items[target_index] = (
        items[target_index],
        items[current_index],
    )
    now = timezone.now()
    changed_items = []
    for index, item in enumerate(items, start=1):
        current_value = int(getattr(item, order_field) or 0)
        if current_value == index:
            continue
        setattr(item, order_field, index)
        if hasattr(item, "updated_at"):
            item.updated_at = now
        changed_items.append(item)

    if not changed_items:
        return False

    update_fields = [order_field]
    if hasattr(instance, "updated_at"):
        update_fields.append("updated_at")

    instance.__class__.objects.bulk_update(changed_items, update_fields)
    return True


INVALID_EXPORT_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|]+')
MARKDOWN_IMAGE_PATTERN = re.compile(r"!\[[^\]]*]\(([^)\n]+)\)")
MARKDOWN_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)\n]+)\)")
COMPETITION_CALENDAR_FINISHED_RETENTION_DAYS = 30
EXPORT_FEATURE_DISABLED_DETAIL = (
    "Export has been disabled to keep cost and abuse risk under control."
)


class ActionThrottleMixin:
    throttle_action_classes = {}
    throttle_apply_to_managers = False

    def get_throttles(self):
        classes = list(getattr(self, "throttle_classes", []))
        action = getattr(self, "action", "")
        user = getattr(self.request, "user", None)

        if action and (self.throttle_apply_to_managers or not is_manager(user)):
            classes.extend(self.throttle_action_classes.get(action, []))

        return [throttle() for throttle in classes]


def export_feature_disabled_response():
    return Response(
        {"detail": EXPORT_FEATURE_DISABLED_DETAIL}, status=status.HTTP_404_NOT_FOUND
    )


def sanitize_export_filename(value: str, fallback: str = "article") -> str:
    name = INVALID_EXPORT_FILENAME_CHARS.sub("_", (value or "").strip())
    name = re.sub(r"\s+", " ", name).strip(" .")
    return name[:120] or fallback


def resolve_wiki_assets_root() -> Path | None:
    project_root = Path(__file__).resolve().parents[2]
    candidates = [
        project_root / "frontend" / "public" / "wiki-assets",
        project_root / "frontend" / "dist" / "wiki-assets",
        project_root / "wiki-assets",
    ]
    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            return candidate
    return None


def extract_markdown_image_sources(content: str) -> list[str]:
    sources = []
    for match in MARKDOWN_IMAGE_PATTERN.finditer(content or ""):
        raw = (match.group(1) or "").strip()
        if not raw:
            continue
        if raw.startswith("<") and raw.endswith(">"):
            url = raw[1:-1].strip()
        else:
            # Markdown image syntax supports optional title after URL.
            split = re.split(r'\s+(?=(?:[^"]*"[^"]*")*[^"]*$)', raw, maxsplit=1)
            url = (split[0] if split else raw).strip().strip("\"'")
        if url:
            sources.append(url)
    return sources


def normalize_markdown_asset_path(raw_src: str) -> str:
    value = unquote((raw_src or "").strip()).replace("\\", "/")
    if not value:
        return ""

    if re.match(r"^[a-z][a-z\d+\-.]*://", value, flags=re.IGNORECASE):
        value = (urlparse(value).path or "").strip()
    else:
        value = value.split("#", 1)[0].split("?", 1)[0]

    if value.startswith("./"):
        value = value[2:]
    if value.startswith("/"):
        value = value[1:]

    lower = value.lower()
    if lower.startswith("assets/"):
        value = value[7:]
    elif lower.startswith("wiki-assets/"):
        value = value[12:]
    else:
        return ""

    parts = [part for part in PurePosixPath(value).parts if part not in {"", "."}]
    if not parts or any(part == ".." for part in parts):
        return ""
    return PurePosixPath(*parts).as_posix()


def resolve_markdown_image_file(raw_src: str) -> Path | None:
    # 1) Static wiki assets exported with the project.
    relative_asset = normalize_markdown_asset_path(raw_src)
    if relative_asset:
        assets_root = resolve_wiki_assets_root()
        if assets_root:
            assets_root = assets_root.resolve()
            candidate = (assets_root / relative_asset).resolve()
            try:
                candidate.relative_to(assets_root)
            except ValueError:
                candidate = None
            if candidate and candidate.exists() and candidate.is_file():
                return candidate

    # 2) Runtime uploaded images under MEDIA_ROOT.
    value = unquote((raw_src or "").strip())
    if not value:
        return None
    parsed = urlparse(value)
    path = parsed.path if parsed.scheme else value
    path = path.split("#", 1)[0].split("?", 1)[0]
    media_url = (getattr(settings, "MEDIA_URL", "/media/") or "/media/").strip()
    if not media_url.startswith("/"):
        media_url = f"/{media_url}"
    if not media_url.endswith("/"):
        media_url = f"{media_url}/"
    if not path.startswith(media_url):
        return None

    media_root = Path(settings.MEDIA_ROOT).resolve()
    relative_media = path[len(media_url) :].lstrip("/")
    if not relative_media:
        return None
    candidate = (media_root / relative_media).resolve()
    try:
        candidate.relative_to(media_root)
    except ValueError:
        return None
    if candidate.exists() and candidate.is_file():
        return candidate
    return None


def markdown_line_to_plain_text(line: str) -> str:
    value = (line or "").strip()
    if not value:
        return ""
    # Keep links visible in exported PDF text.
    value = MARKDOWN_LINK_PATTERN.sub(lambda m: f"{m.group(1)} ({m.group(2)})", value)
    value = re.sub(r"[*_~`>#]", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def filter_visible_competition_calendar_events(queryset, *, now=None):
    reference_now = now or timezone.now()
    cutoff = reference_now - timedelta(
        days=COMPETITION_CALENDAR_FINISHED_RETENTION_DAYS
    )
    return queryset.filter(end_time__gte=cutoff)


class HealthCheckView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = []

    def get(self, request):
        frontend_index = Path(getattr(settings, "FRONTEND_DIST_DIR", "")) / "index.html"
        media_root = Path(settings.MEDIA_ROOT).resolve()
        disk_target = (
            media_root if media_root.exists() else Path(settings.BASE_DIR).resolve()
        )
        disk_usage = shutil.disk_usage(disk_target)
        free_mb = int(disk_usage.free / 1024 / 1024)
        media_ok = (
            media_root.exists()
            and media_root.is_dir()
            and os.access(media_root, os.W_OK)
        )
        frontend_ready = frontend_index.exists()
        serve_frontend = bool(getattr(settings, "SERVE_FRONTEND", False))
        request_id = getattr(request, "request_id", "")
        payload = {
            "status": "ok",
            "request_id": request_id,
            "time": timezone.localtime(timezone.now()).isoformat(),
            "release": getattr(settings, "APP_RELEASE", ""),
            "database": {
                "engine": settings.DATABASES["default"]["ENGINE"],
                "vendor": connection.vendor,
                "ok": True,
            },
            "storage": {
                "path": str(disk_target),
                "free_mb": free_mb,
                "min_required_mb": int(getattr(settings, "HEALTH_MIN_DISK_FREE_MB", 0)),
                "ok": free_mb >= int(getattr(settings, "HEALTH_MIN_DISK_FREE_MB", 0)),
            },
            "media": {
                "root": str(media_root),
                "exists": media_root.exists(),
                "writable": media_ok,
                "ok": media_ok,
            },
            "frontend": {
                "serve_frontend": serve_frontend,
                "dist_ready": frontend_ready,
                "ok": (not serve_frontend) or frontend_ready,
            },
            "security": {
                "debug": bool(settings.DEBUG),
                "https_redirect": bool(getattr(settings, "SECURE_SSL_REDIRECT", False)),
                "session_cookie_secure": bool(
                    getattr(settings, "SESSION_COOKIE_SECURE", False)
                ),
                "csrf_cookie_secure": bool(
                    getattr(settings, "CSRF_COOKIE_SECURE", False)
                ),
                "token_ttl_hours": int(
                    (getattr(settings, "AUTH_SECURITY", {}) or {}).get(
                        "TOKEN_TTL_HOURS", 0
                    )
                ),
            },
        }

        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except Exception as exc:
            payload["status"] = "degraded"
            payload["database"]["ok"] = False
            payload["database"]["error"] = str(exc)
        if not payload["storage"]["ok"]:
            payload["status"] = "degraded"
            payload["storage"]["detail"] = "Low free disk space."
        if not payload["media"]["ok"]:
            payload["status"] = "degraded"
            payload["media"]["detail"] = "Media directory is missing or not writable."
        if serve_frontend and not frontend_ready:
            payload["status"] = "degraded"
            payload["frontend"]["detail"] = "Frontend dist index.html is missing."

        status_code = (
            status.HTTP_200_OK
            if payload["status"] == "ok"
            else status.HTTP_503_SERVICE_UNAVAILABLE
        )
        return Response(payload, status=status_code)


class ImageUploadView(APIView):
    permission_classes = [AuthenticatedAndNotBanned]

    # Keep SVG disabled to reduce XSS surface.
    allowed_content_types = {
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
    }
    allowed_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
    max_bytes = 8 * 1024 * 1024

    def post(self, request):
        if not is_manager(request.user):
            return Response(
                {
                    "detail": "Only admins can upload images to the server. Please use external Markdown image links."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = ImageUploadSerializer(
            data=request.data,
            context={
                "max_bytes": self.max_bytes,
                "allowed_extensions": self.allowed_extensions,
                "allowed_content_types": self.allowed_content_types,
            },
        )
        serializer.is_valid(raise_exception=True)

        image = serializer.validated_data["image"]
        suffix = Path(image.name or "").suffix.lower() or ".png"
        now = timezone.now()
        filename = f"{now:%Y%m%d_%H%M%S}_{uuid4().hex[:10]}{suffix}"
        relative_dir = Path("wiki-uploads") / f"{now:%Y}" / f"{now:%m}"
        storage = FileSystemStorage(
            location=settings.MEDIA_ROOT, base_url=settings.MEDIA_URL
        )
        stored_name = storage.save(str(relative_dir / filename), image)
        public_url = request.build_absolute_uri(storage.url(stored_name))

        markdown = f"![{Path(image.name or 'image').stem}]({public_url})"
        return Response(
            {
                "url": public_url,
                "markdown": markdown,
                "path": stored_name.replace("\\", "/"),
                "name": Path(image.name or filename).name,
                "size": image.size,
            },
            status=status.HTTP_201_CREATED,
        )


class RegisterEmailCodeView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [RegisterRateThrottle]

    def post(self, request):
        serializer = RegisterEmailCodeSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        payload = serializer.save()
        record_security_event(
            event_type=SecurityAuditLog.EventType.REGISTER_CODE_SENT,
            request=request,
            username=str(request.data.get("username", "")).strip(),
            success=True,
            detail="registration code sent",
        )
        return Response(payload, status=status.HTTP_200_OK)


class RegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [RegisterVerifyRateThrottle]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        payload = serializer.save()
        user = payload["user"]
        token = payload["token"]
        record_security_event(
            event_type=SecurityAuditLog.EventType.REGISTER_SUCCESS,
            request=request,
            user=user,
            username=user.username,
            success=True,
            detail="user registered",
        )
        return Response(
            {
                "token": token,
                "user": UserPublicSerializer(
                    user,
                    context={"request": request, "include_private_profile": True},
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )


class RegisterChallengeView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [RegisterChallengeRateThrottle]

    def get(self, request):
        return Response(build_register_challenge())


class PasswordResetCodeView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [PasswordResetRequestRateThrottle]

    def post(self, request):
        serializer = PasswordResetCodeSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        payload = serializer.save()
        record_security_event(
            event_type=SecurityAuditLog.EventType.PASSWORD_RESET_REQUESTED,
            request=request,
            success=True,
            detail="password reset code requested",
        )
        return Response(
            {
                **payload,
                "detail": "If the email exists, a verification code has been sent.",
            },
            status=status.HTTP_200_OK,
        )


class PasswordResetView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [PasswordResetConfirmRateThrottle]

    def post(self, request):
        serializer = PasswordResetSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        payload = serializer.save()
        user = payload["user"]
        token = payload["token"]
        record_security_event(
            event_type=SecurityAuditLog.EventType.PASSWORD_RESET_COMPLETED,
            request=request,
            user=user,
            username=user.username,
            success=True,
            detail="password reset completed",
        )
        return Response(
            {
                "detail": "Password reset successfully.",
                "token": token,
                "user": UserPublicSerializer(
                    user,
                    context={"request": request, "include_private_profile": True},
                ).data,
            },
            status=status.HTTP_200_OK,
        )


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle]

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        return Response(
            {
                "token": payload["token"],
                "user": UserPublicSerializer(
                    payload["user"],
                    context={"request": request, "include_private_profile": True},
                ).data,
            }
        )


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        record_security_event(
            event_type=SecurityAuditLog.EventType.LOGOUT,
            request=request,
            user=request.user,
            username=request.user.username,
            success=True,
            detail="logout success",
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = [AuthenticatedAndNotBanned]

    def get_throttles(self):
        if self.request.method.upper() == "PATCH":
            return [ProfileUpdateRateThrottle()]
        return super().get_throttles()

    def get(self, request):
        try:
            user = request.user
            stats = {
                "star_count": ArticleStar.objects.filter(user=user).count(),
                "comment_count": ArticleComment.objects.filter(author=user).count(),
                "revision_count": RevisionProposal.objects.filter(
                    proposer=user
                ).count(),
                "issue_count": IssueTicket.objects.filter(author=user).count(),
                "question_count": Question.objects.filter(author=user).count(),
                "answer_count": Answer.objects.filter(author=user).count(),
                "article_count": Article.objects.filter(author=user).count(),
            }

            recent_events = ContributionEvent.objects.filter(user=user)[:20]
            starred_articles = Article.objects.filter(
                stargazers__user=user
            ).select_related("category", "author")[:10]

            return Response(
                {
                    "user": UserPublicSerializer(
                        user,
                        context={"request": request, "include_private_profile": True},
                    ).data,
                    "profile_settings": UserProfileSettingsSerializer(user).data,
                    "stats": stats,
                    "recent_events": ContributionEventSerializer(
                        recent_events, many=True
                    ).data,
                    "starred_articles": ArticleSerializer(
                        starred_articles,
                        many=True,
                        context={"request": request},
                    ).data,
                }
            )
        except DatabaseError as exc:
            return schema_outdated_response(exc)

    def patch(self, request):
        serializer = UserProfileUpdateSerializer(
            request.user, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {
                "user": UserPublicSerializer(
                    request.user,
                    context={"request": request, "include_private_profile": True},
                ).data,
                "profile_settings": UserProfileSettingsSerializer(request.user).data,
            }
        )


class EmailChangeCodeView(APIView):
    permission_classes = [AuthenticatedAndNotBanned]
    throttle_classes = [EmailChangeRequestRateThrottle]

    def post(self, request):
        serializer = EmailChangeCodeSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        payload = serializer.save()
        record_security_event(
            event_type=SecurityAuditLog.EventType.EMAIL_CHANGE_REQUESTED,
            request=request,
            user=request.user,
            username=request.user.username,
            success=True,
            detail="email verification code sent",
            metadata={"target_email": str(request.data.get("email", "")).strip()},
        )
        return Response(payload, status=status.HTTP_200_OK)


class EmailChangeView(APIView):
    permission_classes = [AuthenticatedAndNotBanned]
    throttle_classes = [EmailChangeConfirmRateThrottle]

    def post(self, request):
        serializer = EmailChangeSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        payload = serializer.save()
        user = payload["user"]
        record_security_event(
            event_type=SecurityAuditLog.EventType.EMAIL_CHANGED,
            request=request,
            user=user,
            username=user.username,
            success=True,
            detail="email changed",
            metadata={"old_email": payload["old_email"], "new_email": user.email},
        )
        return Response(
            {
                "detail": "Email updated successfully.",
                "user": UserPublicSerializer(
                    user,
                    context={"request": request, "include_private_profile": True},
                ).data,
                "profile_settings": UserProfileSettingsSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )


class MeEventListView(generics.ListAPIView):
    serializer_class = ContributionEventSerializer
    permission_classes = [AuthenticatedAndNotBanned]

    def get_queryset(self):
        queryset = ContributionEvent.objects.filter(
            user=self.request.user
        ).select_related("user")
        event_type = self.request.query_params.get("event_type")
        if event_type in dict(ContributionEvent.EventType.choices):
            queryset = queryset.filter(event_type=event_type)
        return queryset.order_by("-created_at")

    def list(self, request, *args, **kwargs):
        try:
            return super().list(request, *args, **kwargs)
        except DatabaseError as exc:
            return schema_outdated_response(exc)


class MeSecurityEventListView(generics.ListAPIView):
    serializer_class = SelfSecurityAuditLogSerializer
    permission_classes = [AuthenticatedAndNotBanned]

    def get_queryset(self):
        user = self.request.user
        queryset = SecurityAuditLog.objects.filter(
            Q(user=user) | Q(username=user.username)
        )

        event_type = self.request.query_params.get("event_type")
        if event_type in dict(SecurityAuditLog.EventType.choices):
            queryset = queryset.filter(event_type=event_type)

        success = self.request.query_params.get("success")
        if success == "1":
            queryset = queryset.filter(success=True)
        elif success == "0":
            queryset = queryset.filter(success=False)

        return queryset.order_by("-created_at")

    def list(self, request, *args, **kwargs):
        try:
            return super().list(request, *args, **kwargs)
        except DatabaseError as exc:
            return schema_outdated_response(exc)


class MeSecuritySummaryView(APIView):
    permission_classes = [AuthenticatedAndNotBanned]

    def get(self, request):
        try:
            try:
                window_hours = int(request.query_params.get("window_hours", 24))
            except (TypeError, ValueError):
                window_hours = 24
            window_hours = min(max(window_hours, 1), 168)

            user = request.user
            cutoff = timezone.now() - timedelta(hours=window_hours)
            queryset = SecurityAuditLog.objects.filter(
                (Q(user=user) | Q(username=user.username)),
                created_at__gte=cutoff,
            )

            login_failures = queryset.filter(
                event_type__in=[
                    SecurityAuditLog.EventType.LOGIN_FAILED,
                    SecurityAuditLog.EventType.LOGIN_LOCKED,
                    SecurityAuditLog.EventType.LOGIN_DENIED,
                ]
            )
            top_failed_ips = (
                login_failures.exclude(ip_address__isnull=True)
                .exclude(ip_address="")
                .values("ip_address")
                .annotate(count=Count("id"))
                .order_by("-count", "ip_address")[:5]
            )

            return Response(
                {
                    "window_hours": window_hours,
                    "since": timezone.localtime(cutoff).isoformat(),
                    "totals": {
                        "events": queryset.count(),
                        "login_failed": queryset.filter(
                            event_type=SecurityAuditLog.EventType.LOGIN_FAILED
                        ).count(),
                        "login_locked": queryset.filter(
                            event_type=SecurityAuditLog.EventType.LOGIN_LOCKED
                        ).count(),
                        "login_denied": queryset.filter(
                            event_type=SecurityAuditLog.EventType.LOGIN_DENIED
                        ).count(),
                        "password_changed": queryset.filter(
                            event_type=SecurityAuditLog.EventType.PASSWORD_CHANGED
                        ).count(),
                    },
                    "top_failed_ips": list(top_failed_ips),
                }
            )
        except DatabaseError as exc:
            return schema_outdated_response(exc)


class ChangePasswordCodeView(APIView):
    permission_classes = [AuthenticatedAndNotBanned]
    throttle_classes = [PasswordChangeRequestRateThrottle]

    def post(self, request):
        serializer = PasswordChangeCodeSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        payload = serializer.save()
        record_security_event(
            event_type=SecurityAuditLog.EventType.PASSWORD_CHANGE_REQUESTED,
            request=request,
            user=request.user,
            username=request.user.username,
            success=True,
            detail="password change code sent",
        )
        return Response(payload, status=status.HTTP_200_OK)


class ChangePasswordView(APIView):
    permission_classes = [AuthenticatedAndNotBanned]
    throttle_classes = [PasswordChangeConfirmRateThrottle]

    def post(self, request):
        serializer = PasswordChangeSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        payload = serializer.save()
        user = payload["user"]
        token = payload["token"]
        record_security_event(
            event_type=SecurityAuditLog.EventType.PASSWORD_CHANGED,
            request=request,
            user=user,
            username=user.username,
            success=True,
            detail="password changed",
        )
        return Response({"detail": "Password changed successfully.", "token": token})


class CategoryViewSet(viewsets.ModelViewSet):
    serializer_class = CategorySerializer
    queryset = Category.objects.select_related("parent").all()

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [AllowAny()]
        return [AdminOrSuperAdmin()]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        include_hidden = self.request.query_params.get("include_hidden") == "1"

        can_access_hidden = can_access_non_public_items(
            user=user,
            action=getattr(self, "action", ""),
            explicit_include=include_hidden,
            permission_check=is_manager,
        )
        if not can_access_hidden:
            queryset = queryset.filter(is_visible=True)

        if self.request.query_params.get("top_level") == "1":
            queryset = queryset.filter(parent__isnull=True)

        parent = self.request.query_params.get("parent")
        if parent:
            queryset = queryset.filter(parent_id=parent)

        return queryset.order_by("order", "name")

    def list(self, request, *args, **kwargs):
        try:
            return super().list(request, *args, **kwargs)
        except DatabaseError as exc:
            return schema_outdated_response(exc)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        parent = serializer.validated_data.get("parent")
        save_kwargs = {}
        if request.data.get("order", None) in {"", None}:
            save_kwargs["order"] = get_next_order_value(
                Category.objects.filter(parent=parent), "order"
            )
        category = serializer.save(**save_kwargs)
        log_event(
            request.user,
            ContributionEvent.EventType.ADMIN,
            category,
            {"action": "create_category"},
        )
        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        category = self.get_object()
        serializer = self.get_serializer(category, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        log_event(
            request.user,
            ContributionEvent.EventType.ADMIN,
            category,
            {"action": "update_category"},
        )
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        category = self.get_object()
        log_event(
            request.user,
            ContributionEvent.EventType.ADMIN,
            category,
            {"action": "delete_category"},
        )
        return super().destroy(request, *args, **kwargs)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[AdminOrSuperAdmin],
        url_path="move",
    )
    def move(self, request, pk=None):
        category = self.get_object()
        direction = parse_move_direction(request)
        if not direction:
            return Response(
                {"detail": "direction must be up or down."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        moved = move_ordered_instance(
            instance=category,
            queryset=Category.objects.filter(parent=category.parent),
            order_field="order",
            direction=direction,
        )
        if not moved:
            return Response(
                {"detail": "Category is already at the edge."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        category.refresh_from_db()
        log_event(
            request.user,
            ContributionEvent.EventType.ADMIN,
            category,
            {"action": f"move_category_{direction}"},
        )
        return Response(self.get_serializer(category).data)


class ArticleViewSet(ActionThrottleMixin, viewsets.ModelViewSet):
    serializer_class = ArticleSerializer
    queryset = Article.objects.select_related("category", "author", "last_editor").all()
    throttle_action_classes = {
        "create": [ContentCreateRateThrottle],
        "update": [ContentUpdateRateThrottle],
        "partial_update": [ContentUpdateRateThrottle],
        "destroy": [ContentDeleteRateThrottle],
    }

    def get_permissions(self):
        if self.action in {
            "list",
            "retrieve",
            "export_markdown_bundle",
            "export_pdf",
            "export_collection_markdown_bundle",
            "export_collection_pdf",
        }:
            return [AllowAny()]
        if self.action in {"star", "unstar", "mine", "starred"}:
            return [AuthenticatedAndNotBanned()]
        if self.action in {"publish", "bulk_moderate"}:
            return [AuthenticatedAndNotBanned()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ArticleDetailSerializer
        return super().get_serializer_class()

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action == "retrieve":
            queryset = queryset.prefetch_related(
                Prefetch(
                    "revision_proposals",
                    queryset=RevisionProposal.objects.filter(
                        status=RevisionProposal.Status.APPROVED
                    ).select_related("proposer"),
                    to_attr="approved_revision_proposals",
                )
            )
        user = self.request.user
        manager = is_manager(user)

        if manager:
            pass
        elif user.is_authenticated and user.role == User.Role.SCHOOL:
            queryset = queryset.filter(
                Q(status=Article.Status.PUBLISHED)
                | Q(author=user)
                | Q(category__moderation_scope=Category.ModerationScope.SCHOOL)
            )
        elif user.is_authenticated:
            queryset = queryset.filter(
                Q(status=Article.Status.PUBLISHED) | Q(author=user)
            )
        else:
            queryset = queryset.filter(status=Article.Status.PUBLISHED)

        category = self.request.query_params.get("category")
        if category:
            category = category.strip()
            if category.isdigit():
                queryset = queryset.filter(category_id=int(category))
            else:
                queryset = queryset.filter(category__slug=category)

        if manager:
            status_filter = self.request.query_params.get("status")
            if status_filter in dict(Article.Status.choices):
                queryset = queryset.filter(status=status_filter)

            author_filter = self.request.query_params.get("author")
            if author_filter:
                author_filter = author_filter.strip()
                if author_filter.isdigit():
                    queryset = queryset.filter(author_id=int(author_filter))
                else:
                    queryset = queryset.filter(
                        author__username__icontains=author_filter
                    )

        search = self.request.query_params.get("search")
        if search:
            search = search.strip()
            tokens = [
                token
                for token in re.split(r"[\s\u3000\.,，。:：/\\-]+", search)
                if token
            ]
            if tokens:
                try:
                    token_query = Q()
                    for token in tokens:
                        token_query &= Q(title__icontains=token) | Q(
                            summary__icontains=token
                        )
                    queryset = queryset.filter(token_query)
                except DatabaseError:
                    queryset = self._python_search_fallback(queryset, tokens)

        featured_only = self.request.query_params.get("featured") == "1"
        if featured_only:
            queryset = queryset.filter(is_featured=True)

        order = self.request.query_params.get("order")
        if order == "oldest":
            return queryset.order_by("updated_at")
        if order == "created_oldest":
            return queryset.order_by("created_at")
        if order == "created_newest":
            return queryset.order_by("-created_at")
        if order == "updated_newest":
            return queryset.order_by("-updated_at")
        if order == "updated_oldest":
            return queryset.order_by("updated_at")
        return queryset.order_by("display_order", "id")

    def list(self, request, *args, **kwargs):
        try:
            return super().list(request, *args, **kwargs)
        except DatabaseError as exc:
            return schema_outdated_response(exc)

    def _python_search_fallback(self, queryset, tokens):
        matched_ids = []
        for article in queryset.only("id", "title", "summary"):
            text = f"{article.title or ''}\n{article.summary or ''}".lower()
            if all(token.lower() in text for token in tokens):
                matched_ids.append(article.id)
        return queryset.filter(id__in=matched_ids)

    def retrieve(self, request, *args, **kwargs):
        article = self.get_object()
        user = request.user
        is_owner = user.is_authenticated and article.author_id == user.id
        if article.status != Article.Status.PUBLISHED and not (
            is_owner or can_moderate_category(user, article.category)
        ):
            return Response(
                {"detail": "Article is not visible."}, status=status.HTTP_404_NOT_FOUND
            )

        Article.objects.filter(pk=article.pk).update(view_count=article.view_count + 1)
        article.refresh_from_db()
        serializer = self.get_serializer(article)
        return Response(serializer.data)

    @action(
        detail=True,
        methods=["get"],
        permission_classes=[AllowAny],
        url_path="export-markdown-bundle",
    )
    def export_markdown_bundle(self, request, pk=None):
        return export_feature_disabled_response()
        article = self.get_object()
        user = request.user
        is_owner = user.is_authenticated and article.author_id == user.id
        if article.status != Article.Status.PUBLISHED and not (
            is_owner or can_moderate_category(user, article.category)
        ):
            return Response(
                {"detail": "Article is not visible."}, status=status.HTTP_404_NOT_FOUND
            )

        markdown_content = article.content_md or ""
        markdown_name = f"{sanitize_export_filename(article.title, fallback=f'article-{article.id}')}.md"

        buffer = io.BytesIO()
        with zipfile.ZipFile(
            buffer, mode="w", compression=zipfile.ZIP_DEFLATED
        ) as zip_file:
            zip_file.writestr(markdown_name, markdown_content.encode("utf-8"))
            # Keep a stable assets directory in package even when no image is found.
            zip_file.writestr("assets/", b"")

            assets_root = resolve_wiki_assets_root()
            if assets_root:
                added_paths = set()
                for image_src in extract_markdown_image_sources(markdown_content):
                    relative_path = normalize_markdown_asset_path(image_src)
                    if not relative_path or relative_path in added_paths:
                        continue
                    source_path = (assets_root / relative_path).resolve()
                    try:
                        source_path.relative_to(assets_root.resolve())
                    except ValueError:
                        continue
                    if not source_path.exists() or not source_path.is_file():
                        continue
                    zip_file.write(source_path, arcname=f"assets/{relative_path}")
                    added_paths.add(relative_path)

        buffer.seek(0)
        export_name = sanitize_export_filename(
            article.title, fallback=f"article-{article.id}"
        )
        response = HttpResponse(buffer.getvalue(), content_type="application/zip")
        response["Content-Disposition"] = f'attachment; filename="{export_name}.zip"'
        response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return response

    @action(
        detail=True,
        methods=["get"],
        permission_classes=[AllowAny],
        url_path="export-pdf",
    )
    def export_pdf(self, request, pk=None):
        return export_feature_disabled_response()
        article = self.get_object()
        user = request.user
        is_owner = user.is_authenticated and article.author_id == user.id
        if article.status != Article.Status.PUBLISHED and not (
            is_owner or can_moderate_category(user, article.category)
        ):
            return Response(
                {"detail": "Article is not visible."}, status=status.HTTP_404_NOT_FOUND
            )

        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import mm
            from reportlab.lib.styles import ParagraphStyle
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.cidfonts import UnicodeCIDFont
            from reportlab.platypus import Image as PdfImage
            from reportlab.platypus import (
                Paragraph,
                Preformatted,
                SimpleDocTemplate,
                Spacer,
            )
        except Exception as exc:
            return Response(
                {
                    "detail": "PDF 导出依赖缺失，请执行 `venv\\Scripts\\python.exe -m pip install -r backend\\requirements.txt`。",
                    "error": str(exc),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        from xml.sax.saxutils import escape

        try:
            pdfmetrics.getFont("STSong-Light")
        except KeyError:
            pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))

        page_width, _page_height = A4
        content_width = page_width - (18 * mm) * 2

        title_style = ParagraphStyle(
            "ArticlePdfTitle",
            fontName="STSong-Light",
            fontSize=24,
            leading=30,
            spaceAfter=6,
        )
        meta_style = ParagraphStyle(
            "ArticlePdfMeta",
            fontName="STSong-Light",
            fontSize=10,
            textColor="#6b7280",
            leading=14,
            spaceAfter=10,
        )
        heading_style_map = {
            1: ParagraphStyle(
                "ArticlePdfH1",
                fontName="STSong-Light",
                fontSize=21,
                leading=28,
                spaceBefore=8,
                spaceAfter=4,
            ),
            2: ParagraphStyle(
                "ArticlePdfH2",
                fontName="STSong-Light",
                fontSize=18,
                leading=24,
                spaceBefore=8,
                spaceAfter=4,
            ),
            3: ParagraphStyle(
                "ArticlePdfH3",
                fontName="STSong-Light",
                fontSize=15,
                leading=21,
                spaceBefore=6,
                spaceAfter=3,
            ),
            4: ParagraphStyle(
                "ArticlePdfH4",
                fontName="STSong-Light",
                fontSize=13,
                leading=18,
                spaceBefore=5,
                spaceAfter=3,
            ),
            5: ParagraphStyle(
                "ArticlePdfH5",
                fontName="STSong-Light",
                fontSize=12,
                leading=17,
                spaceBefore=4,
                spaceAfter=2,
            ),
            6: ParagraphStyle(
                "ArticlePdfH6",
                fontName="STSong-Light",
                fontSize=11,
                leading=16,
                spaceBefore=4,
                spaceAfter=2,
            ),
        }
        body_style = ParagraphStyle(
            "ArticlePdfBody",
            fontName="STSong-Light",
            fontSize=11,
            leading=18,
            spaceAfter=4,
        )
        quote_style = ParagraphStyle(
            "ArticlePdfQuote",
            parent=body_style,
            leftIndent=10,
            textColor="#425466",
        )
        code_style = ParagraphStyle(
            "ArticlePdfCode",
            fontName="Courier",
            fontSize=9.6,
            leading=13,
            backColor="#f3f4f6",
            borderPadding=6,
            leftIndent=4,
            rightIndent=4,
            spaceBefore=3,
            spaceAfter=6,
        )

        story = [
            Paragraph(escape(article.title or f"Article {article.id}"), title_style),
            Paragraph(
                escape(
                    f"作者 {article.author.username} · 更新于 {timezone.localtime(article.updated_at).strftime('%Y-%m-%d %H:%M')}"
                ),
                meta_style,
            ),
            Spacer(1, 2),
        ]

        code_lines = []
        in_code_block = False
        image_buffers = []

        for raw_line in (article.content_md or "").splitlines():
            line = raw_line.rstrip("\n")
            stripped = line.strip()

            if stripped.startswith("```"):
                if in_code_block:
                    if code_lines:
                        story.append(Preformatted("\n".join(code_lines), code_style))
                        code_lines = []
                in_code_block = not in_code_block
                continue

            if in_code_block:
                code_lines.append(line)
                continue

            if not stripped:
                story.append(Spacer(1, 4))
                continue

            image_sources = extract_markdown_image_sources(stripped)
            if image_sources:
                image_path = resolve_markdown_image_file(image_sources[0])
                if image_path:
                    try:
                        # Downscale large source images to reduce export size and avoid blank rendering in some viewers.
                        from PIL import Image as PilImage, ImageOps

                        with PilImage.open(image_path) as source_img:
                            source_img = ImageOps.exif_transpose(source_img)
                            source_img.thumbnail((1800, 1800))
                            optimized_buffer = io.BytesIO()
                            if source_img.mode in {"RGB", "L"}:
                                source_img.save(
                                    optimized_buffer,
                                    format="JPEG",
                                    quality=86,
                                    optimize=True,
                                    progressive=True,
                                )
                            else:
                                source_img.save(
                                    optimized_buffer, format="PNG", optimize=True
                                )
                            optimized_buffer.seek(0)
                            image_buffers.append(optimized_buffer)
                            image = PdfImage(optimized_buffer)
                        image._restrictSize(content_width, 150 * mm)
                        story.append(image)
                        story.append(Spacer(1, 5))
                        continue
                    except Exception:
                        # Fall back to plain text below if image decoding fails.
                        pass

            if stripped.startswith("#"):
                level = len(stripped) - len(stripped.lstrip("#"))
                level = max(1, min(6, level))
                heading_text = markdown_line_to_plain_text(stripped[level:])
                if heading_text:
                    story.append(
                        Paragraph(escape(heading_text), heading_style_map[level])
                    )
                continue

            if re.match(r"^[-*+]\s+", stripped):
                bullet_text = markdown_line_to_plain_text(
                    re.sub(r"^[-*+]\s+", "", stripped, count=1)
                )
                if bullet_text:
                    story.append(Paragraph(f"• {escape(bullet_text)}", body_style))
                continue

            if re.match(r"^\d+\.\s+", stripped):
                story.append(
                    Paragraph(escape(markdown_line_to_plain_text(stripped)), body_style)
                )
                continue

            if stripped.startswith(">"):
                quote_text = markdown_line_to_plain_text(stripped[1:])
                if quote_text:
                    story.append(Paragraph(escape(quote_text), quote_style))
                continue

            normal_text = markdown_line_to_plain_text(stripped)
            if normal_text:
                story.append(Paragraph(escape(normal_text), body_style))

        if code_lines:
            story.append(Preformatted("\n".join(code_lines), code_style))

        if len(story) <= 3:
            story.append(Paragraph("（正文为空）", body_style))

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=18 * mm,
            rightMargin=18 * mm,
            topMargin=16 * mm,
            bottomMargin=16 * mm,
            title=article.title,
            author=article.author.username,
        )
        doc.build(story)
        buffer.seek(0)

        export_name = sanitize_export_filename(
            article.title, fallback=f"article-{article.id}"
        )
        response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{export_name}.pdf"'
        response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return response

    def _export_queryset_for_collection(self):
        queryset = self.get_queryset().select_related("category", "author")
        return queryset.order_by("category__order", "category__name", "id")

    def _export_collection_name(self):
        category_param = (self.request.query_params.get("category") or "").strip()
        search_param = (self.request.query_params.get("search") or "").strip()

        if category_param:
            category = None
            if category_param.isdigit():
                category = Category.objects.filter(id=int(category_param)).first()
            else:
                category = Category.objects.filter(slug=category_param).first()
            if category:
                return sanitize_export_filename(category.name, fallback="wiki")

        if search_param:
            return sanitize_export_filename(search_param, fallback="wiki-search")
        return "wiki-export"

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[AllowAny],
        url_path="export-collection-markdown-bundle",
    )
    def export_collection_markdown_bundle(self, request):
        return export_feature_disabled_response()
        articles = list(self._export_queryset_for_collection())
        if not articles:
            return Response(
                {"detail": "No articles to export."}, status=status.HTTP_404_NOT_FOUND
            )

        markdown_parts = []
        for index, article in enumerate(articles, start=1):
            markdown_parts.append(f"# {article.title or f'Article {article.id}'}")
            if article.summary:
                markdown_parts.append(f"> {article.summary}")
            markdown_parts.append(article.content_md or "")
            if index != len(articles):
                markdown_parts.append("\n---\n")
        markdown_content = "\n\n".join(markdown_parts).strip() + "\n"

        export_name = self._export_collection_name()
        markdown_name = f"{export_name}.md"

        buffer = io.BytesIO()
        with zipfile.ZipFile(
            buffer, mode="w", compression=zipfile.ZIP_DEFLATED
        ) as zip_file:
            zip_file.writestr(markdown_name, markdown_content.encode("utf-8"))
            zip_file.writestr("assets/", b"")

            assets_root = resolve_wiki_assets_root()
            if assets_root:
                assets_root_resolved = assets_root.resolve()
                added_paths = set()
                for article in articles:
                    for image_src in extract_markdown_image_sources(
                        article.content_md or ""
                    ):
                        relative_path = normalize_markdown_asset_path(image_src)
                        if not relative_path or relative_path in added_paths:
                            continue
                        source_path = (assets_root_resolved / relative_path).resolve()
                        try:
                            source_path.relative_to(assets_root_resolved)
                        except ValueError:
                            continue
                        if not source_path.exists() or not source_path.is_file():
                            continue
                        zip_file.write(source_path, arcname=f"assets/{relative_path}")
                        added_paths.add(relative_path)

        buffer.seek(0)
        response = HttpResponse(buffer.getvalue(), content_type="application/zip")
        response["Content-Disposition"] = f'attachment; filename="{export_name}.zip"'
        response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return response

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[AllowAny],
        url_path="export-collection-pdf",
    )
    def export_collection_pdf(self, request):
        return export_feature_disabled_response()
        articles = list(self._export_queryset_for_collection())
        if not articles:
            return Response(
                {"detail": "No articles to export."}, status=status.HTTP_404_NOT_FOUND
            )

        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import ParagraphStyle
            from reportlab.lib.units import mm
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.cidfonts import UnicodeCIDFont
            from reportlab.platypus import (
                Image as PdfImage,
                Paragraph,
                Preformatted,
                SimpleDocTemplate,
                Spacer,
                Table,
                TableStyle,
            )
        except Exception as exc:
            return Response(
                {
                    "detail": "PDF 导出依赖缺失，请执行 `venv\\Scripts\\python.exe -m pip install -r backend\\requirements.txt`。",
                    "error": str(exc),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        from xml.sax.saxutils import escape

        try:
            pdfmetrics.getFont("STSong-Light")
        except KeyError:
            pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))

        table_separator_pattern = re.compile(
            r"^\s*\|?(?:\s*:?-{3,}:?\s*\|)+\s*:?-{3,}:?\s*\|?\s*$"
        )

        def split_table_row(line: str):
            text = (line or "").strip()
            if text.startswith("|"):
                text = text[1:]
            if text.endswith("|"):
                text = text[:-1]
            return [cell.strip() for cell in text.split("|")]

        page_width, _page_height = A4
        content_width = page_width - (18 * mm) * 2

        title_style = ParagraphStyle(
            "CollectionPdfTitle",
            fontName="STSong-Light",
            fontSize=24,
            leading=30,
            spaceAfter=8,
        )
        article_title_style = ParagraphStyle(
            "CollectionPdfArticleTitle",
            fontName="STSong-Light",
            fontSize=19,
            leading=26,
            spaceBefore=8,
            spaceAfter=5,
        )
        meta_style = ParagraphStyle(
            "CollectionPdfMeta",
            fontName="STSong-Light",
            fontSize=10,
            textColor="#6b7280",
            leading=14,
            spaceAfter=8,
        )
        heading_style_map = {
            1: ParagraphStyle(
                "CollectionPdfH1",
                fontName="STSong-Light",
                fontSize=20,
                leading=27,
                spaceBefore=8,
                spaceAfter=4,
            ),
            2: ParagraphStyle(
                "CollectionPdfH2",
                fontName="STSong-Light",
                fontSize=17,
                leading=23,
                spaceBefore=7,
                spaceAfter=4,
            ),
            3: ParagraphStyle(
                "CollectionPdfH3",
                fontName="STSong-Light",
                fontSize=15,
                leading=20,
                spaceBefore=6,
                spaceAfter=3,
            ),
            4: ParagraphStyle(
                "CollectionPdfH4",
                fontName="STSong-Light",
                fontSize=13,
                leading=18,
                spaceBefore=5,
                spaceAfter=3,
            ),
            5: ParagraphStyle(
                "CollectionPdfH5",
                fontName="STSong-Light",
                fontSize=12,
                leading=17,
                spaceBefore=4,
                spaceAfter=2,
            ),
            6: ParagraphStyle(
                "CollectionPdfH6",
                fontName="STSong-Light",
                fontSize=11,
                leading=16,
                spaceBefore=4,
                spaceAfter=2,
            ),
        }
        body_style = ParagraphStyle(
            "CollectionPdfBody",
            fontName="STSong-Light",
            fontSize=11,
            leading=18,
            spaceAfter=4,
        )
        quote_style = ParagraphStyle(
            "CollectionPdfQuote",
            parent=body_style,
            leftIndent=10,
            textColor="#425466",
        )
        code_style = ParagraphStyle(
            "CollectionPdfCode",
            fontName="Courier",
            fontSize=9.5,
            leading=13,
            backColor="#f3f4f6",
            borderPadding=6,
            leftIndent=4,
            rightIndent=4,
            spaceBefore=3,
            spaceAfter=6,
        )

        story = [Paragraph(escape("AlgoWiki 内容导出"), title_style)]
        image_buffers = []

        for article in articles:
            story.append(
                Paragraph(
                    escape(article.title or f"Article {article.id}"),
                    article_title_style,
                )
            )
            story.append(
                Paragraph(
                    escape(
                        f"作者 {article.author.username} · 更新于 {timezone.localtime(article.updated_at).strftime('%Y-%m-%d %H:%M')}"
                    ),
                    meta_style,
                )
            )
            if article.summary:
                summary_text = markdown_line_to_plain_text(article.summary)
                if summary_text:
                    story.append(Paragraph(escape(summary_text), body_style))
                    story.append(Spacer(1, 2))

            code_lines = []
            in_code_block = False
            lines = (article.content_md or "").splitlines()
            line_index = 0

            while line_index < len(lines):
                line = lines[line_index].rstrip("\n")
                stripped = line.strip()

                if stripped.startswith("```"):
                    if in_code_block and code_lines:
                        story.append(Preformatted("\n".join(code_lines), code_style))
                        code_lines = []
                    in_code_block = not in_code_block
                    line_index += 1
                    continue

                if in_code_block:
                    code_lines.append(line)
                    line_index += 1
                    continue

                if not stripped:
                    story.append(Spacer(1, 4))
                    line_index += 1
                    continue

                if (
                    "|" in stripped
                    and line_index + 1 < len(lines)
                    and table_separator_pattern.match(lines[line_index + 1].strip())
                ):
                    header_cells = split_table_row(stripped)
                    rows = []
                    line_index += 2
                    while line_index < len(lines):
                        candidate = lines[line_index].strip()
                        if not candidate or "|" not in candidate:
                            break
                        rows.append(split_table_row(candidate))
                        line_index += 1

                    col_count = max(
                        [len(header_cells)] + [len(row) for row in rows] + [1]
                    )

                    def normalize_cells(cells):
                        normalized = [
                            markdown_line_to_plain_text(cell)
                            for cell in cells[:col_count]
                        ]
                        while len(normalized) < col_count:
                            normalized.append("")
                        return normalized

                    table_data = [normalize_cells(header_cells)] + [
                        normalize_cells(row) for row in rows
                    ]
                    if table_data:
                        table = Table(table_data, hAlign="LEFT")
                        table.setStyle(
                            TableStyle(
                                [
                                    (
                                        "GRID",
                                        (0, 0),
                                        (-1, -1),
                                        0.6,
                                        colors.HexColor("#c7cfdc"),
                                    ),
                                    (
                                        "BACKGROUND",
                                        (0, 0),
                                        (-1, 0),
                                        colors.HexColor("#eef3fb"),
                                    ),
                                    ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
                                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                                ]
                            )
                        )
                        story.append(table)
                        story.append(Spacer(1, 6))
                    continue

                image_sources = extract_markdown_image_sources(stripped)
                if image_sources:
                    image_path = resolve_markdown_image_file(image_sources[0])
                    if image_path:
                        try:
                            from PIL import Image as PilImage, ImageOps

                            with PilImage.open(image_path) as source_img:
                                source_img = ImageOps.exif_transpose(source_img)
                                source_img.thumbnail((1800, 1800))
                                optimized_buffer = io.BytesIO()
                                if source_img.mode in {"RGB", "L"}:
                                    source_img.save(
                                        optimized_buffer,
                                        format="JPEG",
                                        quality=86,
                                        optimize=True,
                                        progressive=True,
                                    )
                                else:
                                    source_img.save(
                                        optimized_buffer, format="PNG", optimize=True
                                    )
                                optimized_buffer.seek(0)
                                image_buffers.append(optimized_buffer)
                                image = PdfImage(optimized_buffer)
                            image._restrictSize(content_width, 150 * mm)
                            story.append(image)
                            story.append(Spacer(1, 6))
                            line_index += 1
                            continue
                        except Exception:
                            pass

                if stripped.startswith("#"):
                    level = len(stripped) - len(stripped.lstrip("#"))
                    level = max(1, min(6, level))
                    heading_text = markdown_line_to_plain_text(stripped[level:])
                    if heading_text:
                        story.append(
                            Paragraph(escape(heading_text), heading_style_map[level])
                        )
                    line_index += 1
                    continue

                if re.match(r"^[-*+]\s+", stripped):
                    bullet_text = markdown_line_to_plain_text(
                        re.sub(r"^[-*+]\s+", "", stripped, count=1)
                    )
                    if bullet_text:
                        story.append(Paragraph(f"• {escape(bullet_text)}", body_style))
                    line_index += 1
                    continue

                if re.match(r"^\d+\.\s+", stripped):
                    ordered_text = markdown_line_to_plain_text(stripped)
                    if ordered_text:
                        story.append(Paragraph(escape(ordered_text), body_style))
                    line_index += 1
                    continue

                if stripped.startswith(">"):
                    quote_text = markdown_line_to_plain_text(stripped[1:])
                    if quote_text:
                        story.append(Paragraph(escape(quote_text), quote_style))
                    line_index += 1
                    continue

                normal_text = markdown_line_to_plain_text(stripped)
                if normal_text:
                    story.append(Paragraph(escape(normal_text), body_style))
                line_index += 1

            if code_lines:
                story.append(Preformatted("\n".join(code_lines), code_style))

            story.append(Spacer(1, 10))

        buffer = io.BytesIO()
        export_name = self._export_collection_name()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=18 * mm,
            rightMargin=18 * mm,
            topMargin=16 * mm,
            bottomMargin=16 * mm,
            title=export_name,
            author="AlgoWiki",
        )
        doc.build(story)
        buffer.seek(0)

        response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{export_name}.pdf"'
        response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return response

    def create(self, request, *args, **kwargs):
        if request.user.is_banned:
            return Response(
                {"detail": "Banned users cannot create content."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        category = serializer.validated_data["category"]
        if not can_moderate_category(request.user, category):
            return Response(
                {"detail": "You cannot publish in this category."},
                status=status.HTTP_403_FORBIDDEN,
            )

        save_kwargs = {"author": request.user, "last_editor": request.user}
        if request.data.get("display_order", None) in {"", None}:
            save_kwargs["display_order"] = get_next_order_value(
                Article.objects.filter(category=category),
                "display_order",
            )

        article = serializer.save(**save_kwargs)
        log_event(
            request.user,
            ContributionEvent.EventType.ADMIN,
            article,
            {"action": "create_article"},
        )
        return Response(
            self.get_serializer(article).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        article = self.get_object()
        if not can_moderate_category(request.user, article.category):
            return Response(
                {"detail": "No permission to edit this article."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if article.is_locked and not is_manager(request.user):
            return Response(
                {"detail": "This article is locked."}, status=status.HTTP_403_FORBIDDEN
            )

        serializer = self.get_serializer(article, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        next_category = serializer.validated_data.get("category", article.category)
        if not can_moderate_category(request.user, next_category):
            return Response(
                {"detail": "You cannot move this article to the target category."},
                status=status.HTTP_403_FORBIDDEN,
            )
        save_kwargs = {"last_editor": request.user}
        if next_category != article.category and request.data.get(
            "display_order", None
        ) in {"", None}:
            save_kwargs["display_order"] = get_next_order_value(
                Article.objects.filter(category=next_category).exclude(pk=article.pk),
                "display_order",
            )
        serializer.save(**save_kwargs)
        log_event(
            request.user,
            ContributionEvent.EventType.ADMIN,
            article,
            {"action": "update_article"},
        )
        return Response(serializer.data)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[AuthenticatedAndNotBanned],
        url_path="move",
    )
    def move(self, request, pk=None):
        article = self.get_object()
        if not can_moderate_category(request.user, article.category):
            return Response(
                {"detail": "No permission to move this article."},
                status=status.HTTP_403_FORBIDDEN,
            )

        direction = parse_move_direction(request)
        if not direction:
            return Response(
                {"detail": "direction must be up or down."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        moved = move_ordered_instance(
            instance=article,
            queryset=Article.objects.filter(category=article.category),
            order_field="display_order",
            direction=direction,
        )
        if not moved:
            return Response(
                {"detail": "Article is already at the edge."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        article.refresh_from_db()
        log_event(
            request.user,
            ContributionEvent.EventType.ADMIN,
            article,
            {"action": f"move_article_{direction}"},
        )
        return Response(self.get_serializer(article).data)

    @action(
        detail=True, methods=["post"], permission_classes=[AuthenticatedAndNotBanned]
    )
    def star(self, request, pk=None):
        article = self.get_object()
        star, created = ArticleStar.objects.get_or_create(
            user=request.user, article=article
        )
        if created:
            log_event(request.user, ContributionEvent.EventType.STAR, article)
        return Response({"starred": True, "id": star.id})

    @action(
        detail=True, methods=["post"], permission_classes=[AuthenticatedAndNotBanned]
    )
    def unstar(self, request, pk=None):
        article = self.get_object()
        ArticleStar.objects.filter(user=request.user, article=article).delete()
        return Response({"starred": False})

    @action(
        detail=False, methods=["get"], permission_classes=[AuthenticatedAndNotBanned]
    )
    def mine(self, request):
        queryset = self.get_queryset().filter(author=request.user)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(
        detail=False, methods=["get"], permission_classes=[AuthenticatedAndNotBanned]
    )
    def starred(self, request):
        queryset = (
            self.get_queryset()
            .filter(stargazers__user=request.user)
            .order_by("-stargazers__created_at", "-updated_at")
        )
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def _apply_article_moderation(self, article, operator, action):
        action = (action or "").strip().lower()

        if action == "publish":
            if not can_moderate_category(operator, article.category):
                return (
                    False,
                    status.HTTP_403_FORBIDDEN,
                    "No permission to moderate this article.",
                )
            article.status = Article.Status.PUBLISHED
            article.published_at = timezone.now()
            article.save(update_fields=["status", "published_at", "updated_at"])
            log_event(
                operator,
                ContributionEvent.EventType.ADMIN,
                article,
                {"action": "publish_article"},
            )
            return True, status.HTTP_200_OK, None

        if action == "hide":
            if not can_moderate_category(operator, article.category):
                return (
                    False,
                    status.HTTP_403_FORBIDDEN,
                    "No permission to moderate this article.",
                )
            article.status = Article.Status.HIDDEN
            article.save(update_fields=["status", "updated_at"])
            log_event(
                operator,
                ContributionEvent.EventType.ADMIN,
                article,
                {"action": "hide_article"},
            )
            return True, status.HTTP_200_OK, None

        if action == "delete":
            if not is_manager(operator):
                return (
                    False,
                    status.HTTP_403_FORBIDDEN,
                    "Only admins can delete articles.",
                )
            log_event(
                operator,
                ContributionEvent.EventType.ADMIN,
                article,
                {"action": "delete_article"},
            )
            article.delete()
            return True, status.HTTP_200_OK, None

        return False, status.HTTP_400_BAD_REQUEST, "Invalid moderation action."

    @action(
        detail=True, methods=["post"], permission_classes=[AuthenticatedAndNotBanned]
    )
    def publish(self, request, pk=None):
        article = self.get_object()
        ok, error_status, detail = self._apply_article_moderation(
            article, request.user, "publish"
        )
        if not ok:
            return Response({"detail": detail}, status=error_status)
        return Response({"status": article.status})

    def destroy(self, request, *args, **kwargs):
        article = self.get_object()
        ok, error_status, detail = self._apply_article_moderation(
            article, request.user, "delete"
        )
        if not ok:
            return Response({"detail": detail}, status=error_status)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=False,
        methods=["post"],
        permission_classes=[AuthenticatedAndNotBanned],
        url_path="bulk-moderate",
    )
    def bulk_moderate(self, request):
        raw_ids = request.data.get("ids")
        if not isinstance(raw_ids, list) or not raw_ids:
            return Response(
                {"detail": "ids must be a non-empty list."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(raw_ids) > 200:
            return Response(
                {"detail": "Too many ids, max is 200."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ids = []
        for raw_id in raw_ids:
            try:
                article_id = int(raw_id)
            except (TypeError, ValueError):
                return Response(
                    {"detail": "ids must contain integers."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if article_id <= 0:
                return Response(
                    {"detail": "ids must contain positive integers."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if article_id not in ids:
                ids.append(article_id)

        action_name = str(request.data.get("action", "")).strip().lower()
        if action_name not in {"publish", "hide", "delete"}:
            return Response(
                {"detail": "action must be publish, hide or delete."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        article_map = {
            item.id: item
            for item in self.get_queryset()
            .filter(id__in=ids)
            .select_related("category", "author", "last_editor")
        }

        results = []
        success_count = 0
        for article_id in ids:
            article = article_map.get(article_id)
            if not article:
                results.append(
                    {
                        "id": article_id,
                        "success": False,
                        "detail": "Article not found or inaccessible.",
                    }
                )
                continue

            ok, _, detail = self._apply_article_moderation(
                article, request.user, action_name
            )
            if ok:
                success_count += 1
                status_value = (
                    action_name if action_name == "delete" else article.status
                )
                results.append(
                    {"id": article_id, "success": True, "status": status_value}
                )
            else:
                results.append({"id": article_id, "success": False, "detail": detail})

        return Response(
            {
                "total": len(ids),
                "success": success_count,
                "failed": len(ids) - success_count,
                "results": results,
            }
        )


class ArticleCommentViewSet(ReviewNoteActionMixin, ActionThrottleMixin, viewsets.ModelViewSet):
    serializer_class = ArticleCommentSerializer
    queryset = ArticleComment.objects.select_related(
        "article", "author", "parent", "reviewer"
    ).all()
    throttle_action_classes = {
        "create": [ContentCreateRateThrottle],
        "update": [ContentUpdateRateThrottle],
        "partial_update": [ContentUpdateRateThrottle],
        "destroy": [ContentDeleteRateThrottle],
    }

    def get_permissions(self):
        if self.action == "bulk_hide":
            return [AdminOrSuperAdmin()]
        if self.action in {"approve", "reject", "bulk_review", "append_review_note"}:
            return [AdminOrSuperAdmin()]
        if self.action in {"list", "retrieve"}:
            return [AllowAny()]
        return [AuthenticatedAndNotBanned()]

    def get_queryset(self):
        queryset = super().get_queryset()
        article_id = self.request.query_params.get("article")
        if article_id:
            queryset = queryset.filter(article_id=article_id)

        user = self.request.user
        status_filter = self.request.query_params.get("status")
        status_filter = status_filter.strip() if isinstance(status_filter, str) else ""

        if is_manager(user):
            if status_filter in dict(ArticleComment.Status.choices):
                queryset = queryset.filter(status=status_filter)
            elif self.action != "append_review_note":
                queryset = queryset.exclude(status=ArticleComment.Status.HIDDEN)
        elif user and user.is_authenticated and user.role == User.Role.SCHOOL:
            review_scope = Q(
                article__category__moderation_scope=Category.ModerationScope.SCHOOL
            ) | Q(author=user)
            if self.action in {"approve", "reject", "bulk_review"}:
                queryset = queryset.filter(review_scope)
                if status_filter in dict(ArticleComment.Status.choices):
                    queryset = queryset.filter(status=status_filter)
                return queryset
            if status_filter in dict(ArticleComment.Status.choices):
                if status_filter == ArticleComment.Status.VISIBLE:
                    queryset = queryset.filter(status=ArticleComment.Status.VISIBLE)
                else:
                    queryset = queryset.filter(status=status_filter).filter(
                        review_scope
                    )
            else:
                queryset = queryset.filter(
                    Q(status=ArticleComment.Status.VISIBLE)
                    | Q(author=user, status=ArticleComment.Status.PENDING)
                )
        elif user and user.is_authenticated:
            queryset = queryset.filter(
                Q(status=ArticleComment.Status.VISIBLE)
                | Q(author=user, status=ArticleComment.Status.PENDING)
            )
        else:
            queryset = queryset.filter(status=ArticleComment.Status.VISIBLE)

        author_filter = self.request.query_params.get("author")
        if author_filter:
            author_filter = author_filter.strip()
            if author_filter.isdigit():
                queryset = queryset.filter(author_id=int(author_filter))
            else:
                queryset = queryset.filter(author__username__icontains=author_filter)

        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(content__icontains=search.strip())

        return queryset

    @action(
        detail=False, methods=["get"], permission_classes=[AuthenticatedAndNotBanned]
    )
    def mine(self, request):
        queryset = (
            ArticleComment.objects.filter(author=request.user)
            .select_related("article", "author", "parent")
            .order_by("-created_at")
        )
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        article = serializer.validated_data["article"]

        if article.status != Article.Status.PUBLISHED and not can_moderate_category(
            request.user, article.category
        ):
            return Response(
                {"detail": "Article not available for commenting."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not article.allow_comments:
            return Response(
                {"detail": "Comments are disabled for this article."},
                status=status.HTTP_403_FORBIDDEN,
            )

        is_reviewer = can_moderate_category(request.user, article.category)
        comment_status = (
            ArticleComment.Status.VISIBLE
            if is_reviewer
            else ArticleComment.Status.PENDING
        )
        comment = serializer.save(author=request.user, status=comment_status)
        log_event(
            request.user,
            ContributionEvent.EventType.COMMENT,
            comment,
            {"article_id": article.id},
        )
        if (
            comment.status == ArticleComment.Status.VISIBLE
            and article.author_id != request.user.id
        ):
            create_notification(
                user=article.author,
                actor=request.user,
                target=comment,
                title=f"条目收到新评论：{article.title}",
                content=comment.content[:120],
                link=f"/wiki/{article.id}",
            )
        return Response(
            self.get_serializer(comment).data, status=status.HTTP_201_CREATED
        )

    def update(self, request, *args, **kwargs):
        comment = self.get_object()
        partial = kwargs.pop("partial", False)
        manager = is_manager(request.user)
        if comment.author_id != request.user.id and not manager:
            return Response(
                {"detail": "You cannot edit this comment."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = self.get_serializer(comment, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        next_status = comment.status if manager else ArticleComment.Status.PENDING
        serializer.save(status=next_status)
        log_event(
            request.user,
            (
                ContributionEvent.EventType.ADMIN
                if manager
                else ContributionEvent.EventType.COMMENT
            ),
            comment,
            {
                "action": "update_comment",
                "status": next_status,
                "article_id": comment.article_id,
            },
        )
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        comment = self.get_object()
        manager = is_manager(request.user)
        if comment.author_id != request.user.id and not manager:
            return Response(
                {"detail": "You cannot remove this comment."},
                status=status.HTTP_403_FORBIDDEN,
            )
        comment.status = ArticleComment.Status.HIDDEN
        update_fields = ["status", "updated_at"]
        if manager:
            comment.reviewer = request.user
            comment.review_note = ""
            comment.reviewed_at = timezone.now()
            update_fields.extend(["reviewer", "review_note", "reviewed_at"])
        comment.save(update_fields=update_fields)
        if manager:
            log_event(
                request.user,
                ContributionEvent.EventType.ADMIN,
                comment,
                {"action": "hide_comment", "article_id": comment.article_id},
            )
        else:
            log_event(
                request.user,
                ContributionEvent.EventType.COMMENT,
                comment,
                {"action": "hide_own_comment", "article_id": comment.article_id},
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _can_review_comment(self, reviewer, comment) -> bool:
        return is_manager(reviewer)

    def _apply_review_action(self, *, comment, reviewer, action, review_note=""):
        if not self._can_review_comment(reviewer, comment):
            return (
                False,
                status.HTTP_403_FORBIDDEN,
                "No permission to review this comment.",
            )
        if comment.status != ArticleComment.Status.PENDING:
            return False, status.HTTP_400_BAD_REQUEST, "Comment is not pending review."

        review_note = normalize_review_note(review_note)
        if action == "approve":
            comment.status = ArticleComment.Status.VISIBLE
            action_name = "approve_comment"
        elif action == "reject":
            comment.status = ArticleComment.Status.HIDDEN
            action_name = "reject_comment"
        else:
            return False, status.HTTP_400_BAD_REQUEST, "Invalid review action."

        comment.reviewer = reviewer
        comment.review_note = review_note
        comment.reviewed_at = timezone.now()
        comment.save(
            update_fields=[
                "status",
                "reviewer",
                "review_note",
                "reviewed_at",
                "updated_at",
            ]
        )
        log_event(
            reviewer,
            ContributionEvent.EventType.ADMIN,
            comment,
            {
                "action": action_name,
                "article_id": comment.article_id,
                "review_note": (review_note or "")[:500],
            },
        )

        if comment.author_id != reviewer.id:
            create_notification(
                user=comment.author,
                actor=reviewer,
                target=comment,
                title="评论审核结果通知",
                content=build_review_notification_content(
                    action=action,
                    review_note=review_note,
                    approved_fallback=f"你的评论已通过审核：{comment.article.title}",
                    rejected_fallback="请根据管理员批注修改后重新提交。",
                ),
                link=f"/wiki/{comment.article_id}",
                level=(
                    UserNotification.Level.WARNING
                    if action == "reject"
                    else UserNotification.Level.INFO
                ),
            )
        if action == "approve" and comment.article.author_id != comment.author_id:
            create_notification(
                user=comment.article.author,
                actor=comment.author,
                target=comment,
                title=f"条目收到新评论：{comment.article.title}",
                content=comment.content[:120],
                link=f"/wiki/{comment.article_id}",
            )

        return True, status.HTTP_200_OK, ""

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        comment = self.get_object()
        ok, http_status, detail = self._apply_review_action(
            comment=comment,
            reviewer=request.user,
            action="approve",
            review_note=request.data.get("review_note", ""),
        )
        if not ok:
            return Response({"detail": detail}, status=http_status)
        return Response(self.get_serializer(comment).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        comment = self.get_object()
        ok, http_status, detail = self._apply_review_action(
            comment=comment,
            reviewer=request.user,
            action="reject",
            review_note=request.data.get("review_note", ""),
        )
        if not ok:
            return Response({"detail": detail}, status=http_status)
        return Response(self.get_serializer(comment).data)

    @action(detail=False, methods=["post"], url_path="bulk-review")
    def bulk_review(self, request):
        raw_ids = request.data.get("ids")
        action_name = request.data.get("action")
        review_note = request.data.get("review_note", "")
        if not isinstance(raw_ids, list) or not raw_ids:
            return Response(
                {"detail": "ids must be a non-empty list."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if action_name not in {"approve", "reject"}:
            return Response(
                {"detail": "action must be approve or reject."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(raw_ids) > 200:
            return Response(
                {"detail": "Too many ids, max is 200."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ids = []
        for raw_id in raw_ids:
            try:
                comment_id = int(raw_id)
            except (TypeError, ValueError):
                return Response(
                    {"detail": "ids must contain integers."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if comment_id <= 0:
                return Response(
                    {"detail": "ids must contain positive integers."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if comment_id not in ids:
                ids.append(comment_id)

        comments = {
            item.id: item
            for item in ArticleComment.objects.filter(id__in=ids).select_related(
                "article", "author", "article__category"
            )
        }

        results = []
        success_count = 0
        for comment_id in ids:
            comment = comments.get(comment_id)
            if not comment:
                results.append(
                    {"id": comment_id, "success": False, "detail": "Comment not found."}
                )
                continue

            ok, _, detail = self._apply_review_action(
                comment=comment,
                reviewer=request.user,
                action=action_name,
                review_note=review_note,
            )
            if ok:
                success_count += 1
                results.append(
                    {"id": comment_id, "success": True, "status": comment.status}
                )
            else:
                results.append({"id": comment_id, "success": False, "detail": detail})

        return Response(
            {
                "total": len(ids),
                "success": success_count,
                "failed": len(ids) - success_count,
                "results": results,
            }
        )

    @action(
        detail=False,
        methods=["post"],
        permission_classes=[AdminOrSuperAdmin],
        url_path="bulk-hide",
    )
    def bulk_hide(self, request):
        raw_ids = request.data.get("ids")
        if not isinstance(raw_ids, list) or not raw_ids:
            return Response(
                {"detail": "ids must be a non-empty list."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(raw_ids) > 200:
            return Response(
                {"detail": "Too many ids, max is 200."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ids = []
        for raw_id in raw_ids:
            try:
                comment_id = int(raw_id)
            except (TypeError, ValueError):
                return Response(
                    {"detail": "ids must contain integers."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if comment_id <= 0:
                return Response(
                    {"detail": "ids must contain positive integers."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if comment_id not in ids:
                ids.append(comment_id)

        comment_map = {
            item.id: item
            for item in ArticleComment.objects.filter(id__in=ids).select_related(
                "article", "author", "parent"
            )
        }

        results = []
        success_count = 0
        for comment_id in ids:
            comment = comment_map.get(comment_id)
            if not comment:
                results.append(
                    {"id": comment_id, "success": False, "detail": "Comment not found."}
                )
                continue

            if comment.status != ArticleComment.Status.HIDDEN:
                comment.status = ArticleComment.Status.HIDDEN
                comment.save(update_fields=["status", "updated_at"])
            log_event(
                request.user,
                ContributionEvent.EventType.ADMIN,
                comment,
                {"action": "hide_comment_bulk", "article_id": comment.article_id},
            )
            success_count += 1
            results.append(
                {"id": comment_id, "success": True, "status": comment.status}
            )

        return Response(
            {
                "total": len(ids),
                "success": success_count,
                "failed": len(ids) - success_count,
                "results": results,
            }
        )


class RevisionProposalViewSet(ReviewNoteActionMixin, ActionThrottleMixin, viewsets.ModelViewSet):
    serializer_class = RevisionProposalSerializer
    queryset = RevisionProposal.objects.select_related(
        "article", "proposer", "reviewer", "article__category"
    ).all()
    permission_classes = [AuthenticatedAndNotBanned]
    MAX_PENDING_PER_USER = 5
    throttle_action_classes = {
        "create": [ContentCreateRateThrottle],
        "update": [ContentUpdateRateThrottle],
        "partial_update": [ContentUpdateRateThrottle],
        "destroy": [ContentDeleteRateThrottle],
    }

    def _normalize_title(self, value, *, fallback=""):
        text = str(value or "").strip()
        if text:
            return text
        return str(fallback or "")

    def _serialize_snapshot(self, snapshot):
        updated_at = snapshot.updated_at
        if updated_at is not None and timezone.is_naive(updated_at):
            updated_at = timezone.make_aware(updated_at, timezone.get_current_timezone())
        return {
            "title": snapshot.title,
            "summary": snapshot.summary,
            "content_md": snapshot.content_md,
            "updated_at": timezone.localtime(updated_at).isoformat() if updated_at is not None else None,
        }

    def _build_payload_base_snapshot(self, *, payload, fallback_snapshot):
        payload = payload or {}
        return build_snapshot(
            title=self._normalize_title(payload.get("base_title", fallback_snapshot.title), fallback=fallback_snapshot.title),
            summary=payload.get("base_summary", fallback_snapshot.summary),
            content_md=payload.get("base_content_md", fallback_snapshot.content_md),
            updated_at=payload.get("base_updated_at", fallback_snapshot.updated_at),
        )

    def _build_payload_proposed_snapshot(self, *, payload, fallback_snapshot):
        payload = payload or {}
        return build_snapshot(
            title=self._normalize_title(payload.get("proposed_title", fallback_snapshot.title), fallback=fallback_snapshot.title),
            summary=payload.get("proposed_summary", fallback_snapshot.summary),
            content_md=payload.get("proposed_content_md", fallback_snapshot.content_md),
        )

    def _build_proposal_base_snapshot(self, proposal):
        article_snapshot = snapshot_article(proposal.article)
        legacy_empty = (
            proposal.base_updated_at is None
            and not str(proposal.base_title or "").strip()
            and not str(proposal.base_summary or "")
            and not str(proposal.base_content_md or "")
        )
        if legacy_empty:
            return article_snapshot
        return build_snapshot(
            title=self._normalize_title(proposal.base_title, fallback=article_snapshot.title),
            summary=proposal.base_summary,
            content_md=proposal.base_content_md,
            updated_at=proposal.base_updated_at or article_snapshot.updated_at,
        )

    def _build_proposal_proposed_snapshot(self, proposal):
        base_snapshot = self._build_proposal_base_snapshot(proposal)
        return build_snapshot(
            title=self._normalize_title(proposal.proposed_title, fallback=base_snapshot.title),
            summary=proposal.proposed_summary,
            content_md=proposal.proposed_content_md,
        )

    def _snapshot_save_kwargs(self, *, base_snapshot, proposed_snapshot):
        return {
            "base_title": base_snapshot.title,
            "base_summary": base_snapshot.summary,
            "base_content_md": base_snapshot.content_md,
            "base_updated_at": base_snapshot.updated_at,
            "proposed_title": proposed_snapshot.title,
            "proposed_summary": proposed_snapshot.summary,
            "proposed_content_md": proposed_snapshot.content_md,
        }

    def _build_merge_conflict_response(self, *, base_snapshot, current_snapshot, proposed_snapshot, merge_result, detail):
        return Response(
            {
                "detail": detail,
                "code": "revision_merge_conflict",
                "merge": {
                    "base": self._serialize_snapshot(base_snapshot),
                    "current": self._serialize_snapshot(current_snapshot),
                    "proposed": self._serialize_snapshot(proposed_snapshot),
                    "merged": self._serialize_snapshot(merge_result["merged"]),
                    "conflicts": merge_result["conflicts"],
                    "rebased": bool(merge_result.get("rebased")),
                },
            },
            status=status.HTTP_409_CONFLICT,
        )

    def _apply_snapshot_to_article(self, *, article, snapshot, editor):
        article.title = snapshot.title
        article.summary = snapshot.summary
        article.content_md = snapshot.content_md
        article.last_editor = editor
        article.status = Article.Status.PUBLISHED
        article.save()

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if is_manager(user):
            pass
        else:
            queryset = queryset.filter(proposer=user)

        status_filter = self.request.query_params.get("status")
        if status_filter in dict(RevisionProposal.Status.choices):
            queryset = queryset.filter(status=status_filter)

        proposer_filter = self.request.query_params.get("proposer")
        if proposer_filter:
            proposer_filter = proposer_filter.strip()
            if proposer_filter.isdigit():
                queryset = queryset.filter(proposer_id=int(proposer_filter))
            else:
                queryset = queryset.filter(
                    proposer__username__icontains=proposer_filter
                )

        search = self.request.query_params.get("search")
        if search:
            search = search.strip()
            queryset = queryset.filter(
                Q(article__title__icontains=search)
                | Q(proposed_title__icontains=search)
                | Q(reason__icontains=search)
            )

        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target_article = serializer.validated_data["article"]
        article_snapshot = snapshot_article(target_article)
        base_snapshot = self._build_payload_base_snapshot(
            payload=serializer.validated_data,
            fallback_snapshot=article_snapshot,
        )
        proposed_snapshot = self._build_payload_proposed_snapshot(
            payload=serializer.validated_data,
            fallback_snapshot=base_snapshot,
        )
        manager_direct_publish = is_manager(request.user) and can_moderate_category(
            request.user,
            target_article.category,
        )

        if not manager_direct_publish:
            pending_count = RevisionProposal.objects.filter(
                proposer=request.user,
                status=RevisionProposal.Status.PENDING,
            ).count()
            if pending_count >= self.MAX_PENDING_PER_USER:
                return Response(
                    {
                        "detail": (
                            f"You can submit at most {self.MAX_PENDING_PER_USER} pending revision proposals. "
                            "Please wait until existing proposals are reviewed."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if manager_direct_publish:
            with transaction.atomic():
                target_article = Article.objects.select_for_update().select_related("category").get(pk=target_article.pk)
                current_snapshot = snapshot_article(target_article)
                merge_result = merge_article_revision(
                    base=base_snapshot,
                    current=current_snapshot,
                    proposed=proposed_snapshot,
                )
                if merge_result["has_conflicts"]:
                    return self._build_merge_conflict_response(
                        base_snapshot=base_snapshot,
                        current_snapshot=current_snapshot,
                        proposed_snapshot=proposed_snapshot,
                        merge_result=merge_result,
                        detail="This article changed while you were editing. Resolve the merge before publishing.",
                    )

                merged_snapshot = merge_result["merged"]
                proposal = serializer.save(
                    proposer=request.user,
                    **self._snapshot_save_kwargs(
                        base_snapshot=current_snapshot,
                        proposed_snapshot=merged_snapshot,
                    ),
                    status=RevisionProposal.Status.APPROVED,
                    reviewer=request.user,
                    reviewed_at=timezone.now(),
                    review_note="manager_direct_publish",
                )
                self._apply_snapshot_to_article(
                    article=target_article,
                    snapshot=merged_snapshot,
                    editor=request.user,
                )

            log_event(
                request.user,
                ContributionEvent.EventType.ADMIN,
                proposal,
                {
                    "action": "create_revision_direct_publish",
                    "article_id": proposal.article_id,
                },
            )
            return Response(
                self.get_serializer(proposal).data, status=status.HTTP_201_CREATED
            )

        current_snapshot = snapshot_article(target_article)
        merge_result = merge_article_revision(
            base=base_snapshot,
            current=current_snapshot,
            proposed=proposed_snapshot,
        )
        if merge_result["has_conflicts"]:
            return self._build_merge_conflict_response(
                base_snapshot=base_snapshot,
                current_snapshot=current_snapshot,
                proposed_snapshot=proposed_snapshot,
                merge_result=merge_result,
                detail="This article changed while you were editing. Resolve the merge before submitting again.",
            )

        proposal = serializer.save(
            proposer=request.user,
            **self._snapshot_save_kwargs(
                base_snapshot=current_snapshot,
                proposed_snapshot=merge_result["merged"],
            ),
        )
        log_event(request.user, ContributionEvent.EventType.REVISION, proposal, {"article_id": proposal.article_id})
        return Response(self.get_serializer(proposal).data, status=status.HTTP_201_CREATED)

    def _validate_user_pending_operation(self, user, proposal, *, operation):
        if proposal.proposer_id != user.id:
            return False, Response(
                {"detail": "You can only manage your own revision proposals."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if proposal.status != RevisionProposal.Status.PENDING:
            return False, Response(
                {"detail": f"Only pending revision proposals can be {operation}."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return True, None

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        proposal = self.get_object()
        ok, error_response = self._validate_user_pending_operation(
            request.user,
            proposal,
            operation="updated",
        )
        if not ok:
            return error_response

        serializer = self.get_serializer(proposal, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        stored_base_snapshot = self._build_proposal_base_snapshot(proposal)
        stored_proposed_snapshot = self._build_proposal_proposed_snapshot(proposal)
        base_snapshot = self._build_payload_base_snapshot(
            payload=serializer.validated_data,
            fallback_snapshot=stored_base_snapshot,
        )
        proposed_snapshot = self._build_payload_proposed_snapshot(
            payload=serializer.validated_data,
            fallback_snapshot=stored_proposed_snapshot,
        )
        current_snapshot = snapshot_article(proposal.article)
        merge_result = merge_article_revision(
            base=base_snapshot,
            current=current_snapshot,
            proposed=proposed_snapshot,
        )
        if merge_result["has_conflicts"]:
            return self._build_merge_conflict_response(
                base_snapshot=base_snapshot,
                current_snapshot=current_snapshot,
                proposed_snapshot=proposed_snapshot,
                merge_result=merge_result,
                detail="This article changed while the proposal was being edited. Resolve the merge before saving.",
            )

        proposal = serializer.save(
            **self._snapshot_save_kwargs(
                base_snapshot=current_snapshot,
                proposed_snapshot=merge_result["merged"],
            )
        )
        log_event(
            request.user,
            ContributionEvent.EventType.REVISION,
            proposal,
            {"action": "update_revision", "article_id": proposal.article_id},
        )
        return Response(self.get_serializer(proposal).data)

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        proposal = self.get_object()
        ok, error_response = self._validate_user_pending_operation(
            request.user,
            proposal,
            operation="cancelled",
        )
        if not ok:
            return error_response

        log_event(
            request.user,
            ContributionEvent.EventType.REVISION,
            proposal,
            {"action": "cancel_revision", "article_id": proposal.article_id},
        )
        proposal.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _apply_review_action(self, proposal, reviewer, *, action, review_note=""):
        if not is_manager(reviewer):
            return (
                False,
                status.HTTP_403_FORBIDDEN,
                "No permission to review this proposal.",
            )
        if proposal.status != RevisionProposal.Status.PENDING:
            return False, status.HTTP_400_BAD_REQUEST, "Proposal is already reviewed."

        action = (action or "").strip().lower()
        review_note = "" if review_note is None else str(review_note)
        resolution_base_updated_at = None
        resolved_snapshot = None
        request_data = getattr(getattr(self, "request", None), "data", {}) or {}
        raw_resolution_updated_at = request_data.get("resolution_base_updated_at")
        if raw_resolution_updated_at:
            resolution_base_updated_at = parse_datetime(str(raw_resolution_updated_at))
            if resolution_base_updated_at is not None and timezone.is_naive(resolution_base_updated_at):
                resolution_base_updated_at = timezone.make_aware(
                    resolution_base_updated_at,
                    timezone.get_current_timezone(),
                )
        if any(field in request_data for field in ("resolved_title", "resolved_summary", "resolved_content_md")):
            proposal_base_snapshot = self._build_proposal_base_snapshot(proposal)
            resolved_snapshot = self._build_payload_proposed_snapshot(
                payload={
                    "proposed_title": request_data.get("resolved_title", proposal.proposed_title),
                    "proposed_summary": request_data.get("resolved_summary", proposal.proposed_summary),
                    "proposed_content_md": request_data.get("resolved_content_md", proposal.proposed_content_md),
                },
                fallback_snapshot=proposal_base_snapshot,
            )

        if action == "approve":
            with transaction.atomic():
                proposal = (
                    RevisionProposal.objects.select_for_update()
                    .select_related("article", "proposer", "reviewer")
                    .get(pk=proposal.pk)
                )
                article = Article.objects.select_for_update().get(pk=proposal.article_id)
                proposal.article = article
                current_snapshot = snapshot_article(article)
                base_snapshot = self._build_proposal_base_snapshot(proposal)
                proposed_snapshot = self._build_proposal_proposed_snapshot(proposal)

                if resolved_snapshot is not None:
                    current_updated_at = current_snapshot.updated_at
                    if current_updated_at is not None and timezone.is_naive(current_updated_at):
                        current_updated_at = timezone.make_aware(current_updated_at, timezone.get_current_timezone())
                    if resolution_base_updated_at is not None and current_updated_at != resolution_base_updated_at:
                        merge_result = merge_article_revision(
                            base=base_snapshot,
                            current=current_snapshot,
                            proposed=proposed_snapshot,
                        )
                        return False, status.HTTP_409_CONFLICT, self._build_merge_conflict_response(
                            base_snapshot=base_snapshot,
                            current_snapshot=current_snapshot,
                            proposed_snapshot=proposed_snapshot,
                            merge_result=merge_result,
                            detail="The article changed again before the conflict was resolved. Review the latest merge result and try again.",
                        )
                    merged_snapshot = resolved_snapshot
                    base_snapshot = current_snapshot
                else:
                    merge_result = merge_article_revision(
                        base=base_snapshot,
                        current=current_snapshot,
                        proposed=proposed_snapshot,
                    )
                    if merge_result["has_conflicts"]:
                        return False, status.HTTP_409_CONFLICT, self._build_merge_conflict_response(
                            base_snapshot=base_snapshot,
                            current_snapshot=current_snapshot,
                            proposed_snapshot=proposed_snapshot,
                            merge_result=merge_result,
                            detail="This proposal conflicts with the latest article version. Resolve it before approval.",
                        )
                    merged_snapshot = merge_result["merged"]
                    base_snapshot = current_snapshot

                proposal.base_title = base_snapshot.title
                proposal.base_summary = base_snapshot.summary
                proposal.base_content_md = base_snapshot.content_md
                proposal.base_updated_at = base_snapshot.updated_at
                proposal.proposed_title = merged_snapshot.title
                proposal.proposed_summary = merged_snapshot.summary
                proposal.proposed_content_md = merged_snapshot.content_md
                proposal.status = RevisionProposal.Status.APPROVED
                proposal.reviewer = reviewer
                proposal.review_note = review_note
                proposal.reviewed_at = timezone.now()
                proposal.save(
                    update_fields=[
                        "base_title",
                        "base_summary",
                        "base_content_md",
                        "base_updated_at",
                        "proposed_title",
                        "proposed_summary",
                        "proposed_content_md",
                        "status",
                        "reviewer",
                        "review_note",
                        "reviewed_at",
                        "updated_at",
                    ]
                )

                self._apply_snapshot_to_article(
                    article=article,
                    snapshot=merged_snapshot,
                    editor=reviewer,
                )
        elif action == "reject":
            proposal.status = RevisionProposal.Status.REJECTED
            proposal.reviewer = reviewer
            proposal.review_note = review_note
            proposal.reviewed_at = timezone.now()
            proposal.save(
                update_fields=[
                    "status",
                    "reviewer",
                    "review_note",
                    "reviewed_at",
                    "updated_at",
                ]
            )
        else:
            return False, status.HTTP_400_BAD_REQUEST, "Invalid review action."

        log_event(
            reviewer,
            ContributionEvent.EventType.ADMIN,
            proposal,
            {"action": f"{action}_revision"},
        )
        if proposal.proposer_id != reviewer.id:
            status_text = "已通过" if action == "approve" else "已驳回"
            create_notification(
                user=proposal.proposer,
                actor=reviewer,
                target=proposal,
                title=f"修订提议{status_text}：{proposal.article.title}",
                content=(
                    review_note[:180] if review_note else "管理员已处理你的修订提议。"
                ),
                link=f"/wiki/{proposal.article_id}",
                level=(
                    UserNotification.Level.WARNING
                    if action == "reject"
                    else UserNotification.Level.INFO
                ),
            )
        return True, status.HTTP_200_OK, None

    @action(
        detail=True, methods=["post"], permission_classes=[AuthenticatedAndNotBanned]
    )
    def approve(self, request, pk=None):
        proposal = self.get_object()
        ok, error_status, detail = self._apply_review_action(
            proposal,
            request.user,
            action="approve",
            review_note=request.data.get("review_note", ""),
        )
        if not ok:
            if isinstance(detail, Response):
                return detail
            return Response({"detail": detail}, status=error_status)
        proposal.refresh_from_db()
        return Response(self.get_serializer(proposal).data)

    @action(
        detail=True, methods=["post"], permission_classes=[AuthenticatedAndNotBanned]
    )
    def reject(self, request, pk=None):
        proposal = self.get_object()
        ok, error_status, detail = self._apply_review_action(
            proposal,
            request.user,
            action="reject",
            review_note=request.data.get("review_note", ""),
        )
        if not ok:
            if isinstance(detail, Response):
                return detail
            return Response({"detail": detail}, status=error_status)
        proposal.refresh_from_db()
        return Response(self.get_serializer(proposal).data)

    @action(
        detail=False,
        methods=["post"],
        permission_classes=[AdminOrSuperAdmin],
        url_path="bulk-review",
    )
    def bulk_review(self, request):
        raw_ids = request.data.get("ids")
        if not isinstance(raw_ids, list) or not raw_ids:
            return Response(
                {"detail": "ids must be a non-empty list."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(raw_ids) > 200:
            return Response(
                {"detail": "Too many ids, max is 200."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ids = []
        for raw_id in raw_ids:
            try:
                proposal_id = int(raw_id)
            except (TypeError, ValueError):
                return Response(
                    {"detail": "ids must contain integers."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if proposal_id <= 0:
                return Response(
                    {"detail": "ids must contain positive integers."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if proposal_id not in ids:
                ids.append(proposal_id)

        action_name = str(request.data.get("action", "")).strip().lower()
        if action_name not in {"approve", "reject"}:
            return Response(
                {"detail": "action must be approve or reject."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        review_note = request.data.get("review_note", "")
        proposal_map = {
            item.id: item
            for item in self.get_queryset()
            .filter(id__in=ids)
            .select_related("article", "article__category", "proposer", "reviewer")
        }

        results = []
        success_count = 0
        for proposal_id in ids:
            proposal = proposal_map.get(proposal_id)
            if not proposal:
                results.append(
                    {
                        "id": proposal_id,
                        "success": False,
                        "detail": "Proposal not found or inaccessible.",
                    }
                )
                continue

            ok, error_status, detail = self._apply_review_action(
                proposal,
                request.user,
                action=action_name,
                review_note=review_note,
            )
            if ok:
                proposal.refresh_from_db()
                success_count += 1
                results.append(
                    {"id": proposal_id, "success": True, "status": proposal.status}
                )
            else:
                if isinstance(detail, Response):
                    payload = getattr(detail, "data", {}) or {}
                    result_detail = payload.get("detail") if isinstance(payload, dict) else str(payload)
                    result_code = payload.get("code") if isinstance(payload, dict) else ""
                else:
                    result_detail = detail
                    result_code = ""
                results.append(
                    {
                        "id": proposal_id,
                        "success": False,
                        "detail": result_detail,
                        "code": result_code,
                        "status": error_status,
                    }
                )

        return Response(
            {
                "total": len(ids),
                "success": success_count,
                "failed": len(ids) - success_count,
                "results": results,
            }
        )


class IssueTicketViewSet(ReviewNoteActionMixin, ActionThrottleMixin, viewsets.ModelViewSet):
    serializer_class = IssueTicketSerializer
    queryset = IssueTicket.objects.select_related(
        "author", "assignee", "related_article", "reviewer"
    ).all()
    permission_classes = [AuthenticatedAndNotBanned]
    throttle_action_classes = {
        "create": [ContentCreateRateThrottle],
        "update": [ContentUpdateRateThrottle],
        "partial_update": [ContentUpdateRateThrottle],
        "destroy": [ContentDeleteRateThrottle],
    }

    def get_permissions(self):
        if self.action in {"set_status", "bulk_set_status", "append_review_note"}:
            return [AdminOrSuperAdmin()]
        return super().get_permissions()

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        manager = is_manager(user)
        mine_only = self.request.query_params.get("mine") == "1"

        if manager:
            pass
        elif mine_only:
            queryset = queryset.filter(author=user)
        elif user.role == User.Role.SCHOOL:
            queryset = queryset.filter(
                Q(author=user)
                | (
                    Q(visibility=IssueTicket.Visibility.PUBLIC)
                    & (Q(assignee=user) | ~Q(status=IssueTicket.Status.PENDING))
                )
            )
        else:
            queryset = queryset.filter(
                Q(author=user)
                | (
                    Q(visibility=IssueTicket.Visibility.PUBLIC)
                    & ~Q(status=IssueTicket.Status.PENDING)
                )
            )

        if user.role == User.Role.SCHOOL and not manager:
            scope = self.request.query_params.get("scope")
            if scope == "assigned":
                queryset = queryset.filter(
                    assignee=user,
                    visibility=IssueTicket.Visibility.PUBLIC,
                )
            elif scope in {"created", "mine"}:
                queryset = queryset.filter(author=user)
            elif scope == "public":
                queryset = queryset.filter(
                    visibility=IssueTicket.Visibility.PUBLIC,
                ).filter(Q(assignee=user) | ~Q(status=IssueTicket.Status.PENDING))

        visibility_filter = self.request.query_params.get("visibility")
        if visibility_filter in dict(IssueTicket.Visibility.choices):
            queryset = queryset.filter(visibility=visibility_filter)

        status_filter = self.request.query_params.get("status")
        if status_filter in dict(IssueTicket.Status.choices):
            queryset = queryset.filter(status=status_filter)

        kind_filter = self.request.query_params.get("kind")
        if kind_filter in dict(IssueTicket.Kind.choices):
            queryset = queryset.filter(kind=kind_filter)

        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search.strip())
                | Q(content__icontains=search.strip())
            )

        if manager:
            author_filter = self.request.query_params.get("author")
            if author_filter:
                author_filter = author_filter.strip()
                if author_filter.isdigit():
                    queryset = queryset.filter(author_id=int(author_filter))
                else:
                    queryset = queryset.filter(
                        author__username__icontains=author_filter
                    )

            assignee_filter = self.request.query_params.get("assignee")
            if assignee_filter:
                assignee_filter = assignee_filter.strip()
                lowered = assignee_filter.lower()
                if lowered in {"none", "null", "unassigned", "0"}:
                    queryset = queryset.filter(assignee__isnull=True)
                elif assignee_filter.isdigit():
                    queryset = queryset.filter(assignee_id=int(assignee_filter))
                else:
                    queryset = queryset.filter(
                        assignee__username__icontains=assignee_filter
                    )

        order = self.request.query_params.get("order")
        if order == "created_oldest":
            return queryset.order_by("created_at")
        if order == "created_newest":
            return queryset.order_by("-created_at")
        if order == "updated_oldest":
            return queryset.order_by("updated_at")
        return queryset.order_by("-updated_at")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        initial_status = (
            IssueTicket.Status.OPEN
            if request.user.role
            in {User.Role.SCHOOL, User.Role.ADMIN, User.Role.SUPERADMIN}
            else IssueTicket.Status.PENDING
        )
        ticket = serializer.save(author=request.user, status=initial_status)
        log_event(request.user, ContributionEvent.EventType.ISSUE, ticket)
        return Response(
            self.get_serializer(ticket).data, status=status.HTTP_201_CREATED
        )

    def _apply_status_update(
        self,
        *,
        ticket,
        operator,
        new_status,
        assign_to=UNSET,
        resolution_note=UNSET,
    ):
        manager = is_manager(operator)
        if not manager:
            return (
                False,
                status.HTTP_403_FORBIDDEN,
                "No permission to update this ticket.",
            )

        if new_status not in dict(IssueTicket.Status.choices):
            return False, status.HTTP_400_BAD_REQUEST, "Invalid status."
        ticket.status = new_status

        assign_to_given = assign_to is not UNSET
        assignee_id_for_event = ticket.assignee_id

        if assign_to_given:
            assign_text = (
                str(assign_to).strip().lower() if assign_to is not None else ""
            )
            if assign_text in {"", "null", "none", "0"}:
                ticket.assignee = None
                assignee_id_for_event = None
            else:
                try:
                    assign_to_id = int(assign_to)
                except (TypeError, ValueError):
                    return False, status.HTTP_400_BAD_REQUEST, "Invalid assignee id."
                assignee = User.objects.filter(
                    id=assign_to_id,
                    is_active=True,
                    is_banned=False,
                    role__in=[User.Role.SCHOOL, User.Role.ADMIN, User.Role.SUPERADMIN],
                ).first()
                if not assignee:
                    return (
                        False,
                        status.HTTP_400_BAD_REQUEST,
                        "Assignee is not available.",
                    )
                if (
                    ticket.visibility == IssueTicket.Visibility.PRIVATE
                    and assignee.role == User.Role.SCHOOL
                ):
                    return (
                        False,
                        status.HTTP_400_BAD_REQUEST,
                        "Private tickets can only be handled by admins.",
                    )
                ticket.assignee = assignee
                assignee_id_for_event = assignee.id

        resolution_note_given = resolution_note is not UNSET
        if resolution_note_given:
            ticket.resolution_note = normalize_review_note(resolution_note)
            ticket.review_note = ticket.resolution_note

        if new_status != IssueTicket.Status.PENDING:
            ticket.reviewer = operator
            ticket.reviewed_at = timezone.now()

        update_fields = ["status", "updated_at"]
        if assign_to_given:
            update_fields.append("assignee")
        if resolution_note_given:
            update_fields.append("resolution_note")
            update_fields.append("review_note")
        if new_status != IssueTicket.Status.PENDING:
            update_fields.extend(["reviewer", "reviewed_at"])
        ticket.save(update_fields=update_fields)

        payload = {"action": "update_issue_status", "status": ticket.status}
        if assign_to_given:
            payload["assign_to"] = assignee_id_for_event
        if resolution_note_given:
            payload["resolution_note"] = ticket.resolution_note
        log_event(operator, ContributionEvent.EventType.ADMIN, ticket, payload)

        if ticket.author_id != operator.id:
            create_notification(
                user=ticket.author,
                actor=operator,
                target=ticket,
                title=f"工单状态已更新：{ticket.title}",
                content=build_review_notification_content(
                    action="reject" if ticket.status == IssueTicket.Status.REJECTED else "approve",
                    review_note=ticket.resolution_note,
                    approved_fallback=f"当前状态：{ticket.get_status_display()}",
                    rejected_fallback="你的工单已被驳回，请查看处理批注。",
                ),
                link="/profile",
                level=(
                    UserNotification.Level.WARNING
                    if ticket.status == IssueTicket.Status.REJECTED
                    else UserNotification.Level.INFO
                ),
            )

        if assign_to_given and ticket.assignee_id and ticket.assignee_id != operator.id:
            create_notification(
                user=ticket.assignee,
                actor=operator,
                target=ticket,
                title=f"你被指派处理工单：{ticket.title}",
                content=f"状态：{ticket.status}",
                link="/review",
            )
        return True, status.HTTP_200_OK, None

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        ticket = self.get_object()
        manager = is_manager(request.user)

        if not manager and ticket.author_id != request.user.id:
            return Response(
                {"detail": "No permission to edit this ticket."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = self.get_serializer(ticket, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        next_visibility = serializer.validated_data.get("visibility", ticket.visibility)
        if manager and (
            next_visibility == IssueTicket.Visibility.PRIVATE
            and ticket.assignee_id
            and ticket.assignee
            and ticket.assignee.role == User.Role.SCHOOL
        ):
            return Response(
                {"detail": "Private tickets cannot stay assigned to school reviewers."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        save_kwargs = {}
        event_type = (
            ContributionEvent.EventType.ADMIN
            if manager
            else ContributionEvent.EventType.ISSUE
        )
        event_payload = {"action": "update_issue"}
        if not manager:
            save_kwargs.update(
                {
                    "status": IssueTicket.Status.PENDING,
                    "assignee": None,
                    "resolution_note": "",
                }
            )
            event_payload["status"] = IssueTicket.Status.PENDING
            event_payload["requires_review"] = True
        serializer.save(**save_kwargs)
        log_event(request.user, event_type, ticket, event_payload)
        return Response(serializer.data)

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        ticket = self.get_object()
        if not is_manager(request.user):
            return Response(
                {"detail": "Only admins can delete tickets."},
                status=status.HTTP_403_FORBIDDEN,
            )
        with transaction.atomic():
            archive_deleted_content(
                instance=ticket,
                operator=request.user,
                delete_action=DeletedContentArchive.DeleteAction.DELETE,
            )
            log_event(
                request.user,
                ContributionEvent.EventType.ADMIN,
                ticket,
                {"action": "delete_issue"},
            )
            self.perform_destroy(ticket)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], permission_classes=[AdminOrSuperAdmin])
    def set_status(self, request, pk=None):
        ticket = self.get_object()
        assign_to = (
            request.data.get("assign_to", UNSET)
            if "assign_to" in request.data
            else UNSET
        )
        resolution_note = (
            request.data.get("resolution_note", UNSET)
            if "resolution_note" in request.data
            else UNSET
        )
        ok, error_status, detail = self._apply_status_update(
            ticket=ticket,
            operator=request.user,
            new_status=request.data.get("status"),
            assign_to=assign_to,
            resolution_note=resolution_note,
        )
        if not ok:
            return Response({"detail": detail}, status=error_status)
        return Response(self.get_serializer(ticket).data)

    @action(
        detail=False,
        methods=["post"],
        permission_classes=[AdminOrSuperAdmin],
        url_path="bulk-set-status",
    )
    def bulk_set_status(self, request):
        raw_ids = request.data.get("ids")
        if not isinstance(raw_ids, list) or not raw_ids:
            return Response(
                {"detail": "ids must be a non-empty list."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(raw_ids) > 200:
            return Response(
                {"detail": "Too many ids, max is 200."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ids = []
        for raw_id in raw_ids:
            try:
                ticket_id = int(raw_id)
            except (TypeError, ValueError):
                return Response(
                    {"detail": "ids must contain integers."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if ticket_id <= 0:
                return Response(
                    {"detail": "ids must contain positive integers."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if ticket_id not in ids:
                ids.append(ticket_id)

        status_value = request.data.get("status")
        assign_to = (
            request.data.get("assign_to", UNSET)
            if "assign_to" in request.data
            else UNSET
        )
        resolution_note = (
            request.data.get("resolution_note", UNSET)
            if "resolution_note" in request.data
            else UNSET
        )

        ticket_map = {
            ticket.id: ticket
            for ticket in self.get_queryset()
            .filter(id__in=ids)
            .select_related("author", "assignee", "related_article")
        }
        results = []
        success_count = 0
        for ticket_id in ids:
            ticket = ticket_map.get(ticket_id)
            if not ticket:
                results.append(
                    {
                        "id": ticket_id,
                        "success": False,
                        "detail": "Ticket not found or inaccessible.",
                    }
                )
                continue

            ok, _, detail = self._apply_status_update(
                ticket=ticket,
                operator=request.user,
                new_status=status_value,
                assign_to=assign_to,
                resolution_note=resolution_note,
            )
            if ok:
                success_count += 1
                results.append(
                    {"id": ticket_id, "success": True, "status": ticket.status}
                )
            else:
                results.append({"id": ticket_id, "success": False, "detail": detail})

        return Response(
            {
                "total": len(ids),
                "success": success_count,
                "failed": len(ids) - success_count,
                "results": results,
            }
        )


class TrickEntryViewSet(ReviewNoteActionMixin, ActionThrottleMixin, viewsets.ModelViewSet):
    serializer_class = TrickEntrySerializer
    queryset = (
        TrickEntry.objects.select_related("author", "reviewer")
        .prefetch_related("terms")
        .all()
    )
    throttle_action_classes = {
        "create": [ContentCreateRateThrottle],
        "update": [ContentUpdateRateThrottle],
        "partial_update": [ContentUpdateRateThrottle],
        "destroy": [ContentDeleteRateThrottle],
    }

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [AllowAny()]
        if self.action == "create":
            return [AuthenticatedAndNotBanned()]
        if self.action in {"update", "partial_update", "destroy", "like", "unlike"}:
            return [AuthenticatedAndNotBanned()]
        return [AdminOrSuperAdmin()]

    def get_queryset(self):
        queryset = super().get_queryset().annotate(
            like_count=Count("like_records", distinct=True)
        )
        user = self.request.user
        if user and user.is_authenticated:
            queryset = queryset.annotate(
                is_liked=Exists(
                    TrickEntryLike.objects.filter(
                        user=user, trick_entry_id=OuterRef("pk")
                    )
                )
            )
        include_all = self.request.query_params.get("include_all") == "1"
        if is_manager(user):
            if not include_all and self.action != "append_review_note":
                queryset = queryset.exclude(status=TrickEntry.Status.REJECTED)
        elif user and user.is_authenticated:
            queryset = queryset.filter(
                Q(status=TrickEntry.Status.APPROVED)
                | Q(author=user, status=TrickEntry.Status.PENDING)
            )
        else:
            queryset = queryset.filter(status=TrickEntry.Status.APPROVED)

        status_filter = self.request.query_params.get("status")
        if status_filter in dict(TrickEntry.Status.choices):
            if is_manager(user):
                queryset = queryset.filter(status=status_filter)
            elif user and user.is_authenticated:
                if status_filter == TrickEntry.Status.APPROVED:
                    queryset = queryset.filter(status=TrickEntry.Status.APPROVED)
                elif status_filter == TrickEntry.Status.PENDING:
                    queryset = queryset.filter(
                        author=user, status=TrickEntry.Status.PENDING
                    )
                else:
                    queryset = queryset.none()
            elif status_filter != TrickEntry.Status.APPROVED:
                queryset = queryset.none()

        search = self.request.query_params.get("search")
        if search:
            tokens = [item for item in search.strip().split() if item]
            for token in tokens:
                queryset = queryset.filter(
                    Q(title__icontains=token)
                    | Q(content_md__icontains=token)
                    | Q(keywords_text__icontains=token)
                )

        term_id = self.request.query_params.get("term")
        if term_id and term_id.isdigit():
            queryset = queryset.filter(terms__id=int(term_id))

        term_slug = self.request.query_params.get("term_slug")
        if term_slug:
            queryset = queryset.filter(terms__slug=term_slug.strip())

        order = self.request.query_params.get("order")
        if order == "created_oldest":
            return queryset.order_by("created_at", "id").distinct()
        if order == "created_newest":
            return queryset.order_by("-created_at", "-id").distinct()
        if order == "likes_desc":
            return queryset.order_by("-like_count", "-created_at", "-id").distinct()
        return queryset.order_by("-like_count", "-created_at", "-id").distinct()

    def list(self, request, *args, **kwargs):
        try:
            return super().list(request, *args, **kwargs)
        except DatabaseError as exc:
            return schema_outdated_response(exc)

    def retrieve(self, request, *args, **kwargs):
        try:
            return super().retrieve(request, *args, **kwargs)
        except DatabaseError as exc:
            return schema_outdated_response(exc)

    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            is_direct_publish = is_manager(request.user)
            next_status = (
                TrickEntry.Status.APPROVED
                if is_direct_publish
                else TrickEntry.Status.PENDING
            )
            entry = serializer.save(
                author=request.user,
                status=next_status,
                reviewer=request.user if is_direct_publish else None,
                review_note="manager_direct_publish" if is_direct_publish else "",
                reviewed_at=timezone.now() if is_direct_publish else None,
            )
            log_event(
                request.user,
                (
                    ContributionEvent.EventType.ADMIN
                    if is_direct_publish
                    else ContributionEvent.EventType.ISSUE
                ),
                entry,
                {
                    "action": (
                        "create_trick_entry_direct_publish"
                        if is_direct_publish
                        else "create_trick_entry"
                    ),
                    "status": next_status,
                },
            )
            return Response(
                self.get_serializer(entry).data, status=status.HTTP_201_CREATED
            )
        except DatabaseError as exc:
            return schema_outdated_response(exc)

    def update(self, request, *args, **kwargs):
        try:
            partial = kwargs.pop("partial", False)
            entry = self.get_object()
            if not (is_manager(request.user) or entry.author_id == request.user.id):
                return Response(
                    {"detail": "No permission to edit this trick."},
                    status=status.HTTP_403_FORBIDDEN,
                )

            serializer = self.get_serializer(
                entry, data=request.data, partial=partial
            )
            serializer.is_valid(raise_exception=True)

            # Author edits require re-review; manager edits can directly approve.
            next_status = entry.status
            if entry.author_id == request.user.id and not is_manager(request.user):
                next_status = TrickEntry.Status.PENDING
            elif is_manager(request.user):
                next_status = TrickEntry.Status.APPROVED

            serializer.save(
                status=next_status,
                reviewer=request.user if next_status == TrickEntry.Status.APPROVED else None,
                review_note=(
                    "manager_direct_publish"
                    if next_status == TrickEntry.Status.APPROVED and is_manager(request.user)
                    else ""
                ),
                reviewed_at=(
                    timezone.now()
                    if next_status == TrickEntry.Status.APPROVED and is_manager(request.user)
                    else None
                ),
            )
            log_event(
                request.user,
                (
                    ContributionEvent.EventType.ISSUE
                    if entry.author_id == request.user.id
                    else ContributionEvent.EventType.ADMIN
                ),
                entry,
                {"action": "update_trick_entry", "status": next_status},
            )
            return Response(serializer.data)
        except DatabaseError as exc:
            return schema_outdated_response(exc)

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        try:
            entry = self.get_object()
            if not (is_manager(request.user) or entry.author_id == request.user.id):
                return Response(
                    {"detail": "No permission to delete this trick."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            review_note = normalize_review_note(request.data.get("review_note", ""))
            with transaction.atomic():
                archive_deleted_content(
                    instance=entry,
                    operator=request.user,
                    delete_action=DeletedContentArchive.DeleteAction.DELETE,
                )
                if is_manager(request.user) and review_note and entry.author_id != request.user.id:
                    create_notification(
                        user=entry.author,
                        actor=request.user,
                        target=entry,
                        title=f"trick 已删除：{entry.title}",
                        content=f"删除说明：{review_note[:180]}",
                        link="",
                        level=UserNotification.Level.WARNING,
                    )
                log_event(
                    request.user,
                    (
                        ContributionEvent.EventType.ISSUE
                        if entry.author_id == request.user.id
                        else ContributionEvent.EventType.ADMIN
                    ),
                    entry,
                    {
                        "action": "delete_trick_entry",
                        "review_note": review_note[:500],
                    },
                )
                self.perform_destroy(entry)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except DatabaseError as exc:
            return schema_outdated_response(exc)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[AuthenticatedAndNotBanned],
        url_path="like",
    )
    def like(self, request, pk=None):
        entry = self.get_object()
        like, created = TrickEntryLike.objects.get_or_create(
            user=request.user, trick_entry=entry
        )
        if created:
            log_event(
                request.user,
                ContributionEvent.EventType.STAR,
                entry,
                {"action": "like_trick_entry", "like_id": like.id},
            )
        entry.like_count = TrickEntryLike.objects.filter(trick_entry=entry).count()
        entry.is_liked = True
        return Response(self.get_serializer(entry).data)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[AuthenticatedAndNotBanned],
        url_path="unlike",
    )
    def unlike(self, request, pk=None):
        entry = self.get_object()
        TrickEntryLike.objects.filter(user=request.user, trick_entry=entry).delete()
        entry.like_count = TrickEntryLike.objects.filter(trick_entry=entry).count()
        entry.is_liked = False
        return Response(self.get_serializer(entry).data)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[AdminOrSuperAdmin],
        url_path="set-status",
    )
    def set_status(self, request, pk=None):
        entry = self.get_object()
        next_status = request.data.get("status", "").strip()
        review_note = normalize_review_note(request.data.get("review_note", ""))
        if next_status not in dict(TrickEntry.Status.choices):
            return Response(
                {"detail": "Invalid status."}, status=status.HTTP_400_BAD_REQUEST
            )

        entry.status = next_status
        entry.reviewer = request.user
        entry.review_note = review_note
        entry.reviewed_at = timezone.now()
        entry.save(
            update_fields=[
                "status",
                "reviewer",
                "review_note",
                "reviewed_at",
                "updated_at",
            ]
        )
        log_event(
            request.user,
            ContributionEvent.EventType.ADMIN,
            entry,
            {
                "action": "moderate_trick_entry",
                "status": next_status,
                "review_note": review_note[:500],
            },
        )
        if entry.author_id != request.user.id:
            is_rejected = next_status == TrickEntry.Status.REJECTED
            create_notification(
                user=entry.author,
                actor=request.user,
                target=entry,
                title=f"trick 已{'驳回' if is_rejected else '通过'}：{entry.title}",
                content=build_review_notification_content(
                    action="reject" if is_rejected else "approve",
                    review_note=review_note,
                    approved_fallback="你的 trick 已审核通过。",
                    rejected_fallback="你的 trick 未通过审核，请根据批注修改后重新提交。",
                ),
                link="/competition?tab=trick",
                level=(
                    UserNotification.Level.WARNING
                    if is_rejected
                    else UserNotification.Level.INFO
                ),
            )
        return Response(self.get_serializer(entry).data)


class TrickTermViewSet(ActionThrottleMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = TrickTermSerializer
    queryset = TrickTerm.objects.all().annotate(
        usage_count=Count("trick_entries", distinct=True)
    )

    def get_permissions(self):
        return [AllowAny()]

    def get_queryset(self):
        queryset = super().get_queryset().filter(
            is_active=True,
            is_builtin=True,
            slug__in=FIXED_TRICK_TERM_SLUGS,
        )

        search = self.request.query_params.get("search")
        if search:
            keyword = search.strip()
            queryset = queryset.filter(
                Q(name__icontains=keyword) | Q(description__icontains=keyword)
            )
        return queryset.order_by(build_fixed_trick_term_order_expression(), "name")


class TrickTermSuggestionViewSet(
    ReviewNoteActionMixin, ActionThrottleMixin, viewsets.ReadOnlyModelViewSet
):
    serializer_class = TrickTermSuggestionSerializer
    queryset = (
        TrickTermSuggestion.objects.select_related("proposer", "reviewer")
        .prefetch_related("pending_trick_entries")
        .all()
    )

    def get_permissions(self):
        return [AdminOrSuperAdmin()]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if not user or not user.is_authenticated:
            return queryset.none()

        status_filter = self.request.query_params.get("status")
        if status_filter in dict(TrickTermSuggestion.Status.choices):
            queryset = queryset.filter(status=status_filter)
        return queryset.order_by("-created_at")


class QuestionViewSet(ReviewNoteActionMixin, ActionThrottleMixin, viewsets.ModelViewSet):
    serializer_class = QuestionSerializer
    queryset = Question.objects.select_related("author", "category", "reviewer").annotate(
        answers_count=Count("answers")
    )
    throttle_action_classes = {
        "create": [ContentCreateRateThrottle],
        "update": [ContentUpdateRateThrottle],
        "partial_update": [ContentUpdateRateThrottle],
        "destroy": [ContentDeleteRateThrottle],
    }

    def get_permissions(self):
        if self.action in {"approve", "reject", "bulk_moderate", "append_review_note"}:
            return [AdminOrSuperAdmin()]
        if self.action in {"list", "retrieve"}:
            return [AllowAny()]
        if self.action == "mine":
            return [AuthenticatedAndNotBanned()]
        return [AuthenticatedAndNotBanned()]

    def get_queryset(self):
        queryset = super().get_queryset()
        sync_question_auto_close_states(queryset)
        user = self.request.user
        manager = is_manager(user)
        mine_only = self.request.query_params.get("mine") == "1"
        status_filter = self.request.query_params.get("status")
        status_filter = status_filter.strip() if isinstance(status_filter, str) else ""
        wants_hidden_only = status_filter == Question.Status.HIDDEN

        if manager:
            if self.action == "list" and not wants_hidden_only:
                queryset = queryset.exclude(status=Question.Status.HIDDEN)
        elif mine_only:
            if not user.is_authenticated:
                return queryset.none()
            queryset = queryset.filter(author=user)
            if self.action == "list" and not wants_hidden_only:
                queryset = queryset.exclude(status=Question.Status.HIDDEN)
            elif wants_hidden_only:
                archived_hidden_ids = list(
                    Question.objects.filter(author=user, status=Question.Status.HIDDEN)
                    .order_by("-updated_at", "-id")
                    .values_list("id", flat=True)[:30]
                )
                queryset = queryset.filter(id__in=archived_hidden_ids)
        elif user.is_authenticated:
            queryset = queryset.filter(
                Q(status__in=[Question.Status.OPEN, Question.Status.CLOSED])
                | Q(author=user, status=Question.Status.PENDING)
            )
        else:
            queryset = queryset.filter(
                status__in=[Question.Status.OPEN, Question.Status.CLOSED]
            )

        if manager:
            author_filter = self.request.query_params.get("author")
            if author_filter:
                author_filter = author_filter.strip()
                if author_filter.isdigit():
                    queryset = queryset.filter(author_id=int(author_filter))
                else:
                    queryset = queryset.filter(
                        author__username__icontains=author_filter
                    )

        if status_filter in dict(Question.Status.choices):
            if manager or mine_only:
                queryset = queryset.filter(status=status_filter)
            elif status_filter in {Question.Status.OPEN, Question.Status.CLOSED}:
                queryset = queryset.filter(status=status_filter)
            elif status_filter == Question.Status.PENDING and user.is_authenticated:
                queryset = queryset.filter(author=user, status=Question.Status.PENDING)
            else:
                queryset = queryset.none()

        category = self.request.query_params.get("category")
        if category:
            category = category.strip()
            if category.isdigit():
                queryset = queryset.filter(category_id=int(category))
            else:
                queryset = queryset.filter(category__slug=category)

        search = self.request.query_params.get("search")
        if search:
            token = search.strip()
            queryset = queryset.filter(
                Q(title__icontains=token) | Q(content_md__icontains=token)
            )

        order = self.request.query_params.get("order")
        if order == "oldest":
            return queryset.order_by("updated_at")
        if order == "answers":
            return queryset.order_by("-answers_count", "-updated_at")
        if order == "created_oldest":
            return queryset.order_by("created_at")
        if order == "created_newest":
            return queryset.order_by("-created_at")

        return queryset.order_by("-updated_at")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        next_status = (
            Question.Status.OPEN
            if is_manager(request.user)
            else Question.Status.PENDING
        )
        question = serializer.save(
            author=request.user,
            status=next_status,
            auto_close_at=(
                build_question_auto_close_at()
                if next_status == Question.Status.OPEN
                else None
            ),
        )
        log_event(
            request.user,
            ContributionEvent.EventType.QUESTION,
            question,
            {"action": "create_question", "status": next_status},
        )
        return Response(
            self.get_serializer(question).data, status=status.HTTP_201_CREATED
        )

    def update(self, request, *args, **kwargs):
        question = self.get_object()
        partial = kwargs.pop("partial", False)
        manager = is_manager(request.user)
        if question.author_id != request.user.id and not manager:
            return Response(
                {"detail": "No permission."}, status=status.HTTP_403_FORBIDDEN
            )

        serializer = self.get_serializer(question, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        next_status = question.status if manager else Question.Status.PENDING
        save_kwargs = {"status": next_status}
        if next_status != Question.Status.OPEN:
            save_kwargs["auto_close_at"] = None
        serializer.save(**save_kwargs)
        log_event(
            request.user,
            (
                ContributionEvent.EventType.ADMIN
                if manager
                else ContributionEvent.EventType.QUESTION
            ),
            question,
            {"action": "update_question", "status": next_status},
        )
        return Response(serializer.data)

    def _apply_question_moderation(self, question, operator, action, review_note=""):
        action = (action or "").strip().lower()
        manager = is_manager(operator)
        review_note = normalize_review_note(review_note)

        if action == "close":
            if question.status not in {Question.Status.OPEN, Question.Status.CLOSED}:
                return (
                    False,
                    status.HTTP_400_BAD_REQUEST,
                    "Only reviewed questions can be closed.",
                )
            if question.author_id != operator.id and not manager:
                return False, status.HTTP_403_FORBIDDEN, "No permission."
            question.status = Question.Status.CLOSED
            question.auto_close_at = None
            question.save(update_fields=["status", "auto_close_at", "updated_at"])
            log_event(
                operator,
                (
                    ContributionEvent.EventType.ADMIN
                    if manager
                    else ContributionEvent.EventType.QUESTION
                ),
                question,
                {"action": "close_question"},
            )
            return True, status.HTTP_200_OK, None

        if action == "reopen":
            if question.status not in {Question.Status.OPEN, Question.Status.CLOSED}:
                return (
                    False,
                    status.HTTP_400_BAD_REQUEST,
                    "Only reviewed questions can be reopened.",
                )
            if question.author_id != operator.id and not manager:
                return False, status.HTTP_403_FORBIDDEN, "No permission."
            question.status = Question.Status.OPEN
            question.auto_close_at = build_question_auto_close_at()
            question.reviewer = operator
            question.review_note = review_note
            question.reviewed_at = timezone.now()
            question.save(
                update_fields=[
                    "status",
                    "auto_close_at",
                    "reviewer",
                    "review_note",
                    "reviewed_at",
                    "updated_at",
                ]
            )
            log_event(
                operator,
                (
                    ContributionEvent.EventType.ADMIN
                    if manager
                    else ContributionEvent.EventType.QUESTION
                ),
                question,
                {"action": "reopen_question"},
            )
            return True, status.HTTP_200_OK, None

        if action == "approve":
            if not manager:
                return (
                    False,
                    status.HTTP_403_FORBIDDEN,
                    "Only admins can approve questions.",
                )
            if question.status != Question.Status.PENDING:
                return (
                    False,
                    status.HTTP_400_BAD_REQUEST,
                    "Question is not pending review.",
                )
            question.status = Question.Status.OPEN
            question.auto_close_at = build_question_auto_close_at()
            question.reviewer = operator
            question.review_note = review_note
            question.reviewed_at = timezone.now()
            question.save(
                update_fields=[
                    "status",
                    "auto_close_at",
                    "reviewer",
                    "review_note",
                    "reviewed_at",
                    "updated_at",
                ]
            )
            log_event(
                operator,
                ContributionEvent.EventType.ADMIN,
                question,
                {"action": "approve_question"},
            )
            if question.author_id != operator.id:
                create_notification(
                    user=question.author,
                    actor=operator,
                    target=question,
                    title=f"你的问题已通过审核：{question.title}",
                    content=build_review_notification_content(
                        action="approve",
                        review_note=review_note,
                        approved_fallback="问题现在已对外展示。",
                        rejected_fallback="",
                    ),
                    link="/questions",
                )
            return True, status.HTTP_200_OK, None

        if action == "reject":
            if not manager:
                return (
                    False,
                    status.HTTP_403_FORBIDDEN,
                    "Only admins can reject questions.",
                )
            if question.status != Question.Status.PENDING:
                return (
                    False,
                    status.HTTP_400_BAD_REQUEST,
                    "Question is not pending review.",
                )
            question.status = Question.Status.HIDDEN
            question.auto_close_at = None
            question.reviewer = operator
            question.review_note = review_note
            question.reviewed_at = timezone.now()
            question.save(
                update_fields=[
                    "status",
                    "auto_close_at",
                    "reviewer",
                    "review_note",
                    "reviewed_at",
                    "updated_at",
                ]
            )
            log_event(
                operator,
                ContributionEvent.EventType.ADMIN,
                question,
                {"action": "reject_question"},
            )
            if question.author_id != operator.id:
                create_notification(
                    user=question.author,
                    actor=operator,
                    target=question,
                    title=f"你的问题未通过审核：{question.title}",
                    content=build_review_notification_content(
                        action="reject",
                        review_note=review_note,
                        approved_fallback="",
                        rejected_fallback="请根据管理员批注修改后重新提交。",
                    ),
                    link="/profile",
                    level=UserNotification.Level.WARNING,
                )
            return True, status.HTTP_200_OK, None

        if action == "hide":
            if question.author_id != operator.id and not manager:
                return False, status.HTTP_403_FORBIDDEN, "No permission."
            with transaction.atomic():
                if question.status != Question.Status.HIDDEN:
                    archive_deleted_content(
                        instance=question,
                        operator=operator,
                        delete_action=DeletedContentArchive.DeleteAction.HIDE,
                    )
                question.status = Question.Status.HIDDEN
                question.auto_close_at = None
                question.save(update_fields=["status", "auto_close_at", "updated_at"])
            log_event(
                operator,
                (
                    ContributionEvent.EventType.ADMIN
                    if manager
                    else ContributionEvent.EventType.QUESTION
                ),
                question,
                {"action": "hide_question"},
            )
            return True, status.HTTP_200_OK, None

        if action == "restore":
            if question.author_id != operator.id and not manager:
                return False, status.HTTP_403_FORBIDDEN, "No permission."
            if question.status != Question.Status.HIDDEN:
                return (
                    False,
                    status.HTTP_400_BAD_REQUEST,
                    "Only hidden questions can be restored.",
                )
            next_status = Question.Status.OPEN if manager else Question.Status.PENDING
            question.status = next_status
            question.auto_close_at = (
                build_question_auto_close_at()
                if next_status == Question.Status.OPEN
                else None
            )
            question.save(update_fields=["status", "auto_close_at", "updated_at"])
            log_event(
                operator,
                (
                    ContributionEvent.EventType.ADMIN
                    if manager
                    else ContributionEvent.EventType.QUESTION
                ),
                question,
                {"action": "restore_question", "status": next_status},
            )
            return True, status.HTTP_200_OK, None

        return False, status.HTTP_400_BAD_REQUEST, "Invalid moderation action."

    def destroy(self, request, *args, **kwargs):
        question = self.get_object()
        ok, error_status, detail = self._apply_question_moderation(
            question, request.user, "hide"
        )
        if not ok:
            return Response({"detail": detail}, status=error_status)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=True, methods=["post"], permission_classes=[AuthenticatedAndNotBanned]
    )
    def close(self, request, pk=None):
        question = self.get_object()
        ok, error_status, detail = self._apply_question_moderation(
            question, request.user, "close"
        )
        if not ok:
            return Response({"detail": detail}, status=error_status)
        return Response(self.get_serializer(question).data)

    @action(
        detail=True, methods=["post"], permission_classes=[AuthenticatedAndNotBanned]
    )
    def reopen(self, request, pk=None):
        question = self.get_object()
        ok, error_status, detail = self._apply_question_moderation(
            question, request.user, "reopen"
        )
        if not ok:
            return Response({"detail": detail}, status=error_status)
        return Response(self.get_serializer(question).data)

    @action(detail=True, methods=["post"], permission_classes=[AdminOrSuperAdmin])
    def approve(self, request, pk=None):
        question = self.get_object()
        ok, error_status, detail = self._apply_question_moderation(
            question, request.user, "approve", review_note=request.data.get("review_note", "")
        )
        if not ok:
            return Response({"detail": detail}, status=error_status)
        return Response(self.get_serializer(question).data)

    @action(detail=True, methods=["post"], permission_classes=[AdminOrSuperAdmin])
    def reject(self, request, pk=None):
        question = self.get_object()
        ok, error_status, detail = self._apply_question_moderation(
            question, request.user, "reject", review_note=request.data.get("review_note", "")
        )
        if not ok:
            return Response({"detail": detail}, status=error_status)
        return Response(self.get_serializer(question).data)

    @action(
        detail=True, methods=["post"], permission_classes=[AuthenticatedAndNotBanned]
    )
    def restore(self, request, pk=None):
        question = (
            Question.objects.select_related("author", "category").filter(pk=pk).first()
        )
        if not question:
            return Response(
                {"detail": "Question not found."}, status=status.HTTP_404_NOT_FOUND
            )
        ok, error_status, detail = self._apply_question_moderation(
            question, request.user, "restore"
        )
        if not ok:
            return Response({"detail": detail}, status=error_status)
        return Response(self.get_serializer(question).data)

    @action(
        detail=False,
        methods=["post"],
        permission_classes=[AdminOrSuperAdmin],
        url_path="bulk-moderate",
    )
    def bulk_moderate(self, request):
        raw_ids = request.data.get("ids")
        if not isinstance(raw_ids, list) or not raw_ids:
            return Response(
                {"detail": "ids must be a non-empty list."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(raw_ids) > 200:
            return Response(
                {"detail": "Too many ids, max is 200."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ids = []
        for raw_id in raw_ids:
            try:
                question_id = int(raw_id)
            except (TypeError, ValueError):
                return Response(
                    {"detail": "ids must contain integers."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if question_id <= 0:
                return Response(
                    {"detail": "ids must contain positive integers."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if question_id not in ids:
                ids.append(question_id)

        action_name = str(request.data.get("action", "")).strip().lower()
        if action_name not in {"approve", "reject", "close", "reopen", "hide"}:
            return Response(
                {"detail": "action must be approve, reject, close, reopen or hide."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        question_map = {
            item.id: item
            for item in self.get_queryset()
            .filter(id__in=ids)
            .select_related("author", "category")
        }
        results = []
        success_count = 0
        for question_id in ids:
            question = question_map.get(question_id)
            if not question:
                results.append(
                    {
                        "id": question_id,
                        "success": False,
                        "detail": "Question not found or inaccessible.",
                    }
                )
                continue

            ok, _, detail = self._apply_question_moderation(
                question,
                request.user,
                action_name,
                review_note=request.data.get("review_note", ""),
            )
            if ok:
                success_count += 1
                results.append(
                    {"id": question_id, "success": True, "status": question.status}
                )
            else:
                results.append({"id": question_id, "success": False, "detail": detail})

        return Response(
            {
                "total": len(ids),
                "success": success_count,
                "failed": len(ids) - success_count,
                "results": results,
            }
        )

    @action(
        detail=False, methods=["get"], permission_classes=[AuthenticatedAndNotBanned]
    )
    def mine(self, request):
        status_filter = request.query_params.get("status")
        status_filter = status_filter.strip() if isinstance(status_filter, str) else ""
        queryset = Question.objects.filter(author=request.user).select_related(
            "author", "category"
        )
        sync_question_auto_close_states(queryset)
        if status_filter in dict(Question.Status.choices):
            queryset = queryset.filter(status=status_filter)
        else:
            queryset = queryset.exclude(status=Question.Status.HIDDEN)
        if status_filter == Question.Status.HIDDEN:
            hidden_ids = list(
                Question.objects.filter(
                    author=request.user, status=Question.Status.HIDDEN
                )
                .order_by("-updated_at", "-id")
                .values_list("id", flat=True)[:30]
            )
            queryset = queryset.filter(id__in=hidden_ids)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class AnswerViewSet(ReviewNoteActionMixin, ActionThrottleMixin, viewsets.ModelViewSet):
    serializer_class = AnswerSerializer
    queryset = Answer.objects.select_related(
        "author", "question", "question__author", "reviewer"
    ).all()
    throttle_action_classes = {
        "create": [ContentCreateRateThrottle],
        "update": [ContentUpdateRateThrottle],
        "partial_update": [ContentUpdateRateThrottle],
        "destroy": [ContentDeleteRateThrottle],
    }

    def get_permissions(self):
        if self.action in {"approve", "reject", "bulk_moderate", "append_review_note"}:
            return [AdminOrSuperAdmin()]
        if self.action in {"list", "retrieve"}:
            return [AllowAny()]
        if self.action == "mine":
            return [AuthenticatedAndNotBanned()]
        return [AuthenticatedAndNotBanned()]

    def get_queryset(self):
        queryset = super().get_queryset()
        question_id = self.request.query_params.get("question")
        if question_id:
            queryset = queryset.filter(question_id=question_id)

        user = self.request.user
        manager = is_manager(user)
        status_filter = self.request.query_params.get("status")
        status_filter = status_filter.strip() if isinstance(status_filter, str) else ""

        if manager:
            author_filter = self.request.query_params.get("author")
            if author_filter:
                author_filter = author_filter.strip()
                if author_filter.isdigit():
                    queryset = queryset.filter(author_id=int(author_filter))
                else:
                    queryset = queryset.filter(
                        author__username__icontains=author_filter
                    )
        elif user.is_authenticated:
            queryset = queryset.filter(
                Q(status=Answer.Status.VISIBLE)
                | Q(author=user, status=Answer.Status.PENDING)
            )
        else:
            queryset = queryset.filter(status=Answer.Status.VISIBLE)

        if status_filter in dict(Answer.Status.choices):
            if manager:
                queryset = queryset.filter(status=status_filter)
            elif status_filter == Answer.Status.VISIBLE:
                queryset = queryset.filter(status=Answer.Status.VISIBLE)
            elif status_filter == Answer.Status.PENDING and user.is_authenticated:
                queryset = queryset.filter(author=user, status=Answer.Status.PENDING)
            else:
                queryset = queryset.none()

        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(content_md__icontains=search.strip())

        order = self.request.query_params.get("order")
        if order == "latest":
            return queryset.order_by("-created_at")
        if order == "accepted_first":
            return queryset.order_by("-is_accepted", "-created_at")
        return queryset.order_by("created_at")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        question = serializer.validated_data["question"]
        sync_question_auto_close_state(question)
        if question.status != Question.Status.OPEN:
            return Response(
                {"detail": "Question is closed."}, status=status.HTTP_400_BAD_REQUEST
            )
        next_status = (
            Answer.Status.VISIBLE if is_manager(request.user) else Answer.Status.PENDING
        )
        answer = serializer.save(author=request.user, status=next_status)
        log_event(
            request.user,
            ContributionEvent.EventType.ANSWER,
            answer,
            {
                "action": "create_answer",
                "question_id": question.id,
                "status": next_status,
            },
        )
        if (
            answer.status == Answer.Status.VISIBLE
            and question.author_id != request.user.id
        ):
            create_notification(
                user=question.author,
                actor=request.user,
                target=answer,
                title=f"你的问题收到新回答：{question.title}",
                content=answer.content_md[:180],
                link="/questions",
            )
        return Response(
            self.get_serializer(answer).data, status=status.HTTP_201_CREATED
        )

    def update(self, request, *args, **kwargs):
        answer = self.get_object()
        partial = kwargs.pop("partial", False)
        manager = is_manager(request.user)
        if answer.author_id != request.user.id and not manager:
            return Response(
                {"detail": "No permission to edit this answer."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = self.get_serializer(answer, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        save_kwargs = {}
        if not manager:
            save_kwargs["status"] = Answer.Status.PENDING
            if answer.is_accepted:
                save_kwargs["is_accepted"] = False
        serializer.save(**save_kwargs)
        log_event(
            request.user,
            (
                ContributionEvent.EventType.ADMIN
                if manager
                else ContributionEvent.EventType.ANSWER
            ),
            answer,
            {
                "action": "update_answer",
                "status": save_kwargs.get("status", answer.status),
                "is_accepted": answer.is_accepted,
            },
        )
        return Response(serializer.data)

    def _apply_answer_moderation(self, answer, operator, action, review_note=""):
        action = (action or "").strip().lower()
        review_note = normalize_review_note(review_note)
        if not is_manager(operator):
            return False, status.HTTP_403_FORBIDDEN, "Only admins can moderate answers."

        if action == "approve":
            if answer.status != Answer.Status.PENDING:
                return (
                    False,
                    status.HTTP_400_BAD_REQUEST,
                    "Answer is not pending review.",
            )
            answer.status = Answer.Status.VISIBLE
            answer.reviewer = operator
            answer.review_note = review_note
            answer.reviewed_at = timezone.now()
            answer.save(
                update_fields=[
                    "status",
                    "reviewer",
                    "review_note",
                    "reviewed_at",
                    "updated_at",
                ]
            )
            log_event(
                operator,
                ContributionEvent.EventType.ADMIN,
                answer,
                {"action": "approve_answer"},
            )
            if answer.author_id != operator.id:
                create_notification(
                    user=answer.author,
                    actor=operator,
                    target=answer,
                    title=f"你的回答已通过审核：{answer.question.title}",
                    content=build_review_notification_content(
                        action="approve",
                        review_note=review_note,
                        approved_fallback="回答现在已对外展示。",
                        rejected_fallback="",
                    ),
                    link="/questions",
                )
            return True, status.HTTP_200_OK, None

        if action == "reject":
            if answer.status != Answer.Status.PENDING:
                return (
                    False,
                    status.HTTP_400_BAD_REQUEST,
                    "Answer is not pending review.",
            )
            answer.status = Answer.Status.HIDDEN
            answer.is_accepted = False
            answer.reviewer = operator
            answer.review_note = review_note
            answer.reviewed_at = timezone.now()
            answer.save(
                update_fields=[
                    "status",
                    "is_accepted",
                    "reviewer",
                    "review_note",
                    "reviewed_at",
                    "updated_at",
                ]
            )
            log_event(
                operator,
                ContributionEvent.EventType.ADMIN,
                answer,
                {"action": "reject_answer"},
            )
            if answer.author_id != operator.id:
                create_notification(
                    user=answer.author,
                    actor=operator,
                    target=answer,
                    title=f"你的回答未通过审核：{answer.question.title}",
                    content=build_review_notification_content(
                        action="reject",
                        review_note=review_note,
                        approved_fallback="",
                        rejected_fallback="请根据管理员批注修改后重新提交。",
                    ),
                    link="/profile",
                    level=UserNotification.Level.WARNING,
                )
            return True, status.HTTP_200_OK, None

        if action == "hide":
            with transaction.atomic():
                if answer.status != Answer.Status.HIDDEN:
                    archive_deleted_content(
                        instance=answer,
                        operator=operator,
                        delete_action=DeletedContentArchive.DeleteAction.HIDE,
                    )
                answer.status = Answer.Status.HIDDEN
                answer.is_accepted = False
                answer.save(update_fields=["status", "is_accepted", "updated_at"])
            log_event(
                operator,
                ContributionEvent.EventType.ADMIN,
                answer,
                {"action": "hide_answer"},
            )
            return True, status.HTTP_200_OK, None

        return False, status.HTTP_400_BAD_REQUEST, "Invalid moderation action."

    def destroy(self, request, *args, **kwargs):
        answer = self.get_object()
        if answer.author_id != request.user.id and not is_manager(request.user):
            return Response(
                {"detail": "No permission to remove this answer."},
                status=status.HTTP_403_FORBIDDEN,
            )
        with transaction.atomic():
            if answer.status != Answer.Status.HIDDEN:
                archive_deleted_content(
                    instance=answer,
                    operator=request.user,
                    delete_action=DeletedContentArchive.DeleteAction.HIDE,
                )
            answer.status = Answer.Status.HIDDEN
            answer.save(update_fields=["status", "updated_at"])
        log_event(
            request.user,
            ContributionEvent.EventType.ANSWER,
            answer,
            {"action": "hide_answer"},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=True, methods=["post"], permission_classes=[AuthenticatedAndNotBanned]
    )
    def accept(self, request, pk=None):
        answer = self.get_object()
        question = answer.question
        sync_question_auto_close_state(question)
        if answer.status != Answer.Status.VISIBLE:
            return Response(
                {"detail": "Only visible answers can be accepted."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if question.author_id != request.user.id and not is_manager(request.user):
            return Response(
                {"detail": "No permission."}, status=status.HTTP_403_FORBIDDEN
            )

        with transaction.atomic():
            Answer.objects.filter(question=question, is_accepted=True).update(
                is_accepted=False
            )
            answer.is_accepted = True
            answer.save(update_fields=["is_accepted", "updated_at"])

        log_event(
            request.user,
            ContributionEvent.EventType.ANSWER,
            answer,
            {"action": "accept_answer"},
        )
        if answer.author_id != request.user.id:
            create_notification(
                user=answer.author,
                actor=request.user,
                target=answer,
                title=f"你的回答已被采纳：{question.title}",
                content="恭喜！该回答被问题发起者设置为已采纳。",
                link="/questions",
            )
        return Response(self.get_serializer(answer).data)

    @action(detail=True, methods=["post"], permission_classes=[AdminOrSuperAdmin])
    def approve(self, request, pk=None):
        answer = self.get_object()
        ok, error_status, detail = self._apply_answer_moderation(
            answer, request.user, "approve", review_note=request.data.get("review_note", "")
        )
        if not ok:
            return Response({"detail": detail}, status=error_status)
        return Response(self.get_serializer(answer).data)

    @action(detail=True, methods=["post"], permission_classes=[AdminOrSuperAdmin])
    def reject(self, request, pk=None):
        answer = self.get_object()
        ok, error_status, detail = self._apply_answer_moderation(
            answer, request.user, "reject", review_note=request.data.get("review_note", "")
        )
        if not ok:
            return Response({"detail": detail}, status=error_status)
        return Response(self.get_serializer(answer).data)

    @action(
        detail=False,
        methods=["post"],
        permission_classes=[AdminOrSuperAdmin],
        url_path="bulk-moderate",
    )
    def bulk_moderate(self, request):
        raw_ids = request.data.get("ids")
        if not isinstance(raw_ids, list) or not raw_ids:
            return Response(
                {"detail": "ids must be a non-empty list."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(raw_ids) > 200:
            return Response(
                {"detail": "Too many ids, max is 200."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ids = []
        for raw_id in raw_ids:
            try:
                answer_id = int(raw_id)
            except (TypeError, ValueError):
                return Response(
                    {"detail": "ids must contain integers."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if answer_id <= 0:
                return Response(
                    {"detail": "ids must contain positive integers."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if answer_id not in ids:
                ids.append(answer_id)

        action_name = str(request.data.get("action", "")).strip().lower()
        if action_name not in {"approve", "reject", "hide"}:
            return Response(
                {"detail": "action must be approve, reject or hide."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        answer_map = {
            item.id: item
            for item in self.get_queryset()
            .filter(id__in=ids)
            .select_related("author", "question", "question__author")
        }
        results = []
        success_count = 0
        for answer_id in ids:
            answer = answer_map.get(answer_id)
            if not answer:
                results.append(
                    {
                        "id": answer_id,
                        "success": False,
                        "detail": "Answer not found or inaccessible.",
                    }
                )
                continue

            ok, _, detail = self._apply_answer_moderation(
                answer,
                request.user,
                action_name,
                review_note=request.data.get("review_note", ""),
            )
            if ok:
                success_count += 1
                results.append(
                    {"id": answer_id, "success": True, "status": answer.status}
                )
            else:
                results.append({"id": answer_id, "success": False, "detail": detail})

        return Response(
            {
                "total": len(ids),
                "success": success_count,
                "failed": len(ids) - success_count,
                "results": results,
            }
        )

    @action(
        detail=False, methods=["get"], permission_classes=[AuthenticatedAndNotBanned]
    )
    def mine(self, request):
        queryset = Answer.objects.filter(author=request.user).select_related(
            "author", "question", "question__author"
        )
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class AnnouncementViewSet(viewsets.ModelViewSet):
    serializer_class = AnnouncementSerializer
    queryset = Announcement.objects.select_related("created_by").all()

    def get_permissions(self):
        if self.action in {"list", "retrieve", "published_history"}:
            return [AllowAny()]
        if self.action in {"acknowledge", "unread"}:
            return [AuthenticatedAndNotBanned()]
        return [AdminOrSuperAdmin()]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        include_all = self.request.query_params.get("all") == "1"

        manager_detail_actions = {"retrieve", "update", "partial_update", "destroy"}
        can_access_all = is_manager(user) and (
            include_all or self.action in manager_detail_actions
        )

        if not can_access_all:
            queryset = queryset.active()

        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        announcement = serializer.save(created_by=request.user)
        log_event(request.user, ContributionEvent.EventType.ANNOUNCEMENT, announcement)
        recipients = (
            User.objects.filter(is_active=True, is_banned=False)
            .exclude(id=request.user.id)
            .only("id", "is_active", "is_banned")
        )
        bulk_notify_users(
            users=recipients,
            actor=request.user,
            target=announcement,
            title=f"新公告：{announcement.title}",
            content=(announcement.content_md or "")[:180],
            link="/",
            level=UserNotification.Level.INFO,
        )
        return Response(
            self.get_serializer(announcement).data, status=status.HTTP_201_CREATED
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        announcement = self.get_object()
        serializer = self.get_serializer(
            announcement, data=request.data, partial=partial
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        log_event(
            request.user,
            ContributionEvent.EventType.ANNOUNCEMENT,
            announcement,
            {"action": "update_announcement"},
        )
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        announcement = self.get_object()
        with transaction.atomic():
            archive_deleted_content(
                instance=announcement,
                operator=request.user,
                delete_action=DeletedContentArchive.DeleteAction.DELETE,
            )
            log_event(
                request.user,
                ContributionEvent.EventType.ANNOUNCEMENT,
                announcement,
                {"action": "delete_announcement"},
            )
            self.perform_destroy(announcement)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=True, methods=["post"], permission_classes=[AuthenticatedAndNotBanned]
    )
    def acknowledge(self, request, pk=None):
        announcement = self.get_object()
        AnnouncementRead.objects.get_or_create(
            user=request.user, announcement=announcement
        )
        return Response({"acknowledged": True})

    @action(
        detail=False, methods=["get"], permission_classes=[AuthenticatedAndNotBanned]
    )
    def unread(self, request):
        queryset = Announcement.objects.active().exclude(
            read_by_users__user=request.user
        )
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[AllowAny],
        url_path="published-history",
    )
    def published_history(self, request):
        try:
            limit = int(request.query_params.get("limit", 30))
        except (TypeError, ValueError):
            limit = 30
        limit = min(max(limit, 1), 100)

        queryset = Announcement.objects.filter(is_published=True).order_by(
            "-created_at"
        )[:limit]
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class TeamMemberViewSet(viewsets.GenericViewSet):
    serializer_class = TeamMemberSerializer
    queryset = TeamMember.objects.select_related("user").filter(is_active=True)
    pagination_class = None

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [AllowAny()]
        if self.action == "mine":
            return [AuthenticatedAndNotBanned()]
        return [AdminOrSuperAdmin()]

    def list(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_queryset(), many=True)
        return Response(serializer.data)

    @action(
        detail=False,
        methods=["get", "post", "patch", "delete"],
        permission_classes=[AuthenticatedAndNotBanned],
    )
    def mine(self, request):
        if not is_manager(request.user):
            return Response(
                {"detail": "Only admins can manage team cards."},
                status=status.HTTP_403_FORBIDDEN,
            )

        member = TeamMember.objects.filter(user=request.user).first()
        active_member = member if member and member.is_active else None
        if request.method == "GET":
            return Response(
                {
                    "exists": bool(active_member),
                    "member": (
                        TeamMemberSerializer(
                            active_member, context={"request": request}
                        ).data
                        if active_member
                        else None
                    ),
                }
            )

        if request.method == "DELETE":
            if member and member.is_active:
                member.is_active = False
                member.save(update_fields=["is_active", "updated_at"])
            return Response(status=status.HTTP_204_NO_CONTENT)

        partial = request.method == "PATCH"
        serializer = TeamMemberUpsertSerializer(
            member, data=request.data, partial=partial
        )
        serializer.is_valid(raise_exception=True)
        created = member is None
        payload = dict(serializer.validated_data)
        if created:
            member = TeamMember.objects.create(
                user=request.user,
                display_id=payload["display_id"],
                avatar_url=payload.get("avatar_url", ""),
                profile_url=payload["profile_url"],
                is_active=True,
            )
        else:
            for key, value in payload.items():
                setattr(member, key, value)
            member.is_active = True
            member.save(update_fields=[*payload.keys(), "is_active", "updated_at"])
        data = TeamMemberSerializer(member, context={"request": request}).data
        return Response(
            data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )


class ExtensionPageViewSet(viewsets.ModelViewSet):
    serializer_class = ExtensionPageSerializer
    queryset = ExtensionPage.objects.all()
    lookup_field = "slug"

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [AllowAny()]
        return [AdminOrSuperAdmin()]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if is_manager(user):
            include_disabled = self.request.query_params.get("include_disabled") == "1"
            can_access_disabled = can_access_non_public_items(
                user=user,
                action=getattr(self, "action", ""),
                explicit_include=include_disabled,
                permission_check=is_manager,
            )
            if can_access_disabled:
                return queryset
            return queryset.filter(is_enabled=True)

        if user.is_authenticated:
            return queryset.filter(is_enabled=True).exclude(
                access_level=ExtensionPage.AccessLevel.ADMIN
            )

        return queryset.filter(
            is_enabled=True, access_level=ExtensionPage.AccessLevel.PUBLIC
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        page = serializer.save()
        log_event(
            request.user,
            ContributionEvent.EventType.ADMIN,
            page,
            {"action": "create_page"},
        )
        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        page = self.get_object()
        serializer = self.get_serializer(page, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        log_event(
            request.user,
            ContributionEvent.EventType.ADMIN,
            page,
            {"action": "update_page"},
        )
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        page = self.get_object()
        log_event(
            request.user,
            ContributionEvent.EventType.ADMIN,
            page,
            {"action": "delete_page"},
        )
        return super().destroy(request, *args, **kwargs)


class DocumentPageSectionViewSet(viewsets.ModelViewSet):
    serializer_class = DocumentPageSectionSerializer
    queryset = DocumentPageSection.objects.select_related("page").all()

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [AllowAny()]
        return [AdminOrSuperAdmin()]

    def get_queryset(self):
        queryset = super().get_queryset()
        include_hidden = self.request.query_params.get("include_hidden") == "1"

        can_access_hidden = can_access_non_public_items(
            user=self.request.user,
            action=getattr(self, "action", ""),
            explicit_include=include_hidden,
            permission_check=is_manager,
        )
        if not can_access_hidden:
            queryset = queryset.filter(is_visible=True, page__is_enabled=True)
            user = self.request.user
            if not is_manager(user):
                if user.is_authenticated:
                    queryset = queryset.exclude(
                        page__access_level=ExtensionPage.AccessLevel.ADMIN
                    )
                else:
                    queryset = queryset.filter(
                        page__access_level=ExtensionPage.AccessLevel.PUBLIC
                    )

        return queryset.order_by("display_order", "id")

    def list(self, request, *args, **kwargs):
        try:
            return super().list(request, *args, **kwargs)
        except DatabaseError as exc:
            return schema_outdated_response(exc)

    def retrieve(self, request, *args, **kwargs):
        try:
            return super().retrieve(request, *args, **kwargs)
        except DatabaseError as exc:
            return schema_outdated_response(exc)

    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            save_kwargs = {}
            if request.data.get("display_order", None) in {"", None}:
                save_kwargs["display_order"] = get_next_order_value(
                    DocumentPageSection.objects.all(),
                    "display_order",
                )
            section = serializer.save(**save_kwargs)
            log_event(
                request.user,
                ContributionEvent.EventType.ADMIN,
                section,
                {"action": "create_document_page_section"},
            )
            return Response(
                self.get_serializer(section).data, status=status.HTTP_201_CREATED
            )
        except DatabaseError as exc:
            return schema_outdated_response(exc)

    def update(self, request, *args, **kwargs):
        try:
            partial = kwargs.pop("partial", False)
            section = self.get_object()
            serializer = self.get_serializer(
                section, data=request.data, partial=partial
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            log_event(
                request.user,
                ContributionEvent.EventType.ADMIN,
                section,
                {"action": "update_document_page_section"},
            )
            return Response(serializer.data)
        except DatabaseError as exc:
            return schema_outdated_response(exc)

    def destroy(self, request, *args, **kwargs):
        try:
            section = self.get_object()
            related_page = section.page
            log_event(
                request.user,
                ContributionEvent.EventType.ADMIN,
                section,
                {"action": "delete_document_page_section"},
            )
            response = super().destroy(request, *args, **kwargs)
            if (
                related_page
                and not DocumentPageSection.objects.filter(page=related_page).exists()
                and not CompetitionZoneSection.objects.filter(page=related_page).exists()
            ):
                related_page.delete()
            return response
        except DatabaseError as exc:
            return schema_outdated_response(exc)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[AdminOrSuperAdmin],
        url_path="move",
    )
    def move(self, request, pk=None):
        section = self.get_object()
        direction = parse_move_direction(request)
        if not direction:
            return Response(
                {"detail": "direction must be up or down."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        moved = move_ordered_instance(
            instance=section,
            queryset=DocumentPageSection.objects.all(),
            order_field="display_order",
            direction=direction,
        )
        if not moved:
            return Response(
                {"detail": "Section is already at the edge."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        section.refresh_from_db()
        log_event(
            request.user,
            ContributionEvent.EventType.ADMIN,
            section,
            {"action": f"move_document_page_section_{direction}"},
        )
        return Response(self.get_serializer(section).data)


class CompetitionZoneSectionViewSet(viewsets.ModelViewSet):
    serializer_class = CompetitionZoneSectionSerializer
    queryset = CompetitionZoneSection.objects.select_related("page").all()

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [AllowAny()]
        return [AdminOrSuperAdmin()]

    def get_queryset(self):
        queryset = super().get_queryset()
        include_hidden = self.request.query_params.get("include_hidden") == "1"

        can_access_hidden = can_access_non_public_items(
            user=self.request.user,
            action=getattr(self, "action", ""),
            explicit_include=include_hidden,
            permission_check=is_manager,
        )
        if not can_access_hidden:
            queryset = queryset.filter(is_visible=True)

        target_type = self.request.query_params.get("target_type")
        if target_type in dict(CompetitionZoneSection.TargetType.choices):
            queryset = queryset.filter(target_type=target_type)

        builtin_view = self.request.query_params.get("builtin_view")
        if builtin_view in dict(CompetitionZoneSection.BuiltinView.choices):
            queryset = queryset.filter(builtin_view=builtin_view)

        return queryset.order_by("display_order", "id")

    def list(self, request, *args, **kwargs):
        try:
            return super().list(request, *args, **kwargs)
        except DatabaseError as exc:
            return schema_outdated_response(exc)

    def retrieve(self, request, *args, **kwargs):
        try:
            return super().retrieve(request, *args, **kwargs)
        except DatabaseError as exc:
            return schema_outdated_response(exc)

    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            save_kwargs = {}
            if request.data.get("display_order", None) in {"", None}:
                save_kwargs["display_order"] = get_next_order_value(
                    CompetitionZoneSection.objects.all(),
                    "display_order",
                )
            section = serializer.save(**save_kwargs)
            log_event(
                request.user,
                ContributionEvent.EventType.ADMIN,
                section,
                {"action": "create_competition_zone_section"},
            )
            return Response(
                self.get_serializer(section).data, status=status.HTTP_201_CREATED
            )
        except DatabaseError as exc:
            return schema_outdated_response(exc)

    def update(self, request, *args, **kwargs):
        try:
            partial = kwargs.pop("partial", False)
            section = self.get_object()
            serializer = self.get_serializer(
                section, data=request.data, partial=partial
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            log_event(
                request.user,
                ContributionEvent.EventType.ADMIN,
                section,
                {"action": "update_competition_zone_section"},
            )
            return Response(serializer.data)
        except DatabaseError as exc:
            return schema_outdated_response(exc)

    def destroy(self, request, *args, **kwargs):
        try:
            section = self.get_object()
            related_page = section.page
            log_event(
                request.user,
                ContributionEvent.EventType.ADMIN,
                section,
                {"action": "delete_competition_zone_section"},
            )
            response = super().destroy(request, *args, **kwargs)
            if (
                related_page
                and not CompetitionZoneSection.objects.filter(
                    page=related_page
                ).exists()
            ):
                related_page.delete()
            return response
        except DatabaseError as exc:
            return schema_outdated_response(exc)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[AdminOrSuperAdmin],
        url_path="move",
    )
    def move(self, request, pk=None):
        section = self.get_object()
        direction = parse_move_direction(request)
        if not direction:
            return Response(
                {"detail": "direction must be up or down."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        moved = move_ordered_instance(
            instance=section,
            queryset=CompetitionZoneSection.objects.all(),
            order_field="display_order",
            direction=direction,
        )
        if not moved:
            return Response(
                {"detail": "Section is already at the edge."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        section.refresh_from_db()
        log_event(
            request.user,
            ContributionEvent.EventType.ADMIN,
            section,
            {"action": f"move_competition_zone_section_{direction}"},
        )
        return Response(self.get_serializer(section).data)


class HeaderNavigationItemViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = HeaderNavigationItemSerializer
    queryset = HeaderNavigationItem.objects.all()

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [AllowAny()]
        return [AdminOrSuperAdmin()]

    def get_queryset(self):
        queryset = super().get_queryset()
        include_hidden = self.request.query_params.get("include_hidden") == "1"
        can_access_hidden = can_access_non_public_items(
            user=self.request.user,
            action=getattr(self, "action", ""),
            explicit_include=include_hidden,
            permission_check=is_manager,
        )
        if not can_access_hidden:
            queryset = queryset.filter(is_visible=True)
        return queryset.order_by("display_order", "id")

    def list(self, request, *args, **kwargs):
        try:
            return super().list(request, *args, **kwargs)
        except DatabaseError as exc:
            return schema_outdated_response(exc)

    def retrieve(self, request, *args, **kwargs):
        try:
            return super().retrieve(request, *args, **kwargs)
        except DatabaseError as exc:
            return schema_outdated_response(exc)

    def update(self, request, *args, **kwargs):
        try:
            partial = kwargs.pop("partial", False)
            item = self.get_object()
            serializer = self.get_serializer(item, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            log_event(
                request.user,
                ContributionEvent.EventType.ADMIN,
                item,
                {"action": "update_header_navigation_item"},
            )
            return Response(serializer.data)
        except DatabaseError as exc:
            return schema_outdated_response(exc)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[AdminOrSuperAdmin],
        url_path="move",
    )
    def move(self, request, pk=None):
        item = self.get_object()
        direction = parse_move_direction(request)
        if not direction:
            return Response(
                {"detail": "direction must be up or down."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        moved = move_ordered_instance(
            instance=item,
            queryset=HeaderNavigationItem.objects.all(),
            order_field="display_order",
            direction=direction,
        )
        if not moved:
            return Response(
                {"detail": "Header item is already at the edge."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        item.refresh_from_db()
        log_event(
            request.user,
            ContributionEvent.EventType.ADMIN,
            item,
            {"action": f"move_header_navigation_item_{direction}"},
        )
        return Response(self.get_serializer(item).data)


class AssistantProviderConfigViewSet(viewsets.ModelViewSet):
    serializer_class = AssistantProviderConfigSerializer
    queryset = AssistantProviderConfig.objects.select_related(
        "created_by", "updated_by"
    ).all()

    def get_permissions(self):
        if self.action in {"list", "retrieve", "stats"}:
            return [AdminOrSuperAdmin()]
        return [SuperAdminOnly()]

    def perform_create(self, serializer):
        config = serializer.save(
            created_by=self.request.user, updated_by=self.request.user
        )
        log_event(
            self.request.user,
            ContributionEvent.EventType.ADMIN,
            config,
            {"action": "create_assistant_provider_config"},
        )

    def perform_update(self, serializer):
        config = serializer.save(updated_by=self.request.user)
        log_event(
            self.request.user,
            ContributionEvent.EventType.ADMIN,
            config,
            {"action": "update_assistant_provider_config"},
        )

    def perform_destroy(self, instance):
        log_event(
            self.request.user,
            ContributionEvent.EventType.ADMIN,
            instance,
            {"action": "delete_assistant_provider_config"},
        )
        was_default = instance.is_default
        instance.delete()
        if was_default:
            replacement = (
                AssistantProviderConfig.objects.filter(is_enabled=True)
                .order_by("id")
                .first()
            )
            if replacement:
                replacement.is_default = True
                replacement.save(
                    update_fields=["is_default", "is_enabled", "updated_at"]
                )

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[SuperAdminOnly],
        url_path="set-default",
    )
    def set_default(self, request, pk=None):
        config = self.get_object()
        config.is_default = True
        config.is_enabled = True
        config.updated_by = request.user
        config.save(
            update_fields=["is_default", "is_enabled", "updated_by", "updated_at"]
        )
        log_event(
            request.user,
            ContributionEvent.EventType.ADMIN,
            config,
            {"action": "set_default_assistant_provider_config"},
        )
        return Response(self.get_serializer(config).data)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[SuperAdminOnly],
        url_path="test-connection",
    )
    def test_connection(self, request, pk=None):
        config = self.get_object()
        test_started_at = timezone.now()
        try:
            response = invoke_assistant_completion(
                config=config,
                message="请仅回复：连接成功",
                history=[],
                sources=[
                    {
                        "title": "连接测试",
                        "url": "/manage/assistant",
                        "excerpt": "这是一条站内 AI 助手连接测试消息。请仅回复“连接成功”。",
                    }
                ],
            )
            config.last_tested_at = timezone.now()
            config.last_test_success = True
            config.last_test_message = (response.get("content") or "连接成功")[:255]
            config.updated_by = request.user
            config.save(
                update_fields=[
                    "last_tested_at",
                    "last_test_success",
                    "last_test_message",
                    "updated_by",
                    "updated_at",
                ]
            )
            log_event(
                request.user,
                ContributionEvent.EventType.ADMIN,
                config,
                {
                    "action": "test_assistant_provider_config",
                    "success": True,
                    "response_ms": int(
                        (timezone.now() - test_started_at).total_seconds() * 1000
                    ),
                },
            )
            return Response(
                {
                    "detail": "Connection succeeded.",
                    "response_preview": config.last_test_message,
                    "model": response.get("model") or config.model_name,
                }
            )
        except AssistantProviderError as exc:
            config.last_tested_at = timezone.now()
            config.last_test_success = False
            config.last_test_message = str(exc)[:255]
            config.updated_by = request.user
            config.save(
                update_fields=[
                    "last_tested_at",
                    "last_test_success",
                    "last_test_message",
                    "updated_by",
                    "updated_at",
                ]
            )
            log_event(
                request.user,
                ContributionEvent.EventType.ADMIN,
                config,
                {
                    "action": "test_assistant_provider_config",
                    "success": False,
                    "status_code": exc.status_code,
                },
            )
            return Response({"detail": str(exc)}, status=exc.status_code)

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[AdminOrSuperAdmin],
        url_path="stats",
    )
    def stats(self, request):
        now = timezone.now()
        day_start = now - timedelta(hours=24)
        week_start = now - timedelta(days=7)
        configs = list(self.get_queryset())
        totals = {
            "last_24h_requests": 0,
            "last_24h_success": 0,
            "last_24h_tokens": 0,
            "last_7d_requests": 0,
            "last_7d_tokens": 0,
        }
        per_config = []
        for config in configs:
            last_24h = config.interaction_logs.filter(created_at__gte=day_start)
            last_7d = config.interaction_logs.filter(created_at__gte=week_start)
            last_24h_requests = last_24h.count()
            last_24h_success = last_24h.filter(success=True).count()
            last_24h_tokens = int(
                last_24h.aggregate(total=Sum("total_tokens")).get("total") or 0
            )
            last_7d_requests = last_7d.count()
            last_7d_tokens = int(
                last_7d.aggregate(total=Sum("total_tokens")).get("total") or 0
            )
            totals["last_24h_requests"] += last_24h_requests
            totals["last_24h_success"] += last_24h_success
            totals["last_24h_tokens"] += last_24h_tokens
            totals["last_7d_requests"] += last_7d_requests
            totals["last_7d_tokens"] += last_7d_tokens
            per_config.append(
                {
                    "id": config.id,
                    "label": config.label,
                    "assistant_name": config.assistant_name,
                    "provider": config.provider,
                    "model_name": config.model_name,
                    "is_enabled": config.is_enabled,
                    "is_default": config.is_default,
                    "last_24h_requests": last_24h_requests,
                    "last_24h_success": last_24h_success,
                    "last_24h_tokens": last_24h_tokens,
                    "last_7d_requests": last_7d_requests,
                    "last_7d_tokens": last_7d_tokens,
                }
            )
        return Response(
            {
                "totals": totals,
                "per_config": per_config,
            }
        )


class AssistantPublicConfigView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        payload = get_public_assistant_payload(get_active_assistant_config())
        serializer = AssistantPublicConfigSerializer(payload)
        return Response(serializer.data)


class AssistantChatView(APIView):
    permission_classes = [AllowAny]

    def get_throttles(self):
        if self.request.user and self.request.user.is_authenticated:
            return [AssistantUserRateThrottle()]
        return [AssistantAnonRateThrottle()]

    def post(self, request):
        serializer = AssistantChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = serializer.validated_data["message"]
        history = serializer.validated_data.get("history") or []
        session_id = serializer.validated_data.get("session_id", "")
        current_path = serializer.validated_data.get("current_path", "")
        current_title = serializer.validated_data.get("current_title", "")
        config = get_active_assistant_config()
        if not config or not config.show_launcher:
            create_interaction_log(
                request=request,
                config=config,
                success=False,
                prompt_chars=len(message),
                session_id=session_id,
                error_message="assistant disabled",
            )
            return Response(
                {"detail": "AI assistant is currently unavailable."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        started_at = timezone.now()
        try:
            check_daily_limits(config)
            special = build_recent_competition_digest(message)
            if not special:
                special = build_competition_format_digest(
                    message,
                    current_path=current_path,
                    current_title=current_title,
                )
            if not special:
                special = build_original_problem_site_digest(
                    message,
                    current_path=current_path,
                    current_title=current_title,
                )
            if not special:
                special = build_trick_digest(
                    message,
                    current_path=current_path,
                    current_title=current_title,
                )
            if special:
                answer = strip_assistant_self_reference(
                    special["answer"],
                    assistant_name=config.assistant_name,
                )
                answer = apply_brattish_tone_to_answer(
                    answer,
                    seed_text=f"{message}\n{special['model']}",
                )
                sources = special["sources"]
                answer = append_source_hint_to_answer(answer, sources)
                usage = special["usage"]
                create_interaction_log(
                    request=request,
                    config=config,
                    success=True,
                    prompt_chars=len(message),
                    response_chars=len(answer),
                    prompt_tokens=usage.get("prompt_tokens", 0),
                    completion_tokens=usage.get("completion_tokens", 0),
                    total_tokens=usage.get("total_tokens", 0),
                    source_count=len(sources),
                    response_ms=int(
                        (timezone.now() - started_at).total_seconds() * 1000
                    ),
                    session_id=session_id,
                )
                return Response(
                    {
                        "assistant_name": config.assistant_name,
                        "answer": answer,
                        "sources": sources,
                        "model": special["model"],
                        "usage": usage,
                    }
                )

            sources = search_public_corpus(
                message,
                limit=4,
                current_path=current_path,
                current_title=current_title,
            )
            if not sources:
                answer = apply_brattish_tone_to_answer(
                    "站内当前没有足够信息回答这个问题。你可以换个更具体的问法。",
                    seed_text=message,
                )
                create_interaction_log(
                    request=request,
                    config=config,
                    success=True,
                    prompt_chars=len(message),
                    response_chars=len(answer),
                    source_count=0,
                    response_ms=int(
                        (timezone.now() - started_at).total_seconds() * 1000
                    ),
                    session_id=session_id,
                )
                return Response(
                    {
                        "assistant_name": config.assistant_name,
                        "answer": answer,
                        "sources": [],
                        "model": config.model_name,
                        "usage": {
                            "prompt_tokens": 0,
                            "completion_tokens": 0,
                            "total_tokens": 0,
                        },
                    }
                )

            result = invoke_assistant_completion(
                config=config,
                message=message,
                history=history,
                sources=sources,
            )
            raw_answer = (
                result.get("content") or ""
            ).strip() or "站内当前没有足够信息回答这个问题。"
            raw_answer = strip_assistant_self_reference(
                raw_answer, assistant_name=config.assistant_name
            )
            answer = apply_brattish_tone_to_answer(raw_answer, seed_text=message)
            usage = result.get("usage") or {}
            answer = append_source_hint_to_answer(answer, sources)
            create_interaction_log(
                request=request,
                config=config,
                success=True,
                prompt_chars=len(message),
                response_chars=len(answer),
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
                source_count=len(sources),
                response_ms=int((timezone.now() - started_at).total_seconds() * 1000),
                session_id=session_id,
            )
            return Response(
                {
                    "assistant_name": config.assistant_name,
                    "answer": answer,
                    "sources": [
                        {
                            "source_type": item["source_type"],
                            "source_id": item["source_id"],
                            "title": item["title"],
                            "url": item["url"],
                            "excerpt": item["excerpt"],
                        }
                        for item in sources
                    ],
                    "model": result.get("model") or config.model_name,
                    "usage": usage,
                }
            )
        except AssistantProviderError as exc:
            create_interaction_log(
                request=request,
                config=config,
                success=False,
                prompt_chars=len(message),
                source_count=0,
                response_ms=int((timezone.now() - started_at).total_seconds() * 1000),
                session_id=session_id,
                error_message=str(exc),
            )
            api_logger.warning(
                "Assistant chat failed status=%s detail=%s", exc.status_code, str(exc)
            )
            return Response({"detail": str(exc)}, status=exc.status_code)


class FriendlyLinkViewSet(viewsets.ModelViewSet):
    serializer_class = FriendlyLinkSerializer
    queryset = FriendlyLink.objects.select_related("created_by").all()

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [AllowAny()]
        return [AdminOrSuperAdmin()]

    def get_queryset(self):
        queryset = super().get_queryset()
        if is_manager(self.request.user):
            include_disabled = self.request.query_params.get("include_disabled") == "1"
            can_access_disabled = can_access_non_public_items(
                user=self.request.user,
                action=getattr(self, "action", ""),
                explicit_include=include_disabled,
                permission_check=is_manager,
            )
            if can_access_disabled:
                return queryset
            return queryset.filter(is_enabled=True)
        return queryset.filter(is_enabled=True)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        link = serializer.save(created_by=request.user)
        log_event(
            request.user,
            ContributionEvent.EventType.ADMIN,
            link,
            {"action": "create_friendly_link"},
        )
        return Response(self.get_serializer(link).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        link = self.get_object()
        serializer = self.get_serializer(link, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        log_event(
            request.user,
            ContributionEvent.EventType.ADMIN,
            link,
            {"action": "update_friendly_link"},
        )
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        link = self.get_object()
        log_event(
            request.user,
            ContributionEvent.EventType.ADMIN,
            link,
            {"action": "delete_friendly_link"},
        )
        return super().destroy(request, *args, **kwargs)


class CompetitionNoticeViewSet(ReviewNoteActionMixin, viewsets.ModelViewSet):
    serializer_class = CompetitionNoticeSerializer
    queryset = CompetitionNotice.objects.select_related(
        "created_by", "updated_by", "reviewer", "revision_of"
    ).all()

    def get_permissions(self):
        if self.action in {"list", "retrieve", "taxonomy"}:
            return [AllowAny()]
        if self.action in {"approve", "reject", "append_review_note"}:
            return [AdminOrSuperAdmin()]
        return [AuthenticatedAndNotBanned()]

    def _ensure_editor(self, request):
        if request.user.is_banned:
            return Response(
                {"detail": "Banned users cannot edit competition content."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not can_manage_competition(request.user):
            return Response(
                {"detail": "Only school/admin users can edit competition notices."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return None

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        include_hidden = self.request.query_params.get("include_hidden") == "1"
        include_revisions = (
            self.request.query_params.get("include_revisions") == "1"
            or self.action in {"approve", "reject", "append_review_note"}
        )
        if not include_revisions:
            queryset = queryset.filter(revision_of__isnull=True)
        can_access_hidden = can_access_non_public_items(
            user=user,
            action=getattr(self, "action", ""),
            explicit_include=include_hidden,
            permission_check=can_manage_competition,
        )
        if self.action in {"approve", "reject", "append_review_note"} and can_manage_competition(user):
            can_access_hidden = True
        if not can_access_hidden:
            queryset = queryset.filter(
                is_visible=True,
                status=CompetitionNotice.Status.APPROVED,
            )

        status_filter = self.request.query_params.get("status")
        if status_filter in dict(CompetitionNotice.Status.choices):
            if can_manage_competition(user):
                queryset = queryset.filter(status=status_filter)
            elif status_filter != CompetitionNotice.Status.APPROVED:
                queryset = queryset.none()

        series = self.request.query_params.get("series")
        if series in dict(CompetitionNotice.Series.choices):
            queryset = queryset.filter(series=series)

        year = self.request.query_params.get("year")
        if isinstance(year, str) and year.strip():
            try:
                queryset = queryset.filter(year=int(year))
            except (TypeError, ValueError):
                queryset = queryset.none()

        stage = self.request.query_params.get("stage")
        if stage in dict(CompetitionNotice.Stage.choices):
            queryset = queryset.filter(stage=stage)

        search = self.request.query_params.get("search")
        if search:
            token = search.strip()
            queryset = queryset.filter(
                Q(title__icontains=token) | Q(content_md__icontains=token)
            )

        order = self.request.query_params.get("order")
        if order == "oldest":
            return queryset.order_by("published_at", "id")
        return queryset.order_by("-published_at", "-updated_at", "-id")

    def create(self, request, *args, **kwargs):
        try:
            if request.user.is_banned:
                return Response(
                    {"detail": "Banned users cannot edit competition content."},
                    status=status.HTTP_403_FORBIDDEN,
                )

            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            can_publish_directly = can_manage_competition(request.user)
            save_kwargs = {
                "created_by": request.user,
                "updated_by": request.user,
            }
            if can_publish_directly:
                save_kwargs.update(
                    {
                        "status": CompetitionNotice.Status.APPROVED,
                        "reviewer": request.user,
                        "review_note": "manager_direct_publish",
                        "reviewed_at": timezone.now(),
                    }
                )
            else:
                save_kwargs.update(
                    {
                        "status": CompetitionNotice.Status.PENDING,
                        "is_visible": False,
                        "reviewer": None,
                        "review_note": "",
                        "reviewed_at": None,
                    }
                )
            notice = serializer.save(**save_kwargs)
            log_event(
                request.user,
                (
                    ContributionEvent.EventType.ADMIN
                    if can_publish_directly
                    else ContributionEvent.EventType.ANNOUNCEMENT
                ),
                notice,
                {"action": "create_competition_notice"},
            )
            return Response(
                self.get_serializer(notice).data, status=status.HTTP_201_CREATED
            )
        except DatabaseError as exc:
            return schema_outdated_response(exc)

    def update(self, request, *args, **kwargs):
        try:
            if request.user.is_banned:
                return Response(
                    {"detail": "Banned users cannot edit competition content."},
                    status=status.HTTP_403_FORBIDDEN,
                )

            partial = kwargs.pop("partial", False)
            notice = self.get_object()
            if notice.revision_of_id and not can_manage_competition(request.user):
                return Response(
                    {"detail": "Cannot edit a pending competition notice revision."},
                    status=status.HTTP_403_FORBIDDEN,
                )

            serializer = self.get_serializer(notice, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)

            if can_manage_competition(request.user):
                serializer.save(updated_by=request.user)
                log_event(
                    request.user,
                    ContributionEvent.EventType.ADMIN,
                    notice,
                    {"action": "update_competition_notice"},
                )
                return Response(serializer.data)

            revision_values = {
                "title": serializer.validated_data.get("title", notice.title),
                "content_md": serializer.validated_data.get(
                    "content_md", notice.content_md
                ),
                "series": serializer.validated_data.get("series", notice.series),
                "year": serializer.validated_data.get("year", notice.year),
                "stage": serializer.validated_data.get("stage", notice.stage),
            }
            with transaction.atomic():
                revision = (
                    CompetitionNotice.objects.select_for_update()
                    .filter(
                        revision_of=notice,
                        created_by=request.user,
                        status=CompetitionNotice.Status.PENDING,
                    )
                    .order_by("-updated_at", "-id")
                    .first()
                )
                if revision is None:
                    revision = CompetitionNotice(
                        revision_of=notice,
                        created_by=request.user,
                        published_at=timezone.now(),
                    )
                for field, value in revision_values.items():
                    setattr(revision, field, value)
                revision.updated_by = request.user
                revision.is_visible = False
                revision.status = CompetitionNotice.Status.PENDING
                revision.reviewer = None
                revision.review_note = ""
                revision.reviewed_at = None
                revision.save()

            log_event(
                request.user,
                ContributionEvent.EventType.ANNOUNCEMENT,
                revision,
                {
                    "action": "submit_competition_notice_revision",
                    "target_notice_id": notice.id,
                },
            )
            return Response(self.get_serializer(revision).data)
        except DatabaseError as exc:
            return schema_outdated_response(exc)

    def destroy(self, request, *args, **kwargs):
        try:
            denied = self._ensure_editor(request)
            if denied:
                return denied

            notice = self.get_object()
            with transaction.atomic():
                archive_deleted_content(
                    instance=notice,
                    operator=request.user,
                    delete_action=DeletedContentArchive.DeleteAction.DELETE,
                )
                log_event(
                    request.user,
                    ContributionEvent.EventType.ADMIN,
                    notice,
                    {"action": "delete_competition_notice"},
                )
                self.perform_destroy(notice)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except DatabaseError as exc:
            return schema_outdated_response(exc)

    def list(self, request, *args, **kwargs):
        try:
            return super().list(request, *args, **kwargs)
        except DatabaseError as exc:
            return schema_outdated_response(exc)

    def retrieve(self, request, *args, **kwargs):
        try:
            return super().retrieve(request, *args, **kwargs)
        except DatabaseError as exc:
            return schema_outdated_response(exc)

    def _apply_review_action(self, notice, reviewer, *, action, review_note=""):
        if not is_manager(reviewer):
            return False, status.HTTP_403_FORBIDDEN, "Only admins can review notices."
        if notice.status != CompetitionNotice.Status.PENDING:
            return False, status.HTTP_400_BAD_REQUEST, "Notice is already reviewed."

        action = (action or "").strip().lower()
        review_note = "" if review_note is None else str(review_note)
        now = timezone.now()
        revision_target = notice.revision_of
        revision_editor = notice.updated_by or notice.created_by
        if action == "approve":
            notice.status = CompetitionNotice.Status.APPROVED
            notice.is_visible = False if revision_target else True
            notice.published_at = now
            action_name = "approve_competition_notice"
        elif action == "reject":
            notice.status = CompetitionNotice.Status.REJECTED
            notice.is_visible = False
            action_name = "reject_competition_notice"
        else:
            return False, status.HTTP_400_BAD_REQUEST, "Invalid review action."

        notice.reviewer = reviewer
        notice.review_note = review_note
        notice.reviewed_at = now
        notice.updated_by = revision_editor
        notice.save(
            update_fields=[
                "status",
                "is_visible",
                "published_at",
                "reviewer",
                "review_note",
                "reviewed_at",
                "updated_by",
                "updated_at",
            ]
        )
        if action == "approve" and revision_target:
            revision_target.title = notice.title
            revision_target.content_md = notice.content_md
            revision_target.series = notice.series
            revision_target.year = notice.year
            revision_target.stage = notice.stage
            revision_target.is_visible = True
            revision_target.status = CompetitionNotice.Status.APPROVED
            revision_target.published_at = now
            revision_target.updated_by = revision_editor
            revision_target.save(
                update_fields=[
                    "title",
                    "content_md",
                    "series",
                    "year",
                    "stage",
                    "is_visible",
                    "status",
                    "published_at",
                    "updated_by",
                    "updated_at",
                ]
            )
            log_event(
                revision_editor,
                ContributionEvent.EventType.ANNOUNCEMENT,
                revision_target,
                {
                    "action": "update_competition_notice",
                    "revision_id": notice.id,
                },
            )
        log_event(reviewer, ContributionEvent.EventType.ADMIN, notice, {"action": action_name})
        if notice.created_by_id != reviewer.id:
            create_notification(
                user=notice.created_by,
                actor=reviewer,
                target=notice,
                title=f"赛事公告已{'通过' if action == 'approve' else '驳回'}：{notice.title}",
                content=build_review_notification_content(
                    action=action,
                    review_note=review_note,
                    approved_fallback="管理员已处理你的赛事公告提交。",
                    rejected_fallback="管理员驳回了你的赛事公告提交。",
                ),
                link="/competitions?tab=notice",
                level=(
                    UserNotification.Level.WARNING
                    if action == "reject"
                    else UserNotification.Level.INFO
                ),
            )
        return True, status.HTTP_200_OK, None

    @action(detail=True, methods=["post"], permission_classes=[AdminOrSuperAdmin])
    def approve(self, request, pk=None):
        try:
            notice = self.get_object()
            ok, error_status, detail = self._apply_review_action(
                notice,
                request.user,
                action="approve",
                review_note=request.data.get("review_note", ""),
            )
            if not ok:
                return Response({"detail": detail}, status=error_status)
            return Response(self.get_serializer(notice).data)
        except DatabaseError as exc:
            return schema_outdated_response(exc)

    @action(detail=True, methods=["post"], permission_classes=[AdminOrSuperAdmin])
    def reject(self, request, pk=None):
        try:
            notice = self.get_object()
            ok, error_status, detail = self._apply_review_action(
                notice,
                request.user,
                action="reject",
                review_note=request.data.get("review_note", ""),
            )
            if not ok:
                return Response({"detail": detail}, status=error_status)
            return Response(self.get_serializer(notice).data)
        except DatabaseError as exc:
            return schema_outdated_response(exc)

    @action(detail=False, methods=["get"], permission_classes=[AllowAny])
    def taxonomy(self, request):
        try:
            user = request.user
            include_hidden = request.query_params.get("include_hidden") == "1"
            queryset = CompetitionNotice.objects.all()
            if not (can_manage_competition(user) and include_hidden):
                queryset = queryset.filter(
                    is_visible=True,
                    status=CompetitionNotice.Status.APPROVED,
                )

            stage_labels = dict(CompetitionNotice.Stage.choices)
            data = []
            for series_key, series_label in CompetitionNotice.Series.choices:
                series_qs = queryset.filter(series=series_key)
                years = sorted(
                    set(
                        series_qs.exclude(year__isnull=True).values_list(
                            "year", flat=True
                        )
                    ),
                    reverse=True,
                )
                if series_key in {
                    CompetitionNotice.Series.ICPC,
                    CompetitionNotice.Series.CCPC,
                }:
                    stage_keys = [
                        CompetitionNotice.Stage.REGIONAL,
                        CompetitionNotice.Stage.INVITATIONAL,
                        CompetitionNotice.Stage.PROVINCIAL,
                        CompetitionNotice.Stage.NETWORK,
                    ]
                elif series_key == CompetitionNotice.Series.LANQIAO:
                    stage_keys = [
                        CompetitionNotice.Stage.NATIONAL,
                        CompetitionNotice.Stage.PROVINCIAL,
                    ]
                elif series_key == CompetitionNotice.Series.TIANTI:
                    stage_keys = [
                        CompetitionNotice.Stage.POPULAR,
                        CompetitionNotice.Stage.STANDARD,
                    ]
                else:
                    stage_keys = [CompetitionNotice.Stage.GENERAL]

                stages = [
                    {
                        "key": stage_key,
                        "name": stage_labels.get(stage_key, stage_key),
                        "count": series_qs.filter(stage=stage_key).count(),
                    }
                    for stage_key in stage_keys
                ]
                data.append(
                    {
                        "key": series_key,
                        "name": series_label,
                        "count": series_qs.count(),
                        "years": years,
                        "stages": stages,
                    }
                )
            return Response({"series": data})
        except DatabaseError as exc:
            return schema_outdated_response(exc)


class CompetitionScheduleEntryViewSet(ReviewNoteActionMixin, viewsets.ModelViewSet):
    serializer_class = CompetitionScheduleEntrySerializer
    queryset = CompetitionScheduleEntry.objects.select_related(
        "announcement", "created_by", "updated_by", "reviewer"
    ).all()

    def get_permissions(self):
        if self.action in {"list", "retrieve", "years"}:
            return [AllowAny()]
        if self.action in {"approve", "reject", "append_review_note"}:
            return [AdminOrSuperAdmin()]
        return [AuthenticatedAndNotBanned()]

    def _ensure_editor(self, request):
        if request.user.is_banned:
            return Response(
                {"detail": "Banned users cannot edit competition content."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not can_manage_competition(request.user):
            return Response(
                {"detail": "Only school/admin users can edit competition schedules."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return None

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        include_hidden = self.request.query_params.get("include_hidden") == "1"
        can_access_hidden = can_access_non_public_items(
            user=user,
            action=getattr(self, "action", ""),
            explicit_include=include_hidden,
            permission_check=can_manage_competition,
        )
        if self.action in {"approve", "reject", "append_review_note"} and can_manage_competition(user):
            can_access_hidden = True
        if not can_access_hidden:
            queryset = queryset.filter(
                status=CompetitionScheduleEntry.Status.APPROVED
            ).filter(
                Q(announcement__isnull=True)
                | Q(
                    announcement__is_visible=True,
                    announcement__status=CompetitionNotice.Status.APPROVED,
                )
            )

        status_filter = self.request.query_params.get("status")
        if status_filter in dict(CompetitionScheduleEntry.Status.choices):
            if can_manage_competition(user):
                queryset = queryset.filter(status=status_filter)
            elif status_filter != CompetitionScheduleEntry.Status.APPROVED:
                queryset = queryset.none()

        year = self.request.query_params.get("year")
        if isinstance(year, str) and year.strip():
            try:
                queryset = queryset.filter(event_date__year=int(year))
            except (TypeError, ValueError):
                queryset = queryset.none()

        competition_type = self.request.query_params.get("competition_type")
        if competition_type:
            queryset = queryset.filter(
                competition_type__icontains=competition_type.strip()
            )

        series = self.request.query_params.get("series")
        if series in dict(CompetitionNotice.Series.choices):
            queryset = queryset.filter(announcement__series=series)

        order = self.request.query_params.get("order")
        if order == "desc":
            return queryset.order_by("-event_date", "-id")
        return queryset.order_by("event_date", "id")

    def create(self, request, *args, **kwargs):
        try:
            if request.user.is_banned:
                return Response(
                    {"detail": "Banned users cannot edit competition content."},
                    status=status.HTTP_403_FORBIDDEN,
                )

            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            can_publish_directly = can_manage_competition(request.user)
            save_kwargs = {
                "created_by": request.user,
                "updated_by": request.user,
            }
            if can_publish_directly:
                save_kwargs.update(
                    {
                        "status": CompetitionScheduleEntry.Status.APPROVED,
                        "reviewer": request.user,
                        "review_note": "manager_direct_publish",
                        "reviewed_at": timezone.now(),
                    }
                )
            else:
                save_kwargs.update(
                    {
                        "status": CompetitionScheduleEntry.Status.PENDING,
                        "reviewer": None,
                        "review_note": "",
                        "reviewed_at": None,
                    }
                )
            entry = serializer.save(**save_kwargs)
            log_event(
                request.user,
                (
                    ContributionEvent.EventType.ADMIN
                    if can_publish_directly
                    else ContributionEvent.EventType.ISSUE
                ),
                entry,
                {"action": "create_competition_schedule"},
            )
            return Response(
                self.get_serializer(entry).data, status=status.HTTP_201_CREATED
            )
        except DatabaseError as exc:
            return schema_outdated_response(exc)

    def update(self, request, *args, **kwargs):
        try:
            denied = self._ensure_editor(request)
            if denied:
                return denied

            partial = kwargs.pop("partial", False)
            entry = self.get_object()
            serializer = self.get_serializer(entry, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)
            serializer.save(updated_by=request.user)
            log_event(
                request.user,
                ContributionEvent.EventType.ADMIN,
                entry,
                {"action": "update_competition_schedule"},
            )
            return Response(serializer.data)
        except DatabaseError as exc:
            return schema_outdated_response(exc)

    def destroy(self, request, *args, **kwargs):
        try:
            denied = self._ensure_editor(request)
            if denied:
                return denied

            entry = self.get_object()
            with transaction.atomic():
                archive_deleted_content(
                    instance=entry,
                    operator=request.user,
                    delete_action=DeletedContentArchive.DeleteAction.DELETE,
                )
                log_event(
                    request.user,
                    ContributionEvent.EventType.ADMIN,
                    entry,
                    {"action": "delete_competition_schedule"},
                )
                self.perform_destroy(entry)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except DatabaseError as exc:
            return schema_outdated_response(exc)

    def list(self, request, *args, **kwargs):
        try:
            return super().list(request, *args, **kwargs)
        except DatabaseError as exc:
            return schema_outdated_response(exc)

    def retrieve(self, request, *args, **kwargs):
        try:
            return super().retrieve(request, *args, **kwargs)
        except DatabaseError as exc:
            return schema_outdated_response(exc)

    def _apply_review_action(self, entry, reviewer, *, action, review_note=""):
        if not is_manager(reviewer):
            return False, status.HTTP_403_FORBIDDEN, "Only admins can review schedules."
        if entry.status != CompetitionScheduleEntry.Status.PENDING:
            return False, status.HTTP_400_BAD_REQUEST, "Schedule entry is already reviewed."

        action = (action or "").strip().lower()
        review_note = "" if review_note is None else str(review_note)
        now = timezone.now()
        if action == "approve":
            entry.status = CompetitionScheduleEntry.Status.APPROVED
            action_name = "approve_competition_schedule"
        elif action == "reject":
            entry.status = CompetitionScheduleEntry.Status.REJECTED
            action_name = "reject_competition_schedule"
        else:
            return False, status.HTTP_400_BAD_REQUEST, "Invalid review action."

        entry.reviewer = reviewer
        entry.review_note = review_note
        entry.reviewed_at = now
        entry.updated_by = reviewer
        entry.save(
            update_fields=[
                "status",
                "reviewer",
                "review_note",
                "reviewed_at",
                "updated_by",
                "updated_at",
            ]
        )
        log_event(reviewer, ContributionEvent.EventType.ADMIN, entry, {"action": action_name})
        if entry.created_by_id != reviewer.id:
            create_notification(
                user=entry.created_by,
                actor=reviewer,
                target=entry,
                title=f"锦标赛已{'通过' if action == 'approve' else '驳回'}：{entry.competition_type}",
                content=build_review_notification_content(
                    action=action,
                    review_note=review_note,
                    approved_fallback="管理员已处理你的锦标赛提交。",
                    rejected_fallback="管理员驳回了你的锦标赛提交。",
                ),
                link="/competitions?tab=schedule",
                level=(
                    UserNotification.Level.WARNING
                    if action == "reject"
                    else UserNotification.Level.INFO
                ),
            )
        return True, status.HTTP_200_OK, None

    @action(detail=True, methods=["post"], permission_classes=[AdminOrSuperAdmin])
    def approve(self, request, pk=None):
        try:
            entry = self.get_object()
            ok, error_status, detail = self._apply_review_action(
                entry,
                request.user,
                action="approve",
                review_note=request.data.get("review_note", ""),
            )
            if not ok:
                return Response({"detail": detail}, status=error_status)
            return Response(self.get_serializer(entry).data)
        except DatabaseError as exc:
            return schema_outdated_response(exc)

    @action(detail=True, methods=["post"], permission_classes=[AdminOrSuperAdmin])
    def reject(self, request, pk=None):
        try:
            entry = self.get_object()
            ok, error_status, detail = self._apply_review_action(
                entry,
                request.user,
                action="reject",
                review_note=request.data.get("review_note", ""),
            )
            if not ok:
                return Response({"detail": detail}, status=error_status)
            return Response(self.get_serializer(entry).data)
        except DatabaseError as exc:
            return schema_outdated_response(exc)

    @action(detail=False, methods=["get"], permission_classes=[AllowAny])
    def years(self, request):
        try:
            user = request.user
            include_hidden = request.query_params.get("include_hidden") == "1"
            queryset = CompetitionScheduleEntry.objects.all()
            if not (can_manage_competition(user) and include_hidden):
                queryset = queryset.filter(
                    status=CompetitionScheduleEntry.Status.APPROVED
                ).filter(
                    Q(announcement__isnull=True)
                    | Q(
                        announcement__is_visible=True,
                        announcement__status=CompetitionNotice.Status.APPROVED,
                    )
                )

            years = sorted(
                set(queryset.values_list("event_date__year", flat=True)), reverse=True
            )
            if not years:
                years = [2026]
            return Response({"years": years})
        except DatabaseError as exc:
            return schema_outdated_response(exc)


class CompetitionPracticeLinkViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = CompetitionPracticeLinkSerializer
    queryset = CompetitionPracticeLink.objects.select_related(
        "created_by", "updated_by"
    ).all()
    permission_classes = [AllowAny]

    def get_permissions(self):
        if self.action in {"list", "retrieve", "taxonomy"}:
            return [AllowAny()]
        return [AdminOrSuperAdmin()]

    def get_queryset(self):
        queryset = super().get_queryset()

        year = self.request.query_params.get("year")
        if isinstance(year, str) and year.strip():
            try:
                queryset = queryset.filter(year=int(year))
            except (TypeError, ValueError):
                queryset = queryset.none()

        series = self.request.query_params.get("series")
        if series in dict(CompetitionPracticeLink.Series.choices):
            queryset = queryset.filter(series=series)

        stage = self.request.query_params.get("stage")
        if stage in dict(CompetitionPracticeLink.Stage.choices):
            queryset = queryset.filter(stage=stage)

        search = self.request.query_params.get("search")
        if search:
            token = search.strip()
            queryset = queryset.filter(
                Q(short_name__icontains=token)
                | Q(official_name__icontains=token)
                | Q(organizer__icontains=token)
                | Q(practice_links_note__icontains=token)
                | Q(source_section__icontains=token)
            )

        order = self.request.query_params.get("order")
        if order == "year_asc":
            return queryset.order_by("year", "display_order", "id")
        return queryset.order_by("-year", "display_order", "id")

    def list(self, request, *args, **kwargs):
        try:
            return super().list(request, *args, **kwargs)
        except DatabaseError as exc:
            return schema_outdated_response(exc)

    def retrieve(self, request, *args, **kwargs):
        try:
            return super().retrieve(request, *args, **kwargs)
        except DatabaseError as exc:
            return schema_outdated_response(exc)

    @action(
        detail=True,
        methods=["delete"],
        permission_classes=[AdminOrSuperAdmin],
        url_path="remove",
    )
    def remove(self, request, pk=None):
        try:
            entry = self.get_object()
            entry_id = entry.id
            entry_name = entry.short_name or entry.official_name or f"entry-{entry_id}"
            with transaction.atomic():
                archive_deleted_content(
                    instance=entry,
                    operator=request.user,
                    delete_action=DeletedContentArchive.DeleteAction.DELETE,
                )
                log_event(
                    request.user,
                    ContributionEvent.EventType.ADMIN,
                    entry,
                    {
                        "action": "delete_competition_practice_link",
                        "entry_id": entry_id,
                        "short_name": entry_name[:120],
                    },
                )
                entry.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except DatabaseError as exc:
            return schema_outdated_response(exc)

    @action(detail=False, methods=["get"], permission_classes=[AllowAny])
    def taxonomy(self, request):
        try:
            queryset = CompetitionPracticeLink.objects.all()
            years = sorted(set(queryset.values_list("year", flat=True)), reverse=True)
            return Response(
                {
                    "count": queryset.count(),
                    "years": years,
                    "series": [
                        {
                            "key": key,
                            "name": label,
                            "count": queryset.filter(series=key).count(),
                        }
                        for key, label in CompetitionPracticeLink.Series.choices
                    ],
                    "stages": [
                        {
                            "key": key,
                            "name": label,
                            "count": queryset.filter(stage=key).count(),
                        }
                        for key, label in CompetitionPracticeLink.Stage.choices
                    ],
                    "sources": sorted(
                        {
                            value
                            for value in queryset.exclude(source_file="").values_list(
                                "source_file", flat=True
                            )
                        }
                    ),
                }
            )
        except DatabaseError as exc:
            return schema_outdated_response(exc)


class CompetitionPracticeLinkProposalViewSet(
    ReviewNoteActionMixin, ActionThrottleMixin, viewsets.ModelViewSet
):
    serializer_class = CompetitionPracticeLinkProposalSerializer
    queryset = CompetitionPracticeLinkProposal.objects.select_related(
        "target_entry",
        "proposer",
        "reviewer",
    ).all()
    permission_classes = [AuthenticatedAndNotBanned]
    throttle_action_classes = {
        "create": [ContentCreateRateThrottle],
        "update": [ContentUpdateRateThrottle],
        "partial_update": [ContentUpdateRateThrottle],
        "destroy": [ContentDeleteRateThrottle],
    }

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if not is_manager(user):
            queryset = queryset.filter(proposer=user)

        status_filter = self.request.query_params.get("status")
        if status_filter in dict(CompetitionPracticeLinkProposal.Status.choices):
            queryset = queryset.filter(status=status_filter)

        target_entry = self.request.query_params.get("target_entry")
        if isinstance(target_entry, str) and target_entry.strip():
            try:
                queryset = queryset.filter(target_entry_id=int(target_entry))
            except (TypeError, ValueError):
                queryset = queryset.none()

        return queryset.order_by("-created_at")

    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            proposal = serializer.save(proposer=request.user)
            log_event(
                request.user,
                ContributionEvent.EventType.ISSUE,
                proposal,
                {"action": "create_competition_practice_proposal"},
            )
            return Response(
                self.get_serializer(proposal).data, status=status.HTTP_201_CREATED
            )
        except DatabaseError as exc:
            return schema_outdated_response(exc)

    def update(self, request, *args, **kwargs):
        try:
            partial = kwargs.pop("partial", False)
            proposal = self.get_object()
            if not (
                is_manager(request.user) or proposal.proposer_id == request.user.id
            ):
                return Response(
                    {"detail": "No permission to edit this proposal."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            if proposal.status != CompetitionPracticeLinkProposal.Status.PENDING:
                return Response(
                    {"detail": "Only pending proposals can be edited."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            serializer = self.get_serializer(
                proposal, data=request.data, partial=partial
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            log_event(
                request.user,
                (
                    ContributionEvent.EventType.ISSUE
                    if proposal.proposer_id == request.user.id
                    else ContributionEvent.EventType.ADMIN
                ),
                proposal,
                {"action": "update_competition_practice_proposal"},
            )
            return Response(serializer.data)
        except DatabaseError as exc:
            return schema_outdated_response(exc)

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        try:
            proposal = self.get_object()
            if not (
                is_manager(request.user) or proposal.proposer_id == request.user.id
            ):
                return Response(
                    {"detail": "No permission to delete this proposal."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            if proposal.status != CompetitionPracticeLinkProposal.Status.PENDING:
                return Response(
                    {"detail": "Only pending proposals can be deleted."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            log_event(
                request.user,
                (
                    ContributionEvent.EventType.ISSUE
                    if proposal.proposer_id == request.user.id
                    else ContributionEvent.EventType.ADMIN
                ),
                proposal,
                {"action": "delete_competition_practice_proposal"},
            )
            return super().destroy(request, *args, **kwargs)
        except DatabaseError as exc:
            return schema_outdated_response(exc)

    def list(self, request, *args, **kwargs):
        try:
            return super().list(request, *args, **kwargs)
        except DatabaseError as exc:
            return schema_outdated_response(exc)

    def retrieve(self, request, *args, **kwargs):
        try:
            return super().retrieve(request, *args, **kwargs)
        except DatabaseError as exc:
            return schema_outdated_response(exc)

    def _ensure_manager(self, user):
        return bool(user and user.is_authenticated and is_manager(user))

    def _apply_review_action(self, proposal, reviewer, *, action, review_note=""):
        if not self._ensure_manager(reviewer):
            return (
                False,
                status.HTTP_403_FORBIDDEN,
                "Only admins can review practice-link proposals.",
            )
        if proposal.status != CompetitionPracticeLinkProposal.Status.PENDING:
            return False, status.HTTP_400_BAD_REQUEST, "Proposal is already reviewed."

        action = (action or "").strip().lower()
        review_note = "" if review_note is None else str(review_note)
        now = timezone.now()

        if action == "approve":
            with transaction.atomic():
                target = proposal.target_entry
                if target is None:
                    next_display_order = (
                        CompetitionPracticeLink.objects.order_by("-display_order")
                        .values_list("display_order", flat=True)
                        .first()
                        or 0
                    )
                    target = CompetitionPracticeLink.objects.create(
                        source_key=f"manual-proposal-{proposal.id}",
                        year=proposal.proposed_year,
                        series=proposal.proposed_series,
                        stage=proposal.proposed_stage,
                        short_name=proposal.proposed_short_name,
                        official_name=proposal.proposed_official_name,
                        official_url=proposal.proposed_official_url,
                        event_date=proposal.proposed_event_date,
                        event_date_text=proposal.proposed_event_date_text,
                        organizer=proposal.proposed_organizer,
                        practice_links=proposal.proposed_practice_links,
                        practice_links_note=proposal.proposed_practice_links_note,
                        source_file="user_proposal",
                        source_section="user_submission",
                        display_order=next_display_order + 1,
                        created_by=proposal.proposer,
                        updated_by=reviewer,
                    )
                else:
                    target.year = proposal.proposed_year
                    target.series = proposal.proposed_series
                    target.stage = proposal.proposed_stage
                    target.short_name = proposal.proposed_short_name
                    target.official_name = proposal.proposed_official_name
                    target.official_url = proposal.proposed_official_url
                    target.event_date = proposal.proposed_event_date
                    target.event_date_text = proposal.proposed_event_date_text
                    target.organizer = proposal.proposed_organizer
                    target.practice_links = proposal.proposed_practice_links
                    target.practice_links_note = proposal.proposed_practice_links_note
                    if not target.source_file:
                        target.source_file = "user_proposal"
                    if not target.source_section:
                        target.source_section = "user_submission"
                    target.updated_by = reviewer
                    target.save()

                proposal.target_entry = target
                proposal.status = CompetitionPracticeLinkProposal.Status.APPROVED
                proposal.reviewer = reviewer
                proposal.review_note = review_note
                proposal.reviewed_at = now
                proposal.save(
                    update_fields=[
                        "target_entry",
                        "status",
                        "reviewer",
                        "review_note",
                        "reviewed_at",
                        "updated_at",
                    ]
                )
        elif action == "reject":
            proposal.status = CompetitionPracticeLinkProposal.Status.REJECTED
            proposal.reviewer = reviewer
            proposal.review_note = review_note
            proposal.reviewed_at = now
            proposal.save(
                update_fields=[
                    "status",
                    "reviewer",
                    "review_note",
                    "reviewed_at",
                    "updated_at",
                ]
            )
        else:
            return False, status.HTTP_400_BAD_REQUEST, "Invalid review action."

        log_event(
            reviewer,
            ContributionEvent.EventType.ADMIN,
            proposal,
            {"action": f"{action}_competition_practice_proposal"},
        )
        if proposal.proposer_id != reviewer.id:
            create_notification(
                user=proposal.proposer,
                actor=reviewer,
                target=proposal,
                title=f"补题链接申请已{ '通过' if action == 'approve' else '驳回' }：{proposal.proposed_short_name}",
                content=build_review_notification_content(
                    action=action,
                    review_note=review_note,
                    approved_fallback="管理员已处理你的补题链接申请。",
                    rejected_fallback="管理员驳回了你的补题链接申请。",
                ),
                link="/competition",
                level=(
                    UserNotification.Level.WARNING
                    if action == "reject"
                    else UserNotification.Level.INFO
                ),
            )
        return True, status.HTTP_200_OK, None

    @action(detail=True, methods=["post"], permission_classes=[AdminOrSuperAdmin])
    def approve(self, request, pk=None):
        try:
            proposal = self.get_object()
            ok, error_status, detail = self._apply_review_action(
                proposal,
                request.user,
                action="approve",
                review_note=request.data.get("review_note", ""),
            )
            if not ok:
                return Response({"detail": detail}, status=error_status)
            return Response(self.get_serializer(proposal).data)
        except DatabaseError as exc:
            return schema_outdated_response(exc)

    @action(detail=True, methods=["post"], permission_classes=[AdminOrSuperAdmin])
    def reject(self, request, pk=None):
        try:
            proposal = self.get_object()
            ok, error_status, detail = self._apply_review_action(
                proposal,
                request.user,
                action="reject",
                review_note=request.data.get("review_note", ""),
            )
            if not ok:
                return Response({"detail": detail}, status=error_status)
            return Response(self.get_serializer(proposal).data)
        except DatabaseError as exc:
            return schema_outdated_response(exc)


class CompetitionCalendarEventViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = CompetitionCalendarEventSerializer
    queryset = CompetitionCalendarEvent.objects.all()
    permission_classes = [AllowAny]

    def get_queryset(self):
        now = timezone.now()
        queryset = filter_visible_competition_calendar_events(
            super().get_queryset(), now=now
        )

        requested_sites = []
        raw_sites = self.request.query_params.get("sites", "")
        if raw_sites:
            requested_sites.extend(
                item.strip() for item in raw_sites.split(",") if item.strip()
            )

        raw_site = self.request.query_params.get("site", "")
        if raw_site:
            requested_sites.append(raw_site.strip())

        valid_sites = {
            key for key, _label in CompetitionCalendarEvent.SourceSite.choices
        }
        normalized_sites = [site for site in requested_sites if site in valid_sites]
        if normalized_sites:
            queryset = queryset.filter(source_site__in=normalized_sites)

        status_filter = self.request.query_params.get("status")
        if status_filter == "ongoing":
            queryset = queryset.filter(start_time__lte=now, end_time__gt=now)
        elif status_filter == "upcoming":
            queryset = queryset.filter(start_time__gt=now)
        elif status_filter == "finished":
            queryset = queryset.filter(end_time__lte=now)

        search = self.request.query_params.get("search")
        if search:
            token = search.strip()
            queryset = queryset.filter(
                Q(title__icontains=token)
                | Q(organizer__icontains=token)
                | Q(source_id__icontains=token)
            )

        start_from = parse_datetime_query(
            self.request.query_params.get("start_from", ""), end_of_day=False
        )
        if start_from:
            queryset = queryset.filter(end_time__gte=start_from)

        end_to = parse_datetime_query(
            self.request.query_params.get("end_to", ""), end_of_day=True
        )
        if end_to:
            queryset = queryset.filter(start_time__lte=end_to)

        order = self.request.query_params.get("order")
        if order == "desc":
            return queryset.order_by("-start_time", "source_site", "source_id")
        return queryset.order_by("start_time", "source_site", "source_id")

    def list(self, request, *args, **kwargs):
        try:
            return super().list(request, *args, **kwargs)
        except DatabaseError as exc:
            return schema_outdated_response(exc)

    def retrieve(self, request, *args, **kwargs):
        try:
            return super().retrieve(request, *args, **kwargs)
        except DatabaseError as exc:
            return schema_outdated_response(exc)

    @action(detail=False, methods=["get"], permission_classes=[AllowAny])
    def taxonomy(self, request):
        try:
            queryset = filter_visible_competition_calendar_events(
                CompetitionCalendarEvent.objects.all()
            )
            count_map = {
                item["source_site"]: item["count"]
                for item in queryset.values("source_site").annotate(count=Count("id"))
            }
            latest_sync_at = (
                queryset.order_by("-last_synced_at")
                .values_list("last_synced_at", flat=True)
                .first()
            )
            return Response(
                {
                    "sources": [
                        {
                            "key": key,
                            "name": label,
                            "count": count_map.get(key, 0),
                        }
                        for key, label in CompetitionCalendarEvent.SourceSite.choices
                    ],
                    "count": queryset.count(),
                    "latest_sync_at": latest_sync_at,
                }
            )
        except DatabaseError as exc:
            return schema_outdated_response(exc)


class UserManagementViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = UserAdminSerializer
    queryset = User.objects.all().order_by("-date_joined")
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = (
            super().get_queryset().exclude(username=DELETED_USER_PLACEHOLDER_USERNAME)
        )

        role_filter = self.request.query_params.get("role")
        if role_filter in dict(User.Role.choices):
            queryset = queryset.filter(role=role_filter)

        active_filter = self.request.query_params.get("is_active")
        if active_filter == "1":
            queryset = queryset.filter(is_active=True)
        elif active_filter == "0":
            queryset = queryset.filter(is_active=False)

        banned_filter = self.request.query_params.get("is_banned")
        if banned_filter == "1":
            queryset = queryset.filter(is_banned=True)
        elif banned_filter == "0":
            queryset = queryset.filter(is_banned=False)

        search = self.request.query_params.get("search")
        if search:
            token = search.strip()
            queryset = queryset.filter(
                Q(username__icontains=token)
                | Q(email__icontains=token)
                | Q(school_name__icontains=token)
            )

        return queryset

    def list(self, request, *args, **kwargs):
        if not is_manager(request.user):
            return Response(
                {"detail": "No permission."}, status=status.HTTP_403_FORBIDDEN
            )
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        if not is_manager(request.user):
            return Response(
                {"detail": "No permission."}, status=status.HTTP_403_FORBIDDEN
            )
        return super().retrieve(request, *args, **kwargs)

    @action(detail=True, methods=["post"], permission_classes=[AdminOrSuperAdmin])
    def ban(self, request, pk=None):
        target = self.get_object()
        if target.role == User.Role.SUPERADMIN:
            return Response(
                {"detail": "Super admin cannot be banned."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if target.id == request.user.id:
            return Response(
                {"detail": "You cannot ban yourself."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        target.ban(request.data.get("reason", ""))
        Token.objects.filter(user=target).delete()
        log_event(
            request.user,
            ContributionEvent.EventType.ADMIN,
            target,
            {"action": "ban_user"},
        )
        record_security_event(
            event_type=SecurityAuditLog.EventType.USER_BANNED,
            request=request,
            user=request.user,
            username=target.username,
            success=True,
            detail=f"banned user #{target.id}",
            metadata={"target_user_id": target.id},
        )
        return Response(self.get_serializer(target).data)

    @action(detail=True, methods=["post"], permission_classes=[AdminOrSuperAdmin])
    def unban(self, request, pk=None):
        target = self.get_object()
        target.unban()
        log_event(
            request.user,
            ContributionEvent.EventType.ADMIN,
            target,
            {"action": "unban_user"},
        )
        record_security_event(
            event_type=SecurityAuditLog.EventType.USER_UNBANNED,
            request=request,
            user=request.user,
            username=target.username,
            success=True,
            detail=f"unbanned user #{target.id}",
            metadata={"target_user_id": target.id},
        )
        return Response(self.get_serializer(target).data)

    @action(detail=True, methods=["post"], permission_classes=[AdminOrSuperAdmin])
    def soft_delete(self, request, pk=None):
        target = self.get_object()
        if target.role == User.Role.SUPERADMIN:
            return Response(
                {"detail": "Super admin cannot be deleted."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if target.id == request.user.id:
            return Response(
                {"detail": "You cannot delete yourself."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        target.is_active = False
        target.save(update_fields=["is_active"])
        Token.objects.filter(user=target).delete()
        log_event(
            request.user,
            ContributionEvent.EventType.ADMIN,
            target,
            {"action": "soft_delete_user"},
        )
        record_security_event(
            event_type=SecurityAuditLog.EventType.USER_SOFT_DELETED,
            request=request,
            user=request.user,
            username=target.username,
            success=True,
            detail=f"soft-deleted user #{target.id}",
            metadata={"target_user_id": target.id},
        )
        return Response(self.get_serializer(target).data)

    @action(detail=True, methods=["post"], permission_classes=[AdminOrSuperAdmin])
    def hard_delete(self, request, pk=None):
        target = self.get_object()
        if target.role == User.Role.SUPERADMIN:
            return Response(
                {"detail": "Super admin cannot be permanently deleted."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if target.id == request.user.id:
            return Response(
                {"detail": "You cannot permanently delete yourself."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if target.is_active:
            return Response(
                {"detail": "Please soft-delete the user before permanent deletion."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        target_id = target.id
        target_username = target.username
        placeholder = get_deleted_user_placeholder()

        with transaction.atomic():
            reassign_protected_user_relations(
                source_user=target, placeholder_user=placeholder
            )
            log_event(
                request.user,
                ContributionEvent.EventType.ADMIN,
                target,
                {"action": "hard_delete_user", "target_username": target_username},
            )
            target.delete()

        record_security_event(
            event_type=SecurityAuditLog.EventType.USER_HARD_DELETED,
            request=request,
            user=request.user,
            username=target_username,
            success=True,
            detail=f"hard-deleted user #{target_id}",
            metadata={"target_user_id": target_id, "target_username": target_username},
        )
        return Response(
            {
                "detail": "User permanently deleted.",
                "id": target_id,
                "username": target_username,
            }
        )

    @action(detail=True, methods=["post"], permission_classes=[AdminOrSuperAdmin])
    def reactivate(self, request, pk=None):
        target = self.get_object()
        if (
            target.role == User.Role.SUPERADMIN
            and request.user.role != User.Role.SUPERADMIN
        ):
            return Response(
                {"detail": "Only super admins can reactivate super admin accounts."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not target.is_active:
            target.is_active = True
            target.save(update_fields=["is_active"])
            log_event(
                request.user,
                ContributionEvent.EventType.ADMIN,
                target,
                {"action": "reactivate_user"},
            )
            record_security_event(
                event_type=SecurityAuditLog.EventType.USER_REACTIVATED,
                request=request,
                user=request.user,
                username=target.username,
                success=True,
                detail=f"reactivated user #{target.id}",
                metadata={"target_user_id": target.id},
            )
        return Response(self.get_serializer(target).data)

    @action(detail=True, methods=["post"], permission_classes=[AdminOrSuperAdmin], url_path="send-notification")
    def send_notification(self, request, pk=None):
        target = self.get_object()
        title = str(request.data.get("title", "") or "").strip()
        content = str(request.data.get("content", "") or "").strip()
        link = str(request.data.get("link", "") or "").strip()
        level = str(request.data.get("level", UserNotification.Level.INFO) or "").strip()

        if not title:
            return Response(
                {"detail": "title is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(title) > 200:
            return Response(
                {"detail": "title is too long."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not content:
            return Response(
                {"detail": "content is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if level not in dict(UserNotification.Level.choices):
            level = UserNotification.Level.INFO

        notification = create_notification(
            user=target,
            actor=request.user,
            title=title,
            content=content,
            link=link,
            level=level,
        )
        if notification is None:
            return Response(
                {"detail": "Target user cannot receive notifications."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        log_event(
            request.user,
            ContributionEvent.EventType.ADMIN,
            target,
            {"action": "send_user_notification", "level": level},
        )
        return Response(
            {
                "detail": "Notification sent.",
                "id": notification.id,
            }
        )

    @action(
        detail=True, methods=["post"], permission_classes=[AuthenticatedAndNotBanned]
    )
    def set_role(self, request, pk=None):
        if request.user.role != User.Role.SUPERADMIN:
            return Response(
                {"detail": "Only super admins can change roles."},
                status=status.HTTP_403_FORBIDDEN,
            )

        target = self.get_object()
        role = request.data.get("role")
        valid_roles = dict(User.Role.choices)
        if role not in valid_roles:
            return Response(
                {"detail": "Invalid role."}, status=status.HTTP_400_BAD_REQUEST
            )

        if target.id == request.user.id and role != User.Role.SUPERADMIN:
            return Response(
                {"detail": "Cannot downgrade your own super admin role."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        target.role = role
        target.save(update_fields=["role"])
        log_event(
            request.user,
            ContributionEvent.EventType.ADMIN,
            target,
            {"action": "set_role", "role": role},
        )
        record_security_event(
            event_type=SecurityAuditLog.EventType.USER_ROLE_CHANGED,
            request=request,
            user=request.user,
            username=target.username,
            success=True,
            detail=f"changed role for user #{target.id} -> {role}",
            metadata={"target_user_id": target.id, "role": role},
        )
        return Response(self.get_serializer(target).data)

    @action(
        detail=False,
        methods=["post"],
        permission_classes=[AdminOrSuperAdmin],
        url_path="bulk-action",
    )
    def bulk_action(self, request):
        raw_ids = request.data.get("ids")
        if not isinstance(raw_ids, list) or not raw_ids:
            return Response(
                {"detail": "ids must be a non-empty list."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(raw_ids) > 200:
            return Response(
                {"detail": "Too many ids, max is 200."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ids = []
        for raw_id in raw_ids:
            try:
                user_id = int(raw_id)
            except (TypeError, ValueError):
                return Response(
                    {"detail": "ids must contain integers."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if user_id <= 0:
                return Response(
                    {"detail": "ids must contain positive integers."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if user_id not in ids:
                ids.append(user_id)

        action_name = str(request.data.get("action", "")).strip().lower()
        supported_actions = {"ban", "unban", "soft_delete", "reactivate", "set_role"}
        if action_name not in supported_actions:
            return Response(
                {
                    "detail": f"action must be one of: {', '.join(sorted(supported_actions))}."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        role_value = None
        if action_name == "set_role":
            if request.user.role != User.Role.SUPERADMIN:
                return Response(
                    {"detail": "Only super admins can change roles."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            role_value = request.data.get("role")
            if role_value not in dict(User.Role.choices):
                return Response(
                    {"detail": "Invalid role."}, status=status.HTTP_400_BAD_REQUEST
                )

        reason = request.data.get("reason", "")
        target_map = {item.id: item for item in User.objects.filter(id__in=ids)}

        results = []
        success_count = 0

        for user_id in ids:
            target = target_map.get(user_id)
            if not target:
                results.append(
                    {"id": user_id, "success": False, "detail": "User not found."}
                )
                continue
            if is_deleted_user_placeholder(target):
                results.append(
                    {
                        "id": user_id,
                        "success": False,
                        "detail": "System placeholder user cannot be modified.",
                    }
                )
                continue

            if action_name in {"ban", "soft_delete"} and target.id == request.user.id:
                results.append(
                    {
                        "id": user_id,
                        "success": False,
                        "detail": "You cannot operate on yourself.",
                    }
                )
                continue

            if (
                action_name in {"ban", "soft_delete"}
                and target.role == User.Role.SUPERADMIN
            ):
                results.append(
                    {
                        "id": user_id,
                        "success": False,
                        "detail": "Super admin cannot be modified by this action.",
                    }
                )
                continue

            if (
                action_name == "reactivate"
                and target.role == User.Role.SUPERADMIN
                and request.user.role != User.Role.SUPERADMIN
            ):
                results.append(
                    {
                        "id": user_id,
                        "success": False,
                        "detail": "Only super admins can reactivate super admin accounts.",
                    }
                )
                continue

            if (
                action_name == "set_role"
                and target.id == request.user.id
                and role_value != User.Role.SUPERADMIN
            ):
                results.append(
                    {
                        "id": user_id,
                        "success": False,
                        "detail": "Cannot downgrade your own super admin role.",
                    }
                )
                continue

            if action_name == "ban":
                target.ban(reason)
                Token.objects.filter(user=target).delete()
                log_event(
                    request.user,
                    ContributionEvent.EventType.ADMIN,
                    target,
                    {"action": "ban_user_bulk"},
                )
                record_security_event(
                    event_type=SecurityAuditLog.EventType.USER_BANNED,
                    request=request,
                    user=request.user,
                    username=target.username,
                    success=True,
                    detail=f"bulk banned user #{target.id}",
                    metadata={"target_user_id": target.id},
                )
            elif action_name == "unban":
                target.unban()
                log_event(
                    request.user,
                    ContributionEvent.EventType.ADMIN,
                    target,
                    {"action": "unban_user_bulk"},
                )
                record_security_event(
                    event_type=SecurityAuditLog.EventType.USER_UNBANNED,
                    request=request,
                    user=request.user,
                    username=target.username,
                    success=True,
                    detail=f"bulk unbanned user #{target.id}",
                    metadata={"target_user_id": target.id},
                )
            elif action_name == "soft_delete":
                if target.is_active:
                    target.is_active = False
                    target.save(update_fields=["is_active"])
                Token.objects.filter(user=target).delete()
                log_event(
                    request.user,
                    ContributionEvent.EventType.ADMIN,
                    target,
                    {"action": "soft_delete_user_bulk"},
                )
                record_security_event(
                    event_type=SecurityAuditLog.EventType.USER_SOFT_DELETED,
                    request=request,
                    user=request.user,
                    username=target.username,
                    success=True,
                    detail=f"bulk soft-deleted user #{target.id}",
                    metadata={"target_user_id": target.id},
                )
            elif action_name == "reactivate":
                if not target.is_active:
                    target.is_active = True
                    target.save(update_fields=["is_active"])
                log_event(
                    request.user,
                    ContributionEvent.EventType.ADMIN,
                    target,
                    {"action": "reactivate_user_bulk"},
                )
                record_security_event(
                    event_type=SecurityAuditLog.EventType.USER_REACTIVATED,
                    request=request,
                    user=request.user,
                    username=target.username,
                    success=True,
                    detail=f"bulk reactivated user #{target.id}",
                    metadata={"target_user_id": target.id},
                )
            elif action_name == "set_role":
                target.role = role_value
                target.save(update_fields=["role"])
                log_event(
                    request.user,
                    ContributionEvent.EventType.ADMIN,
                    target,
                    {"action": "set_role_bulk", "role": role_value},
                )
                record_security_event(
                    event_type=SecurityAuditLog.EventType.USER_ROLE_CHANGED,
                    request=request,
                    user=request.user,
                    username=target.username,
                    success=True,
                    detail=f"bulk changed role for user #{target.id} -> {role_value}",
                    metadata={"target_user_id": target.id, "role": role_value},
                )

            success_count += 1
            payload = {"id": user_id, "success": True}
            if action_name == "set_role":
                payload["role"] = target.role
            if action_name in {"ban", "unban"}:
                payload["is_banned"] = target.is_banned
            if action_name in {"soft_delete", "reactivate"}:
                payload["is_active"] = target.is_active
            results.append(payload)

        return Response(
            {
                "total": len(ids),
                "success": success_count,
                "failed": len(ids) - success_count,
                "results": results,
            }
        )

    @action(detail=False, methods=["get"], permission_classes=[AdminOrSuperAdmin])
    def assignees(self, request):
        queryset = User.objects.filter(
            is_active=True,
            is_banned=False,
            role__in=[User.Role.SCHOOL, User.Role.ADMIN, User.Role.SUPERADMIN],
        )
        search = request.query_params.get("search")
        if search:
            token = search.strip()
            queryset = queryset.filter(
                Q(username__icontains=token) | Q(school_name__icontains=token)
            )
        queryset = queryset.order_by("role", "username")[:200]
        return Response(
            UserPublicSerializer(queryset, many=True, context={"request": request}).data
        )


class UserNotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = UserNotificationSerializer
    queryset = UserNotification.objects.select_related("user", "actor").all()
    permission_classes = [AuthenticatedAndNotBanned]

    def get_queryset(self):
        queryset = super().get_queryset().filter(user=self.request.user)

        read_filter = self.request.query_params.get("is_read")
        if read_filter == "1":
            queryset = queryset.filter(is_read=True)
        elif read_filter == "0":
            queryset = queryset.filter(is_read=False)

        level = self.request.query_params.get("level")
        if level in dict(UserNotification.Level.choices):
            queryset = queryset.filter(level=level)

        search = self.request.query_params.get("search")
        if search:
            token = search.strip()
            queryset = queryset.filter(
                Q(title__icontains=token) | Q(content__icontains=token)
            )

        return queryset.order_by("is_read", "-created_at")

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[AuthenticatedAndNotBanned],
        url_path="mark-read",
    )
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        notification.mark_read()
        return Response(self.get_serializer(notification).data)

    @action(
        detail=False,
        methods=["post"],
        permission_classes=[AuthenticatedAndNotBanned],
        url_path="mark-all-read",
    )
    def mark_all_read(self, request):
        now = timezone.now()
        updated = (
            self.get_queryset()
            .filter(is_read=False)
            .update(is_read=True, read_at=now, updated_at=now)
        )
        return Response({"updated": updated})

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[AuthenticatedAndNotBanned],
        url_path="unread-count",
    )
    def unread_count(self, request):
        count = self.get_queryset().filter(is_read=False).count()
        return Response({"count": count})


class DeletedContentArchiveViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DeletedContentArchiveSerializer
    queryset = DeletedContentArchive.objects.select_related(
        "original_author", "deleted_by"
    ).all()
    permission_classes = [AdminOrSuperAdmin]

    def get_queryset(self):
        queryset = super().get_queryset()

        target_type = self.request.query_params.get("target_type")
        if target_type:
            queryset = queryset.filter(target_type__icontains=target_type.strip())

        delete_action = self.request.query_params.get("delete_action")
        if delete_action in dict(DeletedContentArchive.DeleteAction.choices):
            queryset = queryset.filter(delete_action=delete_action)

        original_author = self.request.query_params.get("original_author")
        if original_author:
            token = original_author.strip()
            if token.isdigit():
                queryset = queryset.filter(original_author_id=int(token))
            else:
                queryset = queryset.filter(original_author_name__icontains=token)

        deleted_by = self.request.query_params.get("deleted_by")
        if deleted_by:
            token = deleted_by.strip()
            if token.isdigit():
                queryset = queryset.filter(deleted_by_id=int(token))
            else:
                queryset = queryset.filter(deleted_by_name__icontains=token)

        search = self.request.query_params.get("search")
        if search:
            token = search.strip()
            queryset = queryset.filter(
                Q(title__icontains=token)
                | Q(summary__icontains=token)
                | Q(content_md__icontains=token)
                | Q(original_author_name__icontains=token)
                | Q(deleted_by_name__icontains=token)
            )

        start_at = parse_datetime_query(
            self.request.query_params.get("start_at", ""), end_of_day=False
        )
        if start_at:
            queryset = queryset.filter(created_at__gte=start_at)

        end_at = parse_datetime_query(
            self.request.query_params.get("end_at", ""), end_of_day=True
        )
        if end_at:
            queryset = queryset.filter(created_at__lte=end_at)

        return queryset.order_by("-created_at", "-id")

    def list(self, request, *args, **kwargs):
        try:
            return super().list(request, *args, **kwargs)
        except DatabaseError as exc:
            return schema_outdated_response(exc)

    def retrieve(self, request, *args, **kwargs):
        try:
            return super().retrieve(request, *args, **kwargs)
        except DatabaseError as exc:
            return schema_outdated_response(exc)


class SecurityAuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SecurityAuditLogSerializer
    queryset = (
        SecurityAuditLog.objects.select_related("user").all().order_by("-created_at")
    )
    permission_classes = [AdminOrSuperAdmin]

    def get_queryset(self):
        queryset = super().get_queryset()

        event_type = self.request.query_params.get("event_type")
        if event_type in dict(SecurityAuditLog.EventType.choices):
            queryset = queryset.filter(event_type=event_type)

        success = self.request.query_params.get("success")
        if success == "1":
            queryset = queryset.filter(success=True)
        elif success == "0":
            queryset = queryset.filter(success=False)

        username = self.request.query_params.get("username")
        if username:
            token = username.strip()
            queryset = queryset.filter(username__icontains=token)

        ip_address = self.request.query_params.get("ip")
        if ip_address:
            queryset = queryset.filter(ip_address__icontains=ip_address.strip())

        detail = self.request.query_params.get("detail")
        if detail:
            queryset = queryset.filter(detail__icontains=detail.strip())

        start_at = parse_datetime_query(
            self.request.query_params.get("start_at", ""), end_of_day=False
        )
        if start_at:
            queryset = queryset.filter(created_at__gte=start_at)

        end_at = parse_datetime_query(
            self.request.query_params.get("end_at", ""), end_of_day=True
        )
        if end_at:
            queryset = queryset.filter(created_at__lte=end_at)

        return queryset.order_by("-created_at")

    def list(self, request, *args, **kwargs):
        try:
            return super().list(request, *args, **kwargs)
        except DatabaseError as exc:
            return schema_outdated_response(exc)

    def retrieve(self, request, *args, **kwargs):
        try:
            return super().retrieve(request, *args, **kwargs)
        except DatabaseError as exc:
            return schema_outdated_response(exc)

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[AdminOrSuperAdmin],
        url_path="export",
    )
    def export(self, request):
        try:
            queryset = self.get_queryset().select_related("user")
            response = HttpResponse(content_type="text/csv; charset=utf-8")
            response["Content-Disposition"] = (
                f'attachment; filename="algowiki-security-{timezone.now().strftime("%Y%m%d-%H%M%S")}.csv"'
            )
            response.write("\ufeff")

            writer = csv.writer(response)
            writer.writerow(
                [
                    "id",
                    "created_at",
                    "event_type",
                    "success",
                    "username",
                    "ip_address",
                    "detail",
                    "user_id",
                    "user_agent",
                    "metadata",
                ]
            )

            for event in queryset:
                writer.writerow(
                    [
                        event.id,
                        timezone.localtime(event.created_at).strftime(
                            "%Y-%m-%d %H:%M:%S"
                        ),
                        event.event_type,
                        int(bool(event.success)),
                        event.username or "",
                        event.ip_address or "",
                        event.detail or "",
                        event.user_id or "",
                        event.user_agent or "",
                        json.dumps(event.metadata or {}, ensure_ascii=False),
                    ]
                )
            return response
        except DatabaseError as exc:
            return schema_outdated_response(exc)

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[AdminOrSuperAdmin],
        url_path="summary",
    )
    def summary(self, request):
        try:
            queryset = self.get_queryset()

            try:
                window_hours = int(request.query_params.get("window_hours", 24))
            except (TypeError, ValueError):
                window_hours = 24
            window_hours = min(max(window_hours, 1), 168)

            cutoff = timezone.now() - timedelta(hours=window_hours)
            queryset = queryset.filter(created_at__gte=cutoff)

            failed_queryset = queryset.filter(success=False)
            failed_login_queryset = failed_queryset.filter(
                event_type__in=[
                    SecurityAuditLog.EventType.LOGIN_FAILED,
                    SecurityAuditLog.EventType.LOGIN_LOCKED,
                    SecurityAuditLog.EventType.LOGIN_DENIED,
                ]
            )
            top_failed_ips = (
                failed_login_queryset.exclude(ip_address__isnull=True)
                .exclude(ip_address="")
                .values("ip_address")
                .annotate(count=Count("id"))
                .order_by("-count", "ip_address")[:10]
            )

            return Response(
                {
                    "window_hours": window_hours,
                    "since": timezone.localtime(cutoff).isoformat(),
                    "totals": {
                        "all_events": queryset.count(),
                        "failed_events": failed_queryset.count(),
                        "login_failed": failed_queryset.filter(
                            event_type=SecurityAuditLog.EventType.LOGIN_FAILED
                        ).count(),
                        "login_locked": failed_queryset.filter(
                            event_type=SecurityAuditLog.EventType.LOGIN_LOCKED
                        ).count(),
                        "login_denied": failed_queryset.filter(
                            event_type=SecurityAuditLog.EventType.LOGIN_DENIED
                        ).count(),
                    },
                    "unique": {
                        "ips": failed_login_queryset.values("ip_address")
                        .exclude(ip_address__isnull=True)
                        .exclude(ip_address="")
                        .distinct()
                        .count(),
                        "usernames": failed_login_queryset.values("username")
                        .exclude(username="")
                        .distinct()
                        .count(),
                    },
                    "top_failed_ips": list(top_failed_ips),
                }
            )
        except DatabaseError as exc:
            return schema_outdated_response(exc)


class ContributionEventViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ContributionEventSerializer
    queryset = (
        ContributionEvent.objects.select_related("user").all().order_by("-created_at")
    )
    permission_classes = [AdminOrSuperAdmin]

    def get_queryset(self):
        queryset = super().get_queryset()

        event_type = self.request.query_params.get("event_type")
        if event_type in dict(ContributionEvent.EventType.choices):
            queryset = queryset.filter(event_type=event_type)

        target_type = self.request.query_params.get("target_type")
        if target_type:
            queryset = queryset.filter(target_type__icontains=target_type.strip())

        user_filter = self.request.query_params.get("user")
        if user_filter:
            user_filter = user_filter.strip()
            if user_filter.isdigit():
                queryset = queryset.filter(user_id=int(user_filter))
            else:
                queryset = queryset.filter(user__username__icontains=user_filter)

        search = self.request.query_params.get("search")
        if search:
            token = search.strip().lower()
            matched_ids = []
            for event in queryset.only("id", "target_type", "payload"):
                if (
                    token in str(event.target_type or "").lower()
                    or token in str(event.payload or "").lower()
                ):
                    matched_ids.append(event.id)
            queryset = queryset.filter(id__in=matched_ids)

        start_at = parse_datetime_query(
            self.request.query_params.get("start_at", ""), end_of_day=False
        )
        if start_at:
            queryset = queryset.filter(created_at__gte=start_at)

        end_at = parse_datetime_query(
            self.request.query_params.get("end_at", ""), end_of_day=True
        )
        if end_at:
            queryset = queryset.filter(created_at__lte=end_at)

        return queryset

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[AdminOrSuperAdmin],
        url_path="export",
    )
    def export(self, request):
        queryset = self.get_queryset().select_related("user")
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = (
            f'attachment; filename="algowiki-events-{timezone.now().strftime("%Y%m%d-%H%M%S")}.csv"'
        )
        response.write("\ufeff")

        writer = csv.writer(response)
        writer.writerow(
            [
                "id",
                "created_at",
                "event_type",
                "target_type",
                "target_id",
                "user_id",
                "username",
                "payload",
            ]
        )

        for event in queryset:
            writer.writerow(
                [
                    event.id,
                    timezone.localtime(event.created_at).strftime("%Y-%m-%d %H:%M:%S"),
                    event.event_type,
                    event.target_type,
                    event.target_id,
                    event.user_id,
                    event.user.username if event.user_id else "",
                    json.dumps(event.payload or {}, ensure_ascii=False),
                ]
            )
        return response


class SiteVisitTrackView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            increment_site_visit_count()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except DatabaseError as exc:
            return schema_outdated_response(exc)


class SiteVisitStatsView(APIView):
    permission_classes = [SuperAdminOnly]

    def get(self, request):
        try:
            return Response(build_site_visit_stats_payload())
        except DatabaseError as exc:
            return schema_outdated_response(exc)


class AdminOverviewView(APIView):
    permission_classes = [AdminOrSuperAdmin]

    def get(self, request):
        try:
            role_counts = (
                User.objects.filter(is_active=True)
                .values("role")
                .annotate(count=Count("id"))
            )
            role_map = {item["role"]: item["count"] for item in role_counts}

            article_status_counts = Article.objects.values("status").annotate(
                count=Count("id")
            )
            article_status_map = {
                item["status"]: item["count"] for item in article_status_counts
            }

            ticket_status_counts = IssueTicket.objects.values("status").annotate(
                count=Count("id")
            )
            ticket_status_map = {
                item["status"]: item["count"] for item in ticket_status_counts
            }

            revision_status_counts = RevisionProposal.objects.values("status").annotate(
                count=Count("id")
            )
            revision_status_map = {
                item["status"]: item["count"] for item in revision_status_counts
            }

            recent_events = ContributionEvent.objects.select_related("user").all()[:10]
            event_type_counts = (
                ContributionEvent.objects.values("event_type")
                .annotate(count=Count("id"))
                .order_by("-count", "event_type")
            )
            event_type_series = [
                {"event_type": item["event_type"], "count": item["count"]}
                for item in event_type_counts
            ]

            today = timezone.localdate()
            start_day = today - timedelta(days=6)
            daily_rows = (
                ContributionEvent.objects.filter(created_at__date__gte=start_day)
                .annotate(day=TruncDate("created_at"))
                .values("day")
                .annotate(count=Count("id"))
                .order_by("day")
            )
            daily_map = {item["day"]: item["count"] for item in daily_rows}
            daily_events = []
            cursor = start_day
            while cursor <= today:
                daily_events.append(
                    {
                        "date": cursor.isoformat(),
                        "count": daily_map.get(cursor, 0),
                    }
                )
                cursor += timedelta(days=1)

            return Response(
                {
                    "users": {
                        "total": User.objects.count(),
                        "active": User.objects.filter(is_active=True).count(),
                        "banned": User.objects.filter(
                            is_active=True, is_banned=True
                        ).count(),
                        "by_role": {
                            "normal": role_map.get(User.Role.NORMAL, 0),
                            "school": role_map.get(User.Role.SCHOOL, 0),
                            "admin": role_map.get(User.Role.ADMIN, 0),
                            "superadmin": role_map.get(User.Role.SUPERADMIN, 0),
                        },
                    },
                    "content": {
                        "categories": Category.objects.count(),
                        "articles_total": Article.objects.count(),
                        "articles_published": article_status_map.get(
                            Article.Status.PUBLISHED, 0
                        ),
                        "articles_hidden": article_status_map.get(
                            Article.Status.HIDDEN, 0
                        ),
                        "articles_draft": article_status_map.get(
                            Article.Status.DRAFT, 0
                        ),
                        "comments_total": ArticleComment.objects.count(),
                        "comments_hidden": ArticleComment.objects.filter(
                            status=ArticleComment.Status.HIDDEN
                        ).count(),
                    },
                    "workflow": {
                        "tickets_open": ticket_status_map.get(
                            IssueTicket.Status.OPEN, 0
                        ),
                        "tickets_in_progress": ticket_status_map.get(
                            IssueTicket.Status.IN_PROGRESS, 0
                        ),
                        "tickets_resolved": ticket_status_map.get(
                            IssueTicket.Status.RESOLVED, 0
                        ),
                        "revisions_pending": revision_status_map.get(
                            RevisionProposal.Status.PENDING, 0
                        ),
                        "questions_pending": Question.objects.filter(
                            status=Question.Status.PENDING
                        ).count(),
                        "questions_open": Question.objects.filter(
                            status=Question.Status.OPEN
                        ).count(),
                        "answers_pending": Answer.objects.filter(
                            status=Answer.Status.PENDING
                        ).count(),
                        "answers_total": Answer.objects.count(),
                    },
                    "announcements": {
                        "total": Announcement.objects.count(),
                        "published": Announcement.objects.active().count(),
                    },
                    "analytics": {
                        "generated_at": timezone.localtime(timezone.now()).isoformat(),
                        "event_type_counts": event_type_series,
                        "daily_events": daily_events,
                    },
                    "recent_events": ContributionEventSerializer(
                        recent_events, many=True
                    ).data,
                }
            )
        except DatabaseError as exc:
            return schema_outdated_response(exc)


class HomeSummaryView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            announcements = Announcement.objects.active()[:5]
            featured_articles = Article.objects.filter(
                status=Article.Status.PUBLISHED, is_featured=True
            ).select_related("category", "author")[:8]
            if not featured_articles:
                featured_articles = Article.objects.filter(
                    status=Article.Status.PUBLISHED
                ).select_related("category", "author")[:8]

            categories = Category.objects.filter(is_visible=True, parent__isnull=True)
            extension_pages = ExtensionPage.objects.filter(
                is_enabled=True,
                access_level=ExtensionPage.AccessLevel.PUBLIC,
            )
            team_members = TeamMember.objects.select_related("user").filter(
                is_active=True
            )

            return Response(
                {
                    "site": {
                        "name": "AlgoWiki",
                        "tagline": "\u9762\u5411\u7b97\u6cd5\u7ade\u8d5b\u5b66\u4e60\u8005\u7684\u7ed3\u6784\u5316\u77e5\u8bc6\u5e93\u4e0e\u793e\u533a\u534f\u4f5c\u5e73\u53f0\u3002",
                    },
                    "announcements": AnnouncementSerializer(
                        announcements,
                        many=True,
                        context={"request": request},
                    ).data,
                    "featured_articles": ArticleSerializer(
                        featured_articles,
                        many=True,
                        context={"request": request},
                    ).data,
                    "categories": CategorySerializer(categories, many=True).data,
                    "extension_pages": ExtensionPageSerializer(
                        extension_pages, many=True
                    ).data,
                    "team_members": TeamMemberSerializer(
                        team_members,
                        many=True,
                        context={"request": request},
                    ).data,
                }
            )
        except DatabaseError as exc:
            return schema_outdated_response(exc)
