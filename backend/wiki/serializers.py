from pathlib import Path

from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import serializers
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import Throttled

from .competition_practice import parse_practice_links_text, practice_links_to_text
from .models import (
    Announcement,
    AnnouncementRead,
    Answer,
    Article,
    ArticleComment,
    ArticleStar,
    Category,
    CompetitionCalendarEvent,
    CompetitionNotice,
    CompetitionPracticeLink,
    CompetitionPracticeLinkProposal,
    CompetitionScheduleEntry,
    ContributionEvent,
    ExtensionPage,
    FriendlyLink,
    IssueTicket,
    Question,
    RevisionProposal,
    SecurityAuditLog,
    TeamMember,
    TrickEntry,
    UserNotification,
    User,
)
from .permissions import can_moderate_category
from .security import (
    check_login_locked,
    clear_login_failures,
    get_client_ip,
    is_password_reused,
    record_password_history,
    record_security_event,
    register_login_failure,
)


def can_manage_competition(user):
    return bool(
        user
        and user.is_authenticated
        and user.role in {User.Role.SCHOOL, User.Role.ADMIN, User.Role.SUPERADMIN}
    )


class UserPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "role",
            "school_name",
            "avatar_url",
            "bio",
            "date_joined",
        ]

    def _can_view_profile_fields(self, instance) -> bool:
        if self.context.get("include_private_profile"):
            return True

        request = self.context.get("request")
        user = getattr(request, "user", None)
        return bool(
            user
            and user.is_authenticated
            and (user.pk == instance.pk or user.role in {User.Role.ADMIN, User.Role.SUPERADMIN})
        )

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not self._can_view_profile_fields(instance):
            data["school_name"] = ""
            data["avatar_url"] = ""
            data["bio"] = ""
        return data


class UserAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "role",
            "is_active",
            "is_banned",
            "banned_reason",
            "banned_at",
            "date_joined",
            "last_login",
        ]


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(required=False, allow_blank=True)
    school_name = serializers.CharField(required=False, allow_blank=True, max_length=120)
    bio = serializers.CharField(required=False, allow_blank=True)
    avatar_url = serializers.URLField(required=False, allow_blank=True)

    class Meta:
        model = User
        fields = [
            "email",
            "school_name",
            "bio",
            "avatar_url",
        ]

    def validate_email(self, value):
        email = (value or "").strip()
        if not email:
            return ""
        queryset = User.objects.filter(email__iexact=email)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("This email is already in use.")
        return email


class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            raise serializers.ValidationError("Authentication required.")

        old_password = attrs.get("old_password", "")
        new_password = attrs.get("new_password", "")
        confirm_password = attrs.get("confirm_password", "")

        if not user.check_password(old_password):
            raise serializers.ValidationError({"old_password": "Current password is incorrect."})
        if new_password != confirm_password:
            raise serializers.ValidationError({"confirm_password": "The two new passwords do not match."})
        if old_password == new_password:
            raise serializers.ValidationError({"new_password": "New password must be different from the old password."})
        if is_password_reused(user, new_password):
            raise serializers.ValidationError({"new_password": "Cannot reuse recent password."})
        try:
            validate_password(new_password, user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"new_password": list(exc.messages)})
        return attrs


