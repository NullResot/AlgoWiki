import uuid
from datetime import timedelta

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


class User(AbstractUser):
    class Role(models.TextChoices):
        NORMAL = "normal", "Normal User"
        SCHOOL = "school", "School User"
        ADMIN = "admin", "Admin User"
        SUPERADMIN = "superadmin", "Super Admin"

    role = models.CharField(
        max_length=20, choices=Role.choices, default=Role.NORMAL, db_index=True
    )
    school_name = models.CharField(max_length=120, blank=True)
    bio = models.TextField(blank=True)
    avatar_url = models.URLField(blank=True)
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
        TRICK_RECEIVED_DOWNVOTE = "trick_received_downvote", "Trick 收到点踩"
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


class HeaderNavigationItem(TimeStampedModel):
    class NavKey(models.TextChoices):
        HOME = "home", "Home"
        COMPETITION_WIKI = "competition-wiki", "Competition Wiki"
        COMPETITIONS = "competitions", "Competition Zone"
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


class ContributionEvent(models.Model):
    class EventType(models.TextChoices):
        STAR = "star", "Star"
        COMMENT = "comment", "Comment"
        ISSUE = "issue", "Issue"
        REVISION = "revision", "Revision"
        QUESTION = "question", "Question"
        ANSWER = "answer", "Answer"
        ANNOUNCEMENT = "announcement", "Announcement"
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
