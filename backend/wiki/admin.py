from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import (
    Announcement,
    AnnouncementRead,
    Answer,
    Article,
    ArticleComment,
    ArticleStar,
    Category,
    CompetitionNotice,
    CompetitionPracticeLink,
    CompetitionPracticeLinkProposal,
    CompetitionScheduleEntry,
    ContributionEvent,
    ExtensionPage,
    FriendlyLink,
    IssueTicket,
    LoginAttempt,
    PasswordHistory,
    Question,
    RevisionProposal,
    SecurityAuditLog,
    TeamMember,
    TrickEntry,
    UserNotification,
    User,
)

admin.site.site_header = "AlgoWiki Django 原生后台"
admin.site.site_title = "AlgoWiki Django Admin"
admin.site.index_title = "模型级数据管理"


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    fieldsets = DjangoUserAdmin.fieldsets + (
        (
            "Project Fields",
            {
                "fields": (
                    "role",
                    "school_name",
                    "bio",
                    "avatar_url",
                    "is_banned",
                    "banned_reason",
                    "banned_at",
                )
            },
        ),
    )
    list_display = (
        "id",
        "username",
        "email",
        "role",
        "is_active",
        "is_banned",
        "date_joined",
    )
    list_filter = ("role", "is_active", "is_banned")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "slug", "parent", "moderation_scope", "is_visible", "order")
    list_filter = ("moderation_scope", "is_visible")
    search_fields = ("name", "slug")


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "slug",
        "category",
        "author",
        "status",
        "is_featured",
        "updated_at",
    )
    list_filter = ("status", "is_featured", "category")
    search_fields = ("title", "summary", "content_md")


@admin.register(ArticleComment)
class ArticleCommentAdmin(admin.ModelAdmin):
    list_display = ("id", "article", "author", "status", "created_at")
    list_filter = ("status",)


@admin.register(ArticleStar)
class ArticleStarAdmin(admin.ModelAdmin):
    list_display = ("id", "article", "user", "created_at")


@admin.register(RevisionProposal)
class RevisionProposalAdmin(admin.ModelAdmin):
    list_display = ("id", "article", "proposer", "status", "reviewer", "updated_at")
    list_filter = ("status",)


@admin.register(IssueTicket)
class IssueTicketAdmin(admin.ModelAdmin):
    list_display = ("id", "kind", "title", "author", "visibility", "status", "updated_at")
    list_filter = ("kind", "visibility", "status")
    search_fields = ("title", "content")


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "author", "status", "updated_at")
    list_filter = ("status",)


@admin.register(TrickEntry)
class TrickEntryAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "author", "status", "updated_at")
    list_filter = ("status",)
    search_fields = ("title", "content_md", "author__username")


@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display = ("id", "display_id", "user", "profile_url", "is_active", "sort_order", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("display_id", "user__username", "profile_url")


@admin.register(FriendlyLink)
class FriendlyLinkAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "url", "created_by", "is_enabled", "order", "updated_at")
    list_filter = ("is_enabled",)
    search_fields = ("name", "description", "url", "created_by__username")


@admin.register(CompetitionNotice)
class CompetitionNoticeAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "series",
        "year",
        "stage",
        "created_by",
        "is_visible",
        "published_at",
        "updated_at",
    )
    list_filter = ("series", "stage", "year", "is_visible")
    search_fields = ("title", "content_md", "created_by__username")


@admin.register(CompetitionScheduleEntry)
class CompetitionScheduleEntryAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "event_date",
        "competition_time_range",
        "competition_type",
        "location",
        "qq_group",
        "announcement",
        "created_by",
        "updated_at",
    )
    list_filter = ("event_date",)
    search_fields = (
        "competition_type",
        "competition_time_range",
        "location",
        "qq_group",
        "announcement__title",
        "created_by__username",
    )


@admin.register(CompetitionPracticeLink)
class CompetitionPracticeLinkAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "year",
        "series",
        "stage",
        "short_name",
        "source_file",
        "display_order",
        "updated_at",
    )
    list_filter = ("series", "stage", "year", "source_file")
    search_fields = ("short_name", "official_name", "organizer", "practice_links_note", "source_section")


@admin.register(CompetitionPracticeLinkProposal)
class CompetitionPracticeLinkProposalAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "proposed_year",
        "proposed_series",
        "proposed_stage",
        "proposed_short_name",
        "proposer",
        "status",
        "reviewer",
        "updated_at",
    )
    list_filter = ("proposed_series", "proposed_stage", "proposed_year", "status")
    search_fields = ("proposed_short_name", "proposed_official_name", "reason", "review_note", "proposer__username")


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ("id", "question", "author", "is_accepted", "status", "updated_at")
    list_filter = ("is_accepted", "status")


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "created_by", "priority", "is_published", "start_at", "end_at")
    list_filter = ("is_published",)


@admin.register(AnnouncementRead)
class AnnouncementReadAdmin(admin.ModelAdmin):
    list_display = ("id", "announcement", "user", "created_at")


@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    list_display = ("id", "username_ci", "ip_address", "failure_count", "locked_until", "updated_at")
    search_fields = ("username_ci", "ip_address")
    list_filter = ("locked_until",)


@admin.register(SecurityAuditLog)
class SecurityAuditLogAdmin(admin.ModelAdmin):
    list_display = ("id", "event_type", "username", "ip_address", "success", "created_at")
    search_fields = ("username", "ip_address", "detail")
    list_filter = ("event_type", "success")


@admin.register(PasswordHistory)
class PasswordHistoryAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "created_at")
    search_fields = ("user__username",)


@admin.register(UserNotification)
class UserNotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "title", "level", "is_read", "created_at")
    list_filter = ("level", "is_read")
    search_fields = ("title", "content", "link")


@admin.register(ExtensionPage)
class ExtensionPageAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "slug", "access_level", "is_enabled", "updated_at")
    list_filter = ("access_level", "is_enabled")


@admin.register(ContributionEvent)
class ContributionEventAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "event_type", "target_type", "target_id", "created_at")
    list_filter = ("event_type",)