class ImageUploadSerializer(serializers.Serializer):
    image = serializers.FileField()

    def validate_image(self, value):
        max_bytes = int(self.context.get("max_bytes") or 0)
        allowed_extensions = set(self.context.get("allowed_extensions") or [])
        allowed_content_types = set(self.context.get("allowed_content_types") or [])

        if max_bytes > 0 and value.size > max_bytes:
            limit_mb = max_bytes / 1024 / 1024
            raise serializers.ValidationError(f"Image too large, max {limit_mb:.1f}MB.")

        suffix = Path(value.name or "").suffix.lower()
        if allowed_extensions and suffix not in allowed_extensions:
            raise serializers.ValidationError("Unsupported image format.")

        content_type = str(getattr(value, "content_type", "") or "").lower()
        if allowed_content_types and content_type and content_type not in allowed_content_types:
            raise serializers.ValidationError("Unsupported image content type.")

        return value


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ["username", "email", "password", "school_name"]

    def validate_email(self, value):
        email = (value or "").strip()
        if email and User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("This email is already in use.")
        return email

    def validate_password(self, value):
        probe_user = User(
            username=str(self.initial_data.get("username", "")).strip(),
            email=str(self.initial_data.get("email", "")).strip(),
        )
        try:
            validate_password(value, user=probe_user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages))
        return value

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User.objects.create_user(role=User.Role.NORMAL, **validated_data)
        user.set_password(password)
        user.save(update_fields=["password"])
        record_password_history(user)
        Token.objects.get_or_create(user=user)
        return user


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)
    token = serializers.CharField(read_only=True)
    user = UserPublicSerializer(read_only=True)

    def validate(self, attrs):
        request = self.context.get("request")
        username = str(attrs.get("username", "")).strip()
        password = attrs.get("password")
        client_ip = get_client_ip(request)

        is_locked, wait_seconds = check_login_locked(username, client_ip)
        if is_locked:
            record_security_event(
                event_type=SecurityAuditLog.EventType.LOGIN_LOCKED,
                request=request,
                username=username,
                success=False,
                detail="account temporarily locked due to failed attempts",
            )
            raise Throttled(wait=wait_seconds, detail="Too many failed attempts, please try again later.")

        user = authenticate(username=username, password=password)
        if not user:
            register_login_failure(username, client_ip)
            is_locked_after, wait_seconds_after = check_login_locked(username, client_ip)
            if is_locked_after:
                record_security_event(
                    event_type=SecurityAuditLog.EventType.LOGIN_LOCKED,
                    request=request,
                    username=username,
                    success=False,
                    detail="lock triggered after failed login",
                )
                raise Throttled(wait=wait_seconds_after, detail="Too many failed attempts, please try again later.")
            record_security_event(
                event_type=SecurityAuditLog.EventType.LOGIN_FAILED,
                request=request,
                username=username,
                success=False,
                detail="invalid credentials",
            )
            raise serializers.ValidationError("Invalid username or password.")
        if not user.is_active:
            record_security_event(
                event_type=SecurityAuditLog.EventType.LOGIN_DENIED,
                request=request,
                user=user,
                username=username,
                success=False,
                detail="account disabled",
            )
            raise serializers.ValidationError("This account is disabled.")
        if user.is_banned:
            record_security_event(
                event_type=SecurityAuditLog.EventType.LOGIN_DENIED,
                request=request,
                user=user,
                username=username,
                success=False,
                detail="account banned",
            )
            raise serializers.ValidationError("This account has been banned.")

        clear_login_failures(username, client_ip)
        Token.objects.filter(user=user).delete()
        token = Token.objects.create(user=user)
        record_security_event(
            event_type=SecurityAuditLog.EventType.LOGIN_SUCCESS,
            request=request,
            user=user,
            username=username,
            success=True,
            detail="login success",
        )
        return {"user": user, "token": token.key}


class CategorySerializer(serializers.ModelSerializer):
    parent_name = serializers.CharField(source="parent.name", read_only=True)

    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "parent",
            "parent_name",
            "order",
            "moderation_scope",
            "is_visible",
            "created_at",
            "updated_at",
        ]


