from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AnnouncementViewSet,
    AdminOverviewView,
    AnswerViewSet,
    ArticleCommentViewSet,
    ArticleViewSet,
    CategoryViewSet,
    CompetitionCalendarEventViewSet,
    CompetitionNoticeViewSet,
    CompetitionPracticeLinkProposalViewSet,
    CompetitionPracticeLinkViewSet,
    CompetitionScheduleEntryViewSet,
    ContributionEventViewSet,
    ExtensionPageViewSet,
    FriendlyLinkViewSet,
    HealthCheckView,
    HomeSummaryView,
    IssueTicketViewSet,
    LoginView,
    LogoutView,
    ChangePasswordView,
    MeEventListView,
    MeSecurityEventListView,
    MeSecuritySummaryView,
    MeView,
    ImageUploadView,
    QuestionViewSet,
    RegisterView,
    RevisionProposalViewSet,
    SecurityAuditLogViewSet,
    TeamMemberViewSet,
    TrickEntryViewSet,
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
router.register(r"questions", QuestionViewSet, basename="question")
router.register(r"answers", AnswerViewSet, basename="answer")
router.register(r"announcements", AnnouncementViewSet, basename="announcement")
router.register(r"pages", ExtensionPageViewSet, basename="page")
router.register(r"users", UserManagementViewSet, basename="user-management")
router.register(r"notifications", UserNotificationViewSet, basename="notification")
router.register(r"security-logs", SecurityAuditLogViewSet, basename="security-log")
router.register(r"events", ContributionEventViewSet, basename="event")
router.register(r"team-members", TeamMemberViewSet, basename="team-member")
router.register(r"friendly-links", FriendlyLinkViewSet, basename="friendly-link")
router.register(r"competition-calendar", CompetitionCalendarEventViewSet, basename="competition-calendar")
router.register(r"competition-notices", CompetitionNoticeViewSet, basename="competition-notice")
router.register(r"competition-schedules", CompetitionScheduleEntryViewSet, basename="competition-schedule")
router.register(r"competition-practice-links", CompetitionPracticeLinkViewSet, basename="competition-practice-link")
router.register(r"competition-practice-proposals", CompetitionPracticeLinkProposalViewSet, basename="competition-practice-proposal")

urlpatterns = [
    path("health/", HealthCheckView.as_view(), name="health"),
    path("uploads/image/", ImageUploadView.as_view(), name="upload-image"),
    path("auth/register/", RegisterView.as_view(), name="auth-register"),
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("me/", MeView.as_view(), name="me"),
    path("me/events/", MeEventListView.as_view(), name="me-events"),
    path("me/security-events/", MeSecurityEventListView.as_view(), name="me-security-events"),
    path("me/security-summary/", MeSecuritySummaryView.as_view(), name="me-security-summary"),
    path("me/change-password/", ChangePasswordView.as_view(), name="me-change-password"),
    path("admin/overview/", AdminOverviewView.as_view(), name="admin-overview"),
    path("home/summary/", HomeSummaryView.as_view(), name="home-summary"),
    path("", include(router.urls)),
]
