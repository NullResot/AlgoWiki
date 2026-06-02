import random
import re
import secrets
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.hashers import make_password
from django.contrib.auth.password_validation import validate_password
from django.core.files.storage import FileSystemStorage
from django.core import signing
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from django.utils.crypto import salted_hmac
from django.utils.text import slugify
from rest_framework import serializers
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import Throttled

from .competition_practice import parse_practice_links_text, practice_links_to_text
from .models import (
    Announcement,
    AnnouncementRead,
    Answer,
    AIModerationConfig,
    AIModerationRecord,
    AssistantInteractionLog,
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
    EmailVerificationTicket,
    ExtensionPage,
    FriendlyLink,
    GalleryImage,
    GalleryImageFolder,
    HeaderNavigationItem,
    IssueTicket,
    Moment,
    MomentAuditLog,
    MomentComment,
    MomentFavorite,
    MomentImage,
    MomentLike,
    MomentReport,
    MomentSettings,
    MomentUserRestriction,
    PhoneVerification,
    Question,
    RealNameVerification,
    RevisionProposal,
    SecurityAuditLog,
    TeamMember,
    TrickEntry,
    TrickContributionEvent,
    TrickEntryDownvote,
    TrickEntryLike,
    TrickTerm,
    TrickTermSuggestion,
    UserNotification,
    User,
)
from .trick_terms import FIXED_TRICK_TERM_SLUGS
from .image_security import (
    enforce_image_upload_rate_limit,
    moderate_image_url,
    normalize_uploaded_avatar,
)
from .email_auth import (
    build_email_ticket_token,
    create_email_verification_ticket,
    get_email_code_send_wait_seconds,
    get_email_code_window_wait_seconds,
    load_email_ticket_from_token,
    mask_email,
    send_email_change_notice,
    send_email_code,
    validate_email_code,
)
from .phone_verification_providers import build_phone_digest, normalize_phone_context
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
from .user_identity import DELETED_USER_DISPLAY_NAME, is_deleted_user_placeholder


def can_manage_competition(user):
    return bool(
        user
        and user.is_authenticated
        and user.role in {User.Role.SCHOOL, User.Role.ADMIN, User.Role.SUPERADMIN}
    )


REGISTER_CAPTCHA_SIGNING_SALT = "wiki.register.captcha.v1"
REGISTER_CAPTCHA_INTEGER_RE = re.compile(r"^-?\d+$")
LOGIN_PHONE_INPUT_RE = re.compile(r"^\+?[\d\s\-()]+$")


def _build_register_captcha_digest(nonce: str, answer: int) -> str:
    return salted_hmac(
        REGISTER_CAPTCHA_SIGNING_SALT,
        f"{nonce}:{answer}",
        secret=settings.SECRET_KEY,
    ).hexdigest()


def build_register_challenge():
    challenge_kind = random.choice(("add", "sub", "mul"))
    if challenge_kind == "add":
        left = random.randint(3, 25)
        right = random.randint(2, 20)
        symbol = "+"
        answer = left + right
    elif challenge_kind == "sub":
        left = random.randint(8, 30)
        right = random.randint(2, left - 1)
        symbol = "-"
        answer = left - right
    else:
        left = random.randint(2, 9)
        right = random.randint(2, 9)
        symbol = "x"
        answer = left * right

    nonce = secrets.token_urlsafe(12)
    token = signing.dumps(
        {
            "nonce": nonce,
            "digest": _build_register_captcha_digest(nonce, answer),
        },
        salt=REGISTER_CAPTCHA_SIGNING_SALT,
        compress=True,
    )
    return {
        "prompt": f"Solve: {left} {symbol} {right} = ?",
        "token": token,
        "expires_in_seconds": settings.REGISTER_CAPTCHA_TTL_SECONDS,
    }


def validate_register_challenge(*, token: str, answer, website: str = ""):
    if str(website or "").strip():
        raise serializers.ValidationError(
            {"non_field_errors": ["Verification failed."]}
        )

    if not str(token or "").strip():
        raise serializers.ValidationError(
            {"captcha_token": ["Please refresh the verification challenge."]}
        )

    answer_text = str(answer or "").strip()
    if not answer_text:
        raise serializers.ValidationError(
            {"captcha_answer": ["Please enter the verification result."]}
        )
    if not REGISTER_CAPTCHA_INTEGER_RE.fullmatch(answer_text):
        raise serializers.ValidationError(
            {"captcha_answer": ["Verification answer must be an integer."]}
        )

    try:
        payload = signing.loads(
            token,
            salt=REGISTER_CAPTCHA_SIGNING_SALT,
            max_age=settings.REGISTER_CAPTCHA_TTL_SECONDS,
        )
    except signing.SignatureExpired as exc:
        raise serializers.ValidationError(
            {"captcha_answer": ["Verification expired, please refresh and try again."]}
        ) from exc
    except signing.BadSignature as exc:
        raise serializers.ValidationError(
            {"captcha_answer": ["Verification failed, please refresh and try again."]}
        ) from exc

    nonce = str(payload.get("nonce", "")).strip()
    digest = str(payload.get("digest", "")).strip()
    if not nonce or not digest:
        raise serializers.ValidationError(
            {"captcha_answer": ["Verification failed, please refresh and try again."]}
        )

    expected_digest = _build_register_captcha_digest(nonce, int(answer_text))
    if not secrets.compare_digest(expected_digest, digest):
        raise serializers.ValidationError(
            {"captcha_answer": ["Verification answer is incorrect."]}
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
            and (
                user.pk == instance.pk
                or user.role in {User.Role.ADMIN, User.Role.SUPERADMIN}
            )
        )

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if is_deleted_user_placeholder(instance):
            data["username"] = DELETED_USER_DISPLAY_NAME
            data["role"] = User.Role.NORMAL
            data["school_name"] = ""
            data["avatar_url"] = ""
            data["bio"] = ""
            return data

        if not self._can_view_profile_fields(instance):
            data["school_name"] = ""
            if not self.context.get("allow_public_avatar"):
                data["avatar_url"] = ""
            data["bio"] = ""
        return data


class UserAdminSerializer(serializers.ModelSerializer):
    phone_verification = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "role",
            "school_name",
            "is_active",
            "is_banned",
            "banned_reason",
            "banned_at",
            "date_joined",
            "last_login",
            "phone_verification",
        ]

    def get_phone_verification(self, obj):
        try:
            verification = obj.phone_verification
        except PhoneVerification.DoesNotExist:
            verification = None
        if not verification:
            return {
                "status": PhoneVerification.Status.UNVERIFIED,
                "status_label": "Unverified",
                "phone_masked": "",
                "phone_last4": "",
                "verified_at": None,
                "updated_at": None,
            }
        return {
            "status": verification.status,
            "status_label": verification.get_status_display(),
            "phone_masked": verification.phone_masked,
            "phone_last4": verification.phone_last4,
            "verified_at": verification.verified_at,
            "updated_at": verification.updated_at,
        }


def normalize_email(value: str) -> str:
    return str(value or "").strip().lower()


def validate_unique_email(value: str, *, exclude_user=None):
    email = normalize_email(value)
    if not email:
        raise serializers.ValidationError("Email is required.")
    queryset = User.objects.filter(email__iexact=email)
    if exclude_user is not None:
        queryset = queryset.exclude(pk=exclude_user.pk)
    if queryset.exists():
        raise serializers.ValidationError("This email is already in use.")
    return email


class UserProfileSettingsSerializer(serializers.ModelSerializer):
    email_verified = serializers.SerializerMethodField()
    pending_email = serializers.SerializerMethodField()
    pending_email_expires_at = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "email",
            "email_verified",
            "pending_email",
            "pending_email_expires_at",
            "school_name",
            "bio",
            "avatar_url",
        ]

    def _get_pending_ticket(self, instance):
        now = timezone.now()
        return (
            EmailVerificationTicket.objects.filter(
                purpose=EmailVerificationTicket.Purpose.CHANGE_EMAIL,
                user=instance,
                consumed_at__isnull=True,
                expires_at__gt=now,
            )
            .order_by("-created_at")
            .first()
        )

    def get_email_verified(self, instance):
        return bool(instance.email and instance.email_verified_at)

    def get_pending_email(self, instance):
        ticket = self._get_pending_ticket(instance)
        return ticket.email if ticket else ""

    def get_pending_email_expires_at(self, instance):
        ticket = self._get_pending_ticket(instance)
        return ticket.expires_at if ticket else None


AVATAR_ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
AVATAR_ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
AVATAR_UPLOAD_MAX_BYTES = 2 * 1024 * 1024
AVATAR_OUTPUT_SIZE = 256
AVATAR_MAX_OUTPUT_BYTES = 96 * 1024


