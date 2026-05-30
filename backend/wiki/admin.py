from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

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
    LoginAttempt,
    Moment,
    MomentAuditLog,
    MomentComment,
    MomentFavorite,
    MomentImage,
    MomentLike,
    MomentReport,
    MomentSettings,
    MomentUserRestriction,
    PasswordHistory,
    PhoneVerification,
    PhoneVerificationTicket,
    Question,
    RealNameVerification,
    RevisionProposal,
    SecurityAuditLog,
    SiteVisitDailyStat,
    TeamMember,
    TrickContributionEvent,
    TrickEntry,
    TrickEntryDownvote,
    TrickEntryLike,
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
                "email_verified_at",
                "trick_contribution_score",
                )
            },
        ),
    )
    list_display = (
        "id",
        "username",
        "email",
        "role",
        "trick_contribution_score",
        "is_active",
        "is_banned",
        "date_joined",
        "email_verified_at",
    )
    list_filter = ("role", "is_active", "is_banned", "email_verified_at")


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
        "display_order",
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


@admin.register(TrickEntryLike)
class TrickEntryLikeAdmin(admin.ModelAdmin):
    list_display = ("id", "trick_entry", "user", "created_at")
    search_fields = ("trick_entry__title", "user__username")


@admin.register(TrickEntryDownvote)
class TrickEntryDownvoteAdmin(admin.ModelAdmin):
    list_display = ("id", "trick_entry", "user", "rewarded_at", "created_at")
    search_fields = ("trick_entry__title", "user__username")
    list_filter = ("rewarded_at",)


@admin.register(TrickContributionEvent)
class TrickContributionEventAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "action_type",
        "delta",
        "balance_after",
        "trick_title",
        "actor",
        "created_at",
    )
    list_filter = ("action_type", "is_rollback", "created_at")
    search_fields = ("user__username", "actor__username", "trick_title", "event_key")


@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display = ("id", "display_id", "user", "profile_url", "is_active", "sort_order", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("display_id", "user__username", "profile_url")


@admin.register(GalleryImageFolder)
class GalleryImageFolderAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "slug", "display_order", "is_visible", "updated_at")
    list_filter = ("is_visible",)
    search_fields = ("name", "slug", "description")


@admin.register(GalleryImage)
class GalleryImageAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "original_name",
        "folder",
        "status",
        "size_bytes",
        "uploaded_by",
        "deleted_at",
        "delete_after",
    )
    list_filter = ("status", "folder")
    search_fields = ("original_name", "image", "original_path", "recycled_path")


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
        "end_date",
        "competition_time_range",
        "competition_type",
        "location",
        "qq_group",
        "announcement",
        "created_by",
        "updated_at",
    )
    list_filter = ("event_date", "end_date")
    search_fields = (
        "competition_type",
        "competition_time_range",
        "location",
        "qq_group",
        "announcement__title",
        "created_by__username",
    )


@admin.register(DeletedContentArchive)
class DeletedContentArchiveAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "target_type",
        "target_id",
        "delete_action",
        "title",
        "original_author_name",
        "deleted_by_name",
        "created_at",
    )
    list_filter = ("target_type", "delete_action", "created_at")
    search_fields = (
        "title",
        "summary",
        "content_md",
        "original_author_name",
        "deleted_by_name",
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


@admin.register(CompetitionCalendarEvent)
class CompetitionCalendarEventAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "source_site",
        "source_id",
        "title",
        "start_time",
        "end_time",
        "duration_seconds",
        "last_synced_at",
    )
    list_filter = ("source_site", "start_time", "end_time")
    search_fields = ("source_id", "title", "organizer", "url")


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


@admin.register(SiteVisitDailyStat)
class SiteVisitDailyStatAdmin(admin.ModelAdmin):
    list_display = ("date", "page_views", "updated_at")
    list_filter = ("date",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(PasswordHistory)
class PasswordHistoryAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "created_at")
    search_fields = ("user__username",)


@admin.register(EmailVerificationTicket)
class EmailVerificationTicketAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "purpose",
        "email",
        "user",
        "verify_attempt_count",
        "expires_at",
        "consumed_at",
        "created_at",
    )
    list_filter = ("purpose", "expires_at", "consumed_at")
    search_fields = ("email", "user__username", "username_snapshot", "created_ip")


@admin.register(UserNotification)
class UserNotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "title", "level", "is_read", "created_at")
    list_filter = ("level", "is_read")
    search_fields = ("title", "content", "link")


@admin.register(ExtensionPage)
class ExtensionPageAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "slug", "access_level", "is_enabled", "updated_at")
    list_filter = ("access_level", "is_enabled")


@admin.register(CompetitionZoneSection)
class CompetitionZoneSectionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "key",
        "target_type",
        "builtin_view",
        "page",
        "display_order",
        "is_visible",
        "updated_at",
    )
    list_filter = ("target_type", "builtin_view", "is_visible")
    search_fields = ("title", "key", "page__title", "page__slug")


@admin.register(DocumentPageSection)
class DocumentPageSectionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "key",
        "page",
        "display_order",
        "is_visible",
        "updated_at",
    )
    list_filter = ("is_visible",)
    search_fields = ("title", "key", "page__title", "page__slug")


@admin.register(HeaderNavigationItem)
class HeaderNavigationItemAdmin(admin.ModelAdmin):
    list_display = ("id", "key", "title", "display_order", "is_visible", "updated_at")
    list_filter = ("is_visible", "key")
    search_fields = ("key", "title")


