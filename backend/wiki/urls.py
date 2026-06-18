from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AnnouncementViewSet,
    AdminOverviewView,
    AnswerViewSet,
    AIModerationConfigViewSet,
    AIModerationRecordViewSet,
    AssistantChatView,
    AssistantProviderConfigViewSet,
    AssistantPublicConfigView,
    CaptchaAdminOverviewView,
    CaptchaAuditLogViewSet,
    CaptchaPublicConfigView,
    ArticleCommentViewSet,
    ArticleViewSet,
    CategoryViewSet,
    CompetitionCalendarEventViewSet,
    CompetitionNoticeViewSet,
    CompetitionPracticeLinkProposalViewSet,
    CompetitionPracticeLinkViewSet,
    CompetitionScheduleEntryViewSet,
    CompetitionZoneSectionViewSet,
    ContributionEventViewSet,
    ContributionRankingView,
    DeletedContentArchiveViewSet,
    ChangePasswordCodeView,
    DocumentPageSectionViewSet,
    EmailChangeCodeView,
    EmailChangeView,
    ExtensionPageViewSet,
    FriendlyLinkViewSet,
    GalleryImageFolderViewSet,
    GalleryImageViewSet,
    GlobalSearchView,
    HeaderNavigationItemViewSet,
    HealthCheckView,
    HomeSummaryView,
    InvitationRecordViewSet,
    IssueTicketViewSet,
    LoginView,
    LogoutView,
    MomentAuditLogViewSet,
    MomentCommentViewSet,
    MomentImageViewSet,
    MomentOverviewView,
    MomentReportViewSet,
    MomentSettingsViewSet,
    MomentUserRestrictionViewSet,
    MomentViewSet,
    MeCompetitionNoticeListView,
    MeCompetitionPracticeProposalListView,
    ChangePasswordView,
    MeAccountCancellationView,
    MeEventListView,
    MeInvitationView,
    MeSecurityEventListView,
    MeSecuritySummaryView,
    MeTrickContributionView,
    MeTrickListView,
    MeTrickResubmitDeletedView,
    MeView,
    ImageUploadView,
    PasswordResetCodeView,
    PasswordResetView,
    PhoneVerificationViewSet,
    QuestionViewSet,
    RealNameVerificationViewSet,
    RegisterEmailCodeView,
    RegisterView,
    RevisionProposalViewSet,
    SchoolSurveySchoolViewSet,
    SchoolSurveySubmissionViewSet,
    SecurityAuditLogViewSet,
    TeamMemberViewSet,
    TrickEntryViewSet,
    TrickTermSuggestionViewSet,
    TrickTermViewSet,
    SiteVisitStatsView,
    SiteVisitTrackView,
    UserNotificationViewSet,
    UserManagementViewSet,
)

router = DefaultRouter()
router.register(r"categories", CategoryViewSet, basename="category")
router.register(r"articles", ArticleViewSet, basename="article")
router.register(r"comments", ArticleCommentViewSet, basename="comment")
router.register(r"revisions", RevisionProposalViewSet, basename="revision")
router.register(r"issues", IssueTicketViewSet, basename="issue")
router.register(r"tricks", TrickEntryViewSet, basename="trick")
router.register(r"trick-terms", TrickTermViewSet, basename="trick-term")
router.register(
    r"trick-term-suggestions",
    TrickTermSuggestionViewSet,
    basename="trick-term-suggestion",
)
router.register(r"questions", QuestionViewSet, basename="question")
router.register(r"answers", AnswerViewSet, basename="answer")
router.register(r"moments", MomentViewSet, basename="moment")
router.register(r"moment-images", MomentImageViewSet, basename="moment-image")
router.register(r"moment-comments", MomentCommentViewSet, basename="moment-comment")
router.register(r"moment-reports", MomentReportViewSet, basename="moment-report")
router.register(r"moment-settings", MomentSettingsViewSet, basename="moment-settings")
router.register(
    r"moment-restrictions",
    MomentUserRestrictionViewSet,
    basename="moment-restriction",
)
router.register(r"moment-audit-logs", MomentAuditLogViewSet, basename="moment-audit-log")
router.register(
    r"real-name-verifications",
    RealNameVerificationViewSet,
    basename="real-name-verification",
)
router.register(
    r"phone-verifications",
    PhoneVerificationViewSet,
    basename="phone-verification",
)
router.register(r"announcements", AnnouncementViewSet, basename="announcement")
router.register(r"pages", ExtensionPageViewSet, basename="page")
router.register(
    r"document-page-sections",
    DocumentPageSectionViewSet,
    basename="document-page-section",
)
router.register(r"users", UserManagementViewSet, basename="user-management")
router.register(r"notifications", UserNotificationViewSet, basename="notification")
router.register(r"security-logs", SecurityAuditLogViewSet, basename="security-log")
router.register(r"captcha-audit-logs", CaptchaAuditLogViewSet, basename="captcha-audit-log")
router.register(r"events", ContributionEventViewSet, basename="event")
router.register(r"invitations", InvitationRecordViewSet, basename="invitation")
router.register(
    r"deleted-content-archives",
    DeletedContentArchiveViewSet,
    basename="deleted-content-archive",
)
router.register(r"team-members", TeamMemberViewSet, basename="team-member")
router.register(r"friendly-links", FriendlyLinkViewSet, basename="friendly-link")
router.register(r"gallery-folders", GalleryImageFolderViewSet, basename="gallery-folder")
router.register(r"gallery-images", GalleryImageViewSet, basename="gallery-image")
router.register(r"header-nav", HeaderNavigationItemViewSet, basename="header-nav")
router.register(
    r"competition-calendar",
    CompetitionCalendarEventViewSet,
    basename="competition-calendar",
)
router.register(
    r"competition-notices", CompetitionNoticeViewSet, basename="competition-notice"
)
router.register(
    r"competition-schedules",
    CompetitionScheduleEntryViewSet,
    basename="competition-schedule",
)
router.register(
    r"competition-practice-links",
    CompetitionPracticeLinkViewSet,
    basename="competition-practice-link",
)
router.register(
    r"competition-practice-proposals",
    CompetitionPracticeLinkProposalViewSet,
    basename="competition-practice-proposal",
)
router.register(
    r"competition-zone-sections",
    CompetitionZoneSectionViewSet,
    basename="competition-zone-section",
)
router.register(
    r"school-survey-schools",
    SchoolSurveySchoolViewSet,
    basename="school-survey-school",
)
router.register(
    r"school-survey-submissions",
    SchoolSurveySubmissionViewSet,
    basename="school-survey-submission",
)
router.register(
    r"assistant-configs", AssistantProviderConfigViewSet, basename="assistant-config"
)
router.register(
    r"ai-moderation-configs",
    AIModerationConfigViewSet,
    basename="ai-moderation-config",
)
router.register(
    r"ai-moderation-records",
    AIModerationRecordViewSet,
    basename="ai-moderation-record",
)