def _avatar_media_name_from_url(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    parsed = urlparse(text)
    path = parsed.path if parsed.scheme or parsed.netloc else text
    media_url = (settings.MEDIA_URL or "/media/").strip()
    if not media_url.startswith("/"):
        media_url = f"/{media_url}"
    if not media_url.endswith("/"):
        media_url = f"{media_url}/"
    if not path.startswith(media_url):
        return ""
    relative = path[len(media_url) :].lstrip("/")
    if not relative.startswith("avatars/"):
        return ""
    relative_path = PurePosixPath(relative)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        return ""
    return str(relative_path)


def _delete_local_avatar(value: str) -> None:
    relative = _avatar_media_name_from_url(value)
    if not relative:
        return
    media_root = Path(settings.MEDIA_ROOT).resolve()
    target = (media_root / relative).resolve()
    try:
        target.relative_to(media_root)
    except ValueError:
        return
    if target.exists() and target.is_file():
        target.unlink()


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    username = serializers.CharField(required=False, max_length=150)
    school_name = serializers.CharField(
        required=False, allow_blank=True, max_length=120
    )
    bio = serializers.CharField(required=False, allow_blank=True)
    avatar_url = serializers.URLField(required=False, allow_blank=True)
    avatar_image = serializers.FileField(required=False, write_only=True)

    class Meta:
        model = User
        fields = [
            "username",
            "school_name",
            "bio",
            "avatar_url",
            "avatar_image",
        ]

    def validate_username(self, value):
        username = str(value or "").strip()
        if not username:
            raise serializers.ValidationError("Username cannot be empty.")
        try:
            User._meta.get_field("username").run_validators(username)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc
        queryset = User.objects.filter(username__iexact=username)
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("This username is already in use.")
        return username

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if "email" in self.initial_data:
            raise serializers.ValidationError(
                {
                    "email": [
                        "Use the email verification flow to change your email address."
                    ]
                }
            )
        return attrs

    def _save_avatar_image(self, instance, uploaded_file):
        request = self.context.get("request")
        try:
            enforce_image_upload_rate_limit(
                request=request,
                user=instance,
                purpose="avatar-upload",
                upload_count=1,
                upload_bytes=int(getattr(uploaded_file, "size", 0) or 0),
                burst_limit=2,
                burst_window_seconds=60,
                min_interval_seconds=30,
                hourly_limit=6,
                daily_limit=12,
            )
            normalized = normalize_uploaded_avatar(
                uploaded_file,
                allowed_extensions=AVATAR_ALLOWED_EXTENSIONS,
                allowed_content_types=AVATAR_ALLOWED_CONTENT_TYPES,
                max_bytes=AVATAR_UPLOAD_MAX_BYTES,
                output_size=AVATAR_OUTPUT_SIZE,
                max_output_bytes=AVATAR_MAX_OUTPUT_BYTES,
            )
        except ValueError as exc:
            raise serializers.ValidationError({"avatar_image": [str(exc)]}) from exc

        now = timezone.now()
        filename = f"{uuid4().hex}{normalized.extension}"
        relative_dir = PurePosixPath("avatars") / str(instance.pk) / f"{now:%Y}" / f"{now:%m}"
        storage = FileSystemStorage(
            location=settings.MEDIA_ROOT,
            base_url=settings.MEDIA_URL,
        )
        stored_name = storage.save(str(relative_dir / filename), normalized.file)
        public_url = storage.url(stored_name)
        absolute_url = request.build_absolute_uri(public_url) if request else public_url

        moderation = moderate_image_url(absolute_url, data_id=stored_name)
        actor_is_manager = bool(getattr(instance, "is_manager", False))
        if moderation.decision == "reject" or (
            moderation.decision != "approve" and not actor_is_manager
        ):
            _delete_local_avatar(public_url)
            message = moderation.summary or "头像图片未通过审核。"
            raise serializers.ValidationError({"avatar_image": [message]})

        return public_url

    def update(self, instance, validated_data):
        uploaded_avatar = validated_data.pop("avatar_image", None)
        old_avatar_url = instance.avatar_url
        if uploaded_avatar is not None:
            validated_data["avatar_url"] = self._save_avatar_image(instance, uploaded_avatar)
        instance = super().update(instance, validated_data)
        if uploaded_avatar is not None and old_avatar_url != instance.avatar_url:
            _delete_local_avatar(old_avatar_url)
        return instance


class AccountCancellationSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    confirmation = serializers.CharField(write_only=True)

    CONFIRMATION_TEXT = "注销账户"

    def validate(self, attrs):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            raise serializers.ValidationError("Authentication required.")

        if user.role in {User.Role.ADMIN, User.Role.SUPERADMIN}:
            raise serializers.ValidationError(
                {
                    "detail": "管理员账号请先完成权限移交，再由其他管理员处理账号注销。"
                }
            )

        if not user.check_password(attrs.get("current_password", "")):
            raise serializers.ValidationError(
                {"current_password": ["当前密码不正确。"]}
            )

        confirmation = str(attrs.get("confirmation", "") or "").strip()
        if confirmation != self.CONFIRMATION_TEXT:
            raise serializers.ValidationError(
                {"confirmation": [f"请输入“{self.CONFIRMATION_TEXT}”确认操作。"]}
            )
        return attrs


class PasswordChangeCodeSerializer(serializers.Serializer):
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
            raise serializers.ValidationError(
                {"old_password": "Current password is incorrect."}
            )
        if not normalize_email(user.email):
            raise serializers.ValidationError(
                {
                    "non_field_errors": [
                        "Please set an email address before changing password."
                    ]
                }
            )
        if new_password != confirm_password:
            raise serializers.ValidationError(
                {"confirm_password": "The two new passwords do not match."}
            )
        if old_password == new_password:
            raise serializers.ValidationError(
                {
                    "new_password": "New password must be different from the old password."
                }
            )
        if is_password_reused(user, new_password):
            raise serializers.ValidationError(
                {"new_password": "Cannot reuse recent password."}
            )
        try:
            validate_password(new_password, user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"new_password": list(exc.messages)})
        attrs["user"] = user
        attrs["email"] = normalize_email(user.email)
        return attrs

    def create(self, validated_data):
        request = self.context.get("request")
        user = validated_data["user"]
        email = validated_data["email"]

        wait_seconds = get_email_code_send_wait_seconds(
            purpose=EmailVerificationTicket.Purpose.CHANGE_PASSWORD,
            email=email,
            user=user,
        )
        if wait_seconds:
            raise Throttled(
                wait=wait_seconds,
                detail="Please wait before requesting another password change code.",
            )

        window_wait_seconds = get_email_code_window_wait_seconds(
            purpose=EmailVerificationTicket.Purpose.CHANGE_PASSWORD,
            email=email,
            user=user,
        )
        if window_wait_seconds:
            raise Throttled(
                wait=window_wait_seconds,
                detail="Too many password change codes requested. Please retry later.",
            )

        password_hash = make_password(validated_data["new_password"])
        ticket, code = create_email_verification_ticket(
            purpose=EmailVerificationTicket.Purpose.CHANGE_PASSWORD,
            email=email,
            user=user,
            password_hash_snapshot=password_hash,
            created_ip=get_client_ip(request),
        )
        try:
            send_email_code(ticket, code)
        except Exception:
            ticket.delete()
            raise

        return {
            "ticket_token": build_email_ticket_token(ticket),
            "masked_email": mask_email(email),
            "expires_in_seconds": settings.EMAIL_CODE_TTL_SECONDS,
        }


class PasswordChangeSerializer(serializers.Serializer):
    ticket_token = serializers.CharField()
    code = serializers.CharField()

    def validate(self, attrs):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            raise serializers.ValidationError("Authentication required.")

        ticket = load_email_ticket_from_token(
            attrs.get("ticket_token", ""),
            purpose=EmailVerificationTicket.Purpose.CHANGE_PASSWORD,
        )
        if ticket.user_id != user.id:
            raise serializers.ValidationError(
                {
                    "ticket_token": [
                        "Verification session does not belong to the current account."
                    ]
                }
            )
        validate_email_code(ticket, attrs.get("code", ""))
        if not ticket.password_hash_snapshot:
            raise serializers.ValidationError(
                {"ticket_token": ["Verification session is invalid."]}
            )

        attrs["ticket"] = ticket
        attrs["user"] = user
        return attrs

    def create(self, validated_data):
        ticket = validated_data["ticket"]
        user = validated_data["user"]
        user.password = ticket.password_hash_snapshot
        user.save(update_fields=["password"])
        record_password_history(user)
        Token.objects.filter(user=user).delete()
        token = Token.objects.create(user=user)
        ticket.mark_consumed()
        return {"user": user, "token": token.key}


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
        if (
            allowed_content_types
            and content_type
            and content_type not in allowed_content_types
        ):
            raise serializers.ValidationError("Unsupported image content type.")

        return value


