import uuid
from datetime import timedelta
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


def gallery_image_upload_to(instance, filename: str) -> str:
    suffix = Path(filename or "").suffix.lower() or ".png"
    folder_slug = getattr(getattr(instance, "folder", None), "slug", "") or "uncategorized"
    now = timezone.now()
    return f"gallery/{folder_slug}/{now:%Y}/{now:%m}/{uuid.uuid4().hex}{suffix}"


def moment_image_upload_to(instance, filename: str) -> str:
    suffix = Path(filename or "").suffix.lower() or ".png"
    now = timezone.now()
    user_id = getattr(getattr(instance, "uploaded_by", None), "id", None) or "anonymous"
    return f"moments/{user_id}/{now:%Y}/{now:%m}/{uuid.uuid4().hex}{suffix}"


def moment_image_thumbnail_upload_to(instance, filename: str) -> str:
    now = timezone.now()
    user_id = getattr(getattr(instance, "uploaded_by", None), "id", None) or "anonymous"
    return f"moments-thumbs/{user_id}/{now:%Y}/{now:%m}/{uuid.uuid4().hex}.webp"


class User(AbstractUser):
    class Role(models.TextChoices):
        NORMAL = "normal", "Normal User"
        SCHOOL = "school", "School User"
        ADMIN = "admin", "Admin User"
        SUPERADMIN = "superadmin", "Super Admin"

    class Gender(models.TextChoices):
        MALE = "male", "Male"
        FEMALE = "female", "Female"
        PRIVATE = "private", "Private"

    role = models.CharField(
        max_length=20, choices=Role.choices, default=Role.NORMAL, db_index=True
    )
    school_name = models.CharField(max_length=120, blank=True)
    bio = models.TextField(blank=True)
    avatar_url = models.URLField(blank=True)
    gender = models.CharField(
        max_length=20, choices=Gender.choices, default=Gender.PRIVATE, db_index=True
    )
    is_banned = models.BooleanField(default=False)
    banned_reason = models.CharField(max_length=255, blank=True)
    banned_at = models.DateTimeField(null=True, blank=True)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    trick_contribution_score = models.IntegerField(default=0, db_index=True)

    def ban(self, reason: str = "") -> None:
        self.is_banned = True
        self.banned_reason = reason[:255]
        self.banned_at = timezone.now()
        self.save(update_fields=["is_banned", "banned_reason", "banned_at"])

    def unban(self) -> None:
        self.is_banned = False
        self.banned_reason = ""
        self.banned_at = None
        self.save(update_fields=["is_banned", "banned_reason", "banned_at"])

    @property
    def is_school_user(self) -> bool:
        return self.role == self.Role.SCHOOL

    @property
    def is_admin_user(self) -> bool:
        return self.role == self.Role.ADMIN

    @property
    def is_super_admin(self) -> bool:
        return self.role == self.Role.SUPERADMIN

    @property
    def is_manager(self) -> bool:
        return self.role in {self.Role.ADMIN, self.Role.SUPERADMIN}

    def can_assign_admin(self) -> bool:
        return self.role == self.Role.SUPERADMIN


class Category(TimeStampedModel):
    class ModerationScope(models.TextChoices):
        PUBLIC = "public", "Public"
        SCHOOL = "school", "School Column"

    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True, blank=True, null=True)
    description = models.TextField(blank=True)
    parent = models.ForeignKey(
        "self",
        related_name="children",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    order = models.PositiveIntegerField(default=0)
    moderation_scope = models.CharField(
        max_length=20,
        choices=ModerationScope.choices,
        default=ModerationScope.PUBLIC,
    )
    is_visible = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name) or "category"
            candidate = base
            while Category.objects.exclude(pk=self.pk).filter(slug=candidate).exists():
                candidate = f"{base}-{uuid.uuid4().hex[:6]}"
            self.slug = candidate
        super().save(*args, **kwargs)


class Article(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        HIDDEN = "hidden", "Hidden"

    title = models.CharField(max_length=220)
    slug = models.SlugField(max_length=240, unique=True, blank=True, null=True)
    summary = models.TextField(blank=True, default="")
    content_md = models.TextField(default="")
    category = models.ForeignKey(
        Category, related_name="articles", on_delete=models.PROTECT
    )
    display_order = models.PositiveIntegerField(default=0, db_index=True)
    author = models.ForeignKey(
        "User", related_name="articles", on_delete=models.PROTECT
    )
    last_editor = models.ForeignKey(
        "User",
        related_name="edited_articles",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PUBLISHED
    )
    is_featured = models.BooleanField(default=False)
    is_locked = models.BooleanField(default=False)
    allow_comments = models.BooleanField(default=True)
    view_count = models.PositiveIntegerField(default=0)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-is_featured", "-updated_at"]

    def __str__(self) -> str:
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)[:120] or "article"
            candidate = base
            while Article.objects.exclude(pk=self.pk).filter(slug=candidate).exists():
                candidate = f"{base}-{uuid.uuid4().hex[:6]}"
            self.slug = candidate
        if self.status == self.Status.PUBLISHED and not self.published_at:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)


class ArticleStar(models.Model):
    user = models.ForeignKey(
        "User", related_name="starred_articles", on_delete=models.CASCADE
    )
    article = models.ForeignKey(
        Article, related_name="stargazers", on_delete=models.CASCADE
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "article")
        ordering = ["-created_at"]