class ArticleSerializer(serializers.ModelSerializer):
    author = UserPublicSerializer(read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)
    star_count = serializers.IntegerField(source="stargazers.count", read_only=True)
    comment_count = serializers.IntegerField(source="comments.count", read_only=True)
    is_starred = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()

    class Meta:
        model = Article
        fields = [
            "id",
            "title",
            "slug",
            "summary",
            "content_md",
            "category",
            "category_name",
            "author",
            "status",
            "is_featured",
            "is_locked",
            "allow_comments",
            "view_count",
            "published_at",
            "star_count",
            "comment_count",
            "is_starred",
            "can_edit",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "author",
            "slug",
            "view_count",
            "published_at",
            "star_count",
            "comment_count",
            "is_starred",
            "can_edit",
            "created_at",
            "updated_at",
        ]

    def get_is_starred(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        return ArticleStar.objects.filter(user=user, article=obj).exists()

    def get_can_edit(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        return bool(can_moderate_category(user, obj.category))


class ArticleCommentSerializer(serializers.ModelSerializer):
    author = UserPublicSerializer(read_only=True)
    article_title = serializers.CharField(source="article.title", read_only=True)

    class Meta:
        model = ArticleComment
        fields = [
            "id",
            "article",
            "article_title",
            "author",
            "parent",
            "content",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["author", "status", "created_at", "updated_at"]

    def validate(self, attrs):
        article = attrs.get("article") or getattr(self.instance, "article", None)
        parent = attrs.get("parent")
        if parent:
            if not article:
                raise serializers.ValidationError({"parent": "Parent comment requires a target article."})
            if parent.article_id != article.id:
                raise serializers.ValidationError({"parent": "Parent comment must belong to the same article."})
            if parent.status != ArticleComment.Status.VISIBLE:
                raise serializers.ValidationError({"parent": "Parent comment is not available."})
        return attrs


class RevisionProposalSerializer(serializers.ModelSerializer):
    proposer = UserPublicSerializer(read_only=True)
    reviewer = UserPublicSerializer(read_only=True)
    article_title = serializers.CharField(source="article.title", read_only=True)
    article_content_md = serializers.CharField(source="article.content_md", read_only=True)

    class Meta:
        model = RevisionProposal
        fields = [
            "id",
            "article",
            "article_title",
            "article_content_md",
            "proposer",
            "proposed_title",
            "proposed_summary",
            "proposed_content_md",
            "reason",
            "status",
            "reviewer",
            "review_note",
            "reviewed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "proposer",
            "status",
            "reviewer",
            "review_note",
            "reviewed_at",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        if self.instance is None:
            return attrs
        next_article = attrs.get("article")
        if next_article and next_article.id != self.instance.article_id:
            raise serializers.ValidationError(
                {"article": "Cannot change the target article of an existing revision proposal."}
            )
        return attrs


class IssueTicketSerializer(serializers.ModelSerializer):
    author = UserPublicSerializer(read_only=True)
    assignee = UserPublicSerializer(read_only=True)
    related_article_title = serializers.CharField(source="related_article.title", read_only=True)
    visibility_label = serializers.CharField(source="get_visibility_display", read_only=True)

    class Meta:
        model = IssueTicket
        fields = [
            "id",
            "kind",
            "title",
            "content",
            "author",
            "related_article",
            "related_article_title",
            "visibility",
            "visibility_label",
            "status",
            "assignee",
            "resolution_note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "author",
            "status",
            "assignee",
            "resolution_note",
            "created_at",
            "updated_at",
        ]


class TrickEntrySerializer(serializers.ModelSerializer):
    author = UserPublicSerializer(read_only=True)

    class Meta:
        model = TrickEntry
        fields = [
            "id",
            "title",
            "content_md",
            "author",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "author",
            "status",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            "title": {"required": False, "allow_blank": True},
        }


class TeamMemberSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = TeamMember
        fields = [
            "id",
            "display_id",
            "avatar_url",
            "profile_url",
            "username",
            "is_active",
            "sort_order",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "username",
            "is_active",
            "sort_order",
            "created_at",
            "updated_at",
        ]


class TeamMemberUpsertSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeamMember
        fields = [
            "display_id",
            "avatar_url",
            "profile_url",
        ]

    def validate_display_id(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("display_id is required.")
        return value[:80]

    def validate_avatar_url(self, value):
        return (value or "").strip()[:500]

    def validate_profile_url(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("profile_url is required.")
        return value[:500]


class AnswerSerializer(serializers.ModelSerializer):
    author = UserPublicSerializer(read_only=True)
    question_title = serializers.CharField(source="question.title", read_only=True)
    question_status = serializers.CharField(source="question.status", read_only=True)

    class Meta:
        model = Answer
        fields = [
            "id",
            "question",
            "question_title",
            "question_status",
            "author",
            "content_md",
            "is_accepted",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["author", "is_accepted", "status", "created_at", "updated_at"]


class QuestionSerializer(serializers.ModelSerializer):
    author = UserPublicSerializer(read_only=True)
    answers_count = serializers.IntegerField(source="answers.count", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = Question
        fields = [
            "id",
            "title",
            "content_md",
            "author",
            "category",
            "category_name",
            "status",
            "answers_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["author", "status", "answers_count", "created_at", "updated_at"]


class AnnouncementSerializer(serializers.ModelSerializer):
    created_by = UserPublicSerializer(read_only=True)
    is_read = serializers.SerializerMethodField()

    class Meta:
        model = Announcement
        fields = [
            "id",
            "title",
            "content_md",
            "created_by",
            "priority",
            "is_published",
            "start_at",
            "end_at",
            "is_read",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_by", "is_read", "created_at", "updated_at"]

    def get_is_read(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        return AnnouncementRead.objects.filter(user=user, announcement=obj).exists()


class ExtensionPageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExtensionPage
        fields = [
            "id",
            "title",
            "slug",
            "description",
            "content_md",
            "access_level",
            "is_enabled",
            "created_at",
            "updated_at",
        ]


class FriendlyLinkSerializer(serializers.ModelSerializer):
    created_by = UserPublicSerializer(read_only=True)

    class Meta:
        model = FriendlyLink
        fields = [
            "id",
            "name",
            "description",
            "url",
            "created_by",
            "is_enabled",
            "order",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_by", "created_at", "updated_at"]


class CompetitionNoticeSerializer(serializers.ModelSerializer):
    created_by = UserPublicSerializer(read_only=True)
    updated_by = UserPublicSerializer(read_only=True)
    series_label = serializers.CharField(source="get_series_display", read_only=True)
    stage_label = serializers.CharField(source="get_stage_display", read_only=True)
    can_edit = serializers.SerializerMethodField()

    class Meta:
        model = CompetitionNotice
        fields = [
            "id",
            "title",
            "content_md",
            "series",
            "series_label",
            "year",
            "stage",
            "stage_label",
            "is_visible",
            "published_at",
            "created_by",
            "updated_by",
            "can_edit",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "created_by",
            "updated_by",
            "can_edit",
            "created_at",
            "updated_at",
        ]

    def get_can_edit(self, _obj):
        request = self.context.get("request")
        return can_manage_competition(getattr(request, "user", None))

    def validate(self, attrs):
        instance = getattr(self, "instance", None)
        series = attrs.get("series", getattr(instance, "series", None))
        year = attrs.get("year", getattr(instance, "year", None))
        stage = attrs.get("stage", getattr(instance, "stage", CompetitionNotice.Stage.GENERAL))

        if series in {CompetitionNotice.Series.ICPC, CompetitionNotice.Series.CCPC}:
            if year is None:
                raise serializers.ValidationError({"year": "ICPC/CCPC 公告必须填写年份。"})
            if stage not in {
                CompetitionNotice.Stage.REGIONAL,
                CompetitionNotice.Stage.INVITATIONAL,
                CompetitionNotice.Stage.PROVINCIAL,
                CompetitionNotice.Stage.NETWORK,
            }:
                raise serializers.ValidationError({"stage": "ICPC/CCPC 公告必须选择“区域赛/邀请赛/省赛/网络赛”之一。"})
        else:
            attrs["year"] = None
            attrs["stage"] = CompetitionNotice.Stage.GENERAL

        return attrs


class CompetitionScheduleEntrySerializer(serializers.ModelSerializer):
    announcement_title = serializers.CharField(source="announcement.title", read_only=True)
    announcement_series = serializers.CharField(source="announcement.series", read_only=True)
    announcement_year = serializers.IntegerField(source="announcement.year", read_only=True)
    announcement_stage = serializers.CharField(source="announcement.stage", read_only=True)
    created_by = UserPublicSerializer(read_only=True)
    updated_by = UserPublicSerializer(read_only=True)
    can_edit = serializers.SerializerMethodField()
    is_past = serializers.SerializerMethodField()

    class Meta:
        model = CompetitionScheduleEntry
        fields = [
            "id",
            "event_date",
            "competition_time_range",
            "competition_type",
            "location",
            "qq_group",
            "announcement",
            "announcement_title",
            "announcement_series",
            "announcement_year",
            "announcement_stage",
            "created_by",
            "updated_by",
            "can_edit",
            "is_past",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "created_by",
            "updated_by",
            "announcement_title",
            "announcement_series",
            "announcement_year",
            "announcement_stage",
            "can_edit",
            "is_past",
            "created_at",
            "updated_at",
        ]

    def get_can_edit(self, _obj):
        request = self.context.get("request")
        return can_manage_competition(getattr(request, "user", None))

    def get_is_past(self, obj):
        return bool(obj.event_date and obj.event_date < timezone.localdate())

    def validate_announcement(self, value):
        if value and not value.is_visible:
            raise serializers.ValidationError("不能关联已隐藏的赛事公告。")
        return value


class CompetitionPracticeLinkSerializer(serializers.ModelSerializer):
    created_by = UserPublicSerializer(read_only=True)
    updated_by = UserPublicSerializer(read_only=True)
    series_label = serializers.CharField(source="get_series_display", read_only=True)
    stage_label = serializers.CharField(source="get_stage_display", read_only=True)
    practice_links_text = serializers.SerializerMethodField()

    class Meta:
        model = CompetitionPracticeLink
        fields = [
            "id",
            "source_key",
            "year",
            "series",
            "series_label",
            "stage",
            "stage_label",
            "short_name",
            "official_name",
            "official_url",
            "event_date",
            "event_date_text",
            "organizer",
            "practice_links",
            "practice_links_note",
            "practice_links_text",
            "source_file",
            "source_section",
            "display_order",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_practice_links_text(self, obj):
        return practice_links_to_text(obj.practice_links, obj.practice_links_note)


class CompetitionPracticeLinkProposalSerializer(serializers.ModelSerializer):
    proposer = UserPublicSerializer(read_only=True)
    reviewer = UserPublicSerializer(read_only=True)
    target_entry_summary = serializers.CharField(source="target_entry.short_name", read_only=True)
    proposed_series_label = serializers.CharField(source="get_proposed_series_display", read_only=True)
    proposed_stage_label = serializers.CharField(source="get_proposed_stage_display", read_only=True)
    proposed_practice_links_text = serializers.CharField(write_only=True, required=False, allow_blank=True)
    practice_links_text = serializers.SerializerMethodField()

    class Meta:
        model = CompetitionPracticeLinkProposal
        fields = [
            "id",
            "target_entry",
            "target_entry_summary",
            "proposer",
            "proposed_year",
            "proposed_series",
            "proposed_series_label",
            "proposed_stage",
            "proposed_stage_label",
            "proposed_short_name",
            "proposed_official_name",
            "proposed_official_url",
            "proposed_event_date",
            "proposed_event_date_text",
            "proposed_organizer",
            "proposed_practice_links",
            "proposed_practice_links_note",
            "proposed_practice_links_text",
            "practice_links_text",
            "reason",
            "status",
            "reviewer",
            "review_note",
            "reviewed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "proposer",
            "target_entry_summary",
            "proposed_practice_links",
            "proposed_practice_links_note",
            "practice_links_text",
            "status",
            "reviewer",
            "review_note",
            "reviewed_at",
            "created_at",
            "updated_at",
        ]

    def get_practice_links_text(self, obj):
        return practice_links_to_text(obj.proposed_practice_links, obj.proposed_practice_links_note)

    def validate_proposed_year(self, value):
        if value < 2000 or value > 2099:
            raise serializers.ValidationError("Year must be between 2000 and 2099.")
        return value

    def validate_proposed_short_name(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Short name is required.")
        return value[:120]

    def validate_proposed_official_name(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Official name is required.")
        return value[:500]

    def validate_proposed_official_url(self, value):
        return (value or "").strip()

    def validate_proposed_event_date_text(self, value):
        return (value or "").strip()[:80]

    def validate_proposed_organizer(self, value):
        return (value or "").strip()[:255]

    def validate_reason(self, value):
        return (value or "").strip()

    def validate(self, attrs):
        instance = getattr(self, "instance", None)
        target_entry = attrs.get("target_entry", getattr(instance, "target_entry", None))
        if (
            instance
            and "target_entry" in attrs
            and target_entry
            and instance.target_entry_id
            and target_entry.id != instance.target_entry_id
        ):
            raise serializers.ValidationError(
                {"target_entry": "Cannot change the target entry of an existing proposal."}
            )

        text = None
        if "proposed_practice_links_text" in attrs:
            text = attrs.pop("proposed_practice_links_text")
        elif instance is None:
            text = self.initial_data.get("proposed_practice_links_text", "")

        if text is not None:
            links, note = parse_practice_links_text(text)
            attrs["proposed_practice_links"] = links
            attrs["proposed_practice_links_note"] = note

        event_date = attrs.get("proposed_event_date", getattr(instance, "proposed_event_date", None))
        event_date_text = attrs.get(
            "proposed_event_date_text",
            getattr(instance, "proposed_event_date_text", ""),
        )
        if event_date and not event_date_text:
            attrs["proposed_event_date_text"] = event_date.isoformat()

        return attrs


class CompetitionCalendarEventSerializer(serializers.ModelSerializer):
    source_site_label = serializers.CharField(source="get_source_site_display", read_only=True)
    status = serializers.SerializerMethodField()
    duration_label = serializers.SerializerMethodField()
    time_range_label = serializers.SerializerMethodField()

    class Meta:
        model = CompetitionCalendarEvent
        fields = [
            "id",
            "source_site",
            "source_site_label",
            "source_id",
            "title",
            "organizer",
            "url",
            "start_time",
            "end_time",
            "duration_seconds",
            "duration_label",
            "time_range_label",
            "status",
            "last_synced_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_status(self, obj):
        now = timezone.now()
        if obj.start_time <= now < obj.end_time:
            return "ongoing"
        if obj.start_time > now:
            return "upcoming"
        return "finished"

    def get_duration_label(self, obj):
        total_seconds = int(obj.duration_seconds or 0)
        if total_seconds <= 0:
            return "-"

        days, remainder = divmod(total_seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, _seconds = divmod(remainder, 60)
        pieces = []
        if days:
            pieces.append(f"{days}d")
        if hours or days:
            pieces.append(f"{hours}h")
        pieces.append(f"{minutes}m")
        return " ".join(pieces)

    def get_time_range_label(self, obj):
        start_text = timezone.localtime(obj.start_time).strftime("%Y-%m-%d %H:%M")
        end_text = timezone.localtime(obj.end_time).strftime("%Y-%m-%d %H:%M")
        return f"{start_text} - {end_text}"


class ContributionEventSerializer(serializers.ModelSerializer):
    user = UserPublicSerializer(read_only=True)

    class Meta:
        model = ContributionEvent
        fields = [
            "id",
            "user",
            "event_type",
            "target_type",
            "target_id",
            "payload",
            "created_at",
        ]


class UserNotificationSerializer(serializers.ModelSerializer):
    user = UserPublicSerializer(read_only=True)
    actor = UserPublicSerializer(read_only=True)

    class Meta:
        model = UserNotification
        fields = [
            "id",
            "user",
            "actor",
            "title",
            "content",
            "link",
            "level",
            "target_type",
            "target_id",
            "is_read",
            "read_at",
            "created_at",
            "updated_at",
        ]


class SecurityAuditLogSerializer(serializers.ModelSerializer):
    user = UserPublicSerializer(read_only=True)

    class Meta:
        model = SecurityAuditLog
        fields = [
            "id",
            "event_type",
            "user",
            "username",
            "ip_address",
            "user_agent",
            "success",
            "detail",
            "metadata",
            "created_at",
        ]


class SelfSecurityAuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = SecurityAuditLog
        fields = [
            "id",
            "event_type",
            "ip_address",
            "success",
            "detail",
            "created_at",
        ]