class GalleryImageFolderSerializer(serializers.ModelSerializer):
    active_count = serializers.SerializerMethodField()
    recycled_count = serializers.SerializerMethodField()

    class Meta:
        model = GalleryImageFolder
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "display_order",
            "is_visible",
            "active_count",
            "recycled_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]
        extra_kwargs = {
            "slug": {"required": False, "allow_blank": True, "validators": []},
            "description": {"required": False, "allow_blank": True},
            "display_order": {"required": False},
            "is_visible": {"required": False},
        }

    def get_active_count(self, obj):
        annotated = getattr(obj, "active_count", None)
        if annotated is not None:
            return int(annotated)
        return obj.images.filter(status=GalleryImage.Status.ACTIVE).count()

    def get_recycled_count(self, obj):
        annotated = getattr(obj, "recycled_count", None)
        if annotated is not None:
            return int(annotated)
        return obj.images.filter(status=GalleryImage.Status.RECYCLED).count()

    def validate_name(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Folder name is required.")
        return value[:120]

    def validate_slug(self, value):
        value = (value or "").strip()
        return value[:140]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        name = attrs.get("name") or getattr(self.instance, "name", "")
        slug = attrs.get("slug")
        if slug is None:
            slug = getattr(self.instance, "slug", "")
        if not slug:
            slug = self._build_unique_slug(name)
            attrs["slug"] = slug
        queryset = GalleryImageFolder.objects.filter(slug=slug)
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError({"slug": "Folder slug already exists."})
        return attrs

    def _build_unique_slug(self, name):
        base = slugify(name or "") or f"gallery-{secrets.token_hex(4)}"
        base = base[:120].strip("-") or f"gallery-{secrets.token_hex(4)}"
        candidate = base[:140]
        while GalleryImageFolder.objects.filter(slug=candidate).exists():
            candidate = f"{base[:108]}-{secrets.token_hex(4)}"[:140]
        return candidate


class GalleryImageSerializer(serializers.ModelSerializer):
    folder_name = serializers.CharField(source="folder.name", read_only=True)
    folder_slug = serializers.CharField(source="folder.slug", read_only=True)
    uploaded_by = UserPublicSerializer(read_only=True)
    deleted_by = UserPublicSerializer(read_only=True)
    url = serializers.SerializerMethodField()
    markdown = serializers.SerializerMethodField()
    size_label = serializers.SerializerMethodField()
    filename = serializers.SerializerMethodField()

    class Meta:
        model = GalleryImage
        fields = [
            "id",
            "folder",
            "folder_name",
            "folder_slug",
            "image",
            "url",
            "markdown",
            "filename",
            "original_name",
            "content_type",
            "size_bytes",
            "size_label",
            "uploaded_by",
            "status",
            "original_path",
            "recycled_path",
            "deleted_at",
            "delete_after",
            "deleted_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def _absolute_image_url(self, obj):
        if not obj.image:
            return ""
        request = self.context.get("request")
        try:
            raw_url = obj.image.url
        except ValueError:
            return ""
        return request.build_absolute_uri(raw_url) if request else raw_url

    def get_url(self, obj):
        return self._absolute_image_url(obj)

    def get_markdown(self, obj):
        if obj.status != GalleryImage.Status.ACTIVE:
            return ""
        url = self.get_url(obj)
        if not url:
            return ""
        alt = Path(obj.original_name or "image").stem or "image"
        return f"![{alt}]({url})"

    def get_size_label(self, obj):
        size = int(obj.size_bytes or 0)
        if size >= 1024 * 1024:
            return f"{size / 1024 / 1024:.1f} MB"
        if size >= 1024:
            return f"{size / 1024:.0f} KB"
        return f"{size} B"

    def get_filename(self, obj):
        if not obj.image:
            return ""
        return Path(str(obj.image.name or "")).name


class GalleryImageUploadSerializer(serializers.Serializer):
    image = serializers.FileField()
    folder = serializers.PrimaryKeyRelatedField(
        queryset=GalleryImageFolder.objects.filter(is_visible=True),
        required=False,
        allow_null=True,
    )
    folder_slug = serializers.SlugField(required=False, allow_blank=True)
    folder_name = serializers.CharField(required=False, allow_blank=True, max_length=120)

    def validate_image(self, value):
        return ImageUploadSerializer(
            data={"image": value},
            context=self.context,
        ).validate_image(value)

    def validate(self, attrs):
        folder = attrs.get("folder")
        folder_slug = str(attrs.get("folder_slug") or "").strip()
        folder_name = str(attrs.get("folder_name") or "").strip()
        if folder is None and folder_slug:
            folder = GalleryImageFolder.objects.filter(
                slug=folder_slug, is_visible=True
            ).first()
            if folder is None:
                raise serializers.ValidationError({"folder_slug": "Folder not found."})
        attrs["folder"] = folder
        attrs["folder_name"] = folder_name
        return attrs


class RegisterEmailCodeSerializer(serializers.Serializer):
    username = serializers.CharField()
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    school_name = serializers.CharField(
        required=False, allow_blank=True, max_length=120
    )
    captcha_token = serializers.CharField(write_only=True)
    captcha_answer = serializers.CharField(write_only=True)
    website = serializers.CharField(
        write_only=True, required=False, allow_blank=True, default=""
    )

    def validate_username(self, value):
        username = str(value or "").strip()
        if not username:
            raise serializers.ValidationError("Username is required.")
        if User.objects.filter(username__iexact=username).exists():
            raise serializers.ValidationError("This username is already in use.")
        return username

    def validate_email(self, value):
        return validate_unique_email(value)

    def validate_password(self, value):
        probe_user = User(
            username=str(self.initial_data.get("username", "")).strip(),
            email=normalize_email(str(self.initial_data.get("email", ""))),
        )
        try:
            validate_password(value, user=probe_user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages))
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        validate_register_challenge(
            token=attrs.get("captcha_token", ""),
            answer=attrs.get("captcha_answer", ""),
            website=attrs.get("website", ""),
        )
        return attrs

    def create(self, validated_data):
        request = self.context.get("request")
        email = validated_data["email"]
        user_ip = get_client_ip(request)

        wait_seconds = get_email_code_send_wait_seconds(
            purpose=EmailVerificationTicket.Purpose.REGISTER,
            email=email,
        )
        if wait_seconds:
            raise Throttled(
                wait=wait_seconds,
                detail="Please wait before requesting another registration code.",
            )

        window_wait_seconds = get_email_code_window_wait_seconds(
            purpose=EmailVerificationTicket.Purpose.REGISTER,
            email=email,
        )
        if window_wait_seconds:
            raise Throttled(
                wait=window_wait_seconds,
                detail="Too many registration codes requested. Please retry later.",
            )

        validated_data.pop("captcha_token", None)
        validated_data.pop("captcha_answer", None)
        validated_data.pop("website", None)
        password_hash = make_password(validated_data.pop("password"))
        ticket, code = create_email_verification_ticket(
            purpose=EmailVerificationTicket.Purpose.REGISTER,
            email=email,
            username_snapshot=validated_data.get("username", ""),
            school_name_snapshot=validated_data.get("school_name", ""),
            password_hash_snapshot=password_hash,
            created_ip=user_ip,
        )
        try:
            send_email_code(ticket, code)
        except Exception:
            ticket.delete()
            raise

        return {
            "ticket_token": build_email_ticket_token(ticket),
            "masked_email": mask_email(ticket.email),
            "expires_in_seconds": settings.EMAIL_CODE_TTL_SECONDS,
        }


class RegisterSerializer(serializers.Serializer):
    ticket_token = serializers.CharField()
    code = serializers.CharField()

    def validate(self, attrs):
        ticket = load_email_ticket_from_token(
            attrs.get("ticket_token", ""),
            purpose=EmailVerificationTicket.Purpose.REGISTER,
        )
        validate_email_code(ticket, attrs.get("code", ""))

        username = str(ticket.username_snapshot or "").strip()
        email = normalize_email(ticket.email)
        if not username or not email or not ticket.password_hash_snapshot:
            raise serializers.ValidationError(
                {
                    "ticket_token": [
                        "Registration session is incomplete. Please restart the registration flow."
                    ]
                }
            )
        if User.objects.filter(username__iexact=username).exists():
            raise serializers.ValidationError(
                {"username": ["This username is already in use."]}
            )
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError(
                {"email": ["This email is already in use."]}
            )

        attrs["ticket"] = ticket
        return attrs

    def create(self, validated_data):
        ticket = validated_data["ticket"]
        now = timezone.now()
        user = User.objects.create(
            username=ticket.username_snapshot,
            email=normalize_email(ticket.email),
            school_name=ticket.school_name_snapshot,
            role=User.Role.NORMAL,
            password=ticket.password_hash_snapshot,
            email_verified_at=now,
        )
        record_password_history(user)
        token = Token.objects.create(user=user)
        ticket.mark_consumed()
        return {"user": user, "token": token.key}


class PasswordResetCodeSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        email = normalize_email(value)
        if not email:
            raise serializers.ValidationError("Email is required.")
        return email

    def create(self, validated_data):
        request = self.context.get("request")
        email = validated_data["email"]

        wait_seconds = get_email_code_send_wait_seconds(
            purpose=EmailVerificationTicket.Purpose.RESET_PASSWORD,
            email=email,
        )
        if wait_seconds:
            raise Throttled(
                wait=wait_seconds,
                detail="Please wait before requesting another reset code.",
            )

        window_wait_seconds = get_email_code_window_wait_seconds(
            purpose=EmailVerificationTicket.Purpose.RESET_PASSWORD,
            email=email,
        )
        if window_wait_seconds:
            raise Throttled(
                wait=window_wait_seconds,
                detail="Too many reset codes requested. Please retry later.",
            )

        user = User.objects.filter(
            email__iexact=email, is_active=True, is_banned=False
        ).first()
        ticket, code = create_email_verification_ticket(
            purpose=EmailVerificationTicket.Purpose.RESET_PASSWORD,
            email=email,
            user=user,
            created_ip=get_client_ip(request),
        )
        if user is not None:
            try:
                send_email_code(ticket, code)
            except Exception:
                ticket.delete()
                raise

        return {
            "ticket_token": build_email_ticket_token(ticket),
            "masked_email": mask_email(email),
            "expires_in_seconds": settings.EMAIL_CODE_TTL_SECONDS,
        }


class PasswordResetSerializer(serializers.Serializer):
    ticket_token = serializers.CharField()
    code = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        ticket = load_email_ticket_from_token(
            attrs.get("ticket_token", ""),
            purpose=EmailVerificationTicket.Purpose.RESET_PASSWORD,
        )
        validate_email_code(ticket, attrs.get("code", ""))

        user = ticket.user
        if user is None or not user.is_active or user.is_banned:
            raise serializers.ValidationError(
                {"code": ["Verification code is invalid."]}
            )

        new_password = attrs.get("new_password", "")
        confirm_password = attrs.get("confirm_password", "")
        if new_password != confirm_password:
            raise serializers.ValidationError(
                {"confirm_password": "The two new passwords do not match."}
            )
        if is_password_reused(user, new_password):
            raise serializers.ValidationError(
                {"new_password": "Cannot reuse recent password."}
            )
        try:
            validate_password(new_password, user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"new_password": list(exc.messages)})

        attrs["ticket"] = ticket
        attrs["user"] = user
        return attrs

    def create(self, validated_data):
        ticket = validated_data["ticket"]
        user = validated_data["user"]
        user.set_password(validated_data["new_password"])
        user.email_verified_at = timezone.now()
        user.save(update_fields=["password", "email_verified_at"])
        record_password_history(user)
        Token.objects.filter(user=user).delete()
        token = Token.objects.create(user=user)
        ticket.mark_consumed()
        return {"user": user, "token": token.key}


class EmailChangeCodeSerializer(serializers.Serializer):
    email = serializers.EmailField()
    current_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            raise serializers.ValidationError("Authentication required.")

        email = normalize_email(attrs.get("email", ""))
        if not user.check_password(attrs.get("current_password", "")):
            raise serializers.ValidationError(
                {"current_password": "Current password is incorrect."}
            )

        current_email = normalize_email(user.email)
        if email != current_email:
            validate_unique_email(email, exclude_user=user)
        elif user.email_verified_at:
            raise serializers.ValidationError(
                {"email": "Current email is already verified."}
            )

        attrs["email"] = email
        attrs["user"] = user
        return attrs

    def create(self, validated_data):
        request = self.context.get("request")
        user = validated_data["user"]
        email = validated_data["email"]

        wait_seconds = get_email_code_send_wait_seconds(
            purpose=EmailVerificationTicket.Purpose.CHANGE_EMAIL,
            email=email,
            user=user,
        )
        if wait_seconds:
            raise Throttled(
                wait=wait_seconds,
                detail="Please wait before requesting another email code.",
            )

        window_wait_seconds = get_email_code_window_wait_seconds(
            purpose=EmailVerificationTicket.Purpose.CHANGE_EMAIL,
            email=email,
            user=user,
        )
        if window_wait_seconds:
            raise Throttled(
                wait=window_wait_seconds,
                detail="Too many email verification codes requested. Please retry later.",
            )

        ticket, code = create_email_verification_ticket(
            purpose=EmailVerificationTicket.Purpose.CHANGE_EMAIL,
            email=email,
            user=user,
            created_ip=get_client_ip(request),
        )
        try:
            send_email_code(ticket, code)
        except Exception:
            ticket.delete()
            raise

        return {
            "ticket_token": build_email_ticket_token(ticket),
            "masked_email": mask_email(email),
            "expires_in_seconds": settings.EMAIL_CODE_TTL_SECONDS,
        }