class ArticleComment(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        VISIBLE = "visible", "Visible"
        HIDDEN = "hidden", "Hidden"

    article = models.ForeignKey(
        Article, related_name="comments", on_delete=models.CASCADE
    )
    author = models.ForeignKey(
        "User", related_name="article_comments", on_delete=models.CASCADE
    )
    parent = models.ForeignKey(
        "self",
        related_name="replies",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    content = models.TextField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    reviewer = models.ForeignKey(
        "User",
        related_name="reviewed_article_comments",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    review_note = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]


class RevisionProposal(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    article = models.ForeignKey(Article, related_name="revision_proposals", on_delete=models.CASCADE)
    proposer = models.ForeignKey("User", related_name="revision_proposals", on_delete=models.CASCADE)
    base_title = models.CharField(max_length=220, blank=True, default="")
    base_summary = models.TextField(blank=True, default="")
    base_content_md = models.TextField(blank=True, default="")
    base_updated_at = models.DateTimeField(null=True, blank=True)
    proposed_title = models.CharField(max_length=220, blank=True)
    proposed_summary = models.TextField(blank=True)
    proposed_content_md = models.TextField()
    reason = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    reviewer = models.ForeignKey(
        "User",
        related_name="reviewed_revisions",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    review_note = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class IssueTicket(TimeStampedModel):
    class Kind(models.TextChoices):
        ISSUE = "issue", "Issue"
        REQUEST = "request", "Request"

    class Visibility(models.TextChoices):
        PRIVATE = "private", "Private"
        PUBLIC = "public", "Public"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending Review"
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In Progress"
        RESOLVED = "resolved", "Resolved"
        REJECTED = "rejected", "Rejected"

    kind = models.CharField(max_length=20, choices=Kind.choices)
    title = models.CharField(max_length=220)
    content = models.TextField()
    author = models.ForeignKey(
        "User", related_name="issue_tickets", on_delete=models.CASCADE
    )
    related_article = models.ForeignKey(
        Article,
        related_name="issue_tickets",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    visibility = models.CharField(
        max_length=20,
        choices=Visibility.choices,
        default=Visibility.PUBLIC,
        db_index=True,
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    assignee = models.ForeignKey(
        "User",
        related_name="assigned_issue_tickets",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    resolution_note = models.TextField(blank=True)
    reviewer = models.ForeignKey(
        "User",
        related_name="reviewed_issue_tickets",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    review_note = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-updated_at"]


class TrickEntry(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    class DeleteVoteReviewStatus(models.TextChoices):
        NONE = "none", "None"
        PENDING = "pending", "Pending"
        KEPT = "kept", "Kept"
        DELETED = "deleted", "Deleted"

    title = models.CharField(max_length=220)
    content_md = models.TextField()
    keywords_text = models.CharField(max_length=255, blank=True, default="")
    author = models.ForeignKey(
        "User", related_name="trick_entries", on_delete=models.CASCADE
    )
    terms = models.ManyToManyField(
        "TrickTerm", related_name="trick_entries", blank=True
    )
    pending_term_suggestions = models.ManyToManyField(
        "TrickTermSuggestion",
        related_name="pending_trick_entries",
        blank=True,
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    reviewer = models.ForeignKey(
        "User",
        related_name="reviewed_trick_entries",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    review_note = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    delete_vote_review_status = models.CharField(
        max_length=20,
        choices=DeleteVoteReviewStatus.choices,
        default=DeleteVoteReviewStatus.NONE,
        db_index=True,
    )
    delete_vote_review_requested_at = models.DateTimeField(null=True, blank=True)
    delete_vote_reviewer = models.ForeignKey(
        "User",
        related_name="reviewed_trick_delete_votes",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    delete_vote_review_note = models.TextField(blank=True)
    delete_vote_reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-updated_at"]


class TrickEntryLike(models.Model):
    user = models.ForeignKey(
        "User", related_name="trick_entry_likes", on_delete=models.CASCADE
    )
    trick_entry = models.ForeignKey(
        TrickEntry, related_name="like_records", on_delete=models.CASCADE
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "trick_entry")
        ordering = ["-created_at"]


class TrickEntryDownvote(models.Model):
    user = models.ForeignKey(
        "User", related_name="trick_entry_downvotes", on_delete=models.CASCADE
    )
    trick_entry = models.ForeignKey(
        TrickEntry, related_name="downvote_records", on_delete=models.CASCADE
    )
    rewarded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "trick_entry")
        ordering = ["-created_at"]


class TrickContributionEvent(TimeStampedModel):
    class ActionType(models.TextChoices):
        TRICK_APPROVED = "trick_approved", "Trick 通过审核"
        TRICK_APPROVAL_ROLLBACK = "trick_approval_rollback", "Trick 投稿收益回滚"
        TRICK_RECEIVED_LIKE = "trick_received_like", "Trick 收到点赞"
        TRICK_RECEIVED_LIKE_ROLLBACK = "trick_received_like_rollback", "Trick 点赞收益回滚"
        TRICK_CAST_DOWNVOTE = "trick_cast_downvote", "发起 Trick 点踩"
        TRICK_CAST_DOWNVOTE_ROLLBACK = "trick_cast_downvote_rollback", "Trick 点踩消耗回滚"
        TRICK_RECEIVED_DOWNVOTE = "trick_received_downvote", "Trick 收到点踩"
        TRICK_RECEIVED_DOWNVOTE_ROLLBACK = "trick_received_downvote_rollback", "Trick 收到点踩回滚"
        TRICK_DELETE_REVIEW_REWARD = "trick_delete_review_reward", "Trick 删除审核奖励"
        ADMIN_ADJUSTMENT = "admin_adjustment", "管理员调整"

    user = models.ForeignKey(
        "User", related_name="trick_contribution_events", on_delete=models.CASCADE
    )
    actor = models.ForeignKey(
        "User",
        related_name="triggered_trick_contribution_events",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    trick_entry = models.ForeignKey(
        TrickEntry,
        related_name="contribution_events",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    trick_title = models.CharField(max_length=220, blank=True)
    action_type = models.CharField(max_length=40, choices=ActionType.choices, db_index=True)
    delta = models.IntegerField()
    balance_after = models.IntegerField()
    is_rollback = models.BooleanField(default=False, db_index=True)
    event_key = models.CharField(max_length=180, unique=True, blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["action_type", "created_at"]),
        ]


class TrickTerm(TimeStampedModel):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    description = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    is_builtin = models.BooleanField(default=False)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name) or "trick-term"
            candidate = base
            while TrickTerm.objects.exclude(pk=self.pk).filter(slug=candidate).exists():
                candidate = f"{base}-{uuid.uuid4().hex[:6]}"
            self.slug = candidate
        super().save(*args, **kwargs)


class TrickTermSuggestion(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    name = models.CharField(max_length=80)
    normalized_name = models.CharField(max_length=80, db_index=True)
    proposer = models.ForeignKey(
        "User", related_name="trick_term_suggestions", on_delete=models.CASCADE
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    reviewer = models.ForeignKey(
        "User",
        related_name="reviewed_trick_term_suggestions",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    review_note = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["normalized_name", "status"],
                condition=models.Q(status="pending"),
                name="uniq_pending_trick_term_suggestion",
            )
        ]

    def __str__(self) -> str:
        return self.name


class TeamMember(TimeStampedModel):
    user = models.OneToOneField(
        "User",
        related_name="team_member",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    display_id = models.CharField(max_length=80)
    avatar_url = models.CharField(max_length=500, blank=True)
    profile_url = models.URLField(max_length=500)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self) -> str:
        return self.display_id


class GalleryImageFolder(TimeStampedModel):
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)
    description = models.CharField(max_length=255, blank=True)
    display_order = models.PositiveIntegerField(default=0, db_index=True)
    is_visible = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["display_order", "id"]

    def __str__(self) -> str:
        return self.name


class GalleryImage(TimeStampedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        RECYCLED = "recycled", "Recycled"

    folder = models.ForeignKey(
        GalleryImageFolder,
        related_name="images",
        on_delete=models.PROTECT,
    )
    image = models.FileField(upload_to=gallery_image_upload_to, max_length=500)
    original_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=120, blank=True)
    size_bytes = models.PositiveIntegerField(default=0)
    uploaded_by = models.ForeignKey(
        "User",
        related_name="gallery_images",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )
    original_path = models.CharField(max_length=500, blank=True)
    recycled_path = models.CharField(max_length=500, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    delete_after = models.DateTimeField(null=True, blank=True, db_index=True)
    deleted_by = models.ForeignKey(
        "User",
        related_name="deleted_gallery_images",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["folder", "status"]),
        ]

    def __str__(self) -> str:
        return self.original_name


class FriendlyLink(TimeStampedModel):
    name = models.CharField(max_length=120)
    description = models.TextField()
    url = models.URLField(max_length=500)
    created_by = models.ForeignKey(
        "User",
        related_name="friendly_links",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    is_enabled = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self) -> str:
        return self.name


class CompetitionNotice(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    class Series(models.TextChoices):
        ICPC = "icpc", "ICPC"
        CCPC = "ccpc", "CCPC"
        LANQIAO = "lanqiao", "Lanqiao"
        TIANTI = "tianti", "Tianti"

    class Stage(models.TextChoices):
        GENERAL = "general", "General"
        REGIONAL = "regional", "Regional"
        INVITATIONAL = "invitational", "Invitational"
        PROVINCIAL = "provincial", "Provincial"
        NETWORK = "network", "Network"
        NATIONAL = "national", "National"
        POPULAR = "popular", "Popular"
        STANDARD = "standard", "Standard"

    title = models.CharField(max_length=220)
    content_md = models.TextField()
    series = models.CharField(max_length=30, choices=Series.choices, db_index=True)
    year = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    stage = models.CharField(
        max_length=40, choices=Stage.choices, default=Stage.GENERAL, db_index=True
    )
    created_by = models.ForeignKey(
        "User",
        related_name="competition_notices",
        on_delete=models.PROTECT,
    )
    updated_by = models.ForeignKey(
        "User",
        related_name="edited_competition_notices",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    revision_of = models.ForeignKey(
        "self",
        related_name="pending_revisions",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    is_visible = models.BooleanField(default=True, db_index=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.APPROVED, db_index=True
    )
    reviewer = models.ForeignKey(
        "User",
        related_name="reviewed_competition_notices",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    review_note = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-published_at", "-updated_at"]

    def __str__(self) -> str:
        return self.title


class CompetitionScheduleEntry(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    event_date = models.DateField(db_index=True)
    end_date = models.DateField(null=True, blank=True, db_index=True)
    competition_time_range = models.CharField(max_length=60, blank=True)
    competition_type = models.CharField(max_length=120)
    location = models.CharField(max_length=200)
    qq_group = models.CharField(max_length=160, blank=True)
    announcement = models.ForeignKey(
        CompetitionNotice,
        related_name="schedule_entries",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(
        "User",
        related_name="created_competition_schedules",
        on_delete=models.PROTECT,
    )
    updated_by = models.ForeignKey(
        "User",
        related_name="updated_competition_schedules",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.APPROVED, db_index=True
    )
    reviewer = models.ForeignKey(
        "User",
        related_name="reviewed_competition_schedules",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    review_note = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["event_date", "id"]

    def __str__(self) -> str:
        if self.end_date and self.end_date != self.event_date:
            return f"{self.event_date} - {self.end_date} {self.competition_type}"
        return f"{self.event_date} {self.competition_type}"


class DeletedContentArchive(TimeStampedModel):
    class DeleteAction(models.TextChoices):
        DELETE = "delete", "Delete"
        HIDE = "hide", "Hide"

    target_type = models.CharField(max_length=80, db_index=True)
    target_id = models.PositiveBigIntegerField(null=True, blank=True, db_index=True)
    delete_action = models.CharField(
        max_length=20,
        choices=DeleteAction.choices,
        default=DeleteAction.DELETE,
        db_index=True,
    )
    title = models.CharField(max_length=220, blank=True)
    summary = models.CharField(max_length=500, blank=True)
    content_md = models.TextField(blank=True)
    snapshot = models.JSONField(default=dict, blank=True)
    original_author = models.ForeignKey(
        "User",
        related_name="deleted_content_original_archives",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    original_author_name = models.CharField(max_length=150, blank=True)
    deleted_by = models.ForeignKey(
        "User",
        related_name="deleted_content_deleted_archives",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    deleted_by_name = models.CharField(max_length=150, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["target_type", "created_at"]),
            models.Index(fields=["deleted_by", "created_at"]),
            models.Index(fields=["original_author", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.target_type} #{self.target_id or '-'} {self.title or self.summary or 'deleted content'}"


class CompetitionPracticeLink(TimeStampedModel):
    class Series(models.TextChoices):
        ICPC = "icpc", "ICPC"
        CCPC = "ccpc", "CCPC"

    class Stage(models.TextChoices):
        NETWORK = "network", "Network"
        REGIONAL = "regional", "Regional"
        INVITATIONAL = "invitational", "Invitational"
        PROVINCIAL = "provincial", "Provincial"

    source_key = models.CharField(max_length=200, unique=True, db_index=True)
    year = models.PositiveIntegerField(db_index=True)
    series = models.CharField(max_length=20, choices=Series.choices, db_index=True)
    stage = models.CharField(max_length=20, choices=Stage.choices, db_index=True)
    short_name = models.CharField(max_length=120)
    official_name = models.CharField(max_length=500)
    official_url = models.URLField(max_length=500, blank=True)
    event_date = models.DateField(null=True, blank=True, db_index=True)
    event_date_text = models.CharField(max_length=80, blank=True)
    organizer = models.CharField(max_length=255, blank=True)
    practice_links = models.JSONField(default=list, blank=True)
    practice_links_note = models.CharField(max_length=255, blank=True)
    source_file = models.CharField(max_length=120, blank=True)
    source_section = models.CharField(max_length=180, blank=True)
    display_order = models.PositiveIntegerField(default=0, db_index=True)
    created_by = models.ForeignKey(
        "User",
        related_name="created_competition_practice_links",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    updated_by = models.ForeignKey(
        "User",
        related_name="updated_competition_practice_links",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-year", "display_order", "id"]

    def __str__(self) -> str:
        return f"{self.year} {self.get_series_display()} {self.short_name}"


class CompetitionPracticeLinkProposal(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    target_entry = models.ForeignKey(
        CompetitionPracticeLink,
        related_name="proposals",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    proposer = models.ForeignKey(
        "User",
        related_name="competition_practice_link_proposals",
        on_delete=models.CASCADE,
    )
    proposed_year = models.PositiveIntegerField(db_index=True)
    proposed_series = models.CharField(
        max_length=20,
        choices=CompetitionPracticeLink.Series.choices,
        db_index=True,
    )
    proposed_stage = models.CharField(
        max_length=20,
        choices=CompetitionPracticeLink.Stage.choices,
        db_index=True,
    )
    proposed_short_name = models.CharField(max_length=120)
    proposed_official_name = models.CharField(max_length=500)
    proposed_official_url = models.URLField(max_length=500, blank=True)
    proposed_event_date = models.DateField(null=True, blank=True, db_index=True)
    proposed_event_date_text = models.CharField(max_length=80, blank=True)
    proposed_organizer = models.CharField(max_length=255, blank=True)
    proposed_practice_links = models.JSONField(default=list, blank=True)
    proposed_practice_links_note = models.CharField(max_length=255, blank=True)
    reason = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    reviewer = models.ForeignKey(
        "User",
        related_name="reviewed_competition_practice_link_proposals",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    review_note = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.proposed_year} {self.proposed_short_name} ({self.status})"


class CompetitionCalendarEvent(TimeStampedModel):
    class SourceSite(models.TextChoices):
        CODEFORCES = "codeforces", "Codeforces"
        ATCODER = "atcoder", "AtCoder"
        NOWCODER = "nowcoder", "牛客"
        LUOGU = "luogu", "洛谷"

    source_site = models.CharField(
        max_length=20, choices=SourceSite.choices, db_index=True
    )
    source_id = models.CharField(max_length=120, db_index=True)
    title = models.CharField(max_length=300)
    organizer = models.CharField(max_length=200, blank=True)
    url = models.URLField(max_length=500)
    start_time = models.DateTimeField(db_index=True)
    end_time = models.DateTimeField(db_index=True)
    duration_seconds = models.PositiveIntegerField(default=0)
    last_synced_at = models.DateTimeField(default=timezone.now, db_index=True)
    extra = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["start_time", "source_site", "source_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["source_site", "source_id"],
                name="unique_competition_calendar_event_source",
            )
        ]
        indexes = [
            models.Index(fields=["source_site", "start_time"]),
            models.Index(fields=["end_time"]),
        ]

    def __str__(self) -> str:
        return f"{self.get_source_site_display()} {self.title}"


class Question(TimeStampedModel):
    AUTO_CLOSE_AFTER = timedelta(days=7)

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"
        HIDDEN = "hidden", "Hidden"

    title = models.CharField(max_length=220)
    content_md = models.TextField()
    author = models.ForeignKey(
        "User", related_name="questions", on_delete=models.CASCADE
    )
    category = models.ForeignKey(
        Category,
        related_name="questions",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    auto_close_at = models.DateTimeField(null=True, blank=True, db_index=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.OPEN
    )
    reviewer = models.ForeignKey(
        "User",
        related_name="reviewed_questions",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    review_note = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-updated_at"]

    def schedule_auto_close(self, base_time=None):
        self.auto_close_at = (base_time or timezone.now()) + self.AUTO_CLOSE_AFTER
        return self.auto_close_at

    def clear_auto_close(self):
        self.auto_close_at = None
        return self.auto_close_at

    def is_auto_close_due(self, reference_time=None):
        if self.status != self.Status.OPEN or not self.auto_close_at:
            return False
        return self.auto_close_at <= (reference_time or timezone.now())

    def maybe_auto_close(self, reference_time=None, save=True):
        if not self.is_auto_close_due(reference_time):
            return False
        self.status = self.Status.CLOSED
        self.auto_close_at = None
        if save and self.pk:
            self.save(update_fields=["status", "auto_close_at", "updated_at"])
        return True


class Answer(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        VISIBLE = "visible", "Visible"
        HIDDEN = "hidden", "Hidden"

    question = models.ForeignKey(
        Question, related_name="answers", on_delete=models.CASCADE
    )
    author = models.ForeignKey("User", related_name="answers", on_delete=models.CASCADE)
    content_md = models.TextField()
    is_accepted = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.VISIBLE
    )
    reviewer = models.ForeignKey(
        "User",
        related_name="reviewed_answers",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    review_note = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]


class AnnouncementQuerySet(models.QuerySet):
    def active(self):
        now = timezone.now()
        return self.filter(is_published=True, start_at__lte=now).filter(
            models.Q(end_at__isnull=True) | models.Q(end_at__gte=now)
        )


class Announcement(TimeStampedModel):
    title = models.CharField(max_length=220)
    content_md = models.TextField()
    created_by = models.ForeignKey(
        "User", related_name="announcements", on_delete=models.PROTECT
    )
    priority = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=True)
    start_at = models.DateTimeField(default=timezone.now)
    end_at = models.DateTimeField(null=True, blank=True)

    objects = AnnouncementQuerySet.as_manager()

    class Meta:
        ordering = ["-priority", "-created_at"]


class AnnouncementRead(models.Model):
    user = models.ForeignKey(
        "User", related_name="read_announcements", on_delete=models.CASCADE
    )
    announcement = models.ForeignKey(
        Announcement,
        related_name="read_by_users",
        on_delete=models.CASCADE,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "announcement")
        ordering = ["-created_at"]


class LoginAttempt(models.Model):
    key = models.CharField(max_length=255, unique=True, db_index=True)
    username_ci = models.CharField(max_length=150, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True, db_index=True)
    failure_count = models.PositiveIntegerField(default=0)
    last_failed_at = models.DateTimeField(null=True, blank=True)
    locked_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]


class SecurityAuditLog(models.Model):
    class EventType(models.TextChoices):
        LOGIN_SUCCESS = "login_success", "Login Success"
        LOGIN_FAILED = "login_failed", "Login Failed"
        LOGIN_LOCKED = "login_locked", "Login Locked"
        LOGIN_DENIED = "login_denied", "Login Denied"
        REGISTER_SUCCESS = "register_success", "Register Success"
        REGISTER_CODE_SENT = "register_code_sent", "Register Code Sent"
        LOGOUT = "logout", "Logout"
        PASSWORD_CHANGE_REQUESTED = (
            "password_change_requested",
            "Password Change Requested",
        )
        PASSWORD_CHANGED = "password_changed", "Password Changed"
        PASSWORD_RESET_REQUESTED = (
            "password_reset_requested",
            "Password Reset Requested",
        )
        PASSWORD_RESET_COMPLETED = (
            "password_reset_completed",
            "Password Reset Completed",
        )
        EMAIL_CHANGE_REQUESTED = "email_change_requested", "Email Change Requested"
        EMAIL_CHANGED = "email_changed", "Email Changed"
        USER_BANNED = "user_banned", "User Banned"
        USER_UNBANNED = "user_unbanned", "User Unbanned"
        USER_SOFT_DELETED = "user_soft_deleted", "User Soft Deleted"
        USER_HARD_DELETED = "user_hard_deleted", "User Hard Deleted"
        USER_REACTIVATED = "user_reactivated", "User Reactivated"
        USER_ROLE_CHANGED = "user_role_changed", "User Role Changed"

    event_type = models.CharField(
        max_length=40, choices=EventType.choices, db_index=True
    )
    user = models.ForeignKey(
        "User",
        related_name="security_logs",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    username = models.CharField(max_length=150, blank=True, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True, db_index=True)
    user_agent = models.CharField(max_length=255, blank=True)
    success = models.BooleanField(default=True, db_index=True)
    detail = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]


class CaptchaAuditLog(models.Model):
    scene = models.CharField(max_length=64, db_index=True)
    user = models.ForeignKey(
        "User",
        related_name="captcha_audit_logs",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True, db_index=True)
    user_agent = models.TextField(blank=True)
    target_type = models.CharField(max_length=32, blank=True, db_index=True)
    target_hash = models.CharField(max_length=64, blank=True, db_index=True)
    turnstile_success = models.BooleanField(default=False)
    secondary_provider = models.CharField(max_length=32, blank=True)
    secondary_success = models.BooleanField(default=False)
    result = models.CharField(max_length=32, db_index=True)
    error_code = models.CharField(max_length=64, blank=True, db_index=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["scene", "created_at"], name="captcha_scene_created_idx"),
            models.Index(fields=["target_type", "target_hash"], name="captcha_target_hash_idx"),
        ]


class SiteVisitDailyStat(TimeStampedModel):
    date = models.DateField(unique=True, db_index=True)
    page_views = models.PositiveBigIntegerField(default=0)

    class Meta:
        ordering = ["-date"]

    def __str__(self) -> str:
        return f"{self.date}: {self.page_views}"


class PasswordHistory(models.Model):
    user = models.ForeignKey(
        "User", related_name="password_histories", on_delete=models.CASCADE
    )
    password_hash = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class EmailVerificationTicket(TimeStampedModel):
    class Purpose(models.TextChoices):
        REGISTER = "register", "Register"
        RESET_PASSWORD = "reset_password", "Reset Password"
        CHANGE_EMAIL = "change_email", "Change Email"
        CHANGE_PASSWORD = "change_password", "Change Password"

    purpose = models.CharField(max_length=32, choices=Purpose.choices, db_index=True)
    user = models.ForeignKey(
        "User",
        related_name="email_verification_tickets",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    email = models.EmailField(db_index=True)
    username_snapshot = models.CharField(max_length=150, blank=True)
    school_name_snapshot = models.CharField(max_length=120, blank=True)
    password_hash_snapshot = models.CharField(max_length=128, blank=True)
    code_hash = models.CharField(max_length=128)
    verify_attempt_count = models.PositiveSmallIntegerField(default=0)
    created_ip = models.GenericIPAddressField(null=True, blank=True, db_index=True)
    expires_at = models.DateTimeField(db_index=True)
    consumed_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def is_active(self) -> bool:
        return self.consumed_at is None and self.expires_at > timezone.now()

    def mark_consumed(self):
        if self.consumed_at is not None:
            return
        self.consumed_at = timezone.now()
        self.save(update_fields=["consumed_at", "updated_at"])


class UserNotification(TimeStampedModel):
    class Level(models.TextChoices):
        INFO = "info", "Info"
        WARNING = "warning", "Warning"

    user = models.ForeignKey(
        "User", related_name="notifications", on_delete=models.CASCADE
    )
    actor = models.ForeignKey(
        "User",
        related_name="triggered_notifications",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=200)
    content = models.CharField(max_length=500, blank=True)
    link = models.CharField(max_length=255, blank=True)
    level = models.CharField(max_length=20, choices=Level.choices, default=Level.INFO)
    target_type = models.CharField(max_length=80, blank=True)
    target_id = models.PositiveBigIntegerField(null=True, blank=True)
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["is_read", "-created_at"]

    def mark_read(self):
        if self.is_read:
            return
        self.is_read = True
        self.read_at = timezone.now()
        self.save(update_fields=["is_read", "read_at", "updated_at"])


class ExtensionPage(TimeStampedModel):
    class AccessLevel(models.TextChoices):
        PUBLIC = "public", "Public"
        AUTH = "auth", "Authenticated"
        ADMIN = "admin", "Admin"

    title = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180, unique=True)
    description = models.TextField(blank=True)
    content_md = models.TextField(blank=True)
    access_level = models.CharField(
        max_length=20,
        choices=AccessLevel.choices,
        default=AccessLevel.PUBLIC,
    )
    is_enabled = models.BooleanField(default=True)

    class Meta:
        ordering = ["title"]


class DocumentPageSection(TimeStampedModel):
    title = models.CharField(max_length=120)
    key = models.SlugField(max_length=120, unique=True)
    page = models.ForeignKey(
        ExtensionPage,
        related_name="document_page_sections",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    display_order = models.PositiveIntegerField(default=0, db_index=True)
    is_visible = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["display_order", "id"]

    def __str__(self) -> str:
        return self.title


class CompetitionZoneSection(TimeStampedModel):
    class TargetType(models.TextChoices):
        BUILTIN = "builtin", "Built-in"
        PAGE = "page", "Page"

    class BuiltinView(models.TextChoices):
        SCHEDULE = "schedule", "Competition Schedule"
        NOTICE = "notice", "Competition Notice"
        PRACTICE = "practice", "Practice Links"
        CALENDAR = "calendar", "Competition Calendar"
        TRICKS = "tricks", "Trick Entries"
        QA = "qa", "Q&A"

    title = models.CharField(max_length=120)
    key = models.SlugField(max_length=120, unique=True)
    target_type = models.CharField(
        max_length=20, choices=TargetType.choices, default=TargetType.BUILTIN
    )
    builtin_view = models.CharField(
        max_length=30, choices=BuiltinView.choices, blank=True, default=""
    )
    page = models.ForeignKey(
        ExtensionPage,
        related_name="competition_zone_sections",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    display_order = models.PositiveIntegerField(default=0, db_index=True)
    is_visible = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["display_order", "id"]

    def __str__(self) -> str:
        return self.title


class SchoolSurveySchool(TimeStampedModel):
    class SchoolType(models.TextChoices):
        UNIVERSITY = "university", "University"
        OTHER = "other", "Other"

    name = models.CharField(max_length=120, unique=True, db_index=True)
    abbreviation = models.CharField(max_length=40, blank=True)
    province = models.CharField(max_length=80, blank=True, db_index=True)
    city = models.CharField(max_length=80, blank=True, db_index=True)
    school_type = models.CharField(
        max_length=30,
        choices=SchoolType.choices,
        default=SchoolType.UNIVERSITY,
        db_index=True,
    )
    logo_url = models.URLField(max_length=500, blank=True)
    display_order = models.PositiveIntegerField(default=0, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["display_order", "name", "id"]

    def __str__(self) -> str:
        return self.name


class SchoolSurveySubmission(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        ARCHIVED = "archived", "Archived"

    school = models.ForeignKey(
        SchoolSurveySchool,
        related_name="submissions",
        on_delete=models.CASCADE,
    )
    author = models.ForeignKey(
        "User",
        related_name="school_survey_submissions",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    form_data = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    submitted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ["-submitted_at", "-updated_at", "-id"]
        indexes = [
            models.Index(
                fields=["school", "status", "submitted_at"],
                name="survey_sub_school_status_idx",
            ),
            models.Index(
                fields=["author", "status", "updated_at"],
                name="survey_sub_author_status_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.school_id}:{self.status}:{self.pk}"


class HeaderNavigationItem(TimeStampedModel):
    class NavKey(models.TextChoices):
        HOME = "home", "Home"
        COMPETITION_WIKI = "competition-wiki", "Competition Wiki"
        COMPETITIONS = "competitions", "Competition Zone"
        MOMENTS = "moments", "Moments"
        QUESTIONS = "questions", "Q&A"
        ABOUT = "about", "About AlgoWiki"
        FRIENDLY_LINKS = "friendly-links", "Friendly Links"

    key = models.CharField(
        max_length=40, choices=NavKey.choices, unique=True, db_index=True
    )
    title = models.CharField(max_length=80)
    display_order = models.PositiveIntegerField(default=0, db_index=True)
    is_visible = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["display_order", "id"]

    def __str__(self) -> str:
        return self.title


class AssistantProviderConfig(TimeStampedModel):
    class Provider(models.TextChoices):
        DEEPSEEK = "deepseek", "DeepSeek"

    label = models.CharField(max_length=80)
    assistant_name = models.CharField(max_length=80, default="AlgoWiki 助手")
    provider = models.CharField(
        max_length=20,
        choices=Provider.choices,
        default=Provider.DEEPSEEK,
        db_index=True,
    )
    base_url = models.URLField(max_length=500, default="https://api.deepseek.com")
    model_name = models.CharField(max_length=120, default="deepseek-chat")
    api_key_encrypted = models.TextField(blank=True)
    is_enabled = models.BooleanField(default=True, db_index=True)
    is_default = models.BooleanField(default=False, db_index=True)
    show_launcher = models.BooleanField(default=True)
    temperature = models.FloatField(default=0.3)
    max_output_tokens = models.PositiveIntegerField(default=1024)
    request_timeout_seconds = models.PositiveSmallIntegerField(default=30)
    welcome_message = models.TextField(blank=True)
    teaser_message = models.TextField(blank=True)
    suggested_questions = models.JSONField(default=list, blank=True)
    system_prompt = models.TextField(blank=True)
    daily_request_limit = models.PositiveIntegerField(default=0)
    daily_token_limit = models.PositiveIntegerField(default=0)
    last_tested_at = models.DateTimeField(null=True, blank=True)
    last_test_success = models.BooleanField(null=True, blank=True)
    last_test_message = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        "User",
        related_name="created_assistant_provider_configs",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    updated_by = models.ForeignKey(
        "User",
        related_name="updated_assistant_provider_configs",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-is_default", "label", "id"]

    def __str__(self) -> str:
        return f"{self.label} ({self.model_name})"

    @staticmethod
    def _get_cipher() -> Fernet:
        return Fernet(settings.AI_ASSISTANT_ENCRYPTION_KEY.encode("utf-8"))

    @property
    def has_api_key(self) -> bool:
        return bool((self.api_key_encrypted or "").strip())

    @property
    def api_key_masked(self) -> str:
        return "****************" if self.has_api_key else ""

    def set_api_key(self, raw_value: str) -> None:
        value = str(raw_value or "").strip()
        if not value:
            self.api_key_encrypted = ""
            return
        self.api_key_encrypted = (
            self._get_cipher().encrypt(value.encode("utf-8")).decode("utf-8")
        )

    def get_api_key(self) -> str:
        if not self.has_api_key:
            return ""
        try:
            return (
                self._get_cipher()
                .decrypt(self.api_key_encrypted.encode("utf-8"))
                .decode("utf-8")
            )
        except (InvalidToken, ValueError, TypeError):
            return ""

    def save(self, *args, **kwargs):
        if self.is_default:
            self.is_enabled = True
        super().save(*args, **kwargs)
        if self.is_default:
            AssistantProviderConfig.objects.exclude(pk=self.pk).filter(
                is_default=True
            ).update(is_default=False)


class AssistantInteractionLog(models.Model):
    config = models.ForeignKey(
        AssistantProviderConfig,
        related_name="interaction_logs",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    user = models.ForeignKey(
        "User",
        related_name="assistant_interaction_logs",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    session_id = models.CharField(max_length=64, blank=True, db_index=True)
    provider = models.CharField(max_length=20, blank=True, db_index=True)
    model_name = models.CharField(max_length=120, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True, db_index=True)
    user_agent = models.CharField(max_length=255, blank=True)
    prompt_chars = models.PositiveIntegerField(default=0)
    response_chars = models.PositiveIntegerField(default=0)
    prompt_tokens = models.PositiveIntegerField(default=0)
    completion_tokens = models.PositiveIntegerField(default=0)
    total_tokens = models.PositiveIntegerField(default=0)
    source_count = models.PositiveIntegerField(default=0)
    response_ms = models.PositiveIntegerField(default=0)
    success = models.BooleanField(default=True, db_index=True)
    error_message = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]


class AIModerationConfig(TimeStampedModel):
    class Provider(models.TextChoices):
        DEEPSEEK = "deepseek", "DeepSeek"

    class SuspiciousAction(models.TextChoices):
        PENDING = "pending", "Keep Pending"
        APPROVE = "approve", "Approve"
        REJECT = "reject", "Reject"

    class FailureAction(models.TextChoices):
        PENDING = "pending", "Keep Pending"
        APPROVE = "approve", "Approve"

    singleton_key = models.PositiveSmallIntegerField(
        default=1, unique=True, editable=False
    )
    label = models.CharField(max_length=80, default="默认 AI 审核配置")
    provider = models.CharField(
        max_length=20,
        choices=Provider.choices,
        default=Provider.DEEPSEEK,
        db_index=True,
    )
    base_url = models.URLField(max_length=500, default="https://api.deepseek.com")
    model_name = models.CharField(max_length=120, default="deepseek-chat")
    api_key_encrypted = models.TextField(blank=True)
    is_enabled = models.BooleanField(default=False, db_index=True)
    comment_enabled = models.BooleanField(default=True)
    question_enabled = models.BooleanField(default=True)
    answer_enabled = models.BooleanField(default=True)
    ticket_enabled = models.BooleanField(default=True)
    moment_enabled = models.BooleanField(default=True)
    moment_comment_enabled = models.BooleanField(default=True)
    auto_approve_safe = models.BooleanField(default=True)
    auto_reject_unsafe = models.BooleanField(default=True)
    suspicious_action = models.CharField(
        max_length=20,
        choices=SuspiciousAction.choices,
        default=SuspiciousAction.PENDING,
    )
    failure_action = models.CharField(
        max_length=20,
        choices=FailureAction.choices,
        default=FailureAction.PENDING,
    )
    temperature = models.FloatField(default=0.0)
    max_output_tokens = models.PositiveIntegerField(default=512)
    request_timeout_seconds = models.PositiveSmallIntegerField(default=20)
    daily_request_limit = models.PositiveIntegerField(default=0)
    daily_token_limit = models.PositiveIntegerField(default=0)
    max_input_chars = models.PositiveIntegerField(default=4000)
    new_user_strict_days = models.PositiveSmallIntegerField(default=7)
    new_user_strict_max_items = models.PositiveSmallIntegerField(default=3)
    whitelist_keywords = models.JSONField(default=list, blank=True)
    blacklist_keywords = models.JSONField(default=list, blank=True)
    blocked_domains = models.JSONField(default=list, blank=True)
    supplemental_rules = models.TextField(blank=True)
    reject_notice_template = models.CharField(
        max_length=300,
        default="内容未通过 AI 审核：{reason}。请修改后重新提交。",
    )
    created_by = models.ForeignKey(
        "User",
        related_name="created_ai_moderation_configs",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    updated_by = models.ForeignKey(
        "User",
        related_name="updated_ai_moderation_configs",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.label} ({self.model_name})"

    @classmethod
    def get_solo(cls):
        instance = cls.objects.order_by("id").first()
        if instance:
            return instance
        return cls.objects.create(singleton_key=1)

    @staticmethod
    def _get_cipher() -> Fernet:
        return Fernet(settings.AI_ASSISTANT_ENCRYPTION_KEY.encode("utf-8"))

    @property
    def has_api_key(self) -> bool:
        return bool((self.api_key_encrypted or "").strip())

    @property
    def api_key_masked(self) -> str:
        return "****************" if self.has_api_key else ""

    def set_api_key(self, raw_value: str) -> None:
        value = str(raw_value or "").strip()
        if not value:
            self.api_key_encrypted = ""
            return
        self.api_key_encrypted = (
            self._get_cipher().encrypt(value.encode("utf-8")).decode("utf-8")
        )

    def get_api_key(self) -> str:
        if not self.has_api_key:
            return ""
        try:
            return (
                self._get_cipher()
                .decrypt(self.api_key_encrypted.encode("utf-8"))
                .decode("utf-8")
            )
        except (InvalidToken, ValueError, TypeError):
            return ""

    def save(self, *args, **kwargs):
        self.singleton_key = 1
        super().save(*args, **kwargs)


class AIModerationRecord(models.Model):
    class TargetType(models.TextChoices):
        COMMENT = "comment", "Comment"
        QUESTION = "question", "Question"
        ANSWER = "answer", "Answer"
        TICKET = "ticket", "Ticket"
        MOMENT = "moment", "Moment"
        MOMENT_COMMENT = "moment_comment", "Moment Comment"

    class Decision(models.TextChoices):
        APPROVE = "approve", "Approve"
        REJECT = "reject", "Reject"
        MANUAL = "manual", "Manual Review"
        ERROR = "error", "Error"
        SKIPPED = "skipped", "Skipped"

    class RiskLevel(models.TextChoices):
        SAFE = "safe", "Safe"
        SUSPICIOUS = "suspicious", "Suspicious"
        REJECT = "reject", "Reject"
        ERROR = "error", "Error"

    class Status(models.TextChoices):
        APPLIED = "applied", "Applied"
        PENDING_REVIEW = "pending_review", "Pending Review"
        ERROR = "error", "Error"
        SKIPPED = "skipped", "Skipped"

    config = models.ForeignKey(
        AIModerationConfig,
        related_name="moderation_records",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    target_type = models.CharField(
        max_length=20, choices=TargetType.choices, db_index=True
    )
    target_id = models.PositiveBigIntegerField(db_index=True)
    author = models.ForeignKey(
        "User",
        related_name="ai_moderation_records",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    provider = models.CharField(max_length=20, blank=True, db_index=True)
    model_name = models.CharField(max_length=120, blank=True)
    decision = models.CharField(
        max_length=20, choices=Decision.choices, default=Decision.MANUAL, db_index=True
    )
    risk_level = models.CharField(
        max_length=20, choices=RiskLevel.choices, default=RiskLevel.SUSPICIOUS
    )
    categories = models.JSONField(default=list, blank=True)
    summary = models.CharField(max_length=300, blank=True)
    user_notice = models.CharField(max_length=300, blank=True)
    raw_response = models.JSONField(default=dict, blank=True)
    prompt_chars = models.PositiveIntegerField(default=0)
    response_chars = models.PositiveIntegerField(default=0)
    prompt_tokens = models.PositiveIntegerField(default=0)
    completion_tokens = models.PositiveIntegerField(default=0)
    total_tokens = models.PositiveIntegerField(default=0)
    response_ms = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING_REVIEW,
        db_index=True,
    )
    error_message = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["target_type", "target_id"]),
            models.Index(fields=["decision", "created_at"]),
        ]


class RealNameVerification(TimeStampedModel):
    class Status(models.TextChoices):
        UNVERIFIED = "unverified", "Unverified"
        PENDING = "pending", "Pending"
        VERIFIED = "verified", "Verified"
        REJECTED = "rejected", "Rejected"
        REVOKED = "revoked", "Revoked"

    user = models.OneToOneField(
        "User", related_name="real_name_verification", on_delete=models.CASCADE
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.UNVERIFIED, db_index=True
    )
    real_name_masked = models.CharField(max_length=40, blank=True)
    id_number_last4 = models.CharField(max_length=4, blank=True)
    provider = models.CharField(max_length=40, default="manual", blank=True)
    provider_trace_id = models.CharField(max_length=120, blank=True)
    provider_order_no = models.CharField(max_length=64, blank=True, db_index=True)
    provider_certify_id = models.CharField(max_length=120, blank=True, db_index=True)
    provider_scene_id = models.CharField(max_length=40, blank=True)
    provider_sub_code = models.CharField(max_length=80, blank=True)
    provider_status_message = models.CharField(max_length=300, blank=True)
    provider_device_risk = models.CharField(max_length=120, blank=True)
    provider_result = models.JSONField(default=dict, blank=True)
    provider_callback_token = models.CharField(max_length=80, blank=True)
    provider_started_at = models.DateTimeField(null=True, blank=True)
    provider_checked_at = models.DateTimeField(null=True, blank=True)
    provider_expires_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    reviewer = models.ForeignKey(
        "User",
        related_name="reviewed_real_name_verifications",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    review_note = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.status}"

    @property
    def is_verified(self) -> bool:
        return self.status == self.Status.VERIFIED


class PhoneVerification(TimeStampedModel):
    class Status(models.TextChoices):
        UNVERIFIED = "unverified", "Unverified"
        PENDING = "pending", "Pending"
        VERIFIED = "verified", "Verified"
        REJECTED = "rejected", "Rejected"
        REVOKED = "revoked", "Revoked"

    user = models.OneToOneField(
        "User", related_name="phone_verification", on_delete=models.CASCADE
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.UNVERIFIED, db_index=True
    )
    phone_country_code = models.CharField(max_length=8, default="86", blank=True)
    phone_masked = models.CharField(max_length=32, blank=True)
    phone_last4 = models.CharField(max_length=4, blank=True)
    phone_encrypted = models.TextField(blank=True)
    phone_digest = models.CharField(
        max_length=128, blank=True, null=True, unique=True, db_index=True
    )
    provider = models.CharField(max_length=40, default="manual", blank=True)
    provider_out_id = models.CharField(max_length=120, blank=True, db_index=True)
    provider_biz_id = models.CharField(max_length=120, blank=True)
    provider_request_id = models.CharField(max_length=120, blank=True)
    provider_status_message = models.CharField(max_length=300, blank=True)
    provider_result = models.JSONField(default=dict, blank=True)
    provider_started_at = models.DateTimeField(null=True, blank=True)
    provider_checked_at = models.DateTimeField(null=True, blank=True)
    provider_expires_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    reviewer = models.ForeignKey(
        "User",
        related_name="reviewed_phone_verifications",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    review_note = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.status}"

    @property
    def is_verified(self) -> bool:
        return self.status == self.Status.VERIFIED

    @staticmethod
    def _get_phone_cipher() -> Fernet:
        return Fernet(settings.AI_ASSISTANT_ENCRYPTION_KEY.encode("utf-8"))

    def set_phone_number(self, raw_value: str) -> None:
        value = str(raw_value or "").strip()
        if not value:
            self.phone_encrypted = ""
            return
        self.phone_encrypted = (
            self._get_phone_cipher().encrypt(value.encode("utf-8")).decode("utf-8")
        )

    def get_phone_number(self) -> str:
        if not (self.phone_encrypted or "").strip():
            return ""
        try:
            return (
                self._get_phone_cipher()
                .decrypt(self.phone_encrypted.encode("utf-8"))
                .decode("utf-8")
            )
        except (InvalidToken, ValueError, TypeError):
            return ""


class PhoneVerificationTicket(TimeStampedModel):
    user = models.ForeignKey(
        "User", related_name="phone_verification_tickets", on_delete=models.CASCADE
    )
    phone_country_code = models.CharField(max_length=8, default="86", blank=True)
    phone_masked = models.CharField(max_length=32, blank=True)
    phone_last4 = models.CharField(max_length=4, blank=True)
    phone_digest = models.CharField(max_length=128, db_index=True)
    provider = models.CharField(max_length=40, default="aliyun_pnvs", blank=True)
    provider_out_id = models.CharField(max_length=120, blank=True, db_index=True)
    provider_biz_id = models.CharField(max_length=120, blank=True)
    provider_request_id = models.CharField(max_length=120, blank=True)
    provider_response = models.JSONField(default=dict, blank=True)
    verify_attempt_count = models.PositiveSmallIntegerField(default=0)
    created_ip = models.GenericIPAddressField(null=True, blank=True, db_index=True)
    expires_at = models.DateTimeField(db_index=True)
    consumed_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["phone_digest", "created_at"]),
        ]

    @property
    def is_active(self) -> bool:
        return self.consumed_at is None and self.expires_at > timezone.now()

    def mark_consumed(self):
        if self.consumed_at is not None:
            return
        self.consumed_at = timezone.now()
        self.save(update_fields=["consumed_at", "updated_at"])


class MomentSettings(TimeStampedModel):
    singleton_key = models.PositiveSmallIntegerField(
        default=1, unique=True, editable=False
    )
    is_enabled = models.BooleanField(default=False)
    publishing_enabled = models.BooleanField(default=False)
    commenting_enabled = models.BooleanField(default=False)
    reactions_enabled = models.BooleanField(default=True)
    favorites_enabled = models.BooleanField(default=True)
    hot_list_enabled = models.BooleanField(default=False)
    featured_feed_enabled = models.BooleanField(default=False)
    require_real_name = models.BooleanField(default=True)
    require_manual_review_for_new_users = models.BooleanField(default=True)
    new_user_manual_review_count = models.PositiveSmallIntegerField(default=3)
    daily_post_limit = models.PositiveSmallIntegerField(default=20)
    daily_comment_limit = models.PositiveSmallIntegerField(default=80)
    max_images_per_post = models.PositiveSmallIntegerField(default=9)
    max_image_size_mb = models.PositiveSmallIntegerField(default=5)
    max_text_length = models.PositiveIntegerField(default=2000)
    max_comment_length = models.PositiveIntegerField(default=500)
    auto_hide_report_threshold = models.PositiveSmallIntegerField(default=3)
    hot_window_days = models.PositiveSmallIntegerField(default=7)
    hot_limit = models.PositiveSmallIntegerField(default=10)
    hot_like_weight = models.PositiveSmallIntegerField(default=2)
    hot_favorite_weight = models.PositiveSmallIntegerField(default=3)
    hot_comment_weight = models.PositiveSmallIntegerField(default=2)
    hot_report_penalty = models.PositiveSmallIntegerField(default=10)
    rules_summary = models.TextField(
        blank=True,
        default=(
            "请发布与算法学习、竞赛训练、站内协作相关的内容。"
            "禁止发布违法违规、色情低俗、暴力恐怖、涉政攻击、广告引流、"
            "考试或正在进行比赛的题目答案、侵犯隐私或人身攻击内容。"
        ),
    )
    updated_by = models.ForeignKey(
        "User",
        related_name="updated_moment_settings",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["id"]

    @classmethod
    def get_solo(cls):
        instance = cls.objects.order_by("id").first()
        if instance:
            return instance
        return cls.objects.create(singleton_key=1)

    def save(self, *args, **kwargs):
        self.singleton_key = 1
        super().save(*args, **kwargs)


class Moment(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending Review"
        PUBLISHED = "published", "Published"
        REJECTED = "rejected", "Rejected"
        HIDDEN = "hidden", "Hidden"
        DELETED = "deleted", "Deleted"

    author = models.ForeignKey(
        "User", related_name="moments", on_delete=models.PROTECT
    )
    content = models.TextField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)
    reviewed_by = models.ForeignKey(
        "User",
        related_name="reviewed_moments",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.CharField(max_length=300, blank=True)
    allow_hot = models.BooleanField(default=True, db_index=True)
    is_featured = models.BooleanField(default=False, db_index=True)
    comments_locked = models.BooleanField(default=False)
    hidden_by = models.ForeignKey(
        "User",
        related_name="hidden_moments",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    hidden_at = models.DateTimeField(null=True, blank=True)
    hidden_reason = models.CharField(max_length=300, blank=True)
    deleted_by = models.ForeignKey(
        "User",
        related_name="deleted_moments",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    deleted_at = models.DateTimeField(null=True, blank=True)
    like_count = models.PositiveIntegerField(default=0)
    favorite_count = models.PositiveIntegerField(default=0)
    comment_count = models.PositiveIntegerField(default=0)
    report_count = models.PositiveIntegerField(default=0)
    hot_score = models.IntegerField(default=0, db_index=True)
    last_ai_summary = models.CharField(max_length=300, blank=True)
    last_ai_risk_level = models.CharField(max_length=20, blank=True)

    class Meta:
        ordering = ["-published_at", "-created_at", "-id"]
        indexes = [
            models.Index(fields=["status", "published_at"]),
            models.Index(fields=["allow_hot", "hot_score"]),
            models.Index(fields=["author", "status"]),
        ]

    def __str__(self) -> str:
        return f"Moment #{self.pk} by {self.author_id}"

    @property
    def is_public(self) -> bool:
        return self.status == self.Status.PUBLISHED

    def publish(self, *, reviewer=None, note: str = ""):
        self.status = self.Status.PUBLISHED
        self.published_at = self.published_at or timezone.now()
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.review_note = str(note or "").strip()[:300]


class MomentImage(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending Review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        HIDDEN = "hidden", "Hidden"

    moment = models.ForeignKey(
        Moment, related_name="images", on_delete=models.CASCADE
    )
    image = models.ImageField(upload_to=moment_image_upload_to)
    thumbnail = models.ImageField(
        upload_to=moment_image_thumbnail_upload_to, blank=True, default=""
    )
    original_name = models.CharField(max_length=255, blank=True)
    content_type = models.CharField(max_length=120, blank=True)
    size_bytes = models.PositiveIntegerField(default=0)
    width = models.PositiveIntegerField(default=0)
    height = models.PositiveIntegerField(default=0)
    thumbnail_size_bytes = models.PositiveIntegerField(default=0)
    thumbnail_width = models.PositiveIntegerField(default=0)
    thumbnail_height = models.PositiveIntegerField(default=0)
    display_order = models.PositiveSmallIntegerField(default=0)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    uploaded_by = models.ForeignKey(
        "User",
        related_name="uploaded_moment_images",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    moderation_summary = models.CharField(max_length=300, blank=True)
    moderation_provider = models.CharField(max_length=40, blank=True)
    moderation_decision = models.CharField(max_length=20, blank=True, db_index=True)
    moderation_risk_level = models.CharField(max_length=40, blank=True)
    moderation_categories = models.JSONField(default=list, blank=True)
    moderation_raw = models.JSONField(default=dict, blank=True)
    moderation_error = models.CharField(max_length=300, blank=True)
    last_moderated_at = models.DateTimeField(null=True, blank=True)
    recheck_count = models.PositiveSmallIntegerField(default=0)
    deleted_by = models.ForeignKey(
        "User",
        related_name="deleted_moment_images",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    deleted_at = models.DateTimeField(null=True, blank=True)
    delete_after = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ["display_order", "id"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["uploaded_by", "created_at"]),
            models.Index(fields=["delete_after"]),
        ]

    @property
    def url(self) -> str:
        try:
            return self.image.url
        except ValueError:
            return ""

    @property
    def thumbnail_url(self) -> str:
        try:
            return self.thumbnail.url if self.thumbnail else ""
        except ValueError:
            return ""


class MomentComment(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending Review"
        VISIBLE = "visible", "Visible"
        REJECTED = "rejected", "Rejected"
        HIDDEN = "hidden", "Hidden"
        DELETED = "deleted", "Deleted"

    moment = models.ForeignKey(
        Moment, related_name="comments", on_delete=models.CASCADE
    )
    author = models.ForeignKey(
        "User", related_name="moment_comments", on_delete=models.PROTECT
    )
    content = models.TextField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    reviewed_by = models.ForeignKey(
        "User",
        related_name="reviewed_moment_comments",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.CharField(max_length=300, blank=True)
    report_count = models.PositiveIntegerField(default=0)
    deleted_by = models.ForeignKey(
        "User",
        related_name="deleted_moment_comments",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    deleted_at = models.DateTimeField(null=True, blank=True)
    last_ai_summary = models.CharField(max_length=300, blank=True)
    last_ai_risk_level = models.CharField(max_length=20, blank=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(fields=["moment", "status"]),
            models.Index(fields=["author", "status"]),
        ]

    @property
    def is_visible(self) -> bool:
        return self.status == self.Status.VISIBLE


class MomentLike(models.Model):
    moment = models.ForeignKey(
        Moment, related_name="likes", on_delete=models.CASCADE
    )
    user = models.ForeignKey(
        "User", related_name="moment_likes", on_delete=models.CASCADE
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("moment", "user")
        ordering = ["-created_at"]


class MomentFavorite(models.Model):
    moment = models.ForeignKey(
        Moment, related_name="favorites", on_delete=models.CASCADE
    )
    user = models.ForeignKey(
        "User", related_name="moment_favorites", on_delete=models.CASCADE
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("moment", "user")
        ordering = ["-created_at"]


class MomentReport(TimeStampedModel):
    class TargetType(models.TextChoices):
        MOMENT = "moment", "Moment"
        COMMENT = "comment", "Comment"

    class Reason(models.TextChoices):
        SPAM = "spam", "Spam"
        PORN = "porn", "Porn"
        POLITICAL = "political", "Political"
        VIOLENCE = "violence", "Violence"
        ABUSE = "abuse", "Abuse"
        PRIVACY = "privacy", "Privacy"
        CHEATING = "cheating", "Cheating"
        IRRELEVANT = "irrelevant", "Irrelevant"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RESOLVED = "resolved", "Resolved"
        REJECTED = "rejected", "Rejected"

    target_type = models.CharField(
        max_length=20, choices=TargetType.choices, db_index=True
    )
    moment = models.ForeignKey(
        Moment,
        related_name="reports",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    comment = models.ForeignKey(
        MomentComment,
        related_name="reports",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    reporter = models.ForeignKey(
        "User", related_name="moment_reports", on_delete=models.CASCADE
    )
    target_author = models.ForeignKey(
        "User",
        related_name="received_moment_reports",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    reason = models.CharField(
        max_length=20, choices=Reason.choices, default=Reason.OTHER, db_index=True
    )
    description = models.CharField(max_length=500, blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    handled_by = models.ForeignKey(
        "User",
        related_name="handled_moment_reports",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    handled_at = models.DateTimeField(null=True, blank=True)
    resolution_action = models.CharField(max_length=80, blank=True)
    resolution_note = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["target_type", "status", "created_at"])]


class MomentUserRestriction(TimeStampedModel):
    user = models.OneToOneField(
        "User", related_name="moment_restriction", on_delete=models.CASCADE
    )
    can_post = models.BooleanField(default=True)
    can_comment = models.BooleanField(default=True)
    can_react = models.BooleanField(default=True)
    can_upload_images = models.BooleanField(default=True)
    can_enter_hot = models.BooleanField(default=True)
    muted_until = models.DateTimeField(null=True, blank=True)
    reason = models.CharField(max_length=300, blank=True)
    updated_by = models.ForeignKey(
        "User",
        related_name="updated_moment_user_restrictions",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["user__username"]

    @property
    def is_muted(self) -> bool:
        return bool(self.muted_until and self.muted_until > timezone.now())


class MomentAuditLog(models.Model):
    class EventType(models.TextChoices):
        CREATE = "create", "Create"
        UPDATE = "update", "Update"
        APPROVE = "approve", "Approve"
        REJECT = "reject", "Reject"
        HIDE = "hide", "Hide"
        DELETE = "delete", "Delete"
        RESTORE = "restore", "Restore"
        REPORT = "report", "Report"
        RESTRICT = "restrict", "Restrict"
        CONFIG = "config", "Config"
        HOT = "hot", "Hot"
        VERIFY = "verify", "Verify"

    actor = models.ForeignKey(
        "User",
        related_name="moment_audit_actions",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    target_user = models.ForeignKey(
        "User",
        related_name="moment_audit_logs",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    event_type = models.CharField(max_length=20, choices=EventType.choices, db_index=True)
    target_type = models.CharField(max_length=80, blank=True, db_index=True)
    target_id = models.PositiveBigIntegerField(null=True, blank=True, db_index=True)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["event_type", "created_at"]),
            models.Index(fields=["target_type", "target_id"]),
        ]


class ContributionEvent(models.Model):
    class EventType(models.TextChoices):
        STAR = "star", "Star"
        COMMENT = "comment", "Comment"
        ISSUE = "issue", "Issue"
        REVISION = "revision", "Revision"
        QUESTION = "question", "Question"
        ANSWER = "answer", "Answer"
        ANNOUNCEMENT = "announcement", "Announcement"
        MOMENT = "moment", "Moment"
        ADMIN = "admin", "Admin Action"

    user = models.ForeignKey(
        "User", related_name="contribution_events", on_delete=models.CASCADE
    )
    event_type = models.CharField(max_length=20, choices=EventType.choices)
    target_type = models.CharField(max_length=80)
    target_id = models.PositiveBigIntegerField()
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