urlpatterns = [
    path("health/", HealthCheckView.as_view(), name="health"),
    path("captcha/config/", CaptchaPublicConfigView.as_view(), name="captcha-public-config"),
    path(
        "admin/captcha/overview/",
        CaptchaAdminOverviewView.as_view(),
        name="captcha-admin-overview",
    ),
    path(
        "assistant/config/",
        AssistantPublicConfigView.as_view(),
        name="assistant-public-config",
    ),
    path("assistant/chat/", AssistantChatView.as_view(), name="assistant-chat"),
    path("search/", GlobalSearchView.as_view(), name="global-search"),
    path("site-visits/track/", SiteVisitTrackView.as_view(), name="site-visit-track"),
    path("site-visits/stats/", SiteVisitStatsView.as_view(), name="site-visit-stats"),
    path("contribution-rankings/", ContributionRankingView.as_view(), name="contribution-rankings"),
    path("moments/overview/", MomentOverviewView.as_view(), name="moment-overview"),
    path("uploads/image/", ImageUploadView.as_view(), name="upload-image"),
    path(
        "auth/register-email-code/",
        RegisterEmailCodeView.as_view(),
        name="auth-register-email-code",
    ),
    path("auth/register/", RegisterView.as_view(), name="auth-register"),
    path(
        "auth/password-reset-code/",
        PasswordResetCodeView.as_view(),
        name="auth-password-reset-code",
    ),
    path(
        "auth/password-reset/", PasswordResetView.as_view(), name="auth-password-reset"
    ),
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("me/", MeView.as_view(), name="me"),
    path("me/invitations/", MeInvitationView.as_view(), name="me-invitations"),
    path(
        "me/cancel-account/",
        MeAccountCancellationView.as_view(),
        name="me-cancel-account",
    ),
    path("me/tricks/", MeTrickListView.as_view(), name="me-tricks"),
    path(
        "me/trick-contribution/",
        MeTrickContributionView.as_view(),
        name="me-trick-contribution",
    ),
    path(
        "me/tricks/resubmit-deleted/",
        MeTrickResubmitDeletedView.as_view(),
        name="me-tricks-resubmit-deleted",
    ),
    path(
        "me/competition-notices/",
        MeCompetitionNoticeListView.as_view(),
        name="me-competition-notices",
    ),
    path(
        "me/competition-practice-proposals/",
        MeCompetitionPracticeProposalListView.as_view(),
        name="me-competition-practice-proposals",
    ),
    path("me/email-code/", EmailChangeCodeView.as_view(), name="me-email-code"),
    path("me/change-email/", EmailChangeView.as_view(), name="me-change-email"),
    path(
        "me/change-password-code/",
        ChangePasswordCodeView.as_view(),
        name="me-change-password-code",
    ),
    path("me/events/", MeEventListView.as_view(), name="me-events"),
    path(
        "me/security-events/",
        MeSecurityEventListView.as_view(),
        name="me-security-events",
    ),
    path(
        "me/security-summary/",
        MeSecuritySummaryView.as_view(),
        name="me-security-summary",
    ),
    path(
        "me/change-password/", ChangePasswordView.as_view(), name="me-change-password"
    ),
    path("admin/overview/", AdminOverviewView.as_view(), name="admin-overview"),
    path("home/summary/", HomeSummaryView.as_view(), name="home-summary"),
    path("", include(router.urls)),
]