class EmailChangeSerializer(serializers.Serializer):
    ticket_token = serializers.CharField()
    code = serializers.CharField()

    def validate(self, attrs):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            raise serializers.ValidationError("Authentication required.")

        ticket = load_email_ticket_from_token(
            attrs.get("ticket_token", ""),
            purpose=EmailVerificationTicket.Purpose.CHANGE_EMAIL,
        )
        if ticket.user_id != user.id:
            raise serializers.ValidationError(
                {
                    "ticket_token": [
                        "Verification session does not belong to the current account."
                    ]
                }
            )
        validate_email_code(ticket, attrs.get("code", ""))

        if normalize_email(ticket.email) != normalize_email(user.email):
            validate_unique_email(ticket.email, exclude_user=user)

        attrs["ticket"] = ticket
        attrs["user"] = user
        return attrs

    def create(self, validated_data):
        ticket = validated_data["ticket"]
        user = validated_data["user"]
        old_email = user.email
        user.email = normalize_email(ticket.email)
        user.email_verified_at = timezone.now()
        user.save(update_fields=["email", "email_verified_at"])
        ticket.mark_consumed()
        send_email_change_notice(old_email=old_email, new_email=user.email)
        return {"user": user, "old_email": old_email}


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)
    token = serializers.CharField(read_only=True)
    user = UserPublicSerializer(read_only=True)

    def _single_user_or_none(self, queryset):
        users = list(queryset[:2])
        return users[0] if len(users) == 1 else None

    def _email_login_key(self, email: str) -> str:
        digest = salted_hmac(
            "wiki.login.email.v1",
            normalize_email(email),
            secret=settings.SECRET_KEY,
        ).hexdigest()
        return f"email:{digest}"

    def _resolve_login_identifier(self, identifier: str):
        if "@" in identifier:
            email = normalize_email(identifier)
            user = self._single_user_or_none(
                User.objects.filter(
                    email__iexact=email,
                    email_verified_at__isnull=False,
                )
            )
            return {
                "kind": "email",
                "user": user,
                "fallback_key": self._email_login_key(email),
                "audit_username": f"email:{mask_email(email)}",
            }

        if LOGIN_PHONE_INPUT_RE.fullmatch(identifier):
            try:
                country_code, phone_number = normalize_phone_context(
                    country_code="86",
                    phone_number=identifier,
                )
            except DjangoValidationError:
                pass
            else:
                phone_digest = build_phone_digest(country_code, phone_number)
                verification = (
                    PhoneVerification.objects.select_related("user")
                    .filter(
                        status=PhoneVerification.Status.VERIFIED,
                        phone_country_code=country_code,
                        phone_digest=phone_digest,
                    )
                    .first()
                )
                return {
                    "kind": "phone",
                    "user": verification.user if verification else None,
                    "fallback_key": f"phone:{country_code}:{phone_digest}",
                    "audit_username": f"phone:+{country_code}:****{phone_number[-4:]}",
                }

        username = identifier.strip()
        user = self._single_user_or_none(User.objects.filter(username__iexact=username))
        return {
            "kind": "username",
            "user": user,
            "fallback_key": username.lower() or "<empty>",
            "audit_username": username,
        }

    def validate(self, attrs):
        request = self.context.get("request")
        username = str(attrs.get("username", "")).strip()
        password = attrs.get("password")
        client_ip = get_client_ip(request)
        login_identity = self._resolve_login_identifier(username)
        resolved_user = login_identity["user"]
        login_key = resolved_user.username if resolved_user else login_identity["fallback_key"]
        audit_username = (
            resolved_user.username if resolved_user else login_identity["audit_username"]
        )

        is_locked, wait_seconds = check_login_locked(login_key, client_ip)
        if is_locked:
            record_security_event(
                event_type=SecurityAuditLog.EventType.LOGIN_LOCKED,
                request=request,
                username=audit_username,
                success=False,
                detail="account temporarily locked due to failed attempts",
            )
            raise Throttled(
                wait=wait_seconds,
                detail="Too many failed attempts, please try again later.",
            )

        user = (
            authenticate(username=resolved_user.username, password=password)
            if resolved_user
            else None
        )
        if not user:
            register_login_failure(login_key, client_ip)
            is_locked_after, wait_seconds_after = check_login_locked(
                login_key, client_ip
            )
            if is_locked_after:
                record_security_event(
                    event_type=SecurityAuditLog.EventType.LOGIN_LOCKED,
                    request=request,
                    username=audit_username,
                    success=False,
                    detail="lock triggered after failed login",
                )
                raise Throttled(
                    wait=wait_seconds_after,
                    detail="Too many failed attempts, please try again later.",
                )
            record_security_event(
                event_type=SecurityAuditLog.EventType.LOGIN_FAILED,
                request=request,
                username=audit_username,
                success=False,
                detail="invalid credentials",
            )
            raise serializers.ValidationError("Invalid username or password.")
        if not user.is_active:
            record_security_event(
                event_type=SecurityAuditLog.EventType.LOGIN_DENIED,
                request=request,
                user=user,
                username=user.username,
                success=False,
                detail="account disabled",
            )
            raise serializers.ValidationError("This account is disabled.")
        if user.is_banned:
            record_security_event(
                event_type=SecurityAuditLog.EventType.LOGIN_DENIED,
                request=request,
                user=user,
                username=user.username,
                success=False,
                detail="account banned",
            )
            raise serializers.ValidationError("This account has been banned.")

        clear_login_failures(login_key, client_ip)
        Token.objects.filter(user=user).delete()
        token = Token.objects.create(user=user)
        user.last_login = timezone.now()
        user.save(update_fields=["last_login"])
        record_security_event(
            event_type=SecurityAuditLog.EventType.LOGIN_SUCCESS,
            request=request,
            user=user,
            username=user.username,
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
            "display_order",
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
        extra_kwargs = {
            "summary": {"required": False, "allow_blank": True},
            "content_md": {"required": False, "allow_blank": True},
            "display_order": {"required": False},
        }

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


class ArticleContributorSerializer(serializers.Serializer):
    user = UserPublicSerializer(read_only=True)
    is_creator = serializers.BooleanField()
    approved_revision_count = serializers.IntegerField()
    first_contributed_at = serializers.DateTimeField()
    last_contributed_at = serializers.DateTimeField()


class ArticleDetailSerializer(ArticleSerializer):
    contributors = serializers.SerializerMethodField()

    class Meta(ArticleSerializer.Meta):
        fields = [*ArticleSerializer.Meta.fields, "contributors"]

    def get_contributors(self, obj):
        contributor_map = {}

        def record(user, contributed_at, *, is_creator=False, approved_revision=False):
            if not user or not contributed_at:
                return

            payload = contributor_map.get(user.id)
            if payload is None:
                payload = {
                    "user": user,
                    "is_creator": False,
                    "approved_revision_count": 0,
                    "first_contributed_at": contributed_at,
                    "last_contributed_at": contributed_at,
                }
                contributor_map[user.id] = payload
            else:
                if contributed_at < payload["first_contributed_at"]:
                    payload["first_contributed_at"] = contributed_at
                if contributed_at > payload["last_contributed_at"]:
                    payload["last_contributed_at"] = contributed_at

            if is_creator:
                payload["is_creator"] = True
            if approved_revision:
                payload["approved_revision_count"] += 1

        record(obj.author, obj.published_at or obj.created_at, is_creator=True)

        approved_revisions = getattr(obj, "approved_revision_proposals", None)
        if approved_revisions is None:
            approved_revisions = obj.revision_proposals.filter(
                status=RevisionProposal.Status.APPROVED
            ).select_related("proposer")

        for proposal in approved_revisions:
            record(
                proposal.proposer,
                proposal.reviewed_at or proposal.updated_at or proposal.created_at,
                approved_revision=True,
            )

        contributors = sorted(
            contributor_map.values(),
            key=lambda item: (
                item["first_contributed_at"],
                item["last_contributed_at"],
                item["user"].username.casefold(),
                item["user"].id,
            ),
        )
        return ArticleContributorSerializer(
            contributors, many=True, context=self.context
        ).data


def _record_contributor(
    contributor_map, user, contributed_at, *, is_creator=False, approved_revision=False
):
    if not user or not contributed_at:
        return

    payload = contributor_map.get(user.id)
    if payload is None:
        payload = {
            "user": user,
            "is_creator": False,
            "approved_revision_count": 0,
            "first_contributed_at": contributed_at,
            "last_contributed_at": contributed_at,
        }
        contributor_map[user.id] = payload
    else:
        if contributed_at < payload["first_contributed_at"]:
            payload["first_contributed_at"] = contributed_at
        if contributed_at > payload["last_contributed_at"]:
            payload["last_contributed_at"] = contributed_at

    if is_creator:
        payload["is_creator"] = True
    if approved_revision:
        payload["approved_revision_count"] += 1


def _finalize_contributors(contributor_map, *, context):
    contributors = sorted(
        contributor_map.values(),
        key=lambda item: (
            item["first_contributed_at"],
            item["last_contributed_at"],
            item["user"].username.casefold(),
            item["user"].id,
        ),
    )
    return ArticleContributorSerializer(contributors, many=True, context=context).data


def _collect_serializer_instances(serializer, current_obj):
    root = getattr(serializer, "root", None) or serializer
    cache = getattr(root, "_contributor_instance_cache", None)
    if cache is None:
        cache = {}
        setattr(root, "_contributor_instance_cache", cache)

    cache_key = current_obj.__class__
    if cache_key in cache:
        return cache[cache_key]

    instance = getattr(root, "instance", None)
    if instance is None:
        resolved = [current_obj] if current_obj is not None else []
    elif hasattr(instance, "object_list"):
        resolved = [item for item in instance.object_list if item is not None]
    elif isinstance(instance, (list, tuple)):
        resolved = [item for item in instance if item is not None]
    elif hasattr(instance, "__iter__") and not isinstance(instance, (str, bytes, dict)):
        resolved = [item for item in instance if item is not None]
    else:
        resolved = [instance]

    cache[cache_key] = resolved
    return resolved


def _get_contribution_event_cache(serializer, current_obj, *, target_type):
    root = getattr(serializer, "root", None) or serializer
    cache = getattr(root, "_contribution_event_cache", None)
    if cache is None:
        cache = {}
        setattr(root, "_contribution_event_cache", cache)

    instances = _collect_serializer_instances(serializer, current_obj)
    target_ids = tuple(sorted({item.id for item in instances if getattr(item, "id", None)}))
    cache_key = (target_type, target_ids)
    if cache_key not in cache:
        grouped = {}
        if target_ids:
            events = (
                ContributionEvent.objects.filter(target_type=target_type, target_id__in=target_ids)
                .select_related("user")
                .order_by("created_at", "id")
            )
            for event in events:
                grouped.setdefault(event.target_id, []).append(event)
        cache[cache_key] = grouped
    return cache[cache_key]


def _get_practice_proposal_cache(serializer, current_obj):
    root = getattr(serializer, "root", None) or serializer
    cache = getattr(root, "_practice_proposal_cache", None)
    if cache is None:
        cache = {}
        setattr(root, "_practice_proposal_cache", cache)

    instances = _collect_serializer_instances(serializer, current_obj)
    target_ids = tuple(sorted({item.id for item in instances if getattr(item, "id", None)}))
    if target_ids not in cache:
        grouped = {}
        if target_ids:
            proposals = (
                CompetitionPracticeLinkProposal.objects.filter(
                    target_entry_id__in=target_ids,
                    status=CompetitionPracticeLinkProposal.Status.APPROVED,
                )
                .select_related("proposer")
                .order_by("reviewed_at", "updated_at", "created_at", "id")
            )
            for proposal in proposals:
                grouped.setdefault(proposal.target_entry_id, []).append(proposal)
        cache[target_ids] = grouped
    return cache[target_ids]


def _is_practice_creation_proposal(entry, proposal):
    if not entry or not proposal:
        return False
    if proposal.target_entry_id != entry.id:
        return False
    if proposal.proposer_id != entry.created_by_id:
        return False
    if entry.source_file != "user_proposal" or entry.source_section != "user_submission":
        return False

    created_at = getattr(entry, "created_at", None)
    reviewed_at = getattr(proposal, "reviewed_at", None)
    if not created_at or not reviewed_at:
        return False

    return abs((created_at - reviewed_at).total_seconds()) <= 10


class ArticleCommentSerializer(serializers.ModelSerializer):
    author = UserPublicSerializer(read_only=True)
    reviewer = UserPublicSerializer(read_only=True)
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
            "reviewer",
            "review_note",
            "reviewed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "author",
            "status",
            "reviewer",
            "review_note",
            "reviewed_at",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        article = attrs.get("article") or getattr(self.instance, "article", None)
        parent = attrs.get("parent")
        if parent:
            if not article:
                raise serializers.ValidationError(
                    {"parent": "Parent comment requires a target article."}
                )
            if parent.article_id != article.id:
                raise serializers.ValidationError(
                    {"parent": "Parent comment must belong to the same article."}
                )
            if parent.status != ArticleComment.Status.VISIBLE:
                raise serializers.ValidationError(
                    {"parent": "Parent comment is not available."}
                )
        return attrs


class RevisionProposalSerializer(serializers.ModelSerializer):
    proposer = UserPublicSerializer(read_only=True)
    reviewer = UserPublicSerializer(read_only=True)
    article_title = serializers.CharField(source="article.title", read_only=True)
    article_summary = serializers.CharField(source="article.summary", read_only=True)
    article_content_md = serializers.CharField(source="article.content_md", read_only=True)
    article_updated_at = serializers.DateTimeField(source="article.updated_at", read_only=True)
    base_matches_article = serializers.SerializerMethodField()
    base_summary = serializers.CharField(required=False, allow_blank=True, trim_whitespace=False)
    base_content_md = serializers.CharField(required=False, allow_blank=True, trim_whitespace=False)
    proposed_summary = serializers.CharField(required=False, allow_blank=True, trim_whitespace=False)
    proposed_content_md = serializers.CharField(trim_whitespace=False)
    reason = serializers.CharField(required=False, allow_blank=True, trim_whitespace=False)

    class Meta:
        model = RevisionProposal
        fields = [
            "id",
            "article",
            "article_title",
            "article_summary",
            "article_content_md",
            "article_updated_at",
            "proposer",
            "base_title",
            "base_summary",
            "base_content_md",
            "base_updated_at",
            "base_matches_article",
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
                {
                    "article": "Cannot change the target article of an existing revision proposal."
                }
            )
        return attrs

    def get_base_matches_article(self, obj):
        article = getattr(obj, "article", None)
        if not article:
            return False
        return (
            str(obj.base_title or "") == str(article.title or "")
            and str(obj.base_summary or "") == str(article.summary or "")
            and str(obj.base_content_md or "") == str(article.content_md or "")
        )


class IssueTicketSerializer(serializers.ModelSerializer):
    author = UserPublicSerializer(read_only=True)
    assignee = UserPublicSerializer(read_only=True)
    reviewer = UserPublicSerializer(read_only=True)
    related_article_title = serializers.CharField(
        source="related_article.title", read_only=True
    )
    visibility_label = serializers.CharField(
        source="get_visibility_display", read_only=True
    )

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
            "reviewer",
            "review_note",
            "reviewed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "author",
            "status",
            "assignee",
            "resolution_note",
            "reviewer",
            "review_note",
            "reviewed_at",
            "created_at",
            "updated_at",
        ]