@admin.register(AssistantProviderConfig)
class AssistantProviderConfigAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "label",
        "assistant_name",
        "provider",
        "model_name",
        "is_enabled",
        "is_default",
        "show_launcher",
        "updated_at",
        "last_tested_at",
        "last_test_success",
    )
    list_filter = ("provider", "is_enabled", "is_default", "show_launcher", "last_test_success")
    search_fields = ("label", "assistant_name", "model_name", "base_url")
    exclude = ("api_key_encrypted",)


@admin.register(AssistantInteractionLog)
class AssistantInteractionLogAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "config",
        "provider",
        "model_name",
        "user",
        "success",
        "total_tokens",
        "source_count",
        "response_ms",
        "created_at",
    )
    list_filter = ("provider", "success", "created_at")
    search_fields = ("model_name", "session_id", "ip_address", "error_message")


@admin.register(AIModerationConfig)
class AIModerationConfigAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "label",
        "provider",
        "model_name",
        "is_enabled",
        "comment_enabled",
        "question_enabled",
        "answer_enabled",
        "ticket_enabled",
        "moment_enabled",
        "moment_comment_enabled",
        "updated_at",
    )
    list_filter = (
        "provider",
        "is_enabled",
        "comment_enabled",
        "question_enabled",
        "answer_enabled",
        "ticket_enabled",
        "moment_enabled",
        "moment_comment_enabled",
    )
    search_fields = ("label", "model_name", "base_url")
    exclude = ("api_key_encrypted",)


@admin.register(AIModerationRecord)
class AIModerationRecordAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "target_type",
        "target_id",
        "author",
        "decision",
        "risk_level",
        "status",
        "model_name",
        "created_at",
    )
    list_filter = ("target_type", "decision", "risk_level", "status", "created_at")
    search_fields = ("summary", "user_notice", "error_message", "author__username")
    readonly_fields = (
        "config",
        "target_type",
        "target_id",
        "author",
        "provider",
        "model_name",
        "decision",
        "risk_level",
        "categories",
        "summary",
        "user_notice",
        "raw_response",
        "prompt_chars",
        "response_chars",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "response_ms",
        "status",
        "error_message",
        "created_at",
    )


@admin.register(RealNameVerification)
class RealNameVerificationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "status", "real_name_masked", "id_number_last4", "verified_at", "updated_at")
    list_filter = ("status", "provider", "verified_at")
    search_fields = ("user__username", "real_name_masked", "id_number_last4", "provider_trace_id")


@admin.register(PhoneVerification)
class PhoneVerificationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "status", "phone_masked", "phone_last4", "verified_at", "updated_at")
    list_filter = ("status", "provider", "verified_at")
    search_fields = ("user__username", "phone_masked", "phone_last4", "provider_out_id", "provider_biz_id")


@admin.register(PhoneVerificationTicket)
class PhoneVerificationTicketAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "phone_masked", "provider", "provider_out_id", "expires_at", "consumed_at")
    list_filter = ("provider", "expires_at", "consumed_at")
    search_fields = ("user__username", "phone_masked", "phone_last4", "provider_out_id", "provider_biz_id")


@admin.register(MomentSettings)
class MomentSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "is_enabled",
        "publishing_enabled",
        "commenting_enabled",
        "hot_list_enabled",
        "featured_feed_enabled",
        "require_real_name",
        "updated_at",
    )


@admin.register(Moment)
class MomentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "author",
        "status",
        "like_count",
        "favorite_count",
        "comment_count",
        "report_count",
        "allow_hot",
        "is_featured",
        "published_at",
    )
    list_filter = ("status", "allow_hot", "is_featured", "comments_locked", "published_at")
    search_fields = ("content", "author__username", "review_note", "hidden_reason")


@admin.register(MomentImage)
class MomentImageAdmin(admin.ModelAdmin):
    list_display = ("id", "moment", "status", "original_name", "size_bytes", "uploaded_by", "created_at")
    list_filter = ("status", "content_type")
    search_fields = ("original_name", "image", "moderation_summary", "uploaded_by__username")


@admin.register(MomentComment)
class MomentCommentAdmin(admin.ModelAdmin):
    list_display = ("id", "moment", "author", "status", "report_count", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("content", "author__username", "review_note")


@admin.register(MomentLike)
class MomentLikeAdmin(admin.ModelAdmin):
    list_display = ("id", "moment", "user", "created_at")
    search_fields = ("moment__content", "user__username")


@admin.register(MomentFavorite)
class MomentFavoriteAdmin(admin.ModelAdmin):
    list_display = ("id", "moment", "user", "created_at")
    search_fields = ("moment__content", "user__username")


@admin.register(MomentReport)
class MomentReportAdmin(admin.ModelAdmin):
    list_display = ("id", "target_type", "reason", "status", "reporter", "target_author", "created_at")
    list_filter = ("target_type", "reason", "status", "created_at")
    search_fields = ("description", "reporter__username", "target_author__username", "resolution_note")


@admin.register(MomentUserRestriction)
class MomentUserRestrictionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "can_post",
        "can_comment",
        "can_react",
        "can_upload_images",
        "can_enter_hot",
        "muted_until",
    )
    list_filter = ("can_post", "can_comment", "can_react", "can_upload_images", "can_enter_hot")
    search_fields = ("user__username", "reason")


@admin.register(MomentAuditLog)
class MomentAuditLogAdmin(admin.ModelAdmin):
    list_display = ("id", "event_type", "actor", "target_user", "target_type", "target_id", "created_at")
    list_filter = ("event_type", "target_type", "created_at")
    search_fields = ("actor__username", "target_user__username", "target_type")
    readonly_fields = ("actor", "target_user", "event_type", "target_type", "target_id", "payload", "created_at")


@admin.register(ContributionEvent)
class ContributionEventAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "event_type", "target_type", "target_id", "created_at")
    list_filter = ("event_type",)