class TrickEntrySerializer(serializers.ModelSerializer):
    author = UserPublicSerializer(read_only=True)
    reviewer = UserPublicSerializer(read_only=True)
    terms = serializers.SerializerMethodField(read_only=True)
    keywords = serializers.SerializerMethodField(read_only=True)
    contributors = serializers.SerializerMethodField()
    like_count = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField()
    downvote_count = serializers.SerializerMethodField()
    is_downvoted = serializers.SerializerMethodField()
    delete_vote_review_status = serializers.CharField(read_only=True)
    delete_vote_review_requested_at = serializers.DateTimeField(read_only=True)
    delete_vote_review_note = serializers.CharField(read_only=True)
    delete_vote_reviewed_at = serializers.DateTimeField(read_only=True)
    term_ids = serializers.PrimaryKeyRelatedField(
        source="terms",
        queryset=TrickTerm.objects.filter(
            is_active=True,
            is_builtin=True,
            slug__in=FIXED_TRICK_TERM_SLUGS,
        ),
        many=True,
        required=False,
        write_only=True,
    )
    pending_term_names = serializers.ListField(
        child=serializers.CharField(max_length=80),
        required=False,
        write_only=True,
    )

    class Meta:
        model = TrickEntry
        fields = [
            "id",
            "title",
            "content_md",
            "keywords_text",
            "keywords",
            "author",
            "terms",
            "term_ids",
            "pending_term_names",
            "like_count",
            "is_liked",
            "downvote_count",
            "is_downvoted",
            "status",
            "reviewer",
            "review_note",
            "reviewed_at",
            "delete_vote_review_status",
            "delete_vote_review_requested_at",
            "delete_vote_review_note",
            "delete_vote_reviewed_at",
            "contributors",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "author",
            "keywords",
            "like_count",
            "is_liked",
            "downvote_count",
            "is_downvoted",
            "status",
            "reviewer",
            "review_note",
            "reviewed_at",
            "delete_vote_review_status",
            "delete_vote_review_requested_at",
            "delete_vote_review_note",
            "delete_vote_reviewed_at",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            "title": {"required": True, "allow_blank": False},
            "keywords_text": {"required": True, "allow_blank": False},
        }

    def _split_keywords(self, value):
        return [item for item in str(value or "").split() if item]

    def _normalize_keywords_text(self, value):
        ordered = []
        seen = set()
        for raw_item in self._split_keywords(value):
            item = raw_item.strip()
            if not item:
                continue
            normalized = item.casefold()
            if normalized in seen:
                continue
            seen.add(normalized)
            ordered.append(item[:32])
        return " ".join(ordered[:12])

    def get_terms(self, obj):
        ordered_terms = sorted(obj.terms.all(), key=lambda term: str(term.name or ""))
        return [
            {
                "id": term.id,
                "name": term.name,
                "slug": term.slug,
            }
            for term in ordered_terms
        ]

    def get_keywords(self, obj):
        return self._split_keywords(getattr(obj, "keywords_text", ""))

    def get_like_count(self, obj):
        annotated = getattr(obj, "like_count", None)
        if annotated is not None:
            return int(annotated)
        return obj.like_records.count()

    def get_is_liked(self, obj):
        annotated = getattr(obj, "is_liked", None)
        if annotated is not None:
            return bool(annotated)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        return TrickEntryLike.objects.filter(user=user, trick_entry=obj).exists()

    def get_downvote_count(self, obj):
        annotated = getattr(obj, "downvote_count", None)
        if annotated is not None:
            return int(annotated)
        return obj.downvote_records.count()

    def get_is_downvoted(self, obj):
        annotated = getattr(obj, "is_downvoted", None)
        if annotated is not None:
            return bool(annotated)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        return TrickEntryDownvote.objects.filter(user=user, trick_entry=obj).exists()

    def get_contributors(self, obj):
        contributor_map = {}
        _record_contributor(contributor_map, obj.author, obj.created_at, is_creator=True)

        event_cache = _get_contribution_event_cache(self, obj, target_type=TrickEntry.__name__)
        for event in event_cache.get(obj.id, []):
            payload = event.payload if isinstance(event.payload, dict) else {}
            if payload.get("action") != "update_trick_entry":
                continue
            if payload.get("status") != TrickEntry.Status.APPROVED:
                continue
            _record_contributor(
                contributor_map,
                event.user,
                event.created_at,
                approved_revision=True,
            )

        return _finalize_contributors(contributor_map, context=self.context)

    def validate_pending_term_names(self, value):
        cleaned = [
            " ".join(str(item or "").strip().split()) for item in (value or [])
        ]
        cleaned = [item for item in cleaned if item]
        if cleaned:
            raise serializers.ValidationError("trick 词条已固定，请直接选择现有分类。")
        return []

    def validate(self, attrs):
        attrs = super().validate(attrs)
        terms = attrs.get("terms", serializers.empty)
        current_terms = list(self.instance.terms.all()) if self.instance else []

        if terms is serializers.empty:
            terms = current_terms

        if not terms:
            raise serializers.ValidationError({"term_ids": "请至少选择一个词条。"})

        return attrs

    def validate_keywords_text(self, value):
        normalized = self._normalize_keywords_text(value)
        if not normalized:
            raise serializers.ValidationError("请至少填写 1 个关键词。")
        return normalized

    def validate_title(self, value):
        title = str(value or "").strip()
        if not title:
            raise serializers.ValidationError("标题不能为空。")
        return title

    def create(self, validated_data):
        validated_data.pop("pending_term_names", None)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data.pop("pending_term_names", None)
        return super().update(instance, validated_data)


class TrickTermSerializer(serializers.ModelSerializer):
    usage_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = TrickTerm
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "is_active",
            "is_builtin",
            "usage_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["slug", "usage_count", "created_at", "updated_at"]


class TrickTermSuggestionSerializer(serializers.ModelSerializer):
    proposer = UserPublicSerializer(read_only=True)
    reviewer = UserPublicSerializer(read_only=True)
    linked_tricks = serializers.SerializerMethodField(read_only=True)
    linked_tricks_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = TrickTermSuggestion
        fields = [
            "id",
            "name",
            "normalized_name",
            "proposer",
            "status",
            "reviewer",
            "review_note",
            "reviewed_at",
            "linked_tricks",
            "linked_tricks_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "normalized_name",
            "proposer",
            "status",
            "reviewer",
            "review_note",
            "reviewed_at",
            "created_at",
            "updated_at",
        ]

    def validate_name(self, value):
        normalized = " ".join(str(value or "").strip().split()).lower()
        if not normalized:
            raise serializers.ValidationError("词条名称不能为空。")
        if len(normalized) > 80:
            raise serializers.ValidationError("词条名称过长。")
        # Require at least one meaningful character (CJK/letter/digit),
        # preventing placeholders like "??" from being submitted.
        if not re.search(r"[A-Za-z0-9\u4e00-\u9fff]", normalized):
            raise serializers.ValidationError("词条名称无效，请输入有意义的名称。")
        return " ".join(str(value or "").strip().split())

    def create(self, validated_data):
        name = validated_data["name"]
        normalized_name = " ".join(name.strip().split()).lower()
        validated_data["normalized_name"] = normalized_name
        return super().create(validated_data)

    def get_linked_tricks(self, obj):
        return [
            {
                "id": item.id,
                "title": item.title,
            }
            for item in obj.pending_trick_entries.all().order_by("-created_at")[:5]
        ]

    def get_linked_tricks_count(self, obj):
        return obj.pending_trick_entries.count()


class CompetitionZoneSectionSerializer(serializers.ModelSerializer):
    page_slug = serializers.CharField(source="page.slug", read_only=True)
    page_title = serializers.CharField(source="page.title", read_only=True)

    class Meta:
        model = CompetitionZoneSection
        fields = [
            "id",
            "title",
            "key",
            "target_type",
            "builtin_view",
            "page",
            "page_slug",
            "page_title",
            "display_order",
            "is_visible",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at", "page_slug", "page_title"]
        extra_kwargs = {
            "builtin_view": {"required": False, "allow_blank": True},
            "page": {"required": False, "allow_null": True},
            "display_order": {"required": False},
        }

    def validate(self, attrs):
        instance = getattr(self, "instance", None)
        target_type = attrs.get(
            "target_type",
            getattr(instance, "target_type", CompetitionZoneSection.TargetType.BUILTIN),
        )
        builtin_view = attrs.get("builtin_view", getattr(instance, "builtin_view", ""))
        page = attrs.get("page", getattr(instance, "page", None))

        if target_type == CompetitionZoneSection.TargetType.BUILTIN:
            if builtin_view not in dict(CompetitionZoneSection.BuiltinView.choices):
                raise serializers.ValidationError(
                    {"builtin_view": "A valid built-in target is required."}
                )
            attrs["page"] = None
        else:
            attrs["builtin_view"] = ""
            if page is None:
                raise serializers.ValidationError(
                    {"page": "A page target is required."}
                )
            if not page.is_enabled:
                raise serializers.ValidationError(
                    {"page": "Selected page is disabled."}
                )
        return attrs


class DocumentPageSectionSerializer(serializers.ModelSerializer):
    page_slug = serializers.CharField(source="page.slug", read_only=True)
    page_title = serializers.CharField(source="page.title", read_only=True)

    class Meta:
        model = DocumentPageSection
        fields = [
            "id",
            "title",
            "key",
            "page",
            "page_slug",
            "page_title",
            "display_order",
            "is_visible",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at", "page_slug", "page_title"]
        extra_kwargs = {
            "page": {"required": False, "allow_null": True},
            "display_order": {"required": False},
        }

    def validate(self, attrs):
        instance = getattr(self, "instance", None)
        page = attrs.get("page", getattr(instance, "page", None))
        if page is None:
            raise serializers.ValidationError({"page": "A page target is required."})
        if not page.is_enabled:
            raise serializers.ValidationError({"page": "Selected page is disabled."})
        return attrs


class HeaderNavigationItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = HeaderNavigationItem
        fields = [
            "id",
            "key",
            "title",
            "display_order",
            "is_visible",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["key", "created_at", "updated_at"]
        extra_kwargs = {
            "display_order": {"required": False},
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
    reviewer = UserPublicSerializer(read_only=True)
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
            "reviewer",
            "review_note",
            "reviewed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "author",
            "is_accepted",
            "status",
            "reviewer",
            "review_note",
            "reviewed_at",
            "created_at",
            "updated_at",
        ]


class QuestionSerializer(serializers.ModelSerializer):
    author = UserPublicSerializer(read_only=True)
    reviewer = UserPublicSerializer(read_only=True)
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
            "reviewer",
            "review_note",
            "reviewed_at",
            "answers_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "author",
            "status",
            "reviewer",
            "review_note",
            "reviewed_at",
            "answers_count",
            "created_at",
            "updated_at",
        ]


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
        extra_kwargs = {
            "description": {"required": False, "allow_blank": True},
            "content_md": {"required": False, "allow_blank": True},
        }


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
    reviewer = UserPublicSerializer(read_only=True)
    series_label = serializers.CharField(source="get_series_display", read_only=True)
    stage_label = serializers.CharField(source="get_stage_display", read_only=True)
    revision_of_title = serializers.CharField(source="revision_of.title", read_only=True)
    can_edit = serializers.SerializerMethodField()
    contributors = serializers.SerializerMethodField()

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
            "status",
            "reviewer",
            "review_note",
            "reviewed_at",
            "published_at",
            "revision_of",
            "revision_of_title",
            "created_by",
            "updated_by",
            "can_edit",
            "contributors",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "created_by",
            "updated_by",
            "can_edit",
            "status",
            "reviewer",
            "review_note",
            "reviewed_at",
            "revision_of",
            "revision_of_title",
            "created_at",
            "updated_at",
        ]

    def get_can_edit(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        return bool(
            user
            and user.is_authenticated
            and not getattr(user, "is_banned", False)
            and not getattr(obj, "revision_of_id", None)
        )

    def get_contributors(self, obj):
        contributor_map = {}
        _record_contributor(
            contributor_map,
            obj.created_by,
            obj.published_at or obj.created_at,
            is_creator=True,
        )

        event_cache = _get_contribution_event_cache(self, obj, target_type=CompetitionNotice.__name__)
        has_direct_update = False
        for event in event_cache.get(obj.id, []):
            payload = event.payload if isinstance(event.payload, dict) else {}
            if payload.get("action") != "update_competition_notice":
                continue
            has_direct_update = True
            _record_contributor(
                contributor_map,
                event.user,
                event.created_at,
                approved_revision=True,
            )

        if (
            not has_direct_update
            and obj.updated_by_id
            and obj.updated_by_id != obj.created_by_id
            and obj.updated_by_id != obj.reviewer_id
        ):
            _record_contributor(
                contributor_map,
                obj.updated_by,
                obj.updated_at or obj.created_at,
                approved_revision=True,
            )

        return _finalize_contributors(contributor_map, context=self.context)

    def validate(self, attrs):
        instance = getattr(self, "instance", None)
        series = attrs.get("series", getattr(instance, "series", None))
        year = attrs.get("year", getattr(instance, "year", None))
        stage = attrs.get(
            "stage", getattr(instance, "stage", CompetitionNotice.Stage.GENERAL)
        )

        if series in {CompetitionNotice.Series.ICPC, CompetitionNotice.Series.CCPC}:
            if year is None:
                raise serializers.ValidationError(
                    {"year": "ICPC/CCPC 公告必须填写年份。"}
                )
            if stage not in {
                CompetitionNotice.Stage.REGIONAL,
                CompetitionNotice.Stage.INVITATIONAL,
                CompetitionNotice.Stage.PROVINCIAL,
                CompetitionNotice.Stage.NETWORK,
            }:
                raise serializers.ValidationError(
                    {"stage": "ICPC/CCPC 公告必须选择“区域赛/邀请赛/省赛/网络赛”之一。"}
                )
        elif series == CompetitionNotice.Series.LANQIAO:
            if year is None:
                raise serializers.ValidationError(
                    {"year": "蓝桥杯公告必须填写年份。"}
                )
            if stage not in {
                CompetitionNotice.Stage.NATIONAL,
                CompetitionNotice.Stage.PROVINCIAL,
            }:
                raise serializers.ValidationError(
                    {"stage": "蓝桥杯公告必须选择“国赛/省赛”之一。"}
                )
        elif series == CompetitionNotice.Series.TIANTI:
            if year is None:
                raise serializers.ValidationError(
                    {"year": "天梯赛公告必须填写年份。"}
                )
            if stage not in {
                CompetitionNotice.Stage.POPULAR,
                CompetitionNotice.Stage.STANDARD,
            }:
                raise serializers.ValidationError(
                    {"stage": "天梯赛公告必须选择“普及赛/标准赛”之一。"}
                )
        else:
            if year is None:
                raise serializers.ValidationError({"year": "公告必须填写年份。"})
            attrs["stage"] = stage or CompetitionNotice.Stage.GENERAL

        return attrs


class CompetitionScheduleEntrySerializer(serializers.ModelSerializer):
    announcement_title = serializers.CharField(
        source="announcement.title", read_only=True
    )
    announcement_series = serializers.CharField(
        source="announcement.series", read_only=True
    )
    announcement_year = serializers.IntegerField(
        source="announcement.year", read_only=True
    )
    announcement_stage = serializers.CharField(
        source="announcement.stage", read_only=True
    )
    created_by = UserPublicSerializer(read_only=True)
    updated_by = UserPublicSerializer(read_only=True)
    reviewer = UserPublicSerializer(read_only=True)
    can_edit = serializers.SerializerMethodField()
    is_past = serializers.SerializerMethodField()
    contributors = serializers.SerializerMethodField()

    class Meta:
        model = CompetitionScheduleEntry
        fields = [
            "id",
            "event_date",
            "end_date",
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
            "status",
            "reviewer",
            "review_note",
            "reviewed_at",
            "can_edit",
            "is_past",
            "contributors",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            "end_date": {"allow_null": True, "required": False},
            "competition_time_range": {"allow_blank": True, "required": False},
            "qq_group": {"allow_blank": True, "required": False},
            "announcement": {"allow_null": True, "required": False},
        }
        read_only_fields = [
            "created_by",
            "updated_by",
            "announcement_title",
            "announcement_series",
            "announcement_year",
            "announcement_stage",
            "can_edit",
            "is_past",
            "status",
            "reviewer",
            "review_note",
            "reviewed_at",
            "created_at",
            "updated_at",
        ]

    def get_can_edit(self, _obj):
        request = self.context.get("request")
        return can_manage_competition(getattr(request, "user", None))

    def get_is_past(self, obj):
        effective_end_date = obj.end_date or obj.event_date
        return bool(effective_end_date and effective_end_date < timezone.localdate())

    def get_contributors(self, obj):
        contributor_map = {}
        _record_contributor(contributor_map, obj.created_by, obj.created_at, is_creator=True)

        event_cache = _get_contribution_event_cache(
            self, obj, target_type=CompetitionScheduleEntry.__name__
        )
        has_direct_update = False
        for event in event_cache.get(obj.id, []):
            payload = event.payload if isinstance(event.payload, dict) else {}
            if payload.get("action") != "update_competition_schedule":
                continue
            has_direct_update = True
            _record_contributor(
                contributor_map,
                event.user,
                event.created_at,
                approved_revision=True,
            )

        if (
            not has_direct_update
            and obj.updated_by_id
            and obj.updated_by_id != obj.created_by_id
            and obj.updated_by_id != obj.reviewer_id
        ):
            _record_contributor(
                contributor_map,
                obj.updated_by,
                obj.updated_at or obj.created_at,
                approved_revision=True,
            )

        return _finalize_contributors(contributor_map, context=self.context)

    def validate_announcement(self, value):
        if value and (
            not value.is_visible
            or value.status != CompetitionNotice.Status.APPROVED
        ):
            raise serializers.ValidationError("不能关联已隐藏的赛事公告。")
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        instance = getattr(self, "instance", None)
        start_date = attrs.get("event_date", getattr(instance, "event_date", None))
        end_date = (
            attrs.get("end_date")
            if "end_date" in attrs
            else getattr(instance, "end_date", None)
        )

        if not end_date and start_date is not None:
            if (
                not instance
                or "end_date" in attrs
                or getattr(instance, "end_date", None) is None
            ):
                end_date = start_date
                attrs["end_date"] = end_date

        if (
            start_date is not None
            and "event_date" in attrs
            and "end_date" not in attrs
            and getattr(instance, "end_date", None)
            and instance.end_date < start_date
        ):
            end_date = start_date
            attrs["end_date"] = end_date

        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError(
                {"end_date": "结束日期不能早于开始日期。"}
            )
        return attrs


class DeletedContentArchiveSerializer(serializers.ModelSerializer):
    original_author = UserPublicSerializer(read_only=True)
    deleted_by = UserPublicSerializer(read_only=True)

    class Meta:
        model = DeletedContentArchive
        fields = [
            "id",
            "target_type",
            "target_id",
            "delete_action",
            "title",
            "summary",
            "content_md",
            "snapshot",
            "original_author",
            "original_author_name",
            "deleted_by",
            "deleted_by_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class TrickContributionEventSerializer(serializers.ModelSerializer):
    actor = UserPublicSerializer(read_only=True)
    trick_title = serializers.SerializerMethodField()
    action_label = serializers.CharField(source="get_action_type_display", read_only=True)

    class Meta:
        model = TrickContributionEvent
        fields = [
            "id",
            "actor",
            "trick_entry",
            "trick_title",
            "action_type",
            "action_label",
            "delta",
            "balance_after",
            "is_rollback",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_trick_title(self, obj):
        if getattr(obj, "trick_title", ""):
            return obj.trick_title
        return getattr(getattr(obj, "trick_entry", None), "title", "") or ""


class CompetitionPracticeLinkSerializer(serializers.ModelSerializer):
    created_by = UserPublicSerializer(read_only=True)
    updated_by = UserPublicSerializer(read_only=True)
    series_label = serializers.CharField(source="get_series_display", read_only=True)
    stage_label = serializers.CharField(source="get_stage_display", read_only=True)
    practice_links_text = serializers.SerializerMethodField()
    contributors = serializers.SerializerMethodField()

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
            "contributors",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_practice_links_text(self, obj):
        return practice_links_to_text(obj.practice_links, obj.practice_links_note)

    def get_contributors(self, obj):
        contributor_map = {}
        _record_contributor(contributor_map, obj.created_by, obj.created_at, is_creator=True)

        proposal_cache = _get_practice_proposal_cache(self, obj)
        for proposal in proposal_cache.get(obj.id, []):
            if _is_practice_creation_proposal(obj, proposal):
                continue
            _record_contributor(
                contributor_map,
                proposal.proposer,
                proposal.reviewed_at or proposal.updated_at or proposal.created_at,
                approved_revision=True,
            )

        return _finalize_contributors(contributor_map, context=self.context)


class CompetitionPracticeLinkProposalSerializer(serializers.ModelSerializer):
    proposer = UserPublicSerializer(read_only=True)
    reviewer = UserPublicSerializer(read_only=True)
    target_entry_summary = serializers.CharField(
        source="target_entry.short_name", read_only=True
    )
    proposed_series_label = serializers.CharField(
        source="get_proposed_series_display", read_only=True
    )
    proposed_stage_label = serializers.CharField(
        source="get_proposed_stage_display", read_only=True
    )
    proposed_practice_links_text = serializers.CharField(
        write_only=True, required=False, allow_blank=True
    )
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
        return practice_links_to_text(
            obj.proposed_practice_links, obj.proposed_practice_links_note
        )

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
        target_entry = attrs.get(
            "target_entry", getattr(instance, "target_entry", None)
        )
        if (
            instance
            and "target_entry" in attrs
            and target_entry
            and instance.target_entry_id
            and target_entry.id != instance.target_entry_id
        ):
            raise serializers.ValidationError(
                {
                    "target_entry": "Cannot change the target entry of an existing proposal."
                }
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

        event_date = attrs.get(
            "proposed_event_date", getattr(instance, "proposed_event_date", None)
        )
        event_date_text = attrs.get(
            "proposed_event_date_text",
            getattr(instance, "proposed_event_date_text", ""),
        )
        if event_date and not event_date_text:
            attrs["proposed_event_date_text"] = event_date.isoformat()

        return attrs


class CompetitionCalendarEventSerializer(serializers.ModelSerializer):
    source_site_label = serializers.CharField(
        source="get_source_site_display", read_only=True
    )
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


class AIModerationConfigSerializer(serializers.ModelSerializer):
    provider_label = serializers.CharField(source="get_provider_display", read_only=True)
    suspicious_action_label = serializers.CharField(
        source="get_suspicious_action_display", read_only=True
    )
    failure_action_label = serializers.CharField(
        source="get_failure_action_display", read_only=True
    )
    has_api_key = serializers.SerializerMethodField()
    api_key_masked = serializers.SerializerMethodField()
    api_key_input = serializers.CharField(
        write_only=True, required=False, allow_blank=True, trim_whitespace=True
    )
    created_by = UserPublicSerializer(read_only=True)
    updated_by = UserPublicSerializer(read_only=True)

    class Meta:
        model = AIModerationConfig
        fields = [
            "id",
            "label",
            "provider",
            "provider_label",
            "base_url",
            "model_name",
            "has_api_key",
            "api_key_masked",
            "api_key_input",
            "is_enabled",
            "comment_enabled",
            "question_enabled",
            "answer_enabled",
            "ticket_enabled",
            "moment_enabled",
            "moment_comment_enabled",
            "auto_approve_safe",
            "auto_reject_unsafe",
            "suspicious_action",
            "suspicious_action_label",
            "failure_action",
            "failure_action_label",
            "temperature",
            "max_output_tokens",
            "request_timeout_seconds",
            "daily_request_limit",
            "daily_token_limit",
            "max_input_chars",
            "new_user_strict_days",
            "new_user_strict_max_items",
            "whitelist_keywords",
            "blacklist_keywords",
            "blocked_domains",
            "supplemental_rules",
            "reject_notice_template",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "provider_label",
            "suspicious_action_label",
            "failure_action_label",
            "has_api_key",
            "api_key_masked",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]

    SUPERADMIN_ONLY_FIELDS = {
        "provider",
        "base_url",
        "model_name",
        "api_key_input",
        "is_enabled",
        "temperature",
        "max_output_tokens",
        "request_timeout_seconds",
        "daily_request_limit",
        "daily_token_limit",
        "failure_action",
    }

    def get_has_api_key(self, obj):
        return obj.has_api_key

    def get_api_key_masked(self, obj):
        return obj.api_key_masked

    def _is_superadmin(self):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated and user.role == User.Role.SUPERADMIN)

    def _normalize_list(self, value):
        normalized = []
        for item in value or []:
            text = str(item or "").strip()
            if text and text not in normalized:
                normalized.append(text[:120])
        return normalized[:200]

    def validate_label(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Config label is required.")
        return value[:80]

    def validate_base_url(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Base URL is required.")
        return value.rstrip("/")

    def validate_model_name(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Model name is required.")
        return value[:120]

    def validate_temperature(self, value):
        if value < 0 or value > 2:
            raise serializers.ValidationError("Temperature must be between 0 and 2.")
        return value

    def validate_max_output_tokens(self, value):
        if value < 128 or value > 4096:
            raise serializers.ValidationError("max_output_tokens must be between 128 and 4096.")
        return value

    def validate_request_timeout_seconds(self, value):
        if value < 5 or value > 120:
            raise serializers.ValidationError("request_timeout_seconds must be between 5 and 120.")
        return value

    def validate_max_input_chars(self, value):
        if value < 500 or value > 20000:
            raise serializers.ValidationError("max_input_chars must be between 500 and 20000.")
        return value

    def validate_whitelist_keywords(self, value):
        return self._normalize_list(value)

    def validate_blacklist_keywords(self, value):
        return self._normalize_list(value)

    def validate_blocked_domains(self, value):
        normalized = []
        for item in value or []:
            text = str(item or "").strip().lower().lstrip(".")
            if text and text not in normalized:
                normalized.append(text[:120])
        return normalized[:200]

    def validate_supplemental_rules(self, value):
        return (value or "").strip()[:5000]

    def validate_reject_notice_template(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Reject notice template is required.")
        return value[:300]

    def validate(self, attrs):
        if not self._is_superadmin():
            for field_name in self.SUPERADMIN_ONLY_FIELDS:
                attrs.pop(field_name, None)
        return attrs

    def create(self, validated_data):
        api_key_input = validated_data.pop("api_key_input", "")
        instance = super().create(validated_data)
        if api_key_input and self._is_superadmin():
            instance.set_api_key(api_key_input)
            instance.save(update_fields=["api_key_encrypted", "updated_at"])
        return instance

    def update(self, instance, validated_data):
        api_key_input = validated_data.pop("api_key_input", None)
        instance = super().update(instance, validated_data)
        if api_key_input is not None and str(api_key_input).strip() and self._is_superadmin():
            instance.set_api_key(api_key_input)
            instance.save(update_fields=["api_key_encrypted", "updated_at"])
        return instance


class AIModerationRecordSerializer(serializers.ModelSerializer):
    author = UserPublicSerializer(read_only=True)
    target_type_label = serializers.CharField(source="get_target_type_display", read_only=True)
    decision_label = serializers.CharField(source="get_decision_display", read_only=True)
    risk_level_label = serializers.CharField(source="get_risk_level_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    config_label = serializers.CharField(source="config.label", read_only=True)

    class Meta:
        model = AIModerationRecord
        fields = [
            "id",
            "config",
            "config_label",
            "target_type",
            "target_type_label",
            "target_id",
            "author",
            "provider",
            "model_name",
            "decision",
            "decision_label",
            "risk_level",
            "risk_level_label",
            "categories",
            "summary",
            "user_notice",
            "prompt_chars",
            "response_chars",
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "response_ms",
            "status",
            "status_label",
            "error_message",
            "created_at",
        ]
        read_only_fields = fields


class RealNameVerificationSerializer(serializers.ModelSerializer):
    user = UserPublicSerializer(read_only=True)
    reviewer = UserPublicSerializer(read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = RealNameVerification
        fields = [
            "id",
            "user",
            "status",
            "status_label",
            "real_name_masked",
            "id_number_last4",
            "provider",
            "provider_trace_id",
            "provider_order_no",
            "provider_certify_id",
            "provider_scene_id",
            "provider_sub_code",
            "provider_status_message",
            "provider_device_risk",
            "provider_started_at",
            "provider_checked_at",
            "provider_expires_at",
            "submitted_at",
            "verified_at",
            "revoked_at",
            "reviewer",
            "review_note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class RealNameStartSerializer(serializers.Serializer):
    real_name = serializers.CharField(max_length=40, trim_whitespace=True)
    id_number = serializers.CharField(max_length=40, trim_whitespace=True)
    meta_info = serializers.JSONField()
    certify_url_type = serializers.ChoiceField(
        choices=("H5", "WEB"), required=False, default="H5"
    )

    def validate_real_name(self, value):
        value = str(value or "").strip()
        if len(value) < 2:
            raise serializers.ValidationError("真实姓名至少需要 2 个字符。")
        return value

    def validate_id_number(self, value):
        compact = str(value or "").replace(" ", "").upper()
        if not re.fullmatch(r"[0-9A-Z]{6,40}", compact):
            raise serializers.ValidationError("证件号码格式不完整。")
        return compact

    def validate_meta_info(self, value):
        if isinstance(value, dict) and value:
            return value
        if isinstance(value, str) and value.strip():
            return value.strip()
        raise serializers.ValidationError("缺少浏览器实名环境信息，请刷新页面后重试。")


class RealNameCheckSerializer(serializers.Serializer):
    certify_id = serializers.CharField(
        max_length=120, required=False, allow_blank=True, trim_whitespace=True
    )


class PhoneVerificationSerializer(serializers.ModelSerializer):
    user = UserPublicSerializer(read_only=True)
    reviewer = UserPublicSerializer(read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = PhoneVerification
        fields = [
            "id",
            "user",
            "status",
            "status_label",
            "phone_country_code",
            "phone_masked",
            "phone_last4",
            "provider",
            "provider_out_id",
            "provider_biz_id",
            "provider_request_id",
            "provider_status_message",
            "provider_started_at",
            "provider_checked_at",
            "provider_expires_at",
            "submitted_at",
            "verified_at",
            "revoked_at",
            "reviewer",
            "review_note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class PhoneVerificationStartSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=24, trim_whitespace=True)
    country_code = serializers.CharField(
        max_length=8, required=False, allow_blank=True, default="86", trim_whitespace=True
    )

    def validate(self, attrs):
        country_code, phone_number = normalize_phone_context(
            country_code=attrs.get("country_code") or "86",
            phone_number=attrs.get("phone_number") or "",
        )
        attrs["country_code"] = country_code
        attrs["phone_number"] = phone_number
        return attrs


class PhoneVerificationCheckSerializer(serializers.Serializer):
    ticket_token = serializers.CharField(trim_whitespace=True)
    phone_number = serializers.CharField(max_length=24, trim_whitespace=True)
    verify_code = serializers.CharField(max_length=12, trim_whitespace=True)

    def validate_phone_number(self, value):
        _, phone_number = normalize_phone_context(country_code="86", phone_number=value)
        return phone_number

    def validate_verify_code(self, value):
        code = str(value or "").strip()
        if not re.fullmatch(r"\d{4,8}", code):
            raise serializers.ValidationError("验证码格式不正确。")
        return code


class MomentSettingsSerializer(serializers.ModelSerializer):
    updated_by = UserPublicSerializer(read_only=True)

    class Meta:
        model = MomentSettings
        fields = [
            "id",
            "is_enabled",
            "publishing_enabled",
            "commenting_enabled",
            "reactions_enabled",
            "favorites_enabled",
            "hot_list_enabled",
            "featured_feed_enabled",
            "require_real_name",
            "require_manual_review_for_new_users",
            "new_user_manual_review_count",
            "daily_post_limit",
            "daily_comment_limit",
            "max_images_per_post",
            "max_image_size_mb",
            "max_text_length",
            "max_comment_length",
            "auto_hide_report_threshold",
            "hot_window_days",
            "hot_limit",
            "hot_like_weight",
            "hot_favorite_weight",
            "hot_comment_weight",
            "hot_report_penalty",
            "rules_summary",
            "updated_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["updated_by", "created_at", "updated_at"]

    def validate_new_user_manual_review_count(self, value):
        if value > 50:
            raise serializers.ValidationError("新用户人工复核条数不能超过 50。")
        return value

    def validate_daily_post_limit(self, value):
        if value < 1 or value > 200:
            raise serializers.ValidationError("每日发帖上限需要在 1 到 200 之间。")
        return value

    def validate_daily_comment_limit(self, value):
        if value < 1 or value > 500:
            raise serializers.ValidationError("每日评论上限需要在 1 到 500 之间。")
        return value

    def validate_max_images_per_post(self, value):
        if value < 0 or value > 9:
            raise serializers.ValidationError("每条动态最多 9 张图片。")
        return value

    def validate_max_image_size_mb(self, value):
        if value < 1 or value > 20:
            raise serializers.ValidationError("单图大小限制需要在 1 到 20MB 之间。")
        return value

    def validate_hot_limit(self, value):
        if value < 1 or value > 10:
            raise serializers.ValidationError("热门列表数量需要在 1 到 10 之间。")
        return value


class MomentImageSerializer(serializers.ModelSerializer):
    url = serializers.CharField(read_only=True)
    thumbnail_url = serializers.CharField(read_only=True)
    uploaded_by = UserPublicSerializer(read_only=True)
    moment_content = serializers.SerializerMethodField()
    moment_status = serializers.CharField(source="moment.status", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = MomentImage
        fields = [
            "id",
            "moment",
            "moment_content",
            "moment_status",
            "url",
            "thumbnail_url",
            "original_name",
            "content_type",
            "size_bytes",
            "width",
            "height",
            "thumbnail_size_bytes",
            "thumbnail_width",
            "thumbnail_height",
            "display_order",
            "status",
            "status_label",
            "uploaded_by",
            "moderation_summary",
            "moderation_provider",
            "moderation_decision",
            "moderation_risk_level",
            "moderation_categories",
            "moderation_error",
            "last_moderated_at",
            "recheck_count",
            "deleted_at",
            "delete_after",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_moment_content(self, obj):
        text = str(getattr(getattr(obj, "moment", None), "content", "") or "")
        return text[:120]


class MomentSerializer(serializers.ModelSerializer):
    author = UserPublicSerializer(read_only=True)
    reviewed_by = UserPublicSerializer(read_only=True)
    images = serializers.SerializerMethodField()
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    liked = serializers.SerializerMethodField()
    favorited = serializers.SerializerMethodField()
    can_manage = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()

    class Meta:
        model = Moment
        fields = [
            "id",
            "author",
            "content",
            "status",
            "status_label",
            "published_at",
            "reviewed_by",
            "reviewed_at",
            "review_note",
            "allow_hot",
            "is_featured",
            "comments_locked",
            "hidden_reason",
            "like_count",
            "favorite_count",
            "comment_count",
            "report_count",
            "hot_score",
            "last_ai_summary",
            "last_ai_risk_level",
            "liked",
            "favorited",
            "can_manage",
            "can_edit",
            "images",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "author",
            "status",
            "status_label",
            "published_at",
            "reviewed_by",
            "reviewed_at",
            "review_note",
            "hidden_reason",
            "like_count",
            "favorite_count",
            "comment_count",
            "report_count",
            "hot_score",
            "last_ai_summary",
            "last_ai_risk_level",
            "liked",
            "favorited",
            "can_manage",
            "can_edit",
            "images",
            "created_at",
            "updated_at",
        ]

    def _request_user(self):
        request = self.context.get("request")
        return getattr(request, "user", None)

    def _is_manager(self, user):
        return bool(
            user
            and user.is_authenticated
            and user.role in {User.Role.ADMIN, User.Role.SUPERADMIN}
        )

    def get_liked(self, obj):
        user = self._request_user()
        if not user or not user.is_authenticated:
            return False
        return MomentLike.objects.filter(moment=obj, user=user).exists()

    def get_favorited(self, obj):
        user = self._request_user()
        if not user or not user.is_authenticated:
            return False
        return MomentFavorite.objects.filter(moment=obj, user=user).exists()

    def get_can_manage(self, obj):
        return self._is_manager(self._request_user())

    def get_can_edit(self, obj):
        user = self._request_user()
        return bool(user and user.is_authenticated and (obj.author_id == user.id or self._is_manager(user)))

    def get_images(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        can_view_all = bool(
            user
            and user.is_authenticated
            and (obj.author_id == user.id or self._is_manager(user))
        )
        images = obj.images.all()
        if not can_view_all:
            images = [image for image in images if image.status == MomentImage.Status.APPROVED]
        return MomentImageSerializer(images, many=True, context=self.context).data

    def validate_content(self, value):
        value = str(value or "").strip()
        settings_obj = MomentSettings.get_solo()
        if not value:
            raise serializers.ValidationError("动态内容不能为空。")
        if len(value) > int(settings_obj.max_text_length or 2000):
            raise serializers.ValidationError("动态内容超过长度限制。")
        return value


class MomentCommentSerializer(serializers.ModelSerializer):
    author = UserPublicSerializer(read_only=True)
    reviewed_by = UserPublicSerializer(read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    can_manage = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()
    moment_status = serializers.CharField(source="moment.status", read_only=True)
    moment_summary = serializers.SerializerMethodField()

    class Meta:
        model = MomentComment
        fields = [
            "id",
            "moment",
            "moment_status",
            "moment_summary",
            "author",
            "content",
            "status",
            "status_label",
            "reviewed_by",
            "reviewed_at",
            "review_note",
            "report_count",
            "last_ai_summary",
            "last_ai_risk_level",
            "can_manage",
            "can_delete",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "moment",
            "moment_status",
            "moment_summary",
            "author",
            "status",
            "status_label",
            "reviewed_by",
            "reviewed_at",
            "review_note",
            "report_count",
            "last_ai_summary",
            "last_ai_risk_level",
            "can_manage",
            "can_delete",
            "created_at",
            "updated_at",
        ]

    def get_can_manage(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        return bool(
            user
            and user.is_authenticated
            and user.role in {User.Role.ADMIN, User.Role.SUPERADMIN}
        )

    def get_can_delete(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated and (obj.author_id == user.id or self.get_can_manage(obj)))

    def get_moment_summary(self, obj):
        content = str(getattr(getattr(obj, "moment", None), "content", "") or "").strip()
        return content[:120]

    def validate_content(self, value):
        value = str(value or "").strip()
        settings_obj = MomentSettings.get_solo()
        if not value:
            raise serializers.ValidationError("评论内容不能为空。")
        if len(value) > int(settings_obj.max_comment_length or 500):
            raise serializers.ValidationError("评论内容超过长度限制。")
        return value


class MomentReportSerializer(serializers.ModelSerializer):
    reporter = UserPublicSerializer(read_only=True)
    target_author = UserPublicSerializer(read_only=True)
    handled_by = UserPublicSerializer(read_only=True)
    reason_label = serializers.CharField(source="get_reason_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    target_summary = serializers.SerializerMethodField()

    class Meta:
        model = MomentReport
        fields = [
            "id",
            "target_type",
            "moment",
            "comment",
            "target_summary",
            "reporter",
            "target_author",
            "reason",
            "reason_label",
            "description",
            "status",
            "status_label",
            "handled_by",
            "handled_at",
            "resolution_action",
            "resolution_note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "target_summary",
            "reporter",
            "target_author",
            "status",
            "status_label",
            "handled_by",
            "handled_at",
            "resolution_action",
            "resolution_note",
            "created_at",
            "updated_at",
        ]

    def validate_description(self, value):
        return str(value or "").strip()[:500]

    def get_target_summary(self, obj):
        if obj.comment_id and getattr(obj, "comment", None):
            return str(obj.comment.content or "").strip()[:120]
        if obj.moment_id and getattr(obj, "moment", None):
            return str(obj.moment.content or "").strip()[:120]
        return ""


class MomentUserRestrictionSerializer(serializers.ModelSerializer):
    user = UserPublicSerializer(read_only=True)
    updated_by = UserPublicSerializer(read_only=True)
    is_muted = serializers.BooleanField(read_only=True)

    class Meta:
        model = MomentUserRestriction
        fields = [
            "id",
            "user",
            "can_post",
            "can_comment",
            "can_react",
            "can_upload_images",
            "can_enter_hot",
            "muted_until",
            "is_muted",
            "reason",
            "updated_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["user", "updated_by", "created_at", "updated_at", "is_muted"]


class MomentAuditLogSerializer(serializers.ModelSerializer):
    actor = UserPublicSerializer(read_only=True)
    target_user = UserPublicSerializer(read_only=True)
    event_type_label = serializers.CharField(source="get_event_type_display", read_only=True)

    class Meta:
        model = MomentAuditLog
        fields = [
            "id",
            "actor",
            "target_user",
            "event_type",
            "event_type_label",
            "target_type",
            "target_id",
            "payload",
            "created_at",
        ]
        read_only_fields = fields


class AssistantProviderConfigSerializer(serializers.ModelSerializer):
    provider_label = serializers.CharField(
        source="get_provider_display", read_only=True
    )
    has_api_key = serializers.SerializerMethodField()
    api_key_masked = serializers.SerializerMethodField()
    api_key_input = serializers.CharField(
        write_only=True, required=False, allow_blank=True, trim_whitespace=True
    )
    created_by = UserPublicSerializer(read_only=True)
    updated_by = UserPublicSerializer(read_only=True)

    class Meta:
        model = AssistantProviderConfig
        fields = [
            "id",
            "label",
            "assistant_name",
            "provider",
            "provider_label",
            "base_url",
            "model_name",
            "has_api_key",
            "api_key_masked",
            "api_key_input",
            "is_enabled",
            "is_default",
            "show_launcher",
            "temperature",
            "max_output_tokens",
            "request_timeout_seconds",
            "welcome_message",
            "teaser_message",
            "suggested_questions",
            "system_prompt",
            "daily_request_limit",
            "daily_token_limit",
            "last_tested_at",
            "last_test_success",
            "last_test_message",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "provider_label",
            "has_api_key",
            "api_key_masked",
            "last_tested_at",
            "last_test_success",
            "last_test_message",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]

    def get_has_api_key(self, obj):
        return obj.has_api_key

    def get_api_key_masked(self, obj):
        return obj.api_key_masked

    def validate_label(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Config label is required.")
        return value[:80]

    def validate_assistant_name(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Assistant name is required.")
        return value[:80]

    def validate_base_url(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Base URL is required.")
        return value.rstrip("/")

    def validate_model_name(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Model name is required.")
        return value[:120]

    def validate_temperature(self, value):
        if value < 0 or value > 2:
            raise serializers.ValidationError("Temperature must be between 0 and 2.")
        return value

    def validate_suggested_questions(self, value):
        normalized = []
        for item in value or []:
            text = str(item or "").strip()
            if text and text not in normalized:
                normalized.append(text[:80])
        return normalized[:6]

    def validate_welcome_message(self, value):
        return (value or "").strip()

    def validate_teaser_message(self, value):
        return (value or "").strip()[:200]

    def validate_system_prompt(self, value):
        return (value or "").strip()

    def create(self, validated_data):
        api_key_input = validated_data.pop("api_key_input", "")
        instance = super().create(validated_data)
        if api_key_input:
            instance.set_api_key(api_key_input)
            instance.save(update_fields=["api_key_encrypted", "updated_at"])
        return instance

    def update(self, instance, validated_data):
        api_key_input = validated_data.pop("api_key_input", None)
        instance = super().update(instance, validated_data)
        if api_key_input is not None and str(api_key_input).strip():
            instance.set_api_key(api_key_input)
            instance.save(update_fields=["api_key_encrypted", "updated_at"])
        return instance


class AssistantInteractionLogSerializer(serializers.ModelSerializer):
    user = UserPublicSerializer(read_only=True)
    config_label = serializers.CharField(source="config.label", read_only=True)

    class Meta:
        model = AssistantInteractionLog
        fields = [
            "id",
            "config",
            "config_label",
            "user",
            "session_id",
            "provider",
            "model_name",
            "prompt_chars",
            "response_chars",
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "source_count",
            "response_ms",
            "success",
            "error_message",
            "created_at",
        ]
        read_only_fields = fields


class AssistantPublicConfigSerializer(serializers.Serializer):
    enabled = serializers.BooleanField()
    assistant_name = serializers.CharField()
    welcome_message = serializers.CharField()
    teaser_message = serializers.CharField()
    suggested_questions = serializers.ListField(
        child=serializers.CharField(), allow_empty=True
    )


class AssistantChatHistoryItemSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=["user", "assistant"])
    content = serializers.CharField(allow_blank=False, max_length=1500)


class AssistantChatRequestSerializer(serializers.Serializer):
    message = serializers.CharField(allow_blank=False, max_length=1500)
    session_id = serializers.CharField(required=False, allow_blank=True, max_length=64)
    history = AssistantChatHistoryItemSerializer(many=True, required=False)
    current_path = serializers.CharField(
        required=False, allow_blank=True, max_length=255
    )
    current_title = serializers.CharField(
        required=False, allow_blank=True, max_length=120
    )

    def validate_message(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Message cannot be empty.")
        return value

    def validate_current_path(self, value):
        return (value or "").strip()[:255]

    def validate_current_title(self, value):
        return (value or "").strip()[:120]


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
