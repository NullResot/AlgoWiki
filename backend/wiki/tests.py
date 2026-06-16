import json
import io
import re
import tempfile
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient, APIRequestFactory, APITestCase
from django.utils import timezone
from PIL import Image

from .assistant import build_chat_messages_compact, clear_public_corpus_cache
from .models import (
    Announcement,
    Answer,
    AIModerationConfig,
    AIModerationRecord,
    Article,
    ArticleComment,
    ArticleStar,
    AssistantInteractionLog,
    AssistantProviderConfig,
    Category,
    CompetitionZoneSection,
    CompetitionCalendarEvent,
    CompetitionNotice,
    CompetitionPracticeLink,
    CompetitionPracticeLinkProposal,
    CompetitionScheduleEntry,
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
    MomentComment,
    MomentImage,
    MomentReport,
    MomentSettings,
    Question,
    RevisionProposal,
    SchoolSurveySchool,
    SchoolSurveySubmission,
    SecurityAuditLog,
    CaptchaAuditLog,
    SiteVisitDailyStat,
    TeamMember,
    TrickContributionEvent,
    TrickEntry,
    TrickEntryDownvote,
    TrickEntryLike,
    TrickTerm,
    TrickTermSuggestion,
    PasswordHistory,
    UserNotification,
    LoginAttempt,
    PhoneVerification,
    PhoneVerificationTicket,
    RealNameVerification,
    User,
)
from .competition_calendar import NormalizedCompetitionEvent
from .trick_terms import FIXED_TRICK_TERM_NAMES
from .real_name_providers import (
    start_aliyun_real_name_verification,
    sync_aliyun_real_name_verification,
)
from .phone_verification_providers import (
    PhoneVerificationProviderError,
    _call_with_failover,
    build_phone_digest,
    check_aliyun_phone_verification,
    load_phone_ticket_from_token,
    normalize_phone_context,
    start_aliyun_phone_verification,
)


def make_test_image_bytes(*, image_format="PNG", size=(2, 2), color=(255, 255, 255)):
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, format=image_format)
    return buffer.getvalue()


def make_test_image_upload(
    name="tiny.png",
    *,
    image_format="PNG",
    content_type="image/png",
    size=(2, 2),
    color=(255, 255, 255),
):
    return SimpleUploadedFile(
        name,
        make_test_image_bytes(image_format=image_format, size=size, color=color),
        content_type=content_type,
    )
from .serializers import (
    AccountCancellationSerializer,
    ArticleCommentSerializer,
    ArticleSerializer,
    RevisionProposalSerializer,
)


class SchoolSurveyApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="survey_user",
            email="survey_user@example.com",
            password="Password123",
            role=User.Role.NORMAL,
        )
        self.other_user = User.objects.create_user(
            username="survey_reader",
            email="survey_reader@example.com",
            password="Password123",
            role=User.Role.NORMAL,
        )
        self.admin = User.objects.create_user(
            username="survey_admin",
            email="survey_admin@example.com",
            password="Password123",
            role=User.Role.ADMIN,
        )
        self.school = SchoolSurveySchool.objects.create(
            name="测试大学",
            abbreviation="TDU",
            province="测试省",
            city="测试市",
            display_order=1,
        )

    def authenticate(self, user=None):
        user = user or self.user
        self.client.force_authenticate(user=user)

    def test_school_search_lists_universities(self):
        response = self.client.get("/api/school-survey-schools/?search=测试")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["name"], "测试大学")

    def test_school_search_lists_other_school_types(self):
        SchoolSurveySchool.objects.create(
            name="测试职业技术学院",
            abbreviation="TVTC",
            province="测试省",
            city="测试市",
            school_type=SchoolSurveySchool.SchoolType.OTHER,
            display_order=2,
        )

        response = self.client.get("/api/school-survey-schools/?search=职业")

        self.assertEqual(response.status_code, 200)
        self.assertIn("测试职业技术学院", [item["name"] for item in response.data])

    def test_school_search_omits_inactive_schools(self):
        SchoolSurveySchool.objects.create(
            name="隐藏测试大学",
            abbreviation="HDU",
            province="测试省",
            city="测试市",
            display_order=2,
            is_active=False,
        )

        response = self.client.get("/api/school-survey-schools/?search=测试")

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["name"] for item in response.data], ["测试大学"])

    def test_school_list_orders_by_submitted_count_then_abbreviation(self):
        alpha_school = SchoolSurveySchool.objects.create(
            name="Alpha Institute",
            abbreviation="AI",
            display_order=999,
        )
        beta_school = SchoolSurveySchool.objects.create(
            name="Beta College",
            abbreviation="BC",
            display_order=0,
        )
        gamma_school = SchoolSurveySchool.objects.create(
            name="Gamma University",
            abbreviation="GU",
            display_order=0,
        )
        for school in (alpha_school, beta_school, gamma_school):
            SchoolSurveySubmission.objects.create(
                school=school,
                author=self.user,
                status=SchoolSurveySubmission.Status.SUBMITTED,
                submitted_at=timezone.now(),
                form_data={"school_name": school.name},
            )
        SchoolSurveySubmission.objects.create(
            school=gamma_school,
            author=self.other_user,
            status=SchoolSurveySubmission.Status.SUBMITTED,
            submitted_at=timezone.now(),
            form_data={"school_name": gamma_school.name},
        )

        response = self.client.get("/api/school-survey-schools/")

        self.assertEqual(response.status_code, 200)
        names = [item["name"] for item in response.data]
        self.assertLess(names.index("Gamma University"), names.index("Alpha Institute"))
        self.assertLess(names.index("Alpha Institute"), names.index("Beta College"))

    def test_normal_user_cannot_create_school(self):
        self.authenticate()

        response = self.client.post(
            "/api/school-survey-schools/",
            {"name": "普通用户新增学校"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(SchoolSurveySchool.objects.filter(name="普通用户新增学校").exists())

    def test_admin_can_create_school(self):
        self.authenticate(self.admin)

        response = self.client.post(
            "/api/school-survey-schools/",
            {
                "name": "管理员新增职业学院",
                "abbreviation": "AVC",
                "province": "测试省",
                "city": "测试市",
                "school_type": SchoolSurveySchool.SchoolType.OTHER,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        school = SchoolSurveySchool.objects.get(name="管理员新增职业学院")
        self.assertTrue(school.is_active)
        self.assertEqual(school.school_type, SchoolSurveySchool.SchoolType.OTHER)

    def test_admin_reactivates_existing_hidden_school(self):
        hidden = SchoolSurveySchool.objects.create(
            name="已隐藏学校",
            abbreviation="OLD",
            is_active=False,
            school_type=SchoolSurveySchool.SchoolType.UNIVERSITY,
        )
        self.authenticate(self.admin)

        response = self.client.post(
            "/api/school-survey-schools/",
            {
                "name": hidden.name,
                "abbreviation": "NEW",
                "school_type": SchoolSurveySchool.SchoolType.OTHER,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        hidden.refresh_from_db()
        self.assertTrue(hidden.is_active)
        self.assertEqual(hidden.abbreviation, "NEW")
        self.assertEqual(hidden.school_type, SchoolSurveySchool.SchoolType.OTHER)

    def test_my_draft_creates_single_reusable_draft(self):
        self.authenticate()

        first = self.client.get(
            f"/api/school-survey-submissions/my-draft/?school={self.school.id}"
        )
        second = self.client.get(
            f"/api/school-survey-submissions/my-draft/?school={self.school.id}"
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.data["id"], second.data["id"])
        self.assertEqual(
            SchoolSurveySubmission.objects.filter(
                author=self.user,
                school=self.school,
                status=SchoolSurveySubmission.Status.DRAFT,
            ).count(),
            1,
        )

    def test_my_draft_allows_other_school_type(self):
        other_school = SchoolSurveySchool.objects.create(
            name="草稿职业技术学院",
            school_type=SchoolSurveySchool.SchoolType.OTHER,
        )
        self.authenticate()

        response = self.client.get(
            f"/api/school-survey-submissions/my-draft/?school={other_school.id}"
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["school"], other_school.id)

    def test_submit_draft_creates_submitted_history_record(self):
        self.authenticate()
        draft = SchoolSurveySubmission.objects.create(
            school=self.school,
            author=self.user,
            form_data={"school_name": "测试大学", "submitter_contact": "123456"},
        )

        response = self.client.post(
            f"/api/school-survey-submissions/{draft.id}/submit/",
            {"form_data": {"school_name": "测试大学", "submitter_contact": "123456"}},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        draft.refresh_from_db()
        self.assertEqual(draft.status, SchoolSurveySubmission.Status.SUBMITTED)
        self.assertIsNotNone(draft.submitted_at)

    def test_submission_detail_redacts_private_contact_for_other_users(self):
        submission = SchoolSurveySubmission.objects.create(
            school=self.school,
            author=self.user,
            status=SchoolSurveySubmission.Status.SUBMITTED,
            submitted_at=timezone.now(),
            form_data={
                "school_name": "测试大学",
                "submitter_identity": "队员",
                "submitter_contact": "survey_user@example.com",
            },
        )
        self.authenticate(self.other_user)

        response = self.client.get(f"/api/school-survey-submissions/{submission.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["form_data"]["school_name"], "测试大学")
        self.assertNotEqual(
            response.data["form_data"]["submitter_contact"],
            "survey_user@example.com",
        )


@override_settings(
    CAPTCHA_ENABLED=True,
    SECONDARY_CAPTCHA_ENABLED=False,
    TURNSTILE_SECRET_KEY="test-secret",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class CaptchaProtectedApiTests(APITestCase):
    def setUp(self):
        cache.clear()
        mail.outbox = []
        self.temp_media_dir = tempfile.TemporaryDirectory()
        self.media_override = override_settings(
            MEDIA_ROOT=self.temp_media_dir.name,
            MEDIA_URL="/media/",
            IMAGE_MODERATION_PROVIDER="disabled",
        )
        self.media_override.enable()

    def tearDown(self):
        self.media_override.disable()
        self.temp_media_dir.cleanup()

    def captcha_payload(self, token="turnstile-token"):
        return {
            "scene": "send_email_code",
            "turnstile_token": token,
        }

    @override_settings(
        TURNSTILE_SITE_KEY="public-site-key",
        TURNSTILE_SECRET_KEY="server-secret-key",
        SECONDARY_CAPTCHA_ENABLED=True,
        SECONDARY_CAPTCHA_PROVIDER="geetest",
        GEETEST_CAPTCHA_ID="public-geetest-id",
        GEETEST_CAPTCHA_KEY="server-geetest-key",
    )
    def test_public_captcha_config_exposes_only_public_values(self):
        response = self.client.get("/api/captcha/config/")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["enabled"])
        self.assertEqual(response.data["turnstile_site_key"], "public-site-key")
        self.assertTrue(response.data["secondary_enabled"])
        self.assertEqual(response.data["secondary_provider"], "geetest")
        self.assertEqual(response.data["geetest_captcha_id"], "public-geetest-id")
        self.assertNotIn("turnstile_secret_key", response.data)
        self.assertNotIn("geetest_captcha_key", response.data)

    @override_settings(
        TURNSTILE_SITE_KEY="public-site-key",
        TURNSTILE_SECRET_KEY="server-secret-key",
        SECONDARY_CAPTCHA_ENABLED=False,
    )
    def test_admin_captcha_overview_reports_configuration_status(self):
        admin = User.objects.create_user(
            username="captcha_admin",
            password="Password123",
            role=User.Role.ADMIN,
        )
        token = Token.objects.create(user=admin)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        response = self.client.get("/api/admin/captcha/overview/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["config"]["status"], "ok")
        self.assertTrue(response.data["config"]["turnstile"]["site_key_configured"])
        self.assertTrue(response.data["config"]["turnstile"]["secret_key_configured"])
        self.assertNotIn("server-secret-key", str(response.data))

    @override_settings(TURNSTILE_SITE_KEY="", TURNSTILE_SECRET_KEY="")
    def test_admin_captcha_overview_reports_missing_turnstile_config(self):
        admin = User.objects.create_user(
            username="captcha_admin_missing",
            password="Password123",
            role=User.Role.ADMIN,
        )
        token = Token.objects.create(user=admin)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        response = self.client.get("/api/admin/captcha/overview/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["config"]["status"], "misconfigured")
        self.assertFalse(response.data["config"]["turnstile"]["site_key_configured"])
        self.assertFalse(response.data["config"]["turnstile"]["secret_key_configured"])
        self.assertGreaterEqual(len(response.data["config"]["issues"]), 2)

    def test_captcha_audit_logs_require_admin_and_support_summary_filters(self):
        admin = User.objects.create_user(
            username="captcha_log_admin",
            password="Password123",
            role=User.Role.ADMIN,
        )
        normal = User.objects.create_user(
            username="captcha_log_normal",
            password="Password123",
            role=User.Role.NORMAL,
        )
        admin_token = Token.objects.create(user=admin)
        normal_token = Token.objects.create(user=normal)
        CaptchaAuditLog.objects.create(
            scene="upload_image",
            user=normal,
            ip_address="127.0.0.9",
            target_type="user",
            target_hash="hash-1",
            result="failed",
            error_code="CAPTCHA_INVALID",
            error_message="invalid captcha",
        )
        CaptchaAuditLog.objects.create(
            scene="school_survey_submit",
            user=normal,
            ip_address="127.0.0.10",
            target_type="school_survey",
            target_hash="hash-2",
            turnstile_success=True,
            result="success",
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {normal_token.key}")
        forbidden = self.client.get("/api/captcha-audit-logs/")
        self.assertEqual(forbidden.status_code, 403)

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {admin_token.key}")
        logs = self.client.get(
            "/api/captcha-audit-logs/",
            {"result": "failed", "scene": "upload_image"},
        )
        self.assertEqual(logs.status_code, 200)
        self.assertEqual(logs.data["count"], 1)
        self.assertEqual(logs.data["results"][0]["error_code"], "CAPTCHA_INVALID")

        summary = self.client.get(
            "/api/captcha-audit-logs/summary/",
            {"window_hours": 24},
        )
        self.assertEqual(summary.status_code, 200)
        self.assertEqual(summary.data["totals"]["failed"], 1)
        self.assertTrue(
            any(item["error_code"] == "CAPTCHA_INVALID" for item in summary.data["by_error_code"])
        )

    def request_register_email_code(self, captcha=None, *, username="captcha_user", email="captcha_user@example.com"):
        payload = {
            "username": username,
            "email": email,
            "password": "CaptchaTest-93Kp!v2",
            "school_name": "测试大学",
        }
        if captcha is not None:
            payload["captcha"] = captcha
        return self.client.post("/api/auth/register-email-code/", payload, format="json")

    def test_missing_captcha_is_rejected_before_email_send(self):
        response = self.request_register_email_code()

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "CAPTCHA_REQUIRED")
        self.assertEqual(len(mail.outbox), 0)
        self.assertTrue(
            CaptchaAuditLog.objects.filter(
                scene="send_email_code",
                result="failed",
                error_code="CAPTCHA_REQUIRED",
            ).exists()
        )

    @patch("wiki.captcha.TurnstileValidator.verify", return_value={"success": True})
    def test_valid_turnstile_allows_email_send_and_writes_audit(self, _verify):
        response = self.request_register_email_code(self.captcha_payload())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(
            CaptchaAuditLog.objects.filter(
                scene="send_email_code",
                result="success",
                turnstile_success=True,
                target_type="email",
            ).exists()
        )

    @patch("wiki.captcha.TurnstileValidator.verify", return_value={"success": True})
    def test_reused_turnstile_token_is_rejected(self, _verify):
        first = self.request_register_email_code(self.captcha_payload("same-token"))
        second = self.request_register_email_code(
            self.captcha_payload("same-token"),
            username="captcha_user_2",
            email="captcha_user_2@example.com",
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 400)
        self.assertEqual(second.data["code"], "CAPTCHA_DUPLICATED")
        self.assertEqual(len(mail.outbox), 1)

    @patch("wiki.captcha.TurnstileValidator.verify", return_value={"success": True})
    def test_multipart_image_upload_accepts_json_string_captcha(self, _verify):
        admin = User.objects.create_user(
            username="captcha_upload_admin",
            password="Password123",
            role=User.Role.ADMIN,
        )
        token = Token.objects.create(user=admin)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        upload = make_test_image_upload("captcha-upload.png")
        captcha = {
            "scene": "upload_image",
            "turnstile_token": "multipart-upload-token",
        }

        response = self.client.post(
            "/api/uploads/image/",
            {"image": upload, "captcha": json.dumps(captcha)},
            format="multipart",
        )

        self.assertEqual(response.status_code, 201)
        self.assertIn("url", response.data)
        self.assertTrue(
            CaptchaAuditLog.objects.filter(
                scene="upload_image",
                result="success",
                target_type="user",
            ).exists()
        )

    @patch("wiki.captcha.TurnstileValidator.verify", return_value={"success": True})
    def test_gallery_upload_requires_captcha_and_accepts_json_string(self, _verify):
        admin = User.objects.create_user(
            username="captcha_gallery_admin",
            password="Password123",
            role=User.Role.ADMIN,
        )
        token = Token.objects.create(user=admin)
        folder = GalleryImageFolder.objects.create(name="验证码图库", slug="captcha-gallery")
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        missing = self.client.post(
            "/api/gallery-images/upload/",
            {"image": make_test_image_upload("missing.png"), "folder": folder.id},
            format="multipart",
        )
        self.assertEqual(missing.status_code, 400)
        self.assertEqual(missing.data["code"], "CAPTCHA_REQUIRED")

        captcha = {
            "scene": "upload_image",
            "turnstile_token": "gallery-upload-token",
        }
        response = self.client.post(
            "/api/gallery-images/upload/",
            {
                "image": make_test_image_upload("gallery.png"),
                "folder": folder.id,
                "captcha": json.dumps(captcha),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 201)
        self.assertIn("/media/gallery/captcha-gallery/", response.data["url"])

    @patch("wiki.captcha.TurnstileValidator.verify", return_value={"success": True})
    def test_school_survey_patch_submit_requires_captcha(self, _verify):
        user = User.objects.create_user(
            username="captcha_survey_user",
            password="Password123",
            role=User.Role.NORMAL,
        )
        token = Token.objects.create(user=user)
        school = SchoolSurveySchool.objects.create(name="验证码测试大学")
        draft = SchoolSurveySubmission.objects.create(
            school=school,
            author=user,
            status=SchoolSurveySubmission.Status.DRAFT,
            form_data={"school_name": "验证码测试大学", "submitter_contact": "survey@example.com"},
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        missing = self.client.patch(
            f"/api/school-survey-submissions/{draft.id}/",
            {"status": SchoolSurveySubmission.Status.SUBMITTED},
            format="json",
        )
        self.assertEqual(missing.status_code, 400)
        self.assertEqual(missing.data["code"], "CAPTCHA_REQUIRED")

        response = self.client.patch(
            f"/api/school-survey-submissions/{draft.id}/",
            {
                "status": SchoolSurveySubmission.Status.SUBMITTED,
                "captcha": {
                    "scene": "school_survey_submit",
                    "turnstile_token": "school-patch-submit-token",
                },
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        draft.refresh_from_db()
        self.assertEqual(draft.status, SchoolSurveySubmission.Status.SUBMITTED)

    @patch("wiki.captcha.TurnstileValidator.verify", return_value={"success": True})
    def test_moment_image_post_requires_captcha(self, _verify):
        user = User.objects.create_user(
            username="captcha_moment_user",
            password="Password123",
            role=User.Role.NORMAL,
        )
        token = Token.objects.create(user=user)
        settings_obj = MomentSettings.get_solo()
        settings_obj.is_enabled = True
        settings_obj.publishing_enabled = True
        settings_obj.require_real_name = False
        settings_obj.require_manual_review_for_new_users = False
        settings_obj.save()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        missing = self.client.post(
            "/api/moments/",
            {"content": "image without captcha", "images": [make_test_image_upload("missing.png")]},
            format="multipart",
        )
        self.assertEqual(missing.status_code, 400)
        self.assertEqual(missing.data["code"], "CAPTCHA_REQUIRED")

        with patch("wiki.views.apply_moment_ai_review"):
            response = self.client.post(
                "/api/moments/",
                {
                    "content": "image with captcha",
                    "images": [make_test_image_upload("moment.png")],
                    "captcha": json.dumps(
                        {
                            "scene": "upload_image",
                            "turnstile_token": "moment-image-upload-token",
                        }
                    ),
                },
                format="multipart",
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["images"][0]["status"], MomentImage.Status.PENDING)

    def test_account_cancellation_requires_captcha_before_password_check(self):
        user = User.objects.create_user(
            username="captcha_cancel_user",
            password="Password123",
            role=User.Role.NORMAL,
        )
        token = Token.objects.create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        response = self.client.post(
            "/api/me/cancel-account/",
            {
                "current_password": "wrong-password",
                "confirmation": AccountCancellationSerializer.CONFIRMATION_TEXT,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "CAPTCHA_REQUIRED")
        self.assertTrue(User.objects.filter(id=user.id).exists())
        self.assertTrue(Token.objects.filter(key=token.key).exists())
        self.assertTrue(
            CaptchaAuditLog.objects.filter(
                scene="account_cancel",
                result="failed",
                error_code="CAPTCHA_REQUIRED",
                target_type="user",
            ).exists()
        )

    def test_real_name_start_requires_captcha_before_provider_call(self):
        user = User.objects.create_user(
            username="captcha_real_name_user",
            password="Password123",
            role=User.Role.NORMAL,
        )
        token = Token.objects.create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        with patch("wiki.views.start_aliyun_real_name_verification") as provider:
            response = self.client.post(
                "/api/real-name-verifications/me/",
                {
                    "real_name": "Test User",
                    "id_number": "123456789012345678",
                    "meta_info": {"ua": "pytest"},
                },
                format="json",
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "CAPTCHA_REQUIRED")
        provider.assert_not_called()
        self.assertTrue(
            CaptchaAuditLog.objects.filter(
                scene="real_name_start",
                result="failed",
                error_code="CAPTCHA_REQUIRED",
                target_type="user",
            ).exists()
        )


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AuthApiTests(APITestCase):
    def setUp(self):
        cache.clear()
        mail.outbox = []
        self.user = User.objects.create_user(
            username="login_user",
            email="login_user@example.com",
            password="Password123",
            role=User.Role.NORMAL,
        )

    def extract_code_from_last_email(self):
        self.assertTrue(mail.outbox)
        message = mail.outbox[-1]
        match = re.search(r"验证码[:：]\s*(\d+)", message.body)
        self.assertIsNotNone(match)
        return match.group(1)

    def test_legacy_register_challenge_endpoint_is_removed(self):
        response = self.client.get("/api/auth/register-challenge/")

        self.assertEqual(response.status_code, 404)

    def test_login_returns_serialized_user_payload(self):
        before_login = timezone.now()
        response = self.client.post(
            "/api/auth/login/",
            {"username": "login_user", "password": "Password123"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("token", response.data)
        self.assertIn("user", response.data)
        self.assertIsInstance(response.data["user"], dict)
        self.assertEqual(response.data["user"]["username"], "login_user")
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.last_login)
        self.assertGreaterEqual(self.user.last_login, before_login)
        self.assertTrue(
            SecurityAuditLog.objects.filter(
                event_type=SecurityAuditLog.EventType.LOGIN_SUCCESS,
                username="login_user",
                success=True,
            ).exists()
        )

    def test_login_ignores_existing_session_without_csrf_token(self):
        csrf_client = APIClient(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)

        response = csrf_client.post(
            "/api/auth/login/",
            {"username": "login_user", "password": "Password123"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("token", response.data)

    def test_login_rotates_token(self):
        first = self.client.post(
            "/api/auth/login/",
            {"username": "login_user", "password": "Password123"},
            format="json",
        )
        self.assertEqual(first.status_code, 200)
        first_token = first.data["token"]

        second = self.client.post(
            "/api/auth/login/",
            {"username": "login_user", "password": "Password123"},
            format="json",
        )
        self.assertEqual(second.status_code, 200)
        second_token = second.data["token"]

        self.assertNotEqual(first_token, second_token)
        self.assertFalse(Token.objects.filter(key=first_token).exists())
        self.assertTrue(Token.objects.filter(key=second_token).exists())

    def test_login_accepts_verified_email_identifier(self):
        self.user.email_verified_at = timezone.now()
        self.user.save(update_fields=["email_verified_at"])

        response = self.client.post(
            "/api/auth/login/",
            {"username": "LOGIN_USER@EXAMPLE.COM", "password": "Password123"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["user"]["username"], "login_user")

    def test_login_rejects_unverified_email_identifier(self):
        response = self.client.post(
            "/api/auth/login/",
            {"username": "login_user@example.com", "password": "Password123"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertNotIn("token", response.data)

    def test_login_accepts_verified_phone_identifier(self):
        country_code, phone_number = normalize_phone_context(
            country_code="86",
            phone_number="13800138000",
        )
        PhoneVerification.objects.create(
            user=self.user,
            status=PhoneVerification.Status.VERIFIED,
            phone_country_code=country_code,
            phone_masked="138****8000",
            phone_last4="8000",
            phone_digest=build_phone_digest(country_code, phone_number),
            verified_at=timezone.now(),
        )

        response = self.client.post(
            "/api/auth/login/",
            {"username": "+86 138 0013 8000", "password": "Password123"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["user"]["username"], "login_user")

    def test_login_rejects_unverified_phone_identifier(self):
        country_code, phone_number = normalize_phone_context(
            country_code="86",
            phone_number="13800138000",
        )
        PhoneVerification.objects.create(
            user=self.user,
            status=PhoneVerification.Status.PENDING,
            phone_country_code=country_code,
            phone_masked="138****8000",
            phone_last4="8000",
            phone_digest=build_phone_digest(country_code, phone_number),
        )

        response = self.client.post(
            "/api/auth/login/",
            {"username": "13800138000", "password": "Password123"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertNotIn("token", response.data)

    def test_register_code_and_complete_registration(self):
        request_response = self.client.post(
            "/api/auth/register-email-code/",
            {
                "username": "new_user",
                "email": "new_user@example.com",
                "password": "StrongPass123!",
                "school_name": "Algo University",
            },
            format="json",
        )
        self.assertEqual(request_response.status_code, 200)
        self.assertIn("ticket_token", request_response.data)
        self.assertEqual(len(mail.outbox), 1)

        code = self.extract_code_from_last_email()
        response = self.client.post(
            "/api/auth/register/",
            {
                "ticket_token": request_response.data["ticket_token"],
                "code": code,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(username="new_user")
        self.assertEqual(user.email, "new_user@example.com")
        self.assertEqual(user.school_name, "Algo University")
        self.assertIsNotNone(user.email_verified_at)
        self.assertEqual(user.avatar_url, "/wiki-assets/default-avatar.svg")
        self.assertEqual(
            response.data["user"]["avatar_url"], "/wiki-assets/default-avatar.svg"
        )
        self.assertTrue(PasswordHistory.objects.filter(user=user).exists())
        self.assertTrue(
            SecurityAuditLog.objects.filter(
                event_type=SecurityAuditLog.EventType.REGISTER_CODE_SENT,
                username="new_user",
                success=True,
            ).exists()
        )
        self.assertTrue(
            SecurityAuditLog.objects.filter(
                event_type=SecurityAuditLog.EventType.REGISTER_SUCCESS,
                user=user,
                success=True,
            ).exists()
        )

    def test_register_can_upload_optional_avatar(self):
        temp_media_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_media_dir.cleanup)
        request_response = self.client.post(
            "/api/auth/register-email-code/",
            {
                "username": "new_avatar_user",
                "email": "new_avatar_user@example.com",
                "password": "StrongPass123!",
            },
            format="json",
        )
        self.assertEqual(request_response.status_code, 200)
        avatar = make_test_image_upload("avatar.png", size=(640, 480), color=(32, 120, 240))

        with override_settings(MEDIA_ROOT=temp_media_dir.name, MEDIA_URL="/media/"):
            with patch(
                "wiki.serializers.moderate_image_url",
                return_value=SimpleNamespace(
                    provider="test",
                    decision="approve",
                    risk_level="safe",
                    summary="approved",
                ),
            ):
                response = self.client.post(
                    "/api/auth/register/",
                    {
                        "ticket_token": request_response.data["ticket_token"],
                        "code": self.extract_code_from_last_email(),
                        "avatar_image": avatar,
                    },
                    format="multipart",
                )

        self.assertEqual(response.status_code, 201)
        avatar_url = response.data["user"]["avatar_url"]
        self.assertTrue(avatar_url.startswith("/media/avatars/"))
        self.assertTrue(avatar_url.endswith(".webp"))
        stored_path = Path(temp_media_dir.name) / avatar_url.removeprefix("/media/")
        self.assertTrue(stored_path.exists())
        self.assertLess(stored_path.stat().st_size, 96 * 1024)
        user = User.objects.get(username="new_avatar_user")
        self.assertEqual(user.avatar_url, avatar_url)

    def test_register_rejects_duplicate_email(self):
        response = self.client.post(
            "/api/auth/register-email-code/",
            {
                "username": "new_user2",
                "email": "LOGIN_USER@example.com",
                "password": "StrongPass123!",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.data)

    def test_register_email_code_no_longer_requires_legacy_math_captcha(self):
        response = self.client.post(
            "/api/auth/register-email-code/",
            {
                "username": "legacy_captcha_free_user",
                "email": "legacy_captcha_free_user@example.com",
                "password": "StrongPass123!",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("ticket_token", response.data)

    def test_password_reset_flow_updates_password_and_rotates_token(self):
        request_response = self.client.post(
            "/api/auth/password-reset-code/",
            {"email": "login_user@example.com"},
            format="json",
        )
        self.assertEqual(request_response.status_code, 200)
        self.assertIn("ticket_token", request_response.data)
        self.assertEqual(len(mail.outbox), 1)

        code = self.extract_code_from_last_email()
        response = self.client.post(
            "/api/auth/password-reset/",
            {
                "ticket_token": request_response.data["ticket_token"],
                "code": code,
                "new_password": "Password456!",
                "confirm_password": "Password456!",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("token", response.data)

        login_response = self.client.post(
            "/api/auth/login/",
            {"username": "login_user", "password": "Password456!"},
            format="json",
        )
        self.assertEqual(login_response.status_code, 200)
        self.assertTrue(
            SecurityAuditLog.objects.filter(
                event_type=SecurityAuditLog.EventType.PASSWORD_RESET_COMPLETED,
                username="login_user",
                success=True,
            ).exists()
        )

    def test_error_response_contains_request_id(self):
        response = self.client.post(
            "/api/auth/login/",
            {"username": "login_user", "password": "WrongPassword!"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("request_id", response.data)
        self.assertEqual(
            response.headers.get("X-Request-ID"), response.data["request_id"]
        )


class AuthSecurityHardeningTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="secure_user",
            password="StrongPass123!",
            role=User.Role.NORMAL,
        )
        self.admin = User.objects.create_user(
            username="secure_admin",
            password="StrongPass123!",
            role=User.Role.ADMIN,
        )
        self.admin_token = Token.objects.create(user=self.admin)

    @override_settings(
        AUTH_SECURITY={
            "TOKEN_TTL_HOURS": 168,
            "LOGIN_MAX_FAILURES": 3,
            "LOGIN_FAILURE_WINDOW_MINUTES": 15,
            "LOGIN_LOCK_MINUTES": 15,
        }
    )
    def test_login_lockout_after_too_many_failures(self):
        for _ in range(2):
            response = self.client.post(
                "/api/auth/login/",
                {"username": "secure_user", "password": "WrongPass123!"},
                format="json",
            )
            self.assertEqual(response.status_code, 400)

        locked_response = self.client.post(
            "/api/auth/login/",
            {"username": "secure_user", "password": "WrongPass123!"},
            format="json",
        )
        self.assertEqual(locked_response.status_code, 429)
        self.assertTrue(LoginAttempt.objects.filter(username_ci="secure_user").exists())
        self.assertTrue(
            SecurityAuditLog.objects.filter(
                event_type=SecurityAuditLog.EventType.LOGIN_FAILED,
                username="secure_user",
                success=False,
            ).exists()
        )
        self.assertTrue(
            SecurityAuditLog.objects.filter(
                event_type=SecurityAuditLog.EventType.LOGIN_LOCKED,
                username="secure_user",
                success=False,
            ).exists()
        )

    def test_ban_revokes_token_and_blocks_me_endpoint(self):
        victim = User.objects.create_user(
            username="secure_victim",
            password="StrongPass123!",
            role=User.Role.NORMAL,
        )
        victim_token = Token.objects.create(user=victim)

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        ban_response = self.client.post(
            f"/api/users/{victim.id}/ban/",
            {"reason": "security test"},
            format="json",
        )
        self.assertEqual(ban_response.status_code, 200)
        self.assertFalse(Token.objects.filter(key=victim_token.key).exists())
        self.assertTrue(
            SecurityAuditLog.objects.filter(
                event_type=SecurityAuditLog.EventType.USER_BANNED,
                success=True,
                username="secure_victim",
            ).exists()
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {victim_token.key}")
        me_response = self.client.get("/api/me/")
        self.assertIn(me_response.status_code, (401, 403))


@override_settings(QA_MODULE_ENABLED=True)
class CostControlApiTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.category = Category.objects.create(
            name="Cost Control", slug="cost-control"
        )
        self.user = User.objects.create_user(
            username="cost_user",
            password="Password123",
            role=User.Role.NORMAL,
        )
        self.user_token = Token.objects.create(user=self.user)
        self.article = Article.objects.create(
            title="Cost Article",
            summary="summary",
            content_md="body",
            category=self.category,
            author=self.user,
            last_editor=self.user,
            status=Article.Status.PUBLISHED,
        )
        self.question = Question.objects.create(
            title="Existing Question",
            content_md="body",
            author=self.user,
            category=self.category,
            status=Question.Status.PENDING,
        )

    def test_export_endpoints_are_disabled(self):
        article_pdf = self.client.get(f"/api/articles/{self.article.id}/export-pdf/")
        article_markdown = self.client.get(
            f"/api/articles/{self.article.id}/export-markdown-bundle/"
        )
        collection_pdf = self.client.get("/api/articles/export-collection-pdf/")
        collection_markdown = self.client.get(
            "/api/articles/export-collection-markdown-bundle/"
        )

        for response in (
            article_pdf,
            article_markdown,
            collection_pdf,
            collection_markdown,
        ):
            self.assertEqual(response.status_code, 404)
            self.assertIn("disabled", response.data["detail"].lower())

    def test_login_is_rate_limited(self):
        responses = [
            self.client.post(
                "/api/auth/login/",
                {"username": "cost_user", "password": "Password123"},
                format="json",
            )
            for _ in range(4)
        ]

        self.assertEqual(
            [response.status_code for response in responses[:3]], [200, 200, 200]
        )
        self.assertEqual(responses[3].status_code, 429)

    def test_question_submission_is_rate_limited(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.user_token.key}")

        responses = [
            self.client.post(
                "/api/questions/",
                {
                    "title": f"Q{index}",
                    "content_md": "body",
                    "category": self.category.id,
                },
                format="json",
            )
            for index in range(1, 5)
        ]

        self.assertEqual(
            [response.status_code for response in responses[:3]], [201, 201, 201]
        )
        self.assertEqual(responses[3].status_code, 429)

    def test_question_update_is_rate_limited(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.user_token.key}")

        responses = [
            self.client.patch(
                f"/api/questions/{self.question.id}/",
                {"content_md": f"updated {index}"},
                format="json",
            )
            for index in range(1, 5)
        ]

        self.assertEqual(
            [response.status_code for response in responses[:3]], [200, 200, 200]
        )
        self.assertEqual(responses[3].status_code, 429)


class ImageUploadApiTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="upload_user",
            password="Password123",
            role=User.Role.NORMAL,
        )
        self.user_token = Token.objects.create(user=self.user)
        self.admin = User.objects.create_user(
            username="upload_admin",
            password="Password123",
            role=User.Role.ADMIN,
        )
        self.admin_token = Token.objects.create(user=self.admin)
        self.temp_media_dir = tempfile.TemporaryDirectory()
        self.override = override_settings(
            MEDIA_ROOT=self.temp_media_dir.name, MEDIA_URL="/media/"
        )
        self.override.enable()

    def tearDown(self):
        self.override.disable()
        self.temp_media_dir.cleanup()

    def test_normal_user_cannot_upload_image(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.user_token.key}")
        upload = make_test_image_upload("tiny.png")
        response = self.client.post(
            "/api/uploads/image/", {"image": upload}, format="multipart"
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("Only admins can upload images", response.data["detail"])

    def test_admin_user_can_upload_image(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        upload = make_test_image_upload("tiny.png")
        response = self.client.post(
            "/api/uploads/image/", {"image": upload}, format="multipart"
        )
        self.assertEqual(response.status_code, 201)
        self.assertIn("url", response.data)
        self.assertIn("/media/wiki-uploads/", response.data["url"])
        self.assertIn("markdown", response.data)
        self.assertTrue(response.data["markdown"].startswith("![tiny]("))

        stored = Path(self.temp_media_dir.name) / response.data["path"]
        self.assertTrue(stored.exists())

    def test_upload_rejects_non_image_extension(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        bad_file = SimpleUploadedFile(
            "notes.txt", b"not-image", content_type="text/plain"
        )
        response = self.client.post(
            "/api/uploads/image/", {"image": bad_file}, format="multipart"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("image", response.data)

    def test_upload_rejects_corrupt_image_bytes(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        bad_file = SimpleUploadedFile(
            "tiny.png", b"not-an-image", content_type="image/png"
        )
        response = self.client.post(
            "/api/uploads/image/", {"image": bad_file}, format="multipart"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("detail", response.data)


class GalleryImageApiTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="gallery_user",
            password="Password123",
            role=User.Role.NORMAL,
        )
        self.user_token = Token.objects.create(user=self.user)
        self.admin = User.objects.create_user(
            username="gallery_admin",
            password="Password123",
            role=User.Role.ADMIN,
        )
        self.admin_token = Token.objects.create(user=self.admin)
        self.folder = GalleryImageFolder.objects.create(
            name="测试图库",
            slug="test-gallery",
            display_order=1,
        )
        self.temp_media_dir = tempfile.TemporaryDirectory()
        self.override = override_settings(
            MEDIA_ROOT=self.temp_media_dir.name, MEDIA_URL="/media/"
        )
        self.override.enable()

    def tearDown(self):
        self.override.disable()
        self.temp_media_dir.cleanup()

    def tiny_png_upload(self, name="tiny.png"):
        return make_test_image_upload(name)

    def test_normal_user_cannot_access_gallery(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.user_token.key}")
        response = self.client.get("/api/gallery-images/")

        self.assertEqual(response.status_code, 403)

    def test_admin_can_create_gallery_folder_without_slug(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.post(
            "/api/gallery-folders/",
            {"name": "临时图库"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["name"], "临时图库")
        self.assertTrue(response.data["slug"])
        self.assertTrue(GalleryImageFolder.objects.filter(name="临时图库").exists())

    def test_admin_can_upload_recycle_and_restore_gallery_image(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.post(
            "/api/gallery-images/upload/",
            {"image": self.tiny_png_upload(), "folder": self.folder.id},
            format="multipart",
        )

        self.assertEqual(response.status_code, 201)
        self.assertIn("/media/gallery/test-gallery/", response.data["url"])
        self.assertTrue(response.data["markdown"].startswith("![tiny]("))
        image = GalleryImage.objects.get(id=response.data["id"])
        active_path = Path(self.temp_media_dir.name) / image.image.name
        self.assertTrue(active_path.exists())

        delete_response = self.client.delete(f"/api/gallery-images/{image.id}/")
        self.assertEqual(delete_response.status_code, 200)
        image.refresh_from_db()
        self.assertEqual(image.status, GalleryImage.Status.RECYCLED)
        self.assertFalse(active_path.exists())
        recycled_path = Path(self.temp_media_dir.name) / image.image.name
        self.assertTrue(recycled_path.exists())
        self.assertIn("/media/gallery-recycle/", delete_response.data["url"])
        self.assertFalse(delete_response.data["markdown"])

        list_response = self.client.get("/api/gallery-images/", {"status": "recycled"})
        self.assertEqual(list_response.status_code, 200)
        recycled_rows = list_response.data.get("results", list_response.data)
        self.assertEqual(len(recycled_rows), 1)
        self.assertIn("/media/gallery-recycle/", recycled_rows[0]["url"])

        restore_response = self.client.post(f"/api/gallery-images/{image.id}/restore/")
        self.assertEqual(restore_response.status_code, 200)
        image.refresh_from_db()
        self.assertEqual(image.status, GalleryImage.Status.ACTIVE)
        self.assertTrue((Path(self.temp_media_dir.name) / image.image.name).exists())
        self.assertIn("/media/gallery/test-gallery/", restore_response.data["url"])

    def test_admin_can_permanently_delete_recycled_image(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.post(
            "/api/gallery-images/upload/",
            {"image": self.tiny_png_upload("purge.png"), "folder": self.folder.id},
            format="multipart",
        )
        image_id = response.data["id"]

        self.client.delete(f"/api/gallery-images/{image_id}/")
        image = GalleryImage.objects.get(id=image_id)
        recycled_path = Path(self.temp_media_dir.name) / image.image.name
        self.assertTrue(recycled_path.exists())

        purge_response = self.client.delete(f"/api/gallery-images/{image_id}/")
        self.assertEqual(purge_response.status_code, 204)
        self.assertFalse(GalleryImage.objects.filter(id=image_id).exists())
        self.assertFalse(recycled_path.exists())


class DeploymentAccessTests(APITestCase):
    def test_health_endpoint_reports_runtime_status(self):
        response = self.client.get("/api/health/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "ok")
        self.assertTrue(response.data["database"]["ok"])
        self.assertIn("frontend", response.data)
        self.assertIn("storage", response.data)
        self.assertIn("media", response.data)
        self.assertTrue(response.headers.get("X-Request-ID"))
        self.assertEqual(
            response.headers.get("X-Request-ID"), response.data["request_id"]
        )

    def test_health_endpoint_uses_client_request_id_header(self):
        response = self.client.get(
            "/api/health/", HTTP_X_REQUEST_ID="manual-health-check"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["request_id"], "manual-health-check")
        self.assertEqual(response.headers.get("X-Request-ID"), "manual-health-check")

    def test_frontend_dist_is_served_when_enabled(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            dist_dir = Path(temp_dir)
            (dist_dir / "index.html").write_text(
                "<html><body>algowiki frontend</body></html>", encoding="utf-8"
            )
            (dist_dir / "assets").mkdir()
            (dist_dir / "assets" / "app.js").write_text(
                "console.log('algowiki');", encoding="utf-8"
            )

            with override_settings(
                SERVE_FRONTEND=True, FRONTEND_DIST_DIR=str(dist_dir)
            ):
                root_response = self.client.get("/")
                asset_response = self.client.get("/assets/app.js")
                root_body = b"".join(root_response.streaming_content)
                asset_body = b"".join(asset_response.streaming_content)
                root_response.close()
                asset_response.close()

        self.assertEqual(root_response.status_code, 200)
        self.assertIn(b"algowiki frontend", root_body)
        self.assertEqual(asset_response.status_code, 200)
        self.assertIn(b"algowiki", asset_body)


class SecurityAuditEndpointTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="audit_admin",
            password="Password123",
            role=User.Role.ADMIN,
        )
        self.normal = User.objects.create_user(
            username="audit_normal",
            password="Password123",
            role=User.Role.NORMAL,
        )
        self.admin_token = Token.objects.create(user=self.admin)
        self.normal_token = Token.objects.create(user=self.normal)

        SecurityAuditLog.objects.create(
            event_type=SecurityAuditLog.EventType.LOGIN_FAILED,
            username="audit_normal",
            ip_address="127.0.0.1",
            success=False,
            detail="invalid credentials for audit test",
        )
        SecurityAuditLog.objects.create(
            event_type=SecurityAuditLog.EventType.LOGIN_SUCCESS,
            user=self.normal,
            username="audit_normal",
            ip_address="127.0.0.2",
            success=True,
            detail="ok",
        )

    def test_admin_can_list_security_logs(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.get("/api/security-logs/")
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.data["count"], 2)

    def test_security_logs_support_filters(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.get(
            "/api/security-logs/",
            {"event_type": SecurityAuditLog.EventType.LOGIN_FAILED, "success": "0"},
        )
        self.assertEqual(response.status_code, 200)
        items = response.data.get("results", response.data)
        self.assertTrue(items)
        for item in items:
            self.assertEqual(
                item["event_type"], SecurityAuditLog.EventType.LOGIN_FAILED
            )
            self.assertFalse(item["success"])

    def test_security_logs_detail_and_ip_filters(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.get(
            "/api/security-logs/",
            {"ip": "127.0.0.1", "detail": "audit test"},
        )
        self.assertEqual(response.status_code, 200)
        items = response.data.get("results", response.data)
        self.assertEqual(len(items), 1)
        self.assertEqual(
            items[0]["event_type"], SecurityAuditLog.EventType.LOGIN_FAILED
        )

    def test_admin_can_export_security_logs(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.get("/api/security-logs/export/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])
        body = response.content.decode("utf-8")
        self.assertIn("event_type", body)
        self.assertIn(SecurityAuditLog.EventType.LOGIN_FAILED, body)

    def test_admin_can_get_security_log_summary(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.get("/api/security-logs/summary/", {"window_hours": 24})
        self.assertEqual(response.status_code, 200)
        self.assertIn("totals", response.data)
        self.assertIn("top_failed_ips", response.data)
        self.assertGreaterEqual(response.data["totals"]["failed_events"], 1)
        self.assertIn("window_hours", response.data)

    def test_normal_user_cannot_access_security_logs(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.normal_token.key}")
        response = self.client.get("/api/security-logs/")
        self.assertEqual(response.status_code, 403)

    def test_normal_user_cannot_export_security_logs(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.normal_token.key}")
        response = self.client.get("/api/security-logs/export/")
        self.assertEqual(response.status_code, 403)

    def test_normal_user_cannot_get_security_log_summary(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.normal_token.key}")
        response = self.client.get("/api/security-logs/summary/")
        self.assertEqual(response.status_code, 403)


class SeedCommandTests(APITestCase):
    def test_seed_initial_data_can_create_and_reset_superadmin_password(self):
        call_command(
            "seed_initial_data",
            superadmin_username="seed_admin",
            superadmin_password="InitPass123!",
            superadmin_email="seed@example.com",
        )
        user = User.objects.get(username="seed_admin")
        self.assertEqual(user.role, User.Role.SUPERADMIN)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.check_password("InitPass123!"))
        self.assertTrue(PasswordHistory.objects.filter(user=user).exists())

        call_command(
            "seed_initial_data",
            superadmin_username="seed_admin",
            superadmin_password="ResetPass123!",
            superadmin_email="seed@example.com",
            reset_superadmin_password=True,
        )
        user.refresh_from_db()
        self.assertTrue(user.check_password("ResetPass123!"))
        self.assertTrue(PasswordHistory.objects.filter(user=user).exists())

    def test_seed_initial_data_imports_markdown_sections_by_default(self):
        markdown = (
            "# 测试文档\n\n"
            "## 一级章节\n"
            "一级正文\n\n"
            "### 子章节A\n"
            "子章节A正文\n\n"
            "### 子章节B\n"
            "子章节B正文\n\n"
            "## 二级章节\n"
            "二级正文\n"
        )
        tmp_file = tempfile.NamedTemporaryFile(
            "w", suffix=".md", encoding="utf-8", delete=False
        )
        try:
            tmp_file.write(markdown)
            tmp_file.close()

            call_command(
                "seed_initial_data",
                superadmin_username="seed_import_admin",
                superadmin_password="InitPass123!",
                superadmin_email="seed-import@example.com",
                content_file=tmp_file.name,
            )

            titles = set(Article.objects.values_list("title", flat=True))
            self.assertIn("一级章节", titles)
            self.assertIn("子章节A", titles)
            self.assertIn("子章节B", titles)
            self.assertIn("二级章节", titles)
        finally:
            Path(tmp_file.name).unlink(missing_ok=True)

    def test_seed_initial_data_creates_demo_role_accounts(self):
        call_command(
            "seed_initial_data",
            superadmin_username="seed_demo_admin",
            superadmin_password="InitPass123!",
            superadmin_email="seed-demo@example.com",
            demo_password="DemoPass123!",
        )

        normal = User.objects.get(username="demo_normal")
        school = User.objects.get(username="demo_school")
        admin = User.objects.get(username="demo_admin")

        self.assertEqual(normal.role, User.Role.NORMAL)
        self.assertEqual(school.role, User.Role.SCHOOL)
        self.assertEqual(admin.role, User.Role.ADMIN)
        self.assertTrue(normal.check_password("DemoPass123!"))
        self.assertTrue(school.check_password("DemoPass123!"))
        self.assertTrue(admin.check_password("DemoPass123!"))

    def test_seed_initial_data_can_skip_demo_role_accounts(self):
        call_command(
            "seed_initial_data",
            superadmin_username="seed_skip_demo_admin",
            superadmin_password="InitPass123!",
            superadmin_email="seed-skip-demo@example.com",
            skip_demo_users=True,
        )

        self.assertFalse(User.objects.filter(username="demo_normal").exists())
        self.assertFalse(User.objects.filter(username="demo_school").exists())
        self.assertFalse(User.objects.filter(username="demo_admin").exists())

    def test_seed_initial_data_seeds_default_site_content(self):
        call_command(
            "seed_initial_data",
            superadmin_username="seed_site_admin",
            superadmin_password="InitPass123!",
            superadmin_email="seed-site@example.com",
            skip_demo_users=True,
        )

        self.assertTrue(
            TeamMember.objects.filter(display_id="Null_Resot", is_active=True).exists()
        )
        self.assertGreaterEqual(FriendlyLink.objects.filter(is_enabled=True).count(), 6)
        self.assertGreaterEqual(
            CompetitionNotice.objects.filter(is_visible=True).count(), 4
        )
        self.assertGreaterEqual(CompetitionScheduleEntry.objects.count(), 4)
        self.assertGreaterEqual(
            TrickEntry.objects.filter(status=TrickEntry.Status.APPROVED).count(),
            2,
        )

    def test_seed_initial_data_uses_document_snapshot_content(self):
        call_command(
            "seed_initial_data",
            superadmin_username="seed_doc_admin",
            superadmin_password="InitPass123!",
            superadmin_email="seed-doc@example.com",
            skip_demo_users=True,
        )

        about_page = ExtensionPage.objects.get(slug="about")
        trick_guide = ExtensionPage.objects.get(slug="trick-guide")

        self.assertIn("feishu.cn", about_page.content_md)
        self.assertIn("小小丛雨", about_page.content_md)
        self.assertIn("关键词用于通过搜索来快速检索", trick_guide.content_md)

    def test_sync_document_pages_snapshot_can_export_and_import(self):
        page = ExtensionPage.objects.create(
            title="Doc Snapshot Page",
            slug="doc-snapshot-page",
            description="snapshot description",
            content_md="snapshot body",
            access_level=ExtensionPage.AccessLevel.PUBLIC,
            is_enabled=True,
        )
        DocumentPageSection.objects.create(
            title="文档快照页",
            key="doc-snapshot-page",
            page=page,
            display_order=90,
            is_visible=True,
        )

        tmp_file = tempfile.NamedTemporaryFile(
            "w", suffix=".json", encoding="utf-8", delete=False
        )
        tmp_file.close()
        try:
            call_command(
                "sync_document_pages_snapshot",
                direction="export",
                path=tmp_file.name,
            )

            payload = json.loads(Path(tmp_file.name).read_text(encoding="utf-8"))
            exported = {item["slug"]: item for item in payload["pages"]}
            self.assertIn(page.slug, exported)
            self.assertEqual(exported[page.slug]["content_md"], "snapshot body")

            page.delete()
            self.assertFalse(ExtensionPage.objects.filter(slug=page.slug).exists())

            call_command(
                "sync_document_pages_snapshot",
                direction="import",
                path=tmp_file.name,
                overwrite_content=True,
                overwrite_metadata=True,
            )

            restored_page = ExtensionPage.objects.get(slug=page.slug)
            restored_section = DocumentPageSection.objects.get(key="doc-snapshot-page")
            self.assertEqual(restored_page.content_md, "snapshot body")
            self.assertEqual(restored_section.page_id, restored_page.id)
        finally:
            Path(tmp_file.name).unlink(missing_ok=True)

    def test_seed_xcpc_reference_content_syncs_bundled_snapshot_and_prunes_stale_articles(
        self,
    ):
        call_command(
            "seed_initial_data",
            superadmin_username="seed_xcpc_admin",
            superadmin_password="InitPass123!",
            superadmin_email="seed-xcpc@example.com",
            skip_demo_users=True,
        )
        author = User.objects.get(username="seed_xcpc_admin")
        stale_article = Article.objects.create(
            title="obsolete xcpc article",
            slug="xcpc-stale-article",
            summary="old",
            content_md="old",
            category=Category.objects.get(slug="xcpc-preface"),
            author=author,
            last_editor=author,
            status=Article.Status.PUBLISHED,
        )

        call_command("seed_xcpc_reference_content", author="seed_xcpc_admin")

        self.assertTrue(Article.objects.filter(title="阅前须知").exists())
        self.assertTrue(Article.objects.filter(title="比赛介绍｜XCPC").exists())
        self.assertTrue(Article.objects.filter(title="关键网站｜GitHub项目").exists())
        outline = Article.objects.get(title="文章大纲")
        self.assertIn("/wiki-assets/1.png", outline.content_md)
        stale_article.refresh_from_db()
        self.assertEqual(stale_article.status, Article.Status.HIDDEN)


class RolePermissionTests(APITestCase):
    def setUp(self):
        self.public_category = Category.objects.create(name="Public", slug="public")
        self.school_category = Category.objects.create(
            name="Contest",
            slug="contest",
            moderation_scope=Category.ModerationScope.SCHOOL,
        )

        self.normal_user = User.objects.create_user(
            username="normal", password="Password123", role=User.Role.NORMAL
        )
        self.school_user = User.objects.create_user(
            username="school", password="Password123", role=User.Role.SCHOOL
        )
        self.admin_user = User.objects.create_user(
            username="admin", password="Password123", role=User.Role.ADMIN
        )

        self.normal_token = Token.objects.create(user=self.normal_user)
        self.school_token = Token.objects.create(user=self.school_user)
        self.admin_token = Token.objects.create(user=self.admin_user)

    def test_normal_user_cannot_create_article(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.normal_token.key}")
        response = self.client.post(
            "/api/articles/",
            {
                "title": "Not allowed",
                "summary": "x",
                "content_md": "x",
                "category": self.public_category.id,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_school_user_can_create_school_scope_article(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.school_token.key}")
        response = self.client.post(
            "/api/articles/",
            {
                "title": "Contest Content",
                "summary": "x",
                "content_md": "x",
                "category": self.school_category.id,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)

    def test_school_user_cannot_move_article_to_public_category(self):
        article = Article.objects.create(
            title="School Only",
            summary="init",
            content_md="init",
            category=self.school_category,
            author=self.school_user,
            last_editor=self.school_user,
            status=Article.Status.PUBLISHED,
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.school_token.key}")
        response = self.client.patch(
            f"/api/articles/{article.id}/",
            {"category": self.public_category.id},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_admin_can_ban_user(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.post(
            f"/api/users/{self.normal_user.id}/ban/",
            {"reason": "spam"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.normal_user.refresh_from_db()
        self.assertTrue(self.normal_user.is_banned)

    def test_school_user_cannot_approve_revision_even_in_school_scope(self):
        article = Article.objects.create(
            title="Contest Article",
            summary="init",
            content_md="init",
            category=self.school_category,
            author=self.admin_user,
            last_editor=self.admin_user,
            status=Article.Status.PUBLISHED,
        )
        proposal = RevisionProposal.objects.create(
            article=article,
            proposer=self.normal_user,
            proposed_title="Contest Article Updated",
            proposed_summary="updated",
            proposed_content_md="updated body",
            reason="improve details",
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.school_token.key}")
        response = self.client.post(
            f"/api/revisions/{proposal.id}/approve/",
            {"review_note": "ok"},
            format="json",
        )
        self.assertEqual(response.status_code, 404)
        proposal.refresh_from_db()
        article.refresh_from_db()
        self.assertEqual(proposal.status, RevisionProposal.Status.PENDING)
        self.assertEqual(article.title, "Contest Article")

    def test_school_user_cannot_approve_revision_in_public_scope(self):
        article = Article.objects.create(
            title="Public Article",
            summary="init",
            content_md="init",
            category=self.public_category,
            author=self.admin_user,
            last_editor=self.admin_user,
            status=Article.Status.PUBLISHED,
        )
        proposal = RevisionProposal.objects.create(
            article=article,
            proposer=self.normal_user,
            proposed_title="Public Article Updated",
            proposed_summary="updated",
            proposed_content_md="updated body",
            reason="improve details",
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.school_token.key}")
        response = self.client.post(
            f"/api/revisions/{proposal.id}/approve/",
            {"review_note": "not allowed"},
            format="json",
        )
        self.assertEqual(response.status_code, 404)


class StarFlowTests(APITestCase):
    def setUp(self):
        self.category = Category.objects.create(name="DS", slug="ds")
        self.other_category = Category.objects.create(name="Math", slug="math")
        self.user = User.objects.create_user(
            username="u1", password="Password123", role=User.Role.NORMAL
        )
        self.token = Token.objects.create(user=self.user)
        self.author = User.objects.create_user(
            username="author", password="Password123", role=User.Role.ADMIN
        )
        self.article = Article.objects.create(
            title="A1",
            summary="s",
            content_md="content",
            category=self.category,
            author=self.author,
            last_editor=self.author,
            status=Article.Status.PUBLISHED,
        )
        self.article2 = Article.objects.create(
            title="Math Intro",
            summary="math summary",
            content_md="content",
            category=self.other_category,
            author=self.author,
            last_editor=self.author,
            status=Article.Status.PUBLISHED,
        )

    def test_star_and_unstar(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        response_star = self.client.post(f"/api/articles/{self.article.id}/star/")
        self.assertEqual(response_star.status_code, 200)

        response_unstar = self.client.post(f"/api/articles/{self.article.id}/unstar/")
        self.assertEqual(response_unstar.status_code, 200)

        response_starred = self.client.get("/api/articles/starred/")
        self.assertEqual(response_starred.status_code, 200)
        ids = {
            item["id"]
            for item in response_starred.data.get("results", response_starred.data)
        }
        self.assertEqual(ids, set())

    def test_starred_endpoint_returns_only_current_user_collection(self):
        other_user = User.objects.create_user(
            username="u2", password="Password123", role=User.Role.NORMAL
        )
        other_token = Token.objects.create(user=other_user)

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        self.client.post(f"/api/articles/{self.article.id}/star/")

        response = self.client.get("/api/articles/starred/")
        self.assertEqual(response.status_code, 200)
        ids = {item["id"] for item in response.data.get("results", response.data)}
        self.assertEqual(ids, {self.article.id})

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {other_token.key}")
        other_response = self.client.get("/api/articles/starred/")
        self.assertEqual(other_response.status_code, 200)
        other_ids = {
            item["id"]
            for item in other_response.data.get("results", other_response.data)
        }
        self.assertEqual(other_ids, set())

    def test_starred_endpoint_requires_authentication(self):
        response = self.client.get("/api/articles/starred/")
        self.assertIn(response.status_code, (401, 403))

    def test_starred_endpoint_supports_search_and_category_filters(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        self.client.post(f"/api/articles/{self.article.id}/star/")
        self.client.post(f"/api/articles/{self.article2.id}/star/")

        search_response = self.client.get("/api/articles/starred/", {"search": "math"})
        self.assertEqual(search_response.status_code, 200)
        search_ids = {
            item["id"]
            for item in search_response.data.get("results", search_response.data)
        }
        self.assertEqual(search_ids, {self.article2.id})

        category_response = self.client.get(
            "/api/articles/starred/", {"category": self.category.slug}
        )
        self.assertEqual(category_response.status_code, 200)
        category_ids = {
            item["id"]
            for item in category_response.data.get("results", category_response.data)
        }
        self.assertEqual(category_ids, {self.article.id})

    def test_starred_endpoint_orders_by_recent_star_time(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        self.client.post(f"/api/articles/{self.article2.id}/star/")
        self.client.post(f"/api/articles/{self.article.id}/star/")

        response = self.client.get("/api/articles/starred/")
        self.assertEqual(response.status_code, 200)
        items = response.data.get("results", response.data)
        self.assertGreaterEqual(len(items), 2)
        self.assertEqual(items[0]["id"], self.article.id)


class ArticleContributorApiTests(APITestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Wiki", slug="wiki")
        self.creator = User.objects.create_user(
            username="creator", password="Password123", role=User.Role.ADMIN
        )
        self.alice = User.objects.create_user(
            username="alice", password="Password123", role=User.Role.NORMAL
        )
        self.bob = User.objects.create_user(
            username="bob", password="Password123", role=User.Role.NORMAL
        )
        self.reviewer = User.objects.create_user(
            username="reviewer", password="Password123", role=User.Role.ADMIN
        )

        self.article = Article.objects.create(
            title="Contributors Article",
            summary="summary",
            content_md="content",
            category=self.category,
            author=self.creator,
            last_editor=self.creator,
            status=Article.Status.PUBLISHED,
        )

        now = timezone.now().replace(microsecond=0)
        self.creator_time = now - timedelta(days=4)
        self.alice_first_time = now - timedelta(days=3)
        self.alice_second_time = now - timedelta(days=2)
        self.bob_rejected_time = now - timedelta(days=1, hours=12)
        self.bob_approved_time = now - timedelta(days=1)

        Article.objects.filter(pk=self.article.pk).update(
            created_at=self.creator_time,
            published_at=self.creator_time,
            updated_at=self.bob_approved_time,
        )

        self.alice_revision_one = RevisionProposal.objects.create(
            article=self.article,
            proposer=self.alice,
            proposed_title="Contributors Article",
            proposed_summary="first approved",
            proposed_content_md="approved content 1",
            reason="fix wording",
        )
        RevisionProposal.objects.filter(pk=self.alice_revision_one.pk).update(
            status=RevisionProposal.Status.APPROVED,
            reviewer=self.reviewer,
            reviewed_at=self.alice_first_time,
            updated_at=self.alice_first_time,
        )

        self.alice_revision_two = RevisionProposal.objects.create(
            article=self.article,
            proposer=self.alice,
            proposed_title="Contributors Article",
            proposed_summary="second approved",
            proposed_content_md="approved content 2",
            reason="expand details",
        )
        RevisionProposal.objects.filter(pk=self.alice_revision_two.pk).update(
            status=RevisionProposal.Status.APPROVED,
            reviewer=self.reviewer,
            reviewed_at=self.alice_second_time,
            updated_at=self.alice_second_time,
        )

        self.bob_rejected_revision = RevisionProposal.objects.create(
            article=self.article,
            proposer=self.bob,
            proposed_title="Contributors Article",
            proposed_summary="rejected",
            proposed_content_md="rejected content",
            reason="rejected change",
        )
        RevisionProposal.objects.filter(pk=self.bob_rejected_revision.pk).update(
            status=RevisionProposal.Status.REJECTED,
            reviewer=self.reviewer,
            reviewed_at=self.bob_rejected_time,
            updated_at=self.bob_rejected_time,
        )

        self.bob_approved_revision = RevisionProposal.objects.create(
            article=self.article,
            proposer=self.bob,
            proposed_title="Contributors Article",
            proposed_summary="approved",
            proposed_content_md="approved content 3",
            reason="final fix",
        )
        RevisionProposal.objects.filter(pk=self.bob_approved_revision.pk).update(
            status=RevisionProposal.Status.APPROVED,
            reviewer=self.reviewer,
            reviewed_at=self.bob_approved_time,
            updated_at=self.bob_approved_time,
        )

    def test_article_detail_returns_sorted_contributors_from_approved_activity(self):
        response = self.client.get(f"/api/articles/{self.article.id}/")
        self.assertEqual(response.status_code, 200)

        contributors = response.data["contributors"]
        self.assertEqual(
            [item["user"]["username"] for item in contributors],
            ["creator", "alice", "bob"],
        )

        def parse_api_datetime(value):
            return timezone.datetime.fromisoformat(str(value).replace("Z", "+00:00"))

        def assert_api_datetime_equal(serialized_value, expected):
            parsed = parse_api_datetime(serialized_value)
            self.assertEqual(parsed, expected.astimezone(parsed.tzinfo))

        creator_payload = contributors[0]
        self.assertTrue(creator_payload["is_creator"])
        self.assertEqual(creator_payload["approved_revision_count"], 0)
        assert_api_datetime_equal(
            creator_payload["first_contributed_at"], self.creator_time
        )
        assert_api_datetime_equal(
            creator_payload["last_contributed_at"], self.creator_time
        )

        alice_payload = contributors[1]
        self.assertFalse(alice_payload["is_creator"])
        self.assertEqual(alice_payload["approved_revision_count"], 2)
        assert_api_datetime_equal(
            alice_payload["first_contributed_at"], self.alice_first_time
        )
        assert_api_datetime_equal(
            alice_payload["last_contributed_at"], self.alice_second_time
        )

        bob_payload = contributors[2]
        self.assertFalse(bob_payload["is_creator"])
        self.assertEqual(bob_payload["approved_revision_count"], 1)
        assert_api_datetime_equal(
            bob_payload["first_contributed_at"], self.bob_approved_time
        )
        assert_api_datetime_equal(
            bob_payload["last_contributed_at"], self.bob_approved_time
        )


@override_settings(QA_MODULE_ENABLED=True)
class QuestionSecurityTests(APITestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Basic", slug="basic")
        self.author = User.objects.create_user(
            username="author2", password="Password123", role=User.Role.NORMAL
        )
        self.other = User.objects.create_user(
            username="other2", password="Password123", role=User.Role.NORMAL
        )
        self.admin = User.objects.create_user(
            username="admin_q", password="Password123", role=User.Role.ADMIN
        )
        self.author_token = Token.objects.create(user=self.author)
        self.other_token = Token.objects.create(user=self.other)
        self.admin_token = Token.objects.create(user=self.admin)
        self.question = Question.objects.create(
            title="Need help",
            content_md="question body",
            author=self.author,
            category=self.category,
        )

    def test_other_user_cannot_update_or_delete_question(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.other_token.key}")
        update_response = self.client.patch(
            f"/api/questions/{self.question.id}/",
            {"title": "hijacked"},
            format="json",
        )
        self.assertEqual(update_response.status_code, 403)

        delete_response = self.client.delete(f"/api/questions/{self.question.id}/")
        self.assertEqual(delete_response.status_code, 403)

    def test_admin_can_store_and_append_review_note_for_question(self):
        self.question.status = Question.Status.PENDING
        self.question.save(update_fields=["status", "updated_at"])

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        approve_response = self.client.post(
            f"/api/questions/{self.question.id}/approve/",
            {"review_note": "first review note"},
            format="json",
        )
        self.assertEqual(approve_response.status_code, 200)
        self.question.refresh_from_db()
        self.assertEqual(self.question.status, Question.Status.OPEN)
        self.assertEqual(self.question.reviewer_id, self.admin.id)
        self.assertEqual(self.question.review_note, "first review note")
        self.assertIsNotNone(self.question.reviewed_at)

        append_response = self.client.post(
            f"/api/questions/{self.question.id}/append-review-note/",
            {"note": "second review note"},
            format="json",
        )
        self.assertEqual(append_response.status_code, 200)
        self.question.refresh_from_db()
        self.assertIn("first review note", self.question.review_note)
        self.assertIn("second review note", self.question.review_note)
        self.assertIn(self.admin.username, self.question.review_note)

    def test_reject_question_sends_review_note_notification(self):
        self.question.status = Question.Status.PENDING
        self.question.save(update_fields=["status", "updated_at"])

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.post(
            f"/api/questions/{self.question.id}/reject/",
            {"review_note": "标题和内容都需要补充"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.question.refresh_from_db()
        self.assertEqual(self.question.status, Question.Status.HIDDEN)
        self.assertEqual(self.question.review_note, "标题和内容都需要补充")

        notification = UserNotification.objects.get(
            user=self.author,
            target_type="Question",
            target_id=self.question.id,
        )
        self.assertEqual(notification.level, UserNotification.Level.WARNING)
        self.assertIn("标题和内容都需要补充", notification.content)

    def test_owner_delete_hides_question(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.author_token.key}")
        response = self.client.delete(f"/api/questions/{self.question.id}/")
        self.assertEqual(response.status_code, 204)
        self.question.refresh_from_db()
        self.assertEqual(self.question.status, Question.Status.HIDDEN)
        archive = DeletedContentArchive.objects.get(
            target_type="Question",
            target_id=self.question.id,
            delete_action=DeletedContentArchive.DeleteAction.HIDE,
        )
        self.assertEqual(archive.original_author_id, self.author.id)
        self.assertEqual(archive.deleted_by_id, self.author.id)
        self.assertEqual(archive.title, self.question.title)

        list_response = self.client.get("/api/questions/")
        list_ids = {
            item["id"] for item in list_response.data.get("results", list_response.data)
        }
        self.assertNotIn(self.question.id, list_ids)

        mine_response = self.client.get("/api/questions/", {"mine": "1"})
        mine_ids = {
            item["id"] for item in mine_response.data.get("results", mine_response.data)
        }
        self.assertNotIn(self.question.id, mine_ids)

        deleted_response = self.client.get(
            "/api/questions/", {"mine": "1", "status": Question.Status.HIDDEN}
        )
        deleted_ids = {
            item["id"]
            for item in deleted_response.data.get("results", deleted_response.data)
        }
        self.assertIn(self.question.id, deleted_ids)

    def test_owner_can_restore_hidden_question_back_to_pending(self):
        self.question.status = Question.Status.HIDDEN
        self.question.save(update_fields=["status", "updated_at"])

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.author_token.key}")
        response = self.client.post(
            f"/api/questions/{self.question.id}/restore/", format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], Question.Status.PENDING)

        self.question.refresh_from_db()
        self.assertEqual(self.question.status, Question.Status.PENDING)

    def test_hidden_question_archive_keeps_latest_thirty_for_owner(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.author_token.key}")

        Question.objects.filter(id=self.question.id).update(
            status=Question.Status.HIDDEN
        )
        for index in range(35):
            Question.objects.create(
                title=f"Hidden {index}",
                content_md="archived",
                author=self.author,
                category=self.category,
                status=Question.Status.HIDDEN,
            )

        response = self.client.get(
            "/api/questions/", {"mine": "1", "status": Question.Status.HIDDEN}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 30)
        items = list(response.data.get("results", response.data))
        if response.data.get("next"):
            page2 = self.client.get(
                "/api/questions/",
                {"mine": "1", "status": Question.Status.HIDDEN, "page": 2},
            )
            self.assertEqual(page2.status_code, 200)
            items.extend(page2.data.get("results", page2.data))
        self.assertEqual(len(items), 30)
        hidden_titles = {item["title"] for item in items}
        self.assertIn("Hidden 34", hidden_titles)
        self.assertNotIn("Need help", hidden_titles)

    def test_owner_delete_via_method_override_hides_question(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.author_token.key}")
        response = self.client.post(
            f"/api/questions/{self.question.id}/",
            {},
            format="json",
            HTTP_X_HTTP_METHOD_OVERRIDE="DELETE",
        )
        self.assertEqual(response.status_code, 204)
        self.question.refresh_from_db()
        self.assertEqual(self.question.status, Question.Status.HIDDEN)

    def test_questions_list_mine_filter(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.author_token.key}")
        response = self.client.get("/api/questions/", {"mine": "1"})
        self.assertEqual(response.status_code, 200)
        ids = {item["id"] for item in response.data.get("results", response.data)}
        self.assertEqual(ids, {self.question.id})

    def test_manager_default_question_list_hides_hidden_questions_but_allows_hidden_filter(
        self,
    ):
        self.question.status = Question.Status.HIDDEN
        self.question.save(update_fields=["status", "updated_at"])

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")

        default_response = self.client.get("/api/questions/")
        default_ids = {
            item["id"]
            for item in default_response.data.get("results", default_response.data)
        }
        self.assertNotIn(self.question.id, default_ids)

        hidden_response = self.client.get(
            "/api/questions/", {"status": Question.Status.HIDDEN}
        )
        hidden_ids = {
            item["id"]
            for item in hidden_response.data.get("results", hidden_response.data)
        }
        self.assertIn(self.question.id, hidden_ids)

    def test_manager_can_filter_questions_by_author(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.get("/api/questions/", {"author": self.author.username})
        self.assertEqual(response.status_code, 200)
        ids = {item["id"] for item in response.data.get("results", response.data)}
        self.assertEqual(ids, {self.question.id})

    def test_normal_user_created_question_requires_admin_review(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.author_token.key}")
        create_response = self.client.post(
            "/api/questions/",
            {
                "title": "Pending question",
                "content_md": "please review",
                "category": self.category.id,
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(create_response.data["status"], Question.Status.PENDING)
        question_id = create_response.data["id"]

        self.client.credentials()
        public_response = self.client.get("/api/questions/")
        public_ids = {
            item["id"]
            for item in public_response.data.get("results", public_response.data)
        }
        self.assertNotIn(question_id, public_ids)

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.author_token.key}")
        own_response = self.client.get("/api/questions/")
        own_ids = {
            item["id"] for item in own_response.data.get("results", own_response.data)
        }
        self.assertIn(question_id, own_ids)

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        approve_response = self.client.post(
            f"/api/questions/{question_id}/approve/", format="json"
        )
        self.assertEqual(approve_response.status_code, 200)

        self.client.credentials()
        visible_response = self.client.get("/api/questions/")
        visible_ids = {
            item["id"]
            for item in visible_response.data.get("results", visible_response.data)
        }
        self.assertIn(question_id, visible_ids)

    def test_author_editing_visible_question_reverts_to_pending(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.author_token.key}")
        response = self.client.patch(
            f"/api/questions/{self.question.id}/",
            {"title": "Need help updated"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], Question.Status.PENDING)

        self.question.refresh_from_db()
        self.assertEqual(self.question.status, Question.Status.PENDING)

        self.client.credentials()
        public_response = self.client.get("/api/questions/")
        public_ids = {
            item["id"]
            for item in public_response.data.get("results", public_response.data)
        }
        self.assertNotIn(self.question.id, public_ids)


@override_settings(QA_MODULE_ENABLED=True)
class AnswerModerationTests(APITestCase):
    def setUp(self):
        self.category = Category.objects.create(name="QA", slug="qa")
        self.question_author = User.objects.create_user(
            username="qa_author",
            password="Password123",
            role=User.Role.NORMAL,
        )
        self.responder = User.objects.create_user(
            username="qa_responder",
            password="Password123",
            role=User.Role.NORMAL,
        )
        self.admin = User.objects.create_user(
            username="qa_admin",
            password="Password123",
            role=User.Role.ADMIN,
        )
        self.author_token = Token.objects.create(user=self.question_author)
        self.responder_token = Token.objects.create(user=self.responder)
        self.admin_token = Token.objects.create(user=self.admin)
        self.question = Question.objects.create(
            title="Open question",
            content_md="question body",
            author=self.question_author,
            category=self.category,
            status=Question.Status.OPEN,
        )
        self.answer = Answer.objects.create(
            question=self.question,
            author=self.responder,
            content_md="visible answer",
            status=Answer.Status.VISIBLE,
        )

    def test_normal_user_created_answer_requires_admin_review(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.responder_token.key}")
        create_response = self.client.post(
            "/api/answers/",
            {"question": self.question.id, "content_md": "pending answer"},
            format="json",
        )
        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(create_response.data["status"], Answer.Status.PENDING)
        answer_id = create_response.data["id"]

        self.client.credentials()
        public_response = self.client.get(
            "/api/answers/", {"question": self.question.id}
        )
        public_ids = {
            item["id"]
            for item in public_response.data.get("results", public_response.data)
        }
        self.assertNotIn(answer_id, public_ids)

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.responder_token.key}")
        owner_response = self.client.get(
            "/api/answers/", {"question": self.question.id}
        )
        owner_ids = {
            item["id"]
            for item in owner_response.data.get("results", owner_response.data)
        }
        self.assertIn(answer_id, owner_ids)

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        approve_response = self.client.post(
            f"/api/answers/{answer_id}/approve/", format="json"
        )
        self.assertEqual(approve_response.status_code, 200)

        self.client.credentials()
        visible_response = self.client.get(
            "/api/answers/", {"question": self.question.id}
        )
        visible_ids = {
            item["id"]
            for item in visible_response.data.get("results", visible_response.data)
        }
        self.assertIn(answer_id, visible_ids)

    def test_author_editing_visible_answer_reverts_to_pending(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.responder_token.key}")
        response = self.client.patch(
            f"/api/answers/{self.answer.id}/",
            {"content_md": "edited answer"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], Answer.Status.PENDING)

        self.answer.refresh_from_db()
        self.assertEqual(self.answer.status, Answer.Status.PENDING)

        self.client.credentials()
        public_response = self.client.get(
            "/api/answers/", {"question": self.question.id}
        )
        public_ids = {
            item["id"]
            for item in public_response.data.get("results", public_response.data)
        }
        self.assertNotIn(self.answer.id, public_ids)

    def test_reject_answer_sends_review_note_notification(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.responder_token.key}")
        create_response = self.client.post(
            "/api/answers/",
            {"question": self.question.id, "content_md": "pending answer"},
            format="json",
        )
        self.assertEqual(create_response.status_code, 201)
        answer_id = create_response.data["id"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.post(
            f"/api/answers/{answer_id}/reject/",
            {"review_note": "回答过于简略，请补充证明"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)

        answer = Answer.objects.get(pk=answer_id)
        self.assertEqual(answer.status, Answer.Status.HIDDEN)
        self.assertEqual(answer.review_note, "回答过于简略，请补充证明")

        notification = UserNotification.objects.get(
            user=self.responder,
            target_type="Answer",
            target_id=answer_id,
        )
        self.assertEqual(notification.level, UserNotification.Level.WARNING)
        self.assertIn("回答过于简略，请补充证明", notification.content)


@override_settings(QA_MODULE_ENABLED=False)
class QAModuleHiddenTests(APITestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Hidden QA", slug="hidden-qa")
        self.user = User.objects.create_user(
            username="qa_hidden_user",
            password="Password123",
            role=User.Role.NORMAL,
        )
        self.admin = User.objects.create_user(
            username="qa_hidden_admin",
            password="Password123",
            role=User.Role.ADMIN,
        )
        self.token = Token.objects.create(user=self.user)
        self.admin_token = Token.objects.create(user=self.admin)
        self.question = Question.objects.create(
            title="HiddenFeature Public Question",
            content_md="HiddenFeature question body",
            author=self.user,
            category=self.category,
            status=Question.Status.OPEN,
        )
        self.answer = Answer.objects.create(
            question=self.question,
            author=self.user,
            content_md="HiddenFeature answer body",
            status=Answer.Status.VISIBLE,
        )
        CompetitionZoneSection.objects.update_or_create(
            key="qa",
            defaults={
                "title": "Hidden QA",
                "target_type": CompetitionZoneSection.TargetType.BUILTIN,
                "builtin_view": CompetitionZoneSection.BuiltinView.QA,
                "is_visible": True,
            },
        )
        ContributionEvent.objects.create(
            user=self.user,
            event_type=ContributionEvent.EventType.QUESTION,
            target_type="Question",
            target_id=self.question.id,
            payload={"title": self.question.title},
        )
        HeaderNavigationItem.objects.update_or_create(
            key=HeaderNavigationItem.NavKey.QUESTIONS,
            defaults={
                "title": "问答",
                "display_order": 1,
                "is_visible": True,
            },
        )
        DeletedContentArchive.objects.create(
            target_type="Question",
            target_id=self.question.id,
            delete_action=DeletedContentArchive.DeleteAction.HIDE,
            title="HiddenFeature archived question",
            content_md="HiddenFeature archived body",
            original_author=self.user,
            original_author_name=self.user.username,
            deleted_by=self.admin,
            deleted_by_name=self.admin.username,
        )
        AIModerationRecord.objects.create(
            target_type=AIModerationRecord.TargetType.QUESTION,
            target_id=self.question.id,
            author=self.user,
            summary="HiddenFeature moderation record",
        )

    def test_question_and_answer_apis_return_not_found_when_module_is_hidden(self):
        response = self.client.get("/api/questions/")
        self.assertEqual(response.status_code, 404)

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        create_response = self.client.post(
            "/api/questions/",
            {
                "title": "New hidden question",
                "content_md": "body",
                "category": self.category.id,
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, 404)

        answer_response = self.client.get("/api/answers/")
        self.assertEqual(answer_response.status_code, 404)

    def test_public_surfaces_do_not_expose_hidden_qa_module(self):
        search_response = self.client.get("/api/search/", {"q": "HiddenFeature"})
        self.assertEqual(search_response.status_code, 200)
        self.assertFalse(
            any(group.get("key") == "qa" for group in search_response.data["groups"])
        )
        self.assertNotIn(
            "HiddenFeature",
            json.dumps(
                [group.get("results", []) for group in search_response.data["groups"]]
            ),
        )

        sections_response = self.client.get("/api/competition-zone-sections/")
        self.assertEqual(sections_response.status_code, 200)
        rows = (
            sections_response.data.get("results", sections_response.data)
            if isinstance(sections_response.data, dict)
            else sections_response.data
        )
        self.assertFalse(any(item.get("builtin_view") == "qa" for item in rows))

        nav_response = self.client.get("/api/header-nav/")
        self.assertEqual(nav_response.status_code, 200)
        nav_rows = (
            nav_response.data.get("results", nav_response.data)
            if isinstance(nav_response.data, dict)
            else nav_response.data
        )
        self.assertFalse(any(item.get("key") == "questions" for item in nav_rows))

    def test_profile_surfaces_do_not_expose_hidden_qa_module(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

        me_response = self.client.get("/api/me/")
        self.assertEqual(me_response.status_code, 200)
        self.assertEqual(me_response.data["stats"]["question_count"], 0)
        self.assertEqual(me_response.data["stats"]["answer_count"], 0)
        self.assertNotIn("HiddenFeature", json.dumps(me_response.data))

        events_response = self.client.get("/api/me/events/")
        self.assertEqual(events_response.status_code, 200)
        events = (
            events_response.data.get("results", events_response.data)
            if isinstance(events_response.data, dict)
            else events_response.data
        )
        self.assertFalse(
            any(item.get("event_type") in {"question", "answer"} for item in events)
        )

    def test_admin_surfaces_do_not_expose_hidden_qa_module(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")

        archives_response = self.client.get("/api/deleted-content-archives/")
        self.assertEqual(archives_response.status_code, 200)
        archives = (
            archives_response.data.get("results", archives_response.data)
            if isinstance(archives_response.data, dict)
            else archives_response.data
        )
        self.assertFalse(
            any(item.get("target_type") in {"Question", "Answer"} for item in archives)
        )
        self.assertNotIn("HiddenFeature", json.dumps(archives_response.data))

        records_response = self.client.get("/api/ai-moderation-records/")
        self.assertEqual(records_response.status_code, 200)
        records = (
            records_response.data.get("results", records_response.data)
            if isinstance(records_response.data, dict)
            else records_response.data
        )
        self.assertFalse(
            any(item.get("target_type") in {"question", "answer"} for item in records)
        )
        self.assertNotIn("HiddenFeature", json.dumps(records_response.data))

        stats_response = self.client.get("/api/ai-moderation-configs/stats/")
        self.assertEqual(stats_response.status_code, 200)
        self.assertFalse(
            any(
                item.get("target_type") in {"question", "answer"}
                for item in stats_response.data.get("by_type", [])
            )
        )


class ArticleCommentFlowTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.category = Category.objects.create(name="Comment", slug="comment")
        self.author = User.objects.create_user(
            username="article_author", password="Password123", role=User.Role.ADMIN
        )
        self.author_token = Token.objects.create(user=self.author)
        self.user = User.objects.create_user(
            username="comment_user", password="Password123", role=User.Role.NORMAL
        )
        self.other = User.objects.create_user(
            username="comment_other", password="Password123", role=User.Role.NORMAL
        )
        self.token = Token.objects.create(user=self.user)
        self.other_token = Token.objects.create(user=self.other)
        self.article_a = Article.objects.create(
            title="Comment A",
            summary="summary",
            content_md="content",
            category=self.category,
            author=self.author,
            last_editor=self.author,
            status=Article.Status.PUBLISHED,
        )
        self.article_b = Article.objects.create(
            title="Comment B",
            summary="summary",
            content_md="content",
            category=self.category,
            author=self.author,
            last_editor=self.author,
            status=Article.Status.PUBLISHED,
        )
        self.parent = ArticleComment.objects.create(
            article=self.article_a,
            author=self.user,
            content="parent",
            status=ArticleComment.Status.VISIBLE,
        )

    def test_parent_comment_must_belong_to_same_article(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        response = self.client.post(
            "/api/comments/",
            {
                "article": self.article_b.id,
                "parent": self.parent.id,
                "content": "cross article reply",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("parent", response.data)

    def test_owner_can_hide_comment(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        response = self.client.delete(f"/api/comments/{self.parent.id}/")
        self.assertEqual(response.status_code, 204)
        self.parent.refresh_from_db()
        self.assertEqual(self.parent.status, ArticleComment.Status.HIDDEN)

    def test_other_user_cannot_hide_comment(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.other_token.key}")
        response = self.client.delete(f"/api/comments/{self.parent.id}/")
        self.assertEqual(response.status_code, 403)

    def test_mine_endpoint_only_returns_current_user_comments(self):
        my_hidden = ArticleComment.objects.create(
            article=self.article_a,
            author=self.user,
            content="my hidden",
            status=ArticleComment.Status.HIDDEN,
        )
        other_comment = ArticleComment.objects.create(
            article=self.article_a,
            author=self.other,
            content="other comment",
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        response = self.client.get("/api/comments/mine/")
        self.assertEqual(response.status_code, 200)
        ids = {item["id"] for item in response.data.get("results", response.data)}
        self.assertIn(self.parent.id, ids)
        self.assertIn(my_hidden.id, ids)
        self.assertNotIn(other_comment.id, ids)

    def test_mine_endpoint_requires_authentication(self):
        response = self.client.get("/api/comments/mine/")
        self.assertIn(response.status_code, (401, 403))

    def test_comment_submit_requires_review_for_normal_user(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        create_response = self.client.post(
            "/api/comments/",
            {
                "article": self.article_a.id,
                "content": "pending comment",
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(create_response.data["status"], ArticleComment.Status.PENDING)
        pending_id = create_response.data["id"]

        self.client.credentials()
        public_list_response = self.client.get(
            "/api/comments/", {"article": self.article_a.id}
        )
        self.assertEqual(public_list_response.status_code, 200)
        public_ids = {
            item["id"]
            for item in public_list_response.data.get(
                "results", public_list_response.data
            )
        }
        self.assertNotIn(pending_id, public_ids)

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        owner_list_response = self.client.get(
            "/api/comments/", {"article": self.article_a.id}
        )
        self.assertEqual(owner_list_response.status_code, 200)
        owner_ids = {
            item["id"]
            for item in owner_list_response.data.get(
                "results", owner_list_response.data
            )
        }
        self.assertIn(pending_id, owner_ids)

    def test_admin_can_approve_pending_comment(self):
        pending = ArticleComment.objects.create(
            article=self.article_a,
            author=self.user,
            content="pending for approve",
            status=ArticleComment.Status.PENDING,
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.author_token.key}")
        response = self.client.post(
            f"/api/comments/{pending.id}/approve/", {"review_note": "ok"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        pending.refresh_from_db()
        self.assertEqual(pending.status, ArticleComment.Status.VISIBLE)

    def test_reject_comment_saves_review_note_and_notifies_author(self):
        pending = ArticleComment.objects.create(
            article=self.article_a,
            author=self.user,
            content="pending for reject",
            status=ArticleComment.Status.PENDING,
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.author_token.key}")
        response = self.client.post(
            f"/api/comments/{pending.id}/reject/",
            {"review_note": "请补充更具体的反馈内容"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        pending.refresh_from_db()
        self.assertEqual(pending.status, ArticleComment.Status.HIDDEN)
        self.assertEqual(pending.review_note, "请补充更具体的反馈内容")
        self.assertEqual(pending.reviewer_id, self.author.id)
        self.assertIsNotNone(pending.reviewed_at)

        notification = UserNotification.objects.get(
            user=self.user,
            target_type="ArticleComment",
            target_id=pending.id,
        )
        self.assertEqual(notification.level, UserNotification.Level.WARNING)
        self.assertIn("请补充更具体的反馈内容", notification.content)

    def test_admin_default_list_excludes_hidden_comments(self):
        pending = ArticleComment.objects.create(
            article=self.article_a,
            author=self.other,
            content="pending comment",
            status=ArticleComment.Status.PENDING,
        )
        hidden = ArticleComment.objects.create(
            article=self.article_a,
            author=self.other,
            content="hidden comment",
            status=ArticleComment.Status.HIDDEN,
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.author_token.key}")
        response = self.client.get("/api/comments/", {"article": self.article_a.id})
        self.assertEqual(response.status_code, 200)
        ids = {item["id"] for item in response.data.get("results", response.data)}
        self.assertIn(self.parent.id, ids)
        self.assertIn(pending.id, ids)
        self.assertNotIn(hidden.id, ids)

    def test_admin_can_append_review_note_to_hidden_comment(self):
        hidden = ArticleComment.objects.create(
            article=self.article_a,
            author=self.other,
            content="hidden comment",
            status=ArticleComment.Status.HIDDEN,
            review_note="first hidden note",
            reviewer=self.author,
            reviewed_at=timezone.now(),
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.author_token.key}")
        response = self.client.post(
            f"/api/comments/{hidden.id}/append-review-note/",
            {"note": "second hidden note"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        hidden.refresh_from_db()
        self.assertIn("first hidden note", hidden.review_note)
        self.assertIn("second hidden note", hidden.review_note)
        self.assertIn(self.author.username, hidden.review_note)

    def test_admin_can_bulk_reject_pending_comments(self):
        pending_a = ArticleComment.objects.create(
            article=self.article_a,
            author=self.user,
            content="pending-a",
            status=ArticleComment.Status.PENDING,
        )
        pending_b = ArticleComment.objects.create(
            article=self.article_a,
            author=self.other,
            content="pending-b",
            status=ArticleComment.Status.PENDING,
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.author_token.key}")
        response = self.client.post(
            "/api/comments/bulk-review/",
            {
                "ids": [pending_a.id, pending_b.id],
                "action": "reject",
                "review_note": "bad quality",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["success"], 2)
        pending_a.refresh_from_db()
        pending_b.refresh_from_db()
        self.assertEqual(pending_a.status, ArticleComment.Status.HIDDEN)
        self.assertEqual(pending_b.status, ArticleComment.Status.HIDDEN)

    def test_author_editing_visible_comment_reverts_to_pending(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        response = self.client.patch(
            f"/api/comments/{self.parent.id}/",
            {"content": "edited content"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], ArticleComment.Status.PENDING)

        self.parent.refresh_from_db()
        self.assertEqual(self.parent.status, ArticleComment.Status.PENDING)

        self.client.credentials()
        public_response = self.client.get(
            "/api/comments/", {"article": self.article_a.id}
        )
        public_ids = {
            item["id"]
            for item in public_response.data.get("results", public_response.data)
        }
        self.assertNotIn(self.parent.id, public_ids)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", QA_MODULE_ENABLED=True)
class ProfileAndMineEndpointsTests(APITestCase):
    def setUp(self):
        cache.clear()
        mail.outbox = []
        self.category = Category.objects.create(name="Graph", slug="graph")
        self.user = User.objects.create_user(
            username="student",
            email="student@example.com",
            password="Password123",
            role=User.Role.NORMAL,
        )
        self.other = User.objects.create_user(
            username="other",
            email="other@example.com",
            password="Password123",
            role=User.Role.NORMAL,
        )
        self.token = Token.objects.create(user=self.user)

        self.my_question = Question.objects.create(
            title="Q1",
            content_md="question body",
            author=self.user,
            category=self.category,
        )
        self.other_question = Question.objects.create(
            title="Q2",
            content_md="other body",
            author=self.other,
            category=self.category,
        )
        self.my_answer = Answer.objects.create(
            question=self.other_question,
            author=self.user,
            content_md="my answer",
        )
        self.other_answer = Answer.objects.create(
            question=self.my_question,
            author=self.other,
            content_md="other answer",
        )
        self.revision_article = Article.objects.create(
            title="Revision Target",
            summary="summary",
            content_md="origin",
            category=self.category,
            author=self.other,
            last_editor=self.other,
            status=Article.Status.PUBLISHED,
        )
        self.my_revision = RevisionProposal.objects.create(
            article=self.revision_article,
            proposer=self.user,
            proposed_title="Revision Target",
            proposed_summary="my summary",
            proposed_content_md="my revision",
            reason="my reason",
        )
        self.other_revision = RevisionProposal.objects.create(
            article=self.revision_article,
            proposer=self.other,
            proposed_title="Revision Target Other",
            proposed_summary="other summary",
            proposed_content_md="other revision",
            reason="other reason",
        )
        self.my_event_star = ContributionEvent.objects.create(
            user=self.user,
            event_type=ContributionEvent.EventType.STAR,
            target_type="Article",
            target_id=11,
            payload={"action": "star"},
        )
        self.my_event_issue = ContributionEvent.objects.create(
            user=self.user,
            event_type=ContributionEvent.EventType.ISSUE,
            target_type="IssueTicket",
            target_id=22,
            payload={"action": "create_issue"},
        )
        self.other_event = ContributionEvent.objects.create(
            user=self.other,
            event_type=ContributionEvent.EventType.COMMENT,
            target_type="ArticleComment",
            target_id=33,
            payload={"action": "comment"},
        )
        self.my_security_event = SecurityAuditLog.objects.create(
            event_type=SecurityAuditLog.EventType.LOGIN_SUCCESS,
            user=self.user,
            username=self.user.username,
            ip_address="127.0.0.9",
            success=True,
            detail="profile test login success",
        )
        self.my_username_event = SecurityAuditLog.objects.create(
            event_type=SecurityAuditLog.EventType.LOGIN_FAILED,
            username=self.user.username,
            ip_address="127.0.0.10",
            success=False,
            detail="profile test login failed",
        )
        self.other_security_event = SecurityAuditLog.objects.create(
            event_type=SecurityAuditLog.EventType.LOGIN_FAILED,
            username=self.other.username,
            ip_address="127.0.0.11",
            success=False,
            detail="other user event",
        )

    def extract_code_from_last_email(self):
        self.assertTrue(mail.outbox)
        message = mail.outbox[-1]
        match = re.search(r"(\d{4,8})", message.body)
        self.assertIsNotNone(match)
        return match.group(1)

    def request_and_confirm_password_change(
        self, *, token: str, old_password: str, new_password: str
    ):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token}")
        code_response = self.client.post(
            "/api/me/change-password-code/",
            {
                "old_password": old_password,
                "new_password": new_password,
                "confirm_password": new_password,
            },
            format="json",
        )
        self.assertEqual(code_response.status_code, 200)
        confirm_response = self.client.post(
            "/api/me/change-password/",
            {
                "ticket_token": code_response.data["ticket_token"],
                "code": self.extract_code_from_last_email(),
            },
            format="json",
        )
        self.assertEqual(confirm_response.status_code, 200)
        EmailVerificationTicket.objects.filter(
            purpose=EmailVerificationTicket.Purpose.CHANGE_PASSWORD,
            user=self.user,
        ).update(created_at=timezone.now() - timedelta(minutes=2))
        return confirm_response.data["token"]

    def test_patch_me_profile(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        response = self.client.patch(
            "/api/me/",
            {
                "username": "student_renamed",
                "gender": User.Gender.FEMALE,
                "school_name": "Algo University",
                "bio": "Competitive programming learner",
                "avatar_url": "https://example.com/avatar.png",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("profile_settings", response.data)
        self.assertEqual(response.data["user"]["username"], "student_renamed")
        self.assertEqual(response.data["user"]["gender"], User.Gender.FEMALE)
        self.assertEqual(response.data["user"]["school_name"], "Algo University")
        self.assertEqual(
            response.data["user"]["bio"], "Competitive programming learner"
        )
        self.assertEqual(
            response.data["user"]["avatar_url"], "https://example.com/avatar.png"
        )
        self.assertEqual(
            response.data["profile_settings"]["school_name"], "Algo University"
        )
        self.assertEqual(
            response.data["profile_settings"]["gender"], User.Gender.FEMALE
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "student_renamed")
        self.assertEqual(self.user.gender, User.Gender.FEMALE)
        self.assertEqual(self.user.school_name, "Algo University")
        self.assertEqual(self.user.bio, "Competitive programming learner")
        self.assertEqual(self.user.avatar_url, "https://example.com/avatar.png")

    def test_patch_me_profile_uploads_avatar_image(self):
        temp_media_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_media_dir.cleanup)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        avatar = make_test_image_upload("avatar.png", size=(640, 480), color=(32, 120, 240))

        with override_settings(MEDIA_ROOT=temp_media_dir.name, MEDIA_URL="/media/"):
            with patch(
                "wiki.serializers.moderate_image_url",
                return_value=SimpleNamespace(
                    provider="test",
                    decision="approve",
                    risk_level="safe",
                    summary="approved",
                ),
            ):
                response = self.client.patch(
                    "/api/me/",
                    {"username": "student", "avatar_image": avatar},
                    format="multipart",
                )

        self.assertEqual(response.status_code, 200)
        avatar_url = response.data["user"]["avatar_url"]
        self.assertTrue(avatar_url.startswith("/media/avatars/"))
        self.assertTrue(avatar_url.endswith(".webp"))
        stored_path = Path(temp_media_dir.name) / avatar_url.removeprefix("/media/")
        self.assertTrue(stored_path.exists())
        self.assertLess(stored_path.stat().st_size, 96 * 1024)
        self.user.refresh_from_db()
        self.assertEqual(self.user.avatar_url, avatar_url)

    def test_patch_me_profile_allows_manager_avatar_when_moderation_is_manual(self):
        temp_media_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_media_dir.cleanup)
        self.user.role = User.Role.ADMIN
        self.user.save(update_fields=["role"])
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        avatar = make_test_image_upload("avatar.png", size=(640, 480), color=(32, 120, 240))

        with override_settings(MEDIA_ROOT=temp_media_dir.name, MEDIA_URL="/media/"):
            with patch(
                "wiki.serializers.moderate_image_url",
                return_value=SimpleNamespace(
                    provider="aliyun_green",
                    decision="manual",
                    risk_level="unknown",
                    summary="阿里云图片审核暂时不可用。",
                ),
            ):
                response = self.client.patch(
                    "/api/me/",
                    {"username": "student", "avatar_image": avatar},
                    format="multipart",
                )

        self.assertEqual(response.status_code, 200)
        avatar_url = response.data["user"]["avatar_url"]
        self.assertTrue(avatar_url.startswith("/media/avatars/"))
        self.assertTrue(avatar_url.endswith(".webp"))
        stored_path = Path(temp_media_dir.name) / avatar_url.removeprefix("/media/")
        self.assertTrue(stored_path.exists())
        self.user.refresh_from_db()
        self.assertEqual(self.user.avatar_url, avatar_url)

    def test_patch_me_rejects_duplicate_username(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        response = self.client.patch(
            "/api/me/",
            {"username": "OTHER"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("username", response.data)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "student")

    def test_get_me_contains_profile_settings(self):
        self.user.school_name = "Algo University"
        self.user.bio = "Competitive programming learner"
        self.user.avatar_url = "https://example.com/avatar.png"
        self.user.save(update_fields=["school_name", "bio", "avatar_url"])
        pending_moment = Moment.objects.create(
            author=self.user,
            content="pending moment",
            status=Moment.Status.PENDING,
        )
        MomentComment.objects.create(
            moment=pending_moment,
            author=self.user,
            content="pending comment",
            status=MomentComment.Status.PENDING,
        )
        TrickEntry.objects.create(
            title="Pending Trick",
            content_md="pending trick body",
            author=self.user,
            status=TrickEntry.Status.PENDING,
        )
        my_article = Article.objects.create(
            title="My Article",
            summary="my article summary",
            content_md="my article body",
            category=self.category,
            author=self.user,
            status=Article.Status.PUBLISHED,
        )
        ArticleComment.objects.create(
            article=my_article,
            author=self.user,
            content="article comment",
            status=ArticleComment.Status.VISIBLE,
        )
        ArticleStar.objects.create(user=self.user, article=my_article)
        IssueTicket.objects.create(
            kind=IssueTicket.Kind.ISSUE,
            title="My Issue",
            content="issue body",
            author=self.user,
        )
        CompetitionPracticeLinkProposal.objects.create(
            proposer=self.user,
            proposed_year=2026,
            proposed_series=CompetitionPracticeLink.Series.ICPC,
            proposed_stage=CompetitionPracticeLink.Stage.REGIONAL,
            proposed_short_name="Pending Practice",
            proposed_official_name="Pending Practice Official",
            status=CompetitionPracticeLinkProposal.Status.PENDING,
        )
        PhoneVerification.objects.create(
            user=self.user,
            status=PhoneVerification.Status.VERIFIED,
            phone_masked="138****1234",
            phone_last4="1234",
            verified_at=timezone.now(),
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        response = self.client.get("/api/me/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["user"]["school_name"], "Algo University")
        self.assertEqual(
            response.data["user"]["bio"], "Competitive programming learner"
        )
        self.assertEqual(
            response.data["user"]["avatar_url"], "https://example.com/avatar.png"
        )
        self.assertIn("profile_settings", response.data)
        self.assertEqual(
            response.data["profile_settings"]["email"], "student@example.com"
        )
        self.assertFalse(response.data["profile_settings"]["email_verified"])
        self.assertEqual(response.data["phone_verification"]["status"], "verified")
        self.assertEqual(response.data["phone_verification"]["phone_masked"], "138****1234")
        self.assertIn("todo_summary", response.data)
        self.assertIn("creation_summary", response.data)
        todo_items = {
            item["key"]: item for item in response.data["todo_summary"]["items"]
        }
        self.assertEqual(todo_items["phone_verification"]["count"], 0)
        self.assertEqual(todo_items["pending_moments"]["count"], 2)
        self.assertEqual(todo_items["pending_tricks"]["count"], 1)
        self.assertEqual(todo_items["pending_revisions"]["count"], 1)
        self.assertEqual(todo_items["pending_competition"]["count"], 1)
        creation_groups = {
            group["key"]: group for group in response.data["creation_summary"]["groups"]
        }
        self.assertIn("moments", creation_groups)
        self.assertIn("knowledge", creation_groups)
        self.assertIn("competition", creation_groups)
        self.assertIn("collection_feedback", creation_groups)
        knowledge_items = {
            item["key"]: item for item in creation_groups["knowledge"]["items"]
        }
        self.assertEqual(knowledge_items["articles"]["count"], 1)
        self.assertEqual(knowledge_items["article_comments"]["count"], 1)
        self.assertEqual(knowledge_items["revisions_total"]["count"], 1)
        collection_items = {
            item["key"]: item
            for item in creation_groups["collection_feedback"]["items"]
        }
        self.assertEqual(collection_items["stars"]["count"], 1)
        self.assertEqual(collection_items["issues"]["count"], 1)

    def test_public_question_author_profile_fields_are_hidden(self):
        self.other.school_name = "Hidden University"
        self.other.bio = "Should stay private"
        self.other.avatar_url = "https://example.com/hidden.png"
        self.other.save(update_fields=["school_name", "bio", "avatar_url"])

        response = self.client.get("/api/questions/")
        self.assertEqual(response.status_code, 200)
        items = response.data.get("results", response.data)
        question_payload = next(
            item for item in items if item["id"] == self.other_question.id
        )

        self.assertEqual(question_payload["author"]["username"], self.other.username)
        self.assertEqual(question_payload["author"]["school_name"], "")
        self.assertEqual(question_payload["author"]["bio"], "")
        self.assertEqual(question_payload["author"]["avatar_url"], "")

    def test_patch_me_rejects_direct_email_change(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        response = self.client.patch(
            "/api/me/",
            {"email": "OTHER@example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.data)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "student@example.com")

    def test_email_change_flow_updates_email_and_marks_verified(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        request_response = self.client.post(
            "/api/me/email-code/",
            {
                "email": "student+new@example.com",
                "current_password": "Password123",
            },
            format="json",
        )
        self.assertEqual(request_response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        code_match = re.search(r"验证码[:：]\s*(\d+)", mail.outbox[-1].body)
        self.assertIsNotNone(code_match)

        response = self.client.post(
            "/api/me/change-email/",
            {
                "ticket_token": request_response.data["ticket_token"],
                "code": code_match.group(1),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "student+new@example.com")
        self.assertIsNotNone(self.user.email_verified_at)
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn("student@example.com", mail.outbox[-1].body)
        self.assertIn("student+new@example.com", mail.outbox[-1].body)
        self.assertTrue(
            SecurityAuditLog.objects.filter(
                event_type=SecurityAuditLog.EventType.EMAIL_CHANGED,
                username="student",
                success=True,
            ).exists()
        )

    def test_mine_question_and_answer_endpoints(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

        q_response = self.client.get("/api/questions/mine/")
        self.assertEqual(q_response.status_code, 200)
        q_ids = {item["id"] for item in q_response.data.get("results", q_response.data)}
        self.assertEqual(q_ids, {self.my_question.id})

        a_response = self.client.get("/api/answers/mine/")
        self.assertEqual(a_response.status_code, 200)
        a_items = a_response.data.get("results", a_response.data)
        a_ids = {item["id"] for item in a_items}
        self.assertEqual(a_ids, {self.my_answer.id})
        self.assertEqual(a_items[0]["question_title"], self.other_question.title)

    def test_questions_mine_endpoint_hides_deleted_questions_by_default(self):
        self.my_question.status = Question.Status.HIDDEN
        self.my_question.save(update_fields=["status", "updated_at"])

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

        default_response = self.client.get("/api/questions/mine/")
        default_ids = {
            item["id"]
            for item in default_response.data.get("results", default_response.data)
        }
        self.assertNotIn(self.my_question.id, default_ids)

        hidden_response = self.client.get(
            "/api/questions/mine/", {"status": Question.Status.HIDDEN}
        )
        hidden_ids = {
            item["id"]
            for item in hidden_response.data.get("results", hidden_response.data)
        }
        self.assertIn(self.my_question.id, hidden_ids)

    def test_change_password_rotates_token_and_accepts_new_password(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        code_response = self.client.post(
            "/api/me/change-password-code/",
            {
                "old_password": "Password123",
                "new_password": "Password456",
                "confirm_password": "Password456",
            },
            format="json",
        )
        self.assertEqual(code_response.status_code, 200)
        self.assertIn("ticket_token", code_response.data)
        self.assertTrue(
            SecurityAuditLog.objects.filter(
                event_type=SecurityAuditLog.EventType.PASSWORD_CHANGE_REQUESTED,
                user=self.user,
                success=True,
            ).exists()
        )

        response = self.client.post(
            "/api/me/change-password/",
            {
                "ticket_token": code_response.data["ticket_token"],
                "code": self.extract_code_from_last_email(),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("token", response.data)

        old_token = self.token.key
        new_token = response.data["token"]
        self.assertNotEqual(old_token, new_token)
        self.assertFalse(Token.objects.filter(key=old_token).exists())
        self.assertTrue(Token.objects.filter(key=new_token).exists())

        self.client.credentials()
        login_old = self.client.post(
            "/api/auth/login/",
            {"username": "student", "password": "Password123"},
            format="json",
        )
        self.assertEqual(login_old.status_code, 400)

        login_new = self.client.post(
            "/api/auth/login/",
            {"username": "student", "password": "Password456"},
            format="json",
        )
        self.assertEqual(login_new.status_code, 200)

    def test_change_password_rejects_wrong_old_password(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        response = self.client.post(
            "/api/me/change-password-code/",
            {
                "old_password": "WrongPassword",
                "new_password": "Password456",
                "confirm_password": "Password456",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_change_password_rejects_recent_password_reuse(self):
        first_token = self.request_and_confirm_password_change(
            token=self.token.key,
            old_password="Password123",
            new_password="ReuseStrongPass1!",
        )
        second_token = self.request_and_confirm_password_change(
            token=first_token,
            old_password="ReuseStrongPass1!",
            new_password="ReuseStrongPass2!",
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {second_token}")
        third_change = self.client.post(
            "/api/me/change-password-code/",
            {
                "old_password": "ReuseStrongPass2!",
                "new_password": "ReuseStrongPass1!",
                "confirm_password": "ReuseStrongPass1!",
            },
            format="json",
        )

        self.assertEqual(third_change.status_code, 400)
        self.assertIn("Cannot reuse recent password.", str(third_change.data))
        self.assertGreaterEqual(
            PasswordHistory.objects.filter(user=self.user).count(), 2
        )

    def test_mine_events_endpoint_with_filter(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

        response = self.client.get("/api/me/events/")
        self.assertEqual(response.status_code, 200)
        ids = {item["id"] for item in response.data.get("results", response.data)}
        self.assertIn(self.my_event_star.id, ids)
        self.assertIn(self.my_event_issue.id, ids)
        self.assertNotIn(self.other_event.id, ids)

        filtered = self.client.get("/api/me/events/", {"event_type": "issue"})
        self.assertEqual(filtered.status_code, 200)
        filtered_items = filtered.data.get("results", filtered.data)
        filtered_ids = {item["id"] for item in filtered_items}
        self.assertEqual(filtered_ids, {self.my_event_issue.id})

    def test_mine_security_events_endpoint_is_isolated(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

        response = self.client.get("/api/me/security-events/")
        self.assertEqual(response.status_code, 200)
        ids = {item["id"] for item in response.data.get("results", response.data)}
        self.assertIn(self.my_security_event.id, ids)
        self.assertIn(self.my_username_event.id, ids)
        self.assertNotIn(self.other_security_event.id, ids)

        filtered = self.client.get(
            "/api/me/security-events/",
            {"event_type": SecurityAuditLog.EventType.LOGIN_FAILED, "success": "0"},
        )
        self.assertEqual(filtered.status_code, 200)
        filtered_items = filtered.data.get("results", filtered.data)
        filtered_ids = {item["id"] for item in filtered_items}
        self.assertEqual(filtered_ids, {self.my_username_event.id})

    def test_mine_security_events_requires_authentication(self):
        response = self.client.get("/api/me/security-events/")
        self.assertIn(response.status_code, (401, 403))

    def test_mine_security_summary_endpoint(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        response = self.client.get("/api/me/security-summary/", {"window_hours": 48})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["window_hours"], 48)
        self.assertIn("totals", response.data)
        self.assertIn("top_failed_ips", response.data)
        self.assertGreaterEqual(response.data["totals"]["events"], 2)
        self.assertGreaterEqual(response.data["totals"]["login_failed"], 1)

    def test_mine_security_summary_requires_authentication(self):
        response = self.client.get("/api/me/security-summary/")
        self.assertIn(response.status_code, (401, 403))

    def test_revision_list_is_isolated_to_current_user(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

        response = self.client.get("/api/revisions/")
        self.assertEqual(response.status_code, 200)
        ids = {item["id"] for item in response.data.get("results", response.data)}
        self.assertIn(self.my_revision.id, ids)
        self.assertNotIn(self.other_revision.id, ids)

        forced_filter = self.client.get("/api/revisions/", {"proposer": self.other.id})
        self.assertEqual(forced_filter.status_code, 200)
        forced_items = forced_filter.data.get("results", forced_filter.data)
        forced_ids = {item["id"] for item in forced_items}
        self.assertEqual(forced_ids, set())

    def test_user_can_update_own_pending_revision(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        response = self.client.patch(
            f"/api/revisions/{self.my_revision.id}/",
            {
                "proposed_title": "Revision Target Updated",
                "proposed_summary": "updated summary",
                "proposed_content_md": "updated content",
                "reason": "updated reason",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.my_revision.refresh_from_db()
        self.assertEqual(self.my_revision.proposed_title, "Revision Target Updated")
        self.assertEqual(self.my_revision.proposed_content_md, "updated content")

    def test_user_cannot_update_other_user_revision(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        response = self.client.patch(
            f"/api/revisions/{self.other_revision.id}/",
            {"proposed_content_md": "should fail"},
            format="json",
        )
        self.assertEqual(response.status_code, 404)

    def test_user_cannot_update_non_pending_revision(self):
        self.my_revision.status = RevisionProposal.Status.APPROVED
        self.my_revision.save(update_fields=["status", "updated_at"])
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        response = self.client.patch(
            f"/api/revisions/{self.my_revision.id}/",
            {"proposed_content_md": "should fail"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_user_can_cancel_own_pending_revision(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        response = self.client.delete(f"/api/revisions/{self.my_revision.id}/")
        self.assertEqual(response.status_code, 204)
        self.assertFalse(
            RevisionProposal.objects.filter(id=self.my_revision.id).exists()
        )

    def test_user_cannot_cancel_non_pending_revision(self):
        self.my_revision.status = RevisionProposal.Status.REJECTED
        self.my_revision.save(update_fields=["status", "updated_at"])
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        response = self.client.delete(f"/api/revisions/{self.my_revision.id}/")
        self.assertEqual(response.status_code, 400)
        self.assertTrue(
            RevisionProposal.objects.filter(id=self.my_revision.id).exists()
        )

    def test_revision_creation_rejects_more_than_five_pending_items(self):
        for index in range(4):
            RevisionProposal.objects.create(
                article=self.revision_article,
                proposer=self.user,
                proposed_title=f"extra-{index}",
                proposed_summary="s",
                proposed_content_md=f"pending-{index}",
                reason="r",
            )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        response = self.client.post(
            "/api/revisions/",
            {
                "article": self.revision_article.id,
                "proposed_title": "overflow",
                "proposed_summary": "overflow",
                "proposed_content_md": "overflow",
                "reason": "overflow",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("at most 5 pending", str(response.data.get("detail", "")))

    def test_admin_revision_create_is_auto_approved_and_applied(self):
        admin = User.objects.create_user(
            username="revision_admin",
            password="Password123",
            role=User.Role.ADMIN,
        )
        admin_token = Token.objects.create(user=admin)

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {admin_token.key}")
        response = self.client.post(
            "/api/revisions/",
            {
                "article": self.revision_article.id,
                "proposed_title": "Admin Published Title",
                "proposed_summary": "admin summary",
                "proposed_content_md": "admin published content",
                "reason": "manager direct publish",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], RevisionProposal.Status.APPROVED)
        self.revision_article.refresh_from_db()
        self.assertEqual(self.revision_article.title, "Admin Published Title")
        self.assertEqual(self.revision_article.summary, "admin summary")
        self.assertEqual(self.revision_article.content_md, "admin published content")
        self.assertEqual(self.revision_article.last_editor_id, admin.id)

    def test_admin_revision_create_can_clear_summary_immediately(self):
        admin = User.objects.create_user(
            username="revision_admin_blank_summary",
            password="Password123",
            role=User.Role.ADMIN,
        )
        admin_token = Token.objects.create(user=admin)

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {admin_token.key}")
        response = self.client.post(
            "/api/revisions/",
            {
                "article": self.revision_article.id,
                "proposed_title": self.revision_article.title,
                "proposed_summary": "",
                "proposed_content_md": "content after clearing summary",
                "reason": "clear summary",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], RevisionProposal.Status.APPROVED)
        self.revision_article.refresh_from_db()
        self.assertEqual(self.revision_article.summary, "")
        self.assertEqual(
            self.revision_article.content_md, "content after clearing summary"
        )
        self.assertEqual(self.revision_article.last_editor_id, admin.id)


class RevisionMergeFlowTests(APITestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Revision Merge", slug="revision-merge")
        self.author = User.objects.create_user(username="merge_author", password="Password123", role=User.Role.ADMIN)
        self.user = User.objects.create_user(username="merge_user", password="Password123", role=User.Role.NORMAL)
        self.admin = User.objects.create_user(username="merge_admin", password="Password123", role=User.Role.ADMIN)
        self.user_token = Token.objects.create(user=self.user)
        self.admin_token = Token.objects.create(user=self.admin)
        self.article = Article.objects.create(
            title="Merge Article",
            summary="summary",
            content_md="alpha\nbeta\ngamma\n",
            category=self.category,
            author=self.author,
            last_editor=self.author,
            status=Article.Status.PUBLISHED,
        )

    def test_revision_create_auto_rebases_non_overlapping_changes(self):
        base_title = self.article.title
        base_summary = self.article.summary
        base_content_md = self.article.content_md
        base_updated_at = self.article.updated_at

        self.article.content_md = "alpha\nbeta updated\ngamma\n"
        self.article.save(update_fields=["content_md", "updated_at"])

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.user_token.key}")
        response = self.client.post(
            "/api/revisions/",
            {
                "article": self.article.id,
                "base_title": base_title,
                "base_summary": base_summary,
                "base_content_md": base_content_md,
                "base_updated_at": base_updated_at.isoformat(),
                "proposed_title": base_title,
                "proposed_summary": base_summary,
                "proposed_content_md": "alpha\nbeta\ngamma\ndelta\n",
                "reason": "append delta",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], RevisionProposal.Status.PENDING)
        self.assertEqual(response.data["base_content_md"], "alpha\nbeta updated\ngamma\n")
        self.assertEqual(response.data["proposed_content_md"], "alpha\nbeta updated\ngamma\ndelta\n")
        self.assertTrue(response.data["base_matches_article"])

    def test_revision_create_returns_conflict_for_same_line_changes(self):
        base_title = self.article.title
        base_summary = self.article.summary
        base_content_md = self.article.content_md
        base_updated_at = self.article.updated_at

        self.article.content_md = "alpha\nbeta current\ngamma\n"
        self.article.save(update_fields=["content_md", "updated_at"])

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.user_token.key}")
        response = self.client.post(
            "/api/revisions/",
            {
                "article": self.article.id,
                "base_title": base_title,
                "base_summary": base_summary,
                "base_content_md": base_content_md,
                "base_updated_at": base_updated_at.isoformat(),
                "proposed_title": base_title,
                "proposed_summary": base_summary,
                "proposed_content_md": "alpha\nbeta proposed\ngamma\n",
                "reason": "modify beta",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "revision_merge_conflict")
        self.assertIn("<<<<<<< Current Article", response.data["merge"]["merged"]["content_md"])
        self.assertEqual(RevisionProposal.objects.count(), 0)

    def test_revision_approve_auto_merges_non_overlapping_changes(self):
        proposal = RevisionProposal.objects.create(
            article=self.article,
            proposer=self.user,
            base_title=self.article.title,
            base_summary=self.article.summary,
            base_content_md=self.article.content_md,
            base_updated_at=self.article.updated_at,
            proposed_title=self.article.title,
            proposed_summary=self.article.summary,
            proposed_content_md="alpha\nbeta\ngamma\ndelta\n",
            reason="append delta",
        )

        self.article.content_md = "alpha\nbeta updated\ngamma\n"
        self.article.save(update_fields=["content_md", "updated_at"])

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.post(
            f"/api/revisions/{proposal.id}/approve/",
            {"review_note": "merged"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        proposal.refresh_from_db()
        self.article.refresh_from_db()
        self.assertEqual(proposal.status, RevisionProposal.Status.APPROVED)
        self.assertEqual(proposal.base_content_md, "alpha\nbeta updated\ngamma\n")
        self.assertEqual(proposal.proposed_content_md, "alpha\nbeta updated\ngamma\ndelta\n")
        self.assertEqual(self.article.content_md, "alpha\nbeta updated\ngamma\ndelta\n")

    def test_revision_approve_returns_conflict_for_same_line_changes(self):
        proposal = RevisionProposal.objects.create(
            article=self.article,
            proposer=self.user,
            base_title=self.article.title,
            base_summary=self.article.summary,
            base_content_md=self.article.content_md,
            base_updated_at=self.article.updated_at,
            proposed_title=self.article.title,
            proposed_summary=self.article.summary,
            proposed_content_md="alpha\nbeta proposed\ngamma\n",
            reason="modify beta",
        )

        self.article.content_md = "alpha\nbeta current\ngamma\n"
        self.article.save(update_fields=["content_md", "updated_at"])

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.post(
            f"/api/revisions/{proposal.id}/approve/",
            {"review_note": "try approve"},
            format="json",
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "revision_merge_conflict")
        proposal.refresh_from_db()
        self.article.refresh_from_db()
        self.assertEqual(proposal.status, RevisionProposal.Status.PENDING)
        self.assertEqual(self.article.content_md, "alpha\nbeta current\ngamma\n")

    def test_revision_reject_sends_review_note_notification(self):
        proposal = RevisionProposal.objects.create(
            article=self.article,
            proposer=self.user,
            base_title=self.article.title,
            base_summary=self.article.summary,
            base_content_md=self.article.content_md,
            base_updated_at=self.article.updated_at,
            proposed_title=self.article.title,
            proposed_summary=self.article.summary,
            proposed_content_md="alpha\nbeta proposed\ngamma\n",
            reason="modify beta",
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.post(
            f"/api/revisions/{proposal.id}/reject/",
            {"review_note": "Please explain why this change is needed."},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, RevisionProposal.Status.REJECTED)
        self.assertEqual(
            proposal.review_note, "Please explain why this change is needed."
        )
        notification = UserNotification.objects.get(
            user=self.user,
            target_type="RevisionProposal",
            target_id=proposal.id,
        )
        self.assertEqual(notification.level, UserNotification.Level.WARNING)
        self.assertIn("Please explain why", notification.content)


class TrickEntryFlowTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="trick_user",
            password="Password123",
            role=User.Role.NORMAL,
        )
        self.other_user = User.objects.create_user(
            username="trick_other",
            password="Password123",
            role=User.Role.NORMAL,
        )
        self.admin = User.objects.create_user(
            username="trick_admin",
            password="Password123",
            role=User.Role.ADMIN,
        )
        self.token = Token.objects.create(user=self.user)
        self.other_token = Token.objects.create(user=self.other_user)
        self.admin_token = Token.objects.create(user=self.admin)
        self.other_user.trick_contribution_score = 100
        self.other_user.save(update_fields=["trick_contribution_score"])
        self.admin.trick_contribution_score = 100
        self.admin.save(update_fields=["trick_contribution_score"])

        self.approved = TrickEntry.objects.create(
            title="??? trick",
            content_md="?? `x & -x` ???? lowbit?",
            keywords_text="lowbit bitwise",
            author=self.user,
            status=TrickEntry.Status.APPROVED,
        )
        self.pending = TrickEntry.objects.create(
            title="?????",
            content_md="????????",
            author=self.user,
            status=TrickEntry.Status.PENDING,
        )
        self.rejected = TrickEntry.objects.create(
            title="?????",
            content_md="??????????",
            author=self.user,
            status=TrickEntry.Status.REJECTED,
        )
        self.term, _ = TrickTerm.objects.get_or_create(
            name="树状数组",
            defaults={"is_active": True, "is_builtin": True},
        )
        self.popular = TrickEntry.objects.create(
            title="popular trick",
            content_md="popular content",
            keywords_text="tournament graph",
            author=self.other_user,
            status=TrickEntry.Status.APPROVED,
        )

        self.term = TrickTerm.objects.get(name="数据结构")
        self.approved.terms.add(self.term)
        self.popular.terms.add(self.term)
        old_time = timezone.now() - timedelta(days=1)
        TrickEntry.objects.filter(id=self.popular.id).update(
            created_at=old_time,
            updated_at=old_time,
        )
        self.popular.refresh_from_db()
        TrickEntryLike.objects.create(user=self.admin, trick_entry=self.approved)
        TrickEntryLike.objects.create(user=self.admin, trick_entry=self.popular)
        TrickEntryLike.objects.create(user=self.user, trick_entry=self.popular)

    def _create_pending_trick(self, *, author, title, content_md, keywords_text):
        entry = TrickEntry.objects.create(
            title=title,
            content_md=content_md,
            keywords_text=keywords_text,
            author=author,
            status=TrickEntry.Status.PENDING,
        )
        entry.terms.add(self.term)
        return entry

    def _approve_trick(self, entry):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.post(
            f"/api/tricks/{entry.id}/set-status/",
            {"status": TrickEntry.Status.APPROVED},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        entry.refresh_from_db()
        return entry

    def _create_deleted_trick_archive(self):
        entry = TrickEntry.objects.create(
            title="deleted trick",
            content_md="deleted trick body",
            keywords_text="deleted sample",
            author=self.user,
            status=TrickEntry.Status.PENDING,
        )
        entry.terms.add(self.term)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.delete(
            f"/api/tricks/{entry.id}/",
            {"review_note": "duplicate trick"},
            format="json",
        )
        self.assertEqual(response.status_code, 204)
        return DeletedContentArchive.objects.get(
            target_type="TrickEntry",
            target_id=entry.id,
            delete_action=DeletedContentArchive.DeleteAction.DELETE,
        )

    def test_public_list_only_returns_approved_entries(self):
        response = self.client.get("/api/tricks/")
        self.assertEqual(response.status_code, 200)
        items = response.data.get("results", response.data)
        ids = {item["id"] for item in items}
        self.assertIn(self.approved.id, ids)
        self.assertNotIn(self.pending.id, ids)
        self.assertNotIn(self.rejected.id, ids)

    def test_public_list_defaults_to_like_order_and_exposes_like_fields(self):
        response = self.client.get("/api/tricks/")
        self.assertEqual(response.status_code, 200)
        items = response.data.get("results", response.data)
        self.assertGreaterEqual(len(items), 2)
        self.assertEqual(items[0]["id"], self.popular.id)
        self.assertEqual(items[0]["like_count"], 2)
        self.assertFalse(items[0]["is_liked"])
        self.assertEqual(items[0]["keywords"], ["tournament", "graph"])
        self.assertEqual(items[1]["id"], self.approved.id)
        self.assertEqual(items[1]["like_count"], 1)
        self.assertEqual(items[1]["keywords_text"], "lowbit bitwise")

    def test_authenticated_author_can_see_own_pending_entries(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        response = self.client.get("/api/tricks/")
        self.assertEqual(response.status_code, 200)
        items = response.data.get("results", response.data)
        ids = {item["id"] for item in items}
        self.assertIn(self.approved.id, ids)
        self.assertIn(self.pending.id, ids)
        self.assertNotIn(self.rejected.id, ids)

    def test_can_sort_tricks_by_created_newest(self):
        response = self.client.get("/api/tricks/", {"order": "created_newest"})
        self.assertEqual(response.status_code, 200)
        items = response.data.get("results", response.data)
        self.assertGreaterEqual(len(items), 2)
        self.assertEqual(items[0]["id"], self.approved.id)
        self.assertEqual(items[1]["id"], self.popular.id)

    def test_search_matches_trick_keywords(self):
        response = self.client.get("/api/tricks/", {"search": "graph"})
        self.assertEqual(response.status_code, 200)
        items = response.data.get("results", response.data)
        ids = {item["id"] for item in items}
        self.assertIn(self.popular.id, ids)
        self.assertNotIn(self.approved.id, ids)

    def test_authenticated_user_can_create_trick_entry_with_pending_status(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        response = self.client.post(
            "/api/tricks/",
            {
                "title": "prefix sum trick",
                "content_md": "sample trick\\n\\n![img](/wiki-assets/debug.png)",
                "keywords_text": "prefix-sum  lowbit  prefix-sum",
                "term_ids": [self.term.id],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["author"]["username"], self.user.username)
        self.assertEqual(response.data["status"], TrickEntry.Status.PENDING)
        self.assertEqual(response.data["title"], "prefix sum trick")
        self.assertEqual(len(response.data.get("terms") or []), 1)
        self.assertEqual(response.data["terms"][0]["id"], self.term.id)
        self.assertEqual(response.data["keywords_text"], "prefix-sum lowbit")
        self.assertEqual(response.data["keywords"], ["prefix-sum", "lowbit"])

    def test_admin_can_create_trick_entry_with_approved_status(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.post(
            "/api/tricks/",
            {
                "title": "closest pair trick",
                "content_md": "admin trick content",
                "keywords_text": "geometry closest-pair",
                "term_ids": [self.term.id],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], TrickEntry.Status.APPROVED)
        self.assertEqual(response.data["author"]["username"], self.admin.username)
        self.assertEqual(response.data["title"], "closest pair trick")
        self.assertEqual(response.data["keywords"], ["geometry", "closest-pair"])

    def test_create_trick_requires_title_and_keywords(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        response = self.client.post(
            "/api/tricks/",
            {
                "content_md": "sample trick",
                "term_ids": [self.term.id],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("title", response.data)
        self.assertIn("keywords_text", response.data)

    def test_authenticated_user_can_like_and_unlike_trick(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.other_token.key}")
        like_response = self.client.post(
            f"/api/tricks/{self.approved.id}/like/",
            {},
            format="json",
        )
        self.assertEqual(like_response.status_code, 200)
        self.assertEqual(like_response.data["like_count"], 2)
        self.assertTrue(like_response.data["is_liked"])
        self.assertTrue(
            TrickEntryLike.objects.filter(
                user=self.other_user, trick_entry=self.approved
            ).exists()
        )

        repeat_response = self.client.post(
            f"/api/tricks/{self.approved.id}/like/",
            {},
            format="json",
        )
        self.assertEqual(repeat_response.status_code, 200)
        self.assertEqual(repeat_response.data["like_count"], 2)

        unlike_response = self.client.post(
            f"/api/tricks/{self.approved.id}/unlike/",
            {},
            format="json",
        )
        self.assertEqual(unlike_response.status_code, 200)
        self.assertEqual(unlike_response.data["like_count"], 1)
        self.assertFalse(unlike_response.data["is_liked"])
        self.assertFalse(
            TrickEntryLike.objects.filter(
                user=self.other_user, trick_entry=self.approved
            ).exists()
        )

    def test_like_requires_minimum_trick_contribution_score(self):
        low_score_user = User.objects.create_user(
            username="trick_like_low",
            password="Password123",
            role=User.Role.NORMAL,
        )
        low_score_token = Token.objects.create(user=low_score_user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {low_score_token.key}")
        response = self.client.post(
            f"/api/tricks/{self.approved.id}/like/",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("贡献值达到 10", response.data["detail"])

    def test_like_and_unlike_adjust_author_trick_contribution(self):
        baseline_score = self.user.trick_contribution_score
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.other_token.key}")

        like_response = self.client.post(
            f"/api/tricks/{self.approved.id}/like/",
            {},
            format="json",
        )
        self.assertEqual(like_response.status_code, 200)

        self.user.refresh_from_db()
        self.assertEqual(self.user.trick_contribution_score, baseline_score + 1)
        self.assertTrue(
            TrickContributionEvent.objects.filter(
                user=self.user,
                trick_entry=self.approved,
                action_type=TrickContributionEvent.ActionType.TRICK_RECEIVED_LIKE,
            ).exists()
        )

        unlike_response = self.client.post(
            f"/api/tricks/{self.approved.id}/unlike/",
            {},
            format="json",
        )
        self.assertEqual(unlike_response.status_code, 200)

        self.user.refresh_from_db()
        self.assertEqual(self.user.trick_contribution_score, baseline_score)
        self.assertTrue(
            TrickContributionEvent.objects.filter(
                user=self.user,
                trick_entry=self.approved,
                action_type=TrickContributionEvent.ActionType.TRICK_RECEIVED_LIKE_ROLLBACK,
            ).exists()
        )

    def test_downvote_and_undownvote_adjust_trick_contribution(self):
        baseline_author_score = self.user.trick_contribution_score
        baseline_voter_score = self.other_user.trick_contribution_score
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.other_token.key}")

        downvote_response = self.client.post(
            f"/api/tricks/{self.approved.id}/downvote/",
            {},
            format="json",
        )
        self.assertEqual(downvote_response.status_code, 200)
        self.assertEqual(downvote_response.data["downvote_count"], 1)
        self.assertTrue(downvote_response.data["is_downvoted"])
        self.user.refresh_from_db()
        self.other_user.refresh_from_db()
        self.assertEqual(
            self.user.trick_contribution_score,
            baseline_author_score - 2,
        )
        self.assertEqual(
            self.other_user.trick_contribution_score,
            baseline_voter_score - 1,
        )

        undownvote_response = self.client.post(
            f"/api/tricks/{self.approved.id}/undownvote/",
            {},
            format="json",
        )
        self.assertEqual(undownvote_response.status_code, 200)
        self.assertEqual(undownvote_response.data["downvote_count"], 0)
        self.assertFalse(undownvote_response.data["is_downvoted"])
        self.assertFalse(
            TrickEntryDownvote.objects.filter(
                user=self.other_user, trick_entry=self.approved
            ).exists()
        )
        self.user.refresh_from_db()
        self.other_user.refresh_from_db()
        self.assertEqual(self.user.trick_contribution_score, baseline_author_score)
        self.assertEqual(
            self.other_user.trick_contribution_score,
            baseline_voter_score,
        )
        self.assertTrue(
            TrickContributionEvent.objects.filter(
                user=self.other_user,
                trick_entry=self.approved,
                action_type=TrickContributionEvent.ActionType.TRICK_CAST_DOWNVOTE_ROLLBACK,
                is_rollback=True,
            ).exists()
        )
        self.assertTrue(
            TrickContributionEvent.objects.filter(
                user=self.user,
                trick_entry=self.approved,
                action_type=TrickContributionEvent.ActionType.TRICK_RECEIVED_DOWNVOTE_ROLLBACK,
                is_rollback=True,
            ).exists()
        )

    def test_me_trick_contribution_endpoint_returns_score_and_records(self):
        contributor = User.objects.create_user(
            username="trick_contributor",
            password="Password123",
            role=User.Role.NORMAL,
        )
        contributor_token = Token.objects.create(user=contributor)
        entry = self._create_pending_trick(
            author=contributor,
            title="contribution trick",
            content_md="contribution content",
            keywords_text="contribution sample",
        )

        self._approve_trick(entry)
        contributor.refresh_from_db()
        self.assertEqual(contributor.trick_contribution_score, 10)

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {contributor_token.key}")
        response = self.client.get("/api/me/trick-contribution/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["score"], 10)
        self.assertTrue(response.data["can_like"])
        self.assertTrue(response.data["can_downvote"])
        self.assertEqual(response.data["page"], 1)
        self.assertEqual(response.data["page_size"], 10)
        self.assertGreaterEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["action_type"],
            TrickContributionEvent.ActionType.TRICK_APPROVED,
        )
        self.assertEqual(response.data["results"][0]["trick_entry"], entry.id)

    def test_me_trick_contribution_endpoint_paginates_records(self):
        contributor = User.objects.create_user(
            username="trick_contributor_page",
            password="Password123",
            role=User.Role.NORMAL,
            trick_contribution_score=120,
        )
        contributor_token = Token.objects.create(user=contributor)
        for index in range(12):
            TrickContributionEvent.objects.create(
                user=contributor,
                action_type=TrickContributionEvent.ActionType.ADMIN_ADJUSTMENT,
                delta=1,
                balance_after=index + 1,
                metadata={"note": f"manual event {index}"},
            )

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {contributor_token.key}")
        first_page = self.client.get("/api/me/trick-contribution/")
        self.assertEqual(first_page.status_code, 200)
        self.assertEqual(first_page.data["count"], 12)
        self.assertEqual(first_page.data["page"], 1)
        self.assertEqual(first_page.data["page_size"], 10)
        self.assertEqual(first_page.data["total_pages"], 2)
        self.assertEqual(len(first_page.data["results"]), 10)
        self.assertEqual(first_page.data["next"], 2)

        second_page = self.client.get("/api/me/trick-contribution/?page=2")
        self.assertEqual(second_page.status_code, 200)
        self.assertEqual(second_page.data["page"], 2)
        self.assertEqual(len(second_page.data["results"]), 2)
        self.assertEqual(second_page.data["previous"], 1)

    def test_downvotes_trigger_delete_review_and_delete_rewards_are_applied(self):
        author = User.objects.create_user(
            username="trick_downvote_author",
            password="Password123",
            role=User.Role.NORMAL,
        )
        entry = self._create_pending_trick(
            author=author,
            title="downvote target",
            content_md="downvote content",
            keywords_text="downvote target",
        )
        self._approve_trick(entry)
        author.refresh_from_db()
        self.assertEqual(author.trick_contribution_score, 10)

        voter_users = []
        voter_tokens = []
        for index in range(5):
            voter = User.objects.create_user(
                username=f"trick_voter_{index}",
                password="Password123",
                role=User.Role.NORMAL,
                trick_contribution_score=60,
            )
            voter_users.append(voter)
            voter_tokens.append(Token.objects.create(user=voter))

        for token in voter_tokens:
            self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
            response = self.client.post(
                f"/api/tricks/{entry.id}/downvote/",
                {},
                format="json",
            )
            self.assertEqual(response.status_code, 200)

        entry.refresh_from_db()
        author.refresh_from_db()
        self.assertEqual(
            entry.delete_vote_review_status,
            TrickEntry.DeleteVoteReviewStatus.PENDING,
        )
        self.assertEqual(entry.downvote_records.count(), 5)
        self.assertEqual(author.trick_contribution_score, 0)
        self.assertEqual(
            TrickEntryDownvote.objects.filter(trick_entry=entry).count(),
            5,
        )
        for voter in voter_users:
            voter.refresh_from_db()
            self.assertEqual(voter.trick_contribution_score, 59)

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        delete_response = self.client.post(
            f"/api/tricks/{entry.id}/resolve-delete-review/",
            {"action": "delete", "review_note": "内容错误且重复"},
            format="json",
        )
        self.assertEqual(delete_response.status_code, 204)
        self.assertFalse(TrickEntry.objects.filter(id=entry.id).exists())

        author.refresh_from_db()
        self.assertEqual(author.trick_contribution_score, -10)
        self.assertTrue(
            TrickContributionEvent.objects.filter(
                user=author,
                action_type=TrickContributionEvent.ActionType.TRICK_APPROVAL_ROLLBACK,
                event_key=f"trick-approved-rollback:{entry.id}",
            ).exists()
        )

        for voter in voter_users:
            voter.refresh_from_db()
            self.assertEqual(voter.trick_contribution_score, 61)
            self.assertTrue(
                TrickContributionEvent.objects.filter(
                    user=voter,
                    action_type=TrickContributionEvent.ActionType.TRICK_DELETE_REVIEW_REWARD,
                    event_key=f"trick-delete-review-reward:{entry.id}:{voter.id}",
                ).exists()
            )

    def test_create_trick_requires_at_least_one_term(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        response = self.client.post(
            "/api/tricks/",
            {
                "title": "sample trick without term",
                "content_md": "sample trick without term",
                "keywords_text": "sample keyword",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("term_ids", response.data)

    def test_author_can_update_and_delete_own_entry(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        updated_content = "updated trick requires review"
        update_response = self.client.patch(
            f"/api/tricks/{self.approved.id}/",
            {
                "content_md": updated_content,
                "keywords_text": "fenwick lowbit range-query",
            },
            format="json",
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.data["status"], TrickEntry.Status.PENDING)
        self.assertEqual(update_response.data["content_md"], updated_content)
        self.assertEqual(
            update_response.data["keywords"],
            ["fenwick", "lowbit", "range-query"],
        )
        self.approved.refresh_from_db()
        self.assertEqual(self.approved.status, TrickEntry.Status.PENDING)
        self.assertEqual(self.approved.content_md, updated_content)
        self.assertEqual(self.approved.keywords_text, "fenwick lowbit range-query")

        self.client.credentials()
        public_response = self.client.get("/api/tricks/")
        self.assertEqual(public_response.status_code, 200)
        public_items = public_response.data.get("results", public_response.data)
        self.assertNotIn(self.approved.id, {item["id"] for item in public_items})

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        author_response = self.client.get(
            "/api/tricks/", {"status": TrickEntry.Status.PENDING}
        )
        self.assertEqual(author_response.status_code, 200)
        author_items = author_response.data.get("results", author_response.data)
        self.assertIn(self.approved.id, {item["id"] for item in author_items})

        delete_response = self.client.delete(f"/api/tricks/{self.pending.id}/")
        self.assertEqual(delete_response.status_code, 204)
        archive = DeletedContentArchive.objects.get(
            target_type="TrickEntry",
            target_id=self.pending.id,
            delete_action=DeletedContentArchive.DeleteAction.DELETE,
        )
        self.assertEqual(archive.original_author_id, self.user.id)
        self.assertEqual(archive.deleted_by_id, self.user.id)
        self.assertEqual(archive.title, self.pending.title)

    def test_admin_delete_trick_with_note_sends_notification(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        delete_response = self.client.delete(
            f"/api/tricks/{self.pending.id}/",
            {"review_note": "该 trick 与现有内容重复，建议先合并后再提交。"},
            format="json",
        )
        self.assertEqual(delete_response.status_code, 204)
        self.assertFalse(TrickEntry.objects.filter(id=self.pending.id).exists())

        notification = UserNotification.objects.get(
            user=self.user,
            target_type="TrickEntry",
            target_id=self.pending.id,
            title=f"trick 已删除：{self.pending.title}",
        )
        self.assertEqual(notification.level, UserNotification.Level.WARNING)
        self.assertIn("该 trick 与现有内容重复", notification.content)

    def test_me_tricks_includes_rejected_entries_and_deleted_archives(self):
        archive = self._create_deleted_trick_archive()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        response = self.client.get("/api/me/tricks/")
        self.assertEqual(response.status_code, 200)

        records = response.data["results"]
        record_ids = {item["record_id"] for item in records}
        self.assertIn(f"entry-{self.rejected.id}", record_ids)
        self.assertIn(f"archive-{archive.id}", record_ids)

        archive_record = next(
            item for item in records if item["record_id"] == f"archive-{archive.id}"
        )
        self.assertEqual(archive_record["source"], "deleted_archive")
        self.assertEqual(archive_record["title"], "deleted trick")
        self.assertEqual(archive_record["content_md"], "deleted trick body")
        self.assertEqual(archive_record["keywords_text"], "deleted sample")
        self.assertIn(self.term.id, archive_record["term_ids"])

    def test_author_can_resubmit_deleted_trick_from_archive(self):
        archive = self._create_deleted_trick_archive()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        response = self.client.post(
            "/api/me/tricks/resubmit-deleted/",
            {
                "archive_id": archive.id,
                "title": "restored trick",
                "content_md": "restored content from archive",
                "keywords_text": "restored sample",
                "term_ids": [self.term.id],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        entry = TrickEntry.objects.get(id=response.data["id"])
        self.assertEqual(entry.author_id, self.user.id)
        self.assertEqual(entry.status, TrickEntry.Status.PENDING)
        self.assertEqual(entry.title, "restored trick")
        self.assertEqual(entry.content_md, "restored content from archive")
        self.assertEqual(entry.keywords_text, "restored sample")
        self.assertTrue(entry.terms.filter(id=self.term.id).exists())

    def test_other_user_cannot_resubmit_foreign_deleted_trick(self):
        archive = self._create_deleted_trick_archive()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.other_token.key}")
        response = self.client.post(
            "/api/me/tricks/resubmit-deleted/",
            {
                "archive_id": archive.id,
                "title": "stolen trick",
                "content_md": "stolen content",
                "keywords_text": "stolen sample",
                "term_ids": [self.term.id],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 404)

    def test_author_can_update_rejected_trick_for_review(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        response = self.client.patch(
            f"/api/tricks/{self.rejected.id}/",
            {
                "title": "fixed rejected trick",
                "content_md": "fixed rejected trick content",
                "keywords_text": "fixed rejected",
                "term_ids": [self.term.id],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], TrickEntry.Status.PENDING)
        self.rejected.refresh_from_db()
        self.assertEqual(self.rejected.status, TrickEntry.Status.PENDING)
        self.assertEqual(self.rejected.title, "fixed rejected trick")
        self.assertTrue(self.rejected.terms.filter(id=self.term.id).exists())

    def test_author_cannot_clear_required_title(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        update_response = self.client.patch(
            f"/api/tricks/{self.approved.id}/",
            {
                "title": "",
                "content_md": "regenerated title\n\nbody",
                "keywords_text": self.approved.keywords_text,
            },
            format="json",
        )
        self.assertEqual(update_response.status_code, 400)
        self.assertIn("title", update_response.data)
        self.approved.refresh_from_db()
        self.assertEqual(self.approved.title, "??? trick")

    def test_non_author_cannot_update_or_delete_entry(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.other_token.key}")
        update_response = self.client.patch(
            f"/api/tricks/{self.approved.id}/",
            {"content_md": "should fail"},
            format="json",
        )
        self.assertEqual(update_response.status_code, 403)

        delete_response = self.client.delete(f"/api/tricks/{self.approved.id}/")
        self.assertEqual(delete_response.status_code, 403)

    def test_admin_can_include_all_and_moderate_entry(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.get("/api/tricks/", {"include_all": 1})
        self.assertEqual(response.status_code, 200)
        items = response.data.get("results", response.data)
        ids = {item["id"] for item in items}
        self.assertIn(self.approved.id, ids)
        self.assertIn(self.pending.id, ids)
        self.assertIn(self.rejected.id, ids)

        moderate_response = self.client.post(
            f"/api/tricks/{self.pending.id}/set-status/",
            {"status": TrickEntry.Status.APPROVED},
            format="json",
        )
        self.assertEqual(moderate_response.status_code, 200)
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, TrickEntry.Status.APPROVED)

    def test_reject_trick_sends_review_note_notification(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.post(
            f"/api/tricks/{self.pending.id}/set-status/",
            {
                "status": TrickEntry.Status.REJECTED,
                "review_note": "请补充关键词并完善示例",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, TrickEntry.Status.REJECTED)
        self.assertEqual(self.pending.review_note, "请补充关键词并完善示例")

        notification = UserNotification.objects.get(
            user=self.user,
            target_type="TrickEntry",
            target_id=self.pending.id,
        )
        self.assertEqual(notification.level, UserNotification.Level.WARNING)
        self.assertIn("请补充关键词并完善示例", notification.content)

    def test_admin_default_list_hides_rejected_entries(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.get("/api/tricks/")
        self.assertEqual(response.status_code, 200)
        items = response.data.get("results", response.data)
        ids = {item["id"] for item in items}
        self.assertIn(self.approved.id, ids)
        self.assertIn(self.pending.id, ids)
        self.assertNotIn(self.rejected.id, ids)

    def test_admin_can_append_review_note_to_rejected_entry(self):
        self.rejected.review_note = "first rejected note"
        self.rejected.reviewer = self.admin
        self.rejected.reviewed_at = timezone.now()
        self.rejected.save(update_fields=["review_note", "reviewer", "reviewed_at", "updated_at"])

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.post(
            f"/api/tricks/{self.rejected.id}/append-review-note/",
            {"note": "second rejected note"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.rejected.refresh_from_db()
        self.assertIn("first rejected note", self.rejected.review_note)
        self.assertIn("second rejected note", self.rejected.review_note)
        self.assertIn(self.admin.username, self.rejected.review_note)

    def test_admin_can_filter_pending_entries(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.get(
            "/api/tricks/", {"include_all": 1, "status": TrickEntry.Status.PENDING}
        )
        self.assertEqual(response.status_code, 200)
        items = response.data.get("results", response.data)
        ids = {item["id"] for item in items}
        self.assertIn(self.pending.id, ids)
        self.assertNotIn(self.approved.id, ids)
        self.assertNotIn(self.rejected.id, ids)

    def test_trick_list_returns_creator_and_approved_editor_contributors(self):
        update_event = ContributionEvent.objects.create(
            user=self.admin,
            event_type=ContributionEvent.EventType.ADMIN,
            target_type="TrickEntry",
            target_id=self.approved.id,
            payload={"action": "update_trick_entry", "status": TrickEntry.Status.APPROVED},
        )
        moderation_event = ContributionEvent.objects.create(
            user=self.admin,
            event_type=ContributionEvent.EventType.ADMIN,
            target_type="TrickEntry",
            target_id=self.approved.id,
            payload={"action": "moderate_trick_entry", "status": TrickEntry.Status.APPROVED},
        )
        ContributionEvent.objects.filter(id=update_event.id).update(
            created_at=self.approved.created_at + timedelta(minutes=5)
        )
        ContributionEvent.objects.filter(id=moderation_event.id).update(
            created_at=self.approved.created_at + timedelta(minutes=10)
        )

        response = self.client.get("/api/tricks/")
        self.assertEqual(response.status_code, 200)
        items = response.data.get("results", response.data)
        payload = next(item for item in items if item["id"] == self.approved.id)
        contributors = payload["contributors"]

        self.assertEqual(
            [item["user"]["username"] for item in contributors],
            [self.user.username, self.admin.username],
        )
        self.assertTrue(contributors[0]["is_creator"])
        self.assertEqual(contributors[0]["approved_revision_count"], 0)
        self.assertFalse(contributors[1]["is_creator"])
        self.assertEqual(contributors[1]["approved_revision_count"], 1)

    def test_can_filter_tricks_by_term(self):
        self.approved.terms.add(self.term)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        response = self.client.get("/api/tricks/", {"term": self.term.id})
        self.assertEqual(response.status_code, 200)
        items = response.data.get("results", response.data)
        ids = {item["id"] for item in items}
        self.assertIn(self.approved.id, ids)
        self.assertNotIn(self.pending.id, ids)

    def test_trick_can_submit_pending_terms_and_show_after_term_approved(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        create_resp = self.client.post(
            "/api/tricks/",
            {
                "content_md": "pending term sample",
                "pending_term_names": ["点分治专用"],
            },
            format="json",
        )
        self.assertEqual(create_resp.status_code, 201)
        self.assertEqual(create_resp.data["terms"], [])

        entry_id = create_resp.data["id"]
        entry = TrickEntry.objects.get(pk=entry_id)
        suggestion = TrickTermSuggestion.objects.get(normalized_name="点分治专用")
        self.assertTrue(
            entry.pending_term_suggestions.filter(pk=suggestion.pk).exists()
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        moderate_resp = self.client.post(
            f"/api/trick-term-suggestions/{suggestion.id}/set-status/",
            {"status": TrickTermSuggestion.Status.APPROVED},
            format="json",
        )
        self.assertEqual(moderate_resp.status_code, 200)

        entry.refresh_from_db()
        self.assertTrue(entry.terms.filter(name="点分治专用").exists())
        self.assertFalse(
            entry.pending_term_suggestions.filter(pk=suggestion.pk).exists()
        )


class TrickTermSuggestionFlowTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="term_user", password="Password123", role=User.Role.NORMAL
        )
        self.admin = User.objects.create_user(
            username="term_admin", password="Password123", role=User.Role.ADMIN
        )
        self.user_token = Token.objects.create(user=self.user)
        self.admin_token = Token.objects.create(user=self.admin)

    def test_authenticated_user_can_create_term_suggestion(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.user_token.key}")
        response = self.client.post(
            "/api/trick-term-suggestions/", {"name": "虚树"}, format="json"
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], TrickTermSuggestion.Status.PENDING)

    def test_admin_can_approve_term_suggestion_and_create_term(self):
        suggestion = TrickTermSuggestion.objects.create(
            name="点分治",
            normalized_name="点分治",
            proposer=self.user,
            status=TrickTermSuggestion.Status.PENDING,
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.post(
            f"/api/trick-term-suggestions/{suggestion.id}/set-status/",
            {"status": TrickTermSuggestion.Status.APPROVED},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        suggestion.refresh_from_db()
        self.assertEqual(suggestion.status, TrickTermSuggestion.Status.APPROVED)
        self.assertTrue(TrickTerm.objects.filter(name="点分治").exists())


def _override_trick_pending_term_test(self):
    self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
    response = self.client.post(
        "/api/tricks/",
        {
            "content_md": "pending term sample",
            "term_ids": [self.term.id],
            "pending_term_names": ["点分治专用"],
        },
        format="json",
    )
    self.assertEqual(response.status_code, 400)
    self.assertIn("pending_term_names", response.data)


def _override_trick_term_suggestion_create_test(self):
    self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.user_token.key}")
    response = self.client.post(
        "/api/trick-term-suggestions/", {"name": "虚树"}, format="json"
    )
    self.assertEqual(response.status_code, 403)


def _override_trick_term_suggestion_review_test(self):
    response = self.client.get("/api/trick-terms/")
    self.assertEqual(response.status_code, 200)
    items = response.data.get("results", response.data)
    self.assertEqual([item["name"] for item in items], list(FIXED_TRICK_TERM_NAMES))


TrickEntryFlowTests.test_trick_can_submit_pending_terms_and_show_after_term_approved = (
    _override_trick_pending_term_test
)
TrickTermSuggestionFlowTests.test_authenticated_user_can_create_term_suggestion = (
    _override_trick_term_suggestion_create_test
)
TrickTermSuggestionFlowTests.test_admin_can_approve_term_suggestion_and_create_term = (
    _override_trick_term_suggestion_review_test
)


class IssueTicketAdminTests(APITestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Ops", slug="ops")
        self.admin = User.objects.create_user(
            username="ticket_admin", password="Password123", role=User.Role.ADMIN
        )
        self.admin_token = Token.objects.create(user=self.admin)

        self.author_a = User.objects.create_user(
            username="ticket_author_a", password="Password123", role=User.Role.NORMAL
        )
        self.author_b = User.objects.create_user(
            username="ticket_author_b", password="Password123", role=User.Role.NORMAL
        )
        self.author_a_token = Token.objects.create(user=self.author_a)
        self.author_b_token = Token.objects.create(user=self.author_b)
        self.school_assignee = User.objects.create_user(
            username="ticket_school",
            password="Password123",
            role=User.Role.SCHOOL,
        )
        self.school_token = Token.objects.create(user=self.school_assignee)
        self.normal_user = User.objects.create_user(
            username="ticket_normal",
            password="Password123",
            role=User.Role.NORMAL,
        )
        self.normal_token = Token.objects.create(user=self.normal_user)
        self.banned_admin = User.objects.create_user(
            username="ticket_banned_admin",
            password="Password123",
            role=User.Role.ADMIN,
            is_banned=True,
        )

        self.ticket_assigned = IssueTicket.objects.create(
            kind=IssueTicket.Kind.ISSUE,
            title="Assigned ticket",
            content="needs handler",
            author=self.author_a,
            assignee=self.school_assignee,
            related_article=None,
            status=IssueTicket.Status.OPEN,
        )
        self.ticket_unassigned = IssueTicket.objects.create(
            kind=IssueTicket.Kind.REQUEST,
            title="Unassigned ticket",
            content="feature request",
            author=self.author_b,
            related_article=None,
            status=IssueTicket.Status.OPEN,
        )

    def test_normal_user_created_ticket_is_pending_review(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.normal_token.key}")
        response = self.client.post(
            "/api/issues/",
            {
                "kind": IssueTicket.Kind.ISSUE,
                "title": "normal ticket",
                "content": "please review",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], IssueTicket.Status.PENDING)

    def test_school_user_created_ticket_is_open(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.school_token.key}")
        response = self.client.post(
            "/api/issues/",
            {
                "kind": IssueTicket.Kind.REQUEST,
                "title": "school ticket",
                "content": "handled directly",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], IssueTicket.Status.OPEN)

    def test_normal_users_only_see_others_tickets_after_review(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.author_a_token.key}")
        create_response = self.client.post(
            "/api/issues/",
            {
                "kind": IssueTicket.Kind.REQUEST,
                "title": "pending for moderation",
                "content": "waiting review",
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, 201)
        pending_id = create_response.data["id"]
        self.assertEqual(create_response.data["status"], IssueTicket.Status.PENDING)

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.author_b_token.key}")
        list_response = self.client.get("/api/issues/")
        self.assertEqual(list_response.status_code, 200)
        list_ids = {
            item["id"] for item in list_response.data.get("results", list_response.data)
        }
        self.assertIn(self.ticket_assigned.id, list_ids)
        self.assertIn(self.ticket_unassigned.id, list_ids)
        self.assertNotIn(pending_id, list_ids)

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        approve_response = self.client.post(
            f"/api/issues/{pending_id}/set_status/",
            {"status": IssueTicket.Status.OPEN},
            format="json",
        )
        self.assertEqual(approve_response.status_code, 200)

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.author_b_token.key}")
        visible_response = self.client.get("/api/issues/")
        self.assertEqual(visible_response.status_code, 200)
        visible_ids = {
            item["id"]
            for item in visible_response.data.get("results", visible_response.data)
        }
        self.assertIn(pending_id, visible_ids)

    def test_admin_can_filter_tickets_by_author_assignee(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.get(
            "/api/issues/",
            {
                "author": self.author_a.username,
                "assignee": self.school_assignee.id,
                "order": "created_oldest",
            },
        )
        self.assertEqual(response.status_code, 200)
        ids = {item["id"] for item in response.data.get("results", response.data)}
        self.assertEqual(ids, {self.ticket_assigned.id})

        unassigned_response = self.client.get("/api/issues/", {"assignee": "none"})
        self.assertEqual(unassigned_response.status_code, 200)
        unassigned_ids = {
            item["id"]
            for item in unassigned_response.data.get(
                "results", unassigned_response.data
            )
        }
        self.assertIn(self.ticket_unassigned.id, unassigned_ids)
        self.assertNotIn(self.ticket_assigned.id, unassigned_ids)

    def test_set_status_supports_assign_and_clear(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")

        assign_response = self.client.post(
            f"/api/issues/{self.ticket_unassigned.id}/set_status/",
            {
                "status": "in_progress",
                "assign_to": self.school_assignee.id,
                "resolution_note": "accepted",
            },
            format="json",
        )
        self.assertEqual(assign_response.status_code, 200)
        self.ticket_unassigned.refresh_from_db()
        self.assertEqual(self.ticket_unassigned.assignee_id, self.school_assignee.id)
        self.assertEqual(self.ticket_unassigned.status, IssueTicket.Status.IN_PROGRESS)

        clear_response = self.client.post(
            f"/api/issues/{self.ticket_unassigned.id}/set_status/",
            {"status": "resolved", "assign_to": None},
            format="json",
        )
        self.assertEqual(clear_response.status_code, 200)
        self.ticket_unassigned.refresh_from_db()
        self.assertIsNone(self.ticket_unassigned.assignee_id)
        self.assertEqual(self.ticket_unassigned.status, IssueTicket.Status.RESOLVED)

    def test_reject_ticket_sends_resolution_note_notification(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.post(
            f"/api/issues/{self.ticket_unassigned.id}/set_status/",
            {
                "status": IssueTicket.Status.REJECTED,
                "resolution_note": "这个需求暂不计划支持",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.ticket_unassigned.refresh_from_db()
        self.assertEqual(self.ticket_unassigned.status, IssueTicket.Status.REJECTED)
        self.assertEqual(self.ticket_unassigned.review_note, "这个需求暂不计划支持")

        notification = UserNotification.objects.get(
            user=self.author_b,
            target_type="IssueTicket",
            target_id=self.ticket_unassigned.id,
        )
        self.assertEqual(notification.level, UserNotification.Level.WARNING)
        self.assertIn("这个需求暂不计划支持", notification.content)

    def test_set_status_rejects_invalid_assignee(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.post(
            f"/api/issues/{self.ticket_assigned.id}/set_status/",
            {"status": "open", "assign_to": self.normal_user.id},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_assignees_endpoint_only_returns_available_roles(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.get("/api/users/assignees/")
        self.assertEqual(response.status_code, 200)
        ids = {item["id"] for item in response.data}
        self.assertIn(self.admin.id, ids)
        self.assertIn(self.school_assignee.id, ids)
        self.assertNotIn(self.normal_user.id, ids)
        self.assertNotIn(self.banned_admin.id, ids)

    def test_school_assignee_cannot_change_ticket_status(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.school_token.key}")

        list_response = self.client.get("/api/issues/", {"scope": "assigned"})
        self.assertEqual(list_response.status_code, 200)
        list_ids = {
            item["id"] for item in list_response.data.get("results", list_response.data)
        }
        self.assertIn(self.ticket_assigned.id, list_ids)
        self.assertNotIn(self.ticket_unassigned.id, list_ids)

        update_response = self.client.post(
            f"/api/issues/{self.ticket_assigned.id}/set_status/",
            {"status": "in_progress", "resolution_note": "started"},
            format="json",
        )
        self.assertEqual(update_response.status_code, 403)
        self.ticket_assigned.refresh_from_db()
        self.assertEqual(self.ticket_assigned.status, IssueTicket.Status.OPEN)
        self.assertEqual(self.ticket_assigned.resolution_note, "")

        reassign_response = self.client.post(
            f"/api/issues/{self.ticket_assigned.id}/set_status/",
            {"status": "resolved", "assign_to": self.admin.id},
            format="json",
        )
        self.assertEqual(reassign_response.status_code, 403)

    def test_school_assignee_cannot_edit_ticket_content(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.school_token.key}")
        response = self.client.patch(
            f"/api/issues/{self.ticket_assigned.id}/",
            {"title": "hijacked title"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_ticket_author_can_edit_own_ticket(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.author_a_token.key}")
        self.ticket_assigned.resolution_note = "existing note"
        self.ticket_assigned.save(update_fields=["resolution_note", "updated_at"])
        response = self.client.patch(
            f"/api/issues/{self.ticket_assigned.id}/",
            {"title": "updated by author"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.ticket_assigned.refresh_from_db()
        self.assertEqual(self.ticket_assigned.title, "updated by author")
        self.assertEqual(self.ticket_assigned.status, IssueTicket.Status.PENDING)
        self.assertIsNone(self.ticket_assigned.assignee_id)
        self.assertEqual(self.ticket_assigned.resolution_note, "")

    def test_only_manager_can_delete_ticket(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.author_a_token.key}")
        forbidden = self.client.delete(f"/api/issues/{self.ticket_assigned.id}/")
        self.assertEqual(forbidden.status_code, 403)
        self.assertTrue(IssueTicket.objects.filter(id=self.ticket_assigned.id).exists())

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        allowed = self.client.delete(f"/api/issues/{self.ticket_assigned.id}/")
        self.assertEqual(allowed.status_code, 204)
        self.assertFalse(
            IssueTicket.objects.filter(id=self.ticket_assigned.id).exists()
        )

    def test_bulk_set_status_updates_multiple_tickets_for_admin(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.post(
            "/api/issues/bulk-set-status/",
            {
                "ids": [self.ticket_assigned.id, self.ticket_unassigned.id],
                "status": "in_progress",
                "assign_to": self.school_assignee.id,
                "resolution_note": "bulk process",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["success"], 2)
        self.assertEqual(response.data["failed"], 0)

        self.ticket_assigned.refresh_from_db()
        self.ticket_unassigned.refresh_from_db()
        self.assertEqual(self.ticket_assigned.status, IssueTicket.Status.IN_PROGRESS)
        self.assertEqual(self.ticket_unassigned.status, IssueTicket.Status.IN_PROGRESS)
        self.assertEqual(self.ticket_assigned.assignee_id, self.school_assignee.id)
        self.assertEqual(self.ticket_unassigned.assignee_id, self.school_assignee.id)
        self.assertEqual(self.ticket_assigned.resolution_note, "bulk process")

    def test_bulk_set_status_for_school_user_is_forbidden(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.school_token.key}")
        response = self.client.post(
            "/api/issues/bulk-set-status/",
            {
                "ids": [self.ticket_assigned.id],
                "status": "resolved",
                "assign_to": self.admin.id,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)

        self.ticket_assigned.refresh_from_db()
        self.assertNotEqual(self.ticket_assigned.status, IssueTicket.Status.RESOLVED)

    def test_private_ticket_only_visible_to_author_and_admin(self):
        private_ticket = IssueTicket.objects.create(
            kind=IssueTicket.Kind.ISSUE,
            title="Private ticket",
            content="secret",
            author=self.author_a,
            visibility=IssueTicket.Visibility.PRIVATE,
            status=IssueTicket.Status.OPEN,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.author_a_token.key}")
        own_response = self.client.get("/api/issues/", {"mine": 1})
        own_ids = {
            item["id"] for item in own_response.data.get("results", own_response.data)
        }
        self.assertIn(private_ticket.id, own_ids)

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.author_b_token.key}")
        other_response = self.client.get("/api/issues/", {"scope": "all"})
        other_ids = {
            item["id"]
            for item in other_response.data.get("results", other_response.data)
        }
        self.assertNotIn(private_ticket.id, other_ids)

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        admin_response = self.client.get(
            "/api/issues/", {"visibility": IssueTicket.Visibility.PRIVATE}
        )
        admin_ids = {
            item["id"]
            for item in admin_response.data.get("results", admin_response.data)
        }
        self.assertIn(private_ticket.id, admin_ids)

    def test_visibility_filter_returns_expected_subset(self):
        IssueTicket.objects.create(
            kind=IssueTicket.Kind.REQUEST,
            title="Private mine",
            content="mine only",
            author=self.author_a,
            visibility=IssueTicket.Visibility.PRIVATE,
            status=IssueTicket.Status.OPEN,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.author_a_token.key}")
        response = self.client.get(
            "/api/issues/",
            {"mine": 1, "visibility": IssueTicket.Visibility.PRIVATE},
        )
        items = response.data.get("results", response.data)
        self.assertTrue(items)
        self.assertTrue(
            all(item["visibility"] == IssueTicket.Visibility.PRIVATE for item in items)
        )

    def test_private_ticket_cannot_be_assigned_to_school_user(self):
        private_ticket = IssueTicket.objects.create(
            kind=IssueTicket.Kind.ISSUE,
            title="Private assign",
            content="secret assignment",
            author=self.author_a,
            visibility=IssueTicket.Visibility.PRIVATE,
            status=IssueTicket.Status.OPEN,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.post(
            f"/api/issues/{private_ticket.id}/set_status/",
            {
                "status": IssueTicket.Status.IN_PROGRESS,
                "assign_to": self.school_assignee.id,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn(
            "Private tickets can only be handled by admins.", str(response.data)
        )

    def test_author_cannot_switch_assigned_school_ticket_to_private(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.author_a_token.key}")
        response = self.client.patch(
            f"/api/issues/{self.ticket_assigned.id}/",
            {"visibility": IssueTicket.Visibility.PRIVATE},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.ticket_assigned.refresh_from_db()
        self.assertEqual(
            self.ticket_assigned.visibility, IssueTicket.Visibility.PRIVATE
        )
        self.assertEqual(self.ticket_assigned.status, IssueTicket.Status.PENDING)
        self.assertIsNone(self.ticket_assigned.assignee_id)


class CompetitionPracticeLinkApiTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="practice_admin", password="Password123", role=User.Role.ADMIN
        )
        self.proposer = User.objects.create_user(
            username="practice_user", password="Password123", role=User.Role.NORMAL
        )
        self.admin_token = Token.objects.create(user=self.admin)
        self.proposer_token = Token.objects.create(user=self.proposer)

        self.entry = CompetitionPracticeLink.objects.create(
            source_key="seed-icpc-2024-online",
            year=2024,
            series=CompetitionPracticeLink.Series.ICPC,
            stage=CompetitionPracticeLink.Stage.NETWORK,
            short_name="网络预选赛",
            official_name="2024 ICPC Online Contest",
            official_url="https://example.com/icpc-online",
            event_date_text="2024-09-15",
            organizer="在线-PTA",
            practice_links=[{"label": "QOJ", "url": "https://qoj.ac/contest/1797"}],
            practice_links_note="",
            source_file="02 - ICPC.md",
            source_section="2024.9-2025 赛季 49th",
            display_order=1,
        )
        self.other_entry = CompetitionPracticeLink.objects.create(
            source_key="seed-ccpc-2023-onsite",
            year=2023,
            series=CompetitionPracticeLink.Series.CCPC,
            stage=CompetitionPracticeLink.Stage.REGIONAL,
            short_name="秦皇岛",
            official_name="2023 CCPC Qinhuangdao Onsite",
            official_url="https://example.com/ccpc-qhd",
            event_date_text="2023-10-15",
            organizer="东北大学秦皇岛分校",
            practice_links=[
                {"label": "GYM", "url": "https://codeforces.com/gym/104787"}
            ],
            source_file="03 - CCPC.md",
            source_section="2023.9-2024 赛季 9th",
            display_order=2,
        )

    def test_public_list_and_taxonomy_support_filters(self):
        response = self.client.get(
            "/api/competition-practice-links/",
            {
                "year": 2024,
                "series": CompetitionPracticeLink.Series.ICPC,
                "stage": CompetitionPracticeLink.Stage.NETWORK,
            },
        )
        self.assertEqual(response.status_code, 200)
        items = response.data.get("results", response.data)
        ids = {item["id"] for item in items}
        self.assertEqual(ids, {self.entry.id})
        self.assertEqual(
            items[0]["practice_links_text"], "QOJ https://qoj.ac/contest/1797"
        )

        taxonomy = self.client.get("/api/competition-practice-links/taxonomy/")
        self.assertEqual(taxonomy.status_code, 200)
        self.assertIn(2024, taxonomy.data["years"])
        self.assertIn("02 - ICPC.md", taxonomy.data["sources"])

    def test_authenticated_user_can_submit_proposal(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.proposer_token.key}")
        response = self.client.post(
            "/api/competition-practice-proposals/",
            {
                "target_entry": self.entry.id,
                "proposed_year": 2024,
                "proposed_series": CompetitionPracticeLink.Series.ICPC,
                "proposed_stage": CompetitionPracticeLink.Stage.NETWORK,
                "proposed_short_name": "网络预选赛(I)",
                "proposed_official_name": "2024 ICPC Asia EC 网络预选赛",
                "proposed_official_url": "https://example.com/icpc-ec",
                "proposed_event_date_text": "2024-09-15",
                "proposed_organizer": "在线-PTA",
                "proposed_practice_links_text": "QOJ https://qoj.ac/contest/1797\nPTA https://pintia.cn/market/item/1",
                "reason": "补充了 PTA 链接",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.data["status"], CompetitionPracticeLinkProposal.Status.PENDING
        )
        self.assertEqual(len(response.data["proposed_practice_links"]), 2)

    def test_admin_can_approve_proposal_and_update_entry(self):
        proposal = CompetitionPracticeLinkProposal.objects.create(
            target_entry=self.entry,
            proposer=self.proposer,
            proposed_year=2024,
            proposed_series=CompetitionPracticeLink.Series.ICPC,
            proposed_stage=CompetitionPracticeLink.Stage.NETWORK,
            proposed_short_name="网络预选赛(I)",
            proposed_official_name="2024 ICPC Asia EC 网络预选赛",
            proposed_official_url="https://example.com/icpc-ec",
            proposed_event_date_text="2024-09-15",
            proposed_organizer="在线-PTA",
            proposed_practice_links=[
                {"label": "QOJ", "url": "https://qoj.ac/contest/1797"},
                {"label": "PTA", "url": "https://pintia.cn/market/item/1"},
            ],
            proposed_practice_links_note="",
            reason="补充新链接",
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.post(
            f"/api/competition-practice-proposals/{proposal.id}/approve/",
            {"review_note": "已核对"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        proposal.refresh_from_db()
        self.entry.refresh_from_db()
        self.assertEqual(
            proposal.status, CompetitionPracticeLinkProposal.Status.APPROVED
        )
        self.assertEqual(self.entry.short_name, "网络预选赛(I)")
        self.assertEqual(len(self.entry.practice_links), 2)
        self.assertTrue(
            UserNotification.objects.filter(
                user=self.proposer,
                target_type="CompetitionPracticeLinkProposal",
                target_id=proposal.id,
            ).exists()
        )

    def test_admin_can_reject_proposal_with_review_note_notification(self):
        proposal = CompetitionPracticeLinkProposal.objects.create(
            target_entry=self.entry,
            proposer=self.proposer,
            proposed_year=2024,
            proposed_series=CompetitionPracticeLink.Series.ICPC,
            proposed_stage=CompetitionPracticeLink.Stage.NETWORK,
            proposed_short_name="Online Contest Update",
            proposed_official_name="2024 ICPC Online Contest Update",
            proposed_official_url="https://example.com/icpc-update",
            proposed_event_date_text="2024-09-15",
            proposed_organizer="Online",
            proposed_practice_links=[{"label": "QOJ", "url": "https://qoj.ac/contest/1797"}],
            proposed_practice_links_note="",
            reason="update practice link",
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.post(
            f"/api/competition-practice-proposals/{proposal.id}/reject/",
            {"review_note": "The official link is not verifiable."},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        proposal.refresh_from_db()
        self.assertEqual(
            proposal.status, CompetitionPracticeLinkProposal.Status.REJECTED
        )
        self.assertEqual(proposal.review_note, "The official link is not verifiable.")
        notification = UserNotification.objects.get(
            user=self.proposer,
            target_type="CompetitionPracticeLinkProposal",
            target_id=proposal.id,
        )
        self.assertEqual(notification.level, UserNotification.Level.WARNING)
        self.assertIn("official link", notification.content)

    def test_admin_can_remove_entry(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.delete(
            f"/api/competition-practice-links/{self.entry.id}/remove/"
        )
        self.assertEqual(response.status_code, 204)
        self.assertFalse(
            CompetitionPracticeLink.objects.filter(id=self.entry.id).exists()
        )

    def test_list_returns_creator_and_approved_modifier_contributors(self):
        entry = CompetitionPracticeLink.objects.create(
            source_key="manual-contributor-entry",
            year=2025,
            series=CompetitionPracticeLink.Series.ICPC,
            stage=CompetitionPracticeLink.Stage.REGIONAL,
            short_name="区域赛补题",
            official_name="2025 ICPC Regional",
            official_url="https://example.com/icpc-regional",
            event_date_text="2025-10-01",
            organizer="AlgoWiki",
            practice_links=[{"label": "QOJ", "url": "https://qoj.ac/contest/2501"}],
            practice_links_note="",
            source_file="manual.md",
            source_section="contributors",
            display_order=9,
            created_by=self.admin,
            updated_by=self.admin,
        )
        proposal = CompetitionPracticeLinkProposal.objects.create(
            target_entry=entry,
            proposer=self.proposer,
            proposed_year=2025,
            proposed_series=CompetitionPracticeLink.Series.ICPC,
            proposed_stage=CompetitionPracticeLink.Stage.REGIONAL,
            proposed_short_name="区域赛补题",
            proposed_official_name="2025 ICPC Regional Updated",
            proposed_official_url="https://example.com/icpc-regional",
            proposed_event_date_text="2025-10-01",
            proposed_organizer="AlgoWiki",
            proposed_practice_links=[
                {"label": "QOJ", "url": "https://qoj.ac/contest/2501"},
                {"label": "PTA", "url": "https://pintia.cn/problem-sets/2501"},
            ],
            proposed_practice_links_note="",
            reason="增加 PTA",
            status=CompetitionPracticeLinkProposal.Status.APPROVED,
            reviewer=self.admin,
            reviewed_at=timezone.now(),
        )
        CompetitionPracticeLinkProposal.objects.filter(id=proposal.id).update(
            created_at=timezone.now() - timedelta(days=1)
        )

        response = self.client.get(
            "/api/competition-practice-links/",
            {"year": 2025, "search": "区域赛补题"},
        )
        self.assertEqual(response.status_code, 200)
        items = response.data.get("results", response.data)
        payload = next(item for item in items if item["id"] == entry.id)
        contributors = payload["contributors"]

        self.assertEqual(
            [item["user"]["username"] for item in contributors],
            [self.admin.username, self.proposer.username],
        )
        self.assertTrue(contributors[0]["is_creator"])
        self.assertEqual(contributors[0]["approved_revision_count"], 0)
        self.assertFalse(contributors[1]["is_creator"])
        self.assertEqual(contributors[1]["approved_revision_count"], 1)

    def test_new_entry_from_approved_proposal_only_counts_creator_once(self):
        proposal = CompetitionPracticeLinkProposal.objects.create(
            proposer=self.proposer,
            proposed_year=2026,
            proposed_series=CompetitionPracticeLink.Series.CCPC,
            proposed_stage=CompetitionPracticeLink.Stage.INVITATIONAL,
            proposed_short_name="新建补题条目",
            proposed_official_name="2026 CCPC Invitational",
            proposed_official_url="https://example.com/ccpc-invite",
            proposed_event_date_text="2026-08-10",
            proposed_organizer="AlgoWiki",
            proposed_practice_links=[{"label": "QOJ", "url": "https://qoj.ac/contest/2601"}],
            proposed_practice_links_note="",
            reason="新增补题入口",
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.post(
            f"/api/competition-practice-proposals/{proposal.id}/approve/",
            {"review_note": "通过"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        proposal.refresh_from_db()
        entry = proposal.target_entry
        self.assertIsNotNone(entry)

        list_response = self.client.get(
            "/api/competition-practice-links/",
            {"year": 2026, "search": "新建补题条目"},
        )
        self.assertEqual(list_response.status_code, 200)
        items = list_response.data.get("results", list_response.data)
        payload = next(item for item in items if item["id"] == entry.id)
        contributors = payload["contributors"]

        self.assertEqual(
            [item["user"]["username"] for item in contributors],
            [self.proposer.username],
        )
        self.assertTrue(contributors[0]["is_creator"])
        self.assertEqual(contributors[0]["approved_revision_count"], 0)

    def test_normal_user_cannot_remove_entry(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.proposer_token.key}")
        response = self.client.delete(
            f"/api/competition-practice-links/{self.entry.id}/remove/"
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(
            CompetitionPracticeLink.objects.filter(id=self.entry.id).exists()
        )

    def test_import_command_loads_snapshot_json(self):
        snapshot = [
            {
                "source_key": "manual-import-1",
                "year": 2025,
                "series": CompetitionPracticeLink.Series.CCPC,
                "stage": CompetitionPracticeLink.Stage.INVITATIONAL,
                "short_name": "测试邀请赛",
                "official_name": "测试邀请赛 Official",
                "official_url": "https://example.com/invite",
                "event_date": "2025-05-01",
                "event_date_text": "2025-05-01",
                "organizer": "Test Org",
                "practice_links": [
                    {"label": "GYM", "url": "https://codeforces.com/gym/123456"}
                ],
                "practice_links_note": "",
                "source_file": "01 - 省赛与邀请赛.md",
                "source_section": "测试赛季",
                "display_order": 9,
            }
        ]
        tmp_file = tempfile.NamedTemporaryFile(
            "w", suffix=".json", encoding="utf-8", delete=False
        )
        try:
            json.dump(snapshot, tmp_file, ensure_ascii=False)
            tmp_file.close()
            call_command(
                "import_competition_practice_links",
                snapshot=tmp_file.name,
                replace_missing=True,
            )
            self.assertTrue(
                CompetitionPracticeLink.objects.filter(
                    source_key="manual-import-1"
                ).exists()
            )
        finally:
            Path(tmp_file.name).unlink(missing_ok=True)


class UserManagementRecoveryTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="recover_admin", password="Password123", role=User.Role.ADMIN
        )
        self.admin_token = Token.objects.create(user=self.admin)

        self.super_admin = User.objects.create_user(
            username="recover_super",
            password="Password123",
            role=User.Role.SUPERADMIN,
            is_staff=True,
            is_superuser=True,
        )
        self.super_admin_token = Token.objects.create(user=self.super_admin)
        self.super_admin_target = User.objects.create_user(
            username="recover_super_target",
            password="Password123",
            role=User.Role.SUPERADMIN,
            is_staff=True,
            is_superuser=True,
            is_active=False,
        )

        self.normal = User.objects.create_user(
            username="recover_normal",
            password="Password123",
            role=User.Role.NORMAL,
            is_active=False,
        )
        self.normal_active = User.objects.create_user(
            username="recover_normal_active",
            password="Password123",
            role=User.Role.NORMAL,
        )
        self.normal_token = Token.objects.create(user=self.normal_active)
        self.category = Category.objects.create(
            name="Recover Category", slug="recover-category"
        )
        self.article = Article.objects.create(
            title="Recover Article",
            summary="summary",
            content_md="content",
            category=self.category,
            author=self.normal,
            status=Article.Status.PUBLISHED,
        )
        self.announcement = Announcement.objects.create(
            title="Recover Announcement",
            content_md="content",
            created_by=self.normal,
        )

    def test_admin_can_reactivate_normal_user(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.post(f"/api/users/{self.normal.id}/reactivate/")
        self.assertEqual(response.status_code, 200)
        self.normal.refresh_from_db()
        self.assertTrue(self.normal.is_active)

    def test_user_management_exposes_full_phone_only_to_super_admin(self):
        country_code, phone_number = normalize_phone_context(
            country_code="86",
            phone_number="13800138000",
        )
        verification = PhoneVerification.objects.create(
            user=self.normal_active,
            status=PhoneVerification.Status.VERIFIED,
            phone_country_code=country_code,
            phone_masked="138****8000",
            phone_last4="8000",
            phone_digest=build_phone_digest(country_code, phone_number),
            verified_at=timezone.now(),
        )
        verification.set_phone_number(phone_number)
        verification.save(update_fields=["phone_encrypted", "updated_at"])

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        admin_response = self.client.get(
            "/api/users/", {"id": self.normal_active.id}, format="json"
        )
        self.assertEqual(admin_response.status_code, 200)
        admin_item = admin_response.data["results"][0]
        self.assertEqual(admin_item["avatar_url"], "")
        self.assertEqual(admin_item["phone_verification"]["phone_masked"], "138****8000")
        self.assertEqual(admin_item["phone_verification"]["phone_number"], "")
        self.assertFalse(admin_item["phone_verification"]["can_view_full_phone"])

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {self.super_admin_token.key}"
        )
        super_response = self.client.get(
            "/api/users/", {"id": self.normal_active.id}, format="json"
        )
        self.assertEqual(super_response.status_code, 200)
        super_item = super_response.data["results"][0]
        self.assertEqual(super_item["phone_verification"]["phone_number"], phone_number)
        self.assertTrue(super_item["phone_verification"]["can_view_full_phone"])

    def test_user_management_marks_legacy_verified_phone_for_reverification(self):
        country_code, phone_number = normalize_phone_context(
            country_code="86",
            phone_number="13800138000",
        )
        PhoneVerification.objects.create(
            user=self.normal_active,
            status=PhoneVerification.Status.VERIFIED,
            phone_country_code=country_code,
            phone_masked="138****8000",
            phone_last4="8000",
            phone_digest=build_phone_digest(country_code, phone_number),
            verified_at=timezone.now(),
        )

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {self.super_admin_token.key}"
        )
        response = self.client.get(
            "/api/users/", {"id": self.normal_active.id}, format="json"
        )

        self.assertEqual(response.status_code, 200)
        item = response.data["results"][0]
        verification = item["phone_verification"]
        self.assertEqual(verification["phone_masked"], "138****8000")
        self.assertEqual(verification["phone_number"], "")
        self.assertFalse(verification["has_full_phone"])
        self.assertTrue(verification["requires_reverification"])
        self.assertTrue(verification["can_view_full_phone"])

    def test_admin_cannot_reactivate_super_admin(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.post(
            f"/api/users/{self.super_admin_target.id}/reactivate/"
        )
        self.assertEqual(response.status_code, 403)

    def test_super_admin_can_reactivate_super_admin(self):
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {self.super_admin_token.key}"
        )
        response = self.client.post(
            f"/api/users/{self.super_admin_target.id}/reactivate/"
        )
        self.assertEqual(response.status_code, 200)
        self.super_admin_target.refresh_from_db()
        self.assertTrue(self.super_admin_target.is_active)

    def test_normal_user_cannot_reactivate(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.normal_token.key}")
        response = self.client.post(f"/api/users/{self.admin.id}/reactivate/")
        self.assertEqual(response.status_code, 403)

    def test_soft_deleted_user_token_is_revoked_and_cannot_access_me(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.post(f"/api/users/{self.normal_active.id}/soft_delete/")
        self.assertEqual(response.status_code, 200)

        self.normal_active.refresh_from_db()
        self.assertFalse(self.normal_active.is_active)
        self.assertFalse(Token.objects.filter(key=self.normal_token.key).exists())

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.normal_token.key}")
        me_response = self.client.get("/api/me/")
        self.assertIn(me_response.status_code, (401, 403))

        pwd_response = self.client.post(
            "/api/me/change-password/",
            {
                "old_password": "Password123",
                "new_password": "Password456",
                "confirm_password": "Password456",
            },
            format="json",
        )
        self.assertIn(pwd_response.status_code, (401, 403))

    def test_admin_can_hard_delete_inactive_user_and_username_becomes_reusable(self):
        competition_notice = CompetitionNotice.objects.create(
            title="Recover Competition Notice",
            content_md="notice content",
            series=CompetitionNotice.Series.ICPC,
            year=2026,
            stage=CompetitionNotice.Stage.REGIONAL,
            created_by=self.normal,
            updated_by=self.normal,
            reviewer=self.normal,
        )
        schedule_entry = CompetitionScheduleEntry.objects.create(
            event_date=timezone.now().date(),
            competition_type="ICPC Regional",
            location="Online",
            announcement=competition_notice,
            created_by=self.normal,
            updated_by=self.normal,
            reviewer=self.normal,
        )
        practice_link = CompetitionPracticeLink.objects.create(
            source_key="recover-practice-link",
            year=2026,
            series=CompetitionPracticeLink.Series.ICPC,
            stage=CompetitionPracticeLink.Stage.REGIONAL,
            short_name="Recover Practice",
            official_name="Recover Practice Official",
            created_by=self.normal,
            updated_by=self.normal,
        )
        practice_proposal = CompetitionPracticeLinkProposal.objects.create(
            target_entry=practice_link,
            proposer=self.normal,
            proposed_year=2026,
            proposed_series=CompetitionPracticeLink.Series.ICPC,
            proposed_stage=CompetitionPracticeLink.Stage.REGIONAL,
            proposed_short_name="Recover Proposal",
            proposed_official_name="Recover Proposal Official",
            reviewer=self.normal,
        )
        moment = Moment.objects.create(
            author=self.normal,
            content="moment removed with user",
            status=Moment.Status.PUBLISHED,
            published_at=timezone.now(),
        )
        other_moment = Moment.objects.create(
            author=self.admin,
            content="other moment",
            status=Moment.Status.PUBLISHED,
            published_at=timezone.now(),
        )
        authored_comment = MomentComment.objects.create(
            moment=other_moment,
            author=self.normal,
            content="comment removed with user",
            status=MomentComment.Status.VISIBLE,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.post(f"/api/users/{self.normal.id}/hard_delete/")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(id=self.normal.id).exists())
        self.assertFalse(User.objects.filter(username="recover_normal").exists())

        placeholder = User.objects.get(username="system_deleted_user")
        self.article.refresh_from_db()
        self.announcement.refresh_from_db()
        self.assertEqual(self.article.author_id, placeholder.id)
        self.assertEqual(self.announcement.created_by_id, placeholder.id)

        competition_notice.refresh_from_db()
        schedule_entry.refresh_from_db()
        practice_link.refresh_from_db()
        practice_proposal.refresh_from_db()
        self.assertEqual(competition_notice.created_by_id, placeholder.id)
        self.assertEqual(competition_notice.updated_by_id, placeholder.id)
        self.assertEqual(competition_notice.reviewer_id, placeholder.id)
        self.assertEqual(schedule_entry.created_by_id, placeholder.id)
        self.assertEqual(schedule_entry.updated_by_id, placeholder.id)
        self.assertEqual(schedule_entry.reviewer_id, placeholder.id)
        self.assertEqual(practice_link.created_by_id, placeholder.id)
        self.assertEqual(practice_link.updated_by_id, placeholder.id)
        self.assertEqual(practice_proposal.proposer_id, placeholder.id)
        self.assertEqual(practice_proposal.reviewer_id, placeholder.id)

        moment.refresh_from_db()
        authored_comment.refresh_from_db()
        self.assertEqual(moment.status, Moment.Status.DELETED)
        self.assertEqual(moment.author_id, placeholder.id)
        self.assertEqual(authored_comment.status, MomentComment.Status.DELETED)
        self.assertEqual(authored_comment.author_id, placeholder.id)
        self.assertTrue(
            DeletedContentArchive.objects.filter(
                target_type="Moment",
                target_id=moment.id,
                original_author=placeholder,
            ).exists()
        )
        self.assertTrue(
            DeletedContentArchive.objects.filter(
                target_type="MomentComment",
                target_id=authored_comment.id,
                original_author=placeholder,
            ).exists()
        )
        self.assertTrue(
            SecurityAuditLog.objects.filter(
                event_type=SecurityAuditLog.EventType.USER_HARD_DELETED,
                username="recover_normal",
                success=True,
            ).exists()
        )

        recreated = User.objects.create_user(
            username="recover_normal", password="Password123", role=User.Role.NORMAL
        )
        self.assertIsNotNone(recreated.id)

    def test_user_can_cancel_account_and_public_content_shows_deleted_user(self):
        article = Article.objects.create(
            title="Cancelled User Article",
            summary="summary",
            content_md="content",
            category=self.category,
            author=self.normal_active,
            status=Article.Status.PUBLISHED,
        )
        comment = ArticleComment.objects.create(
            article=article,
            author=self.normal_active,
            content="comment",
            status=ArticleComment.Status.VISIBLE,
        )
        revision = RevisionProposal.objects.create(
            article=article,
            proposer=self.normal_active,
            base_title=article.title,
            base_summary=article.summary,
            base_content_md=article.content_md,
            proposed_title="Updated title",
            proposed_summary="Updated summary",
            proposed_content_md="Updated content",
            reason="cleanup",
        )
        moment = Moment.objects.create(
            author=self.normal_active,
            content="cancelled user moment",
            status=Moment.Status.PUBLISHED,
            published_at=timezone.now(),
        )
        other_moment = Moment.objects.create(
            author=self.admin,
            content="other moment",
            status=Moment.Status.PUBLISHED,
            published_at=timezone.now(),
        )
        authored_moment_comment = MomentComment.objects.create(
            moment=other_moment,
            author=self.normal_active,
            content="cancelled user comment",
            status=MomentComment.Status.VISIBLE,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.normal_token.key}")
        response = self.client.post(
            "/api/me/cancel-account/",
            {
                "current_password": "Password123",
                "confirmation": "注销账户",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(id=self.normal_active.id).exists())
        self.assertFalse(Token.objects.filter(key=self.normal_token.key).exists())

        placeholder = User.objects.get(username="system_deleted_user")
        article.refresh_from_db()
        comment.refresh_from_db()
        revision.refresh_from_db()
        moment.refresh_from_db()
        authored_moment_comment.refresh_from_db()
        self.assertEqual(article.author_id, placeholder.id)
        self.assertEqual(comment.author_id, placeholder.id)
        self.assertEqual(revision.proposer_id, placeholder.id)
        self.assertEqual(moment.status, Moment.Status.DELETED)
        self.assertEqual(moment.author_id, placeholder.id)
        self.assertEqual(authored_moment_comment.status, MomentComment.Status.DELETED)
        self.assertEqual(authored_moment_comment.author_id, placeholder.id)

        self.assertEqual(
            ArticleSerializer(article).data["author"]["username"],
            "已注销用户",
        )
        self.assertEqual(
            ArticleCommentSerializer(comment).data["author"]["username"],
            "已注销用户",
        )
        self.assertEqual(
            RevisionProposalSerializer(revision).data["proposer"]["username"],
            "已注销用户",
        )

        me_response = self.client.get("/api/me/")
        self.assertIn(me_response.status_code, (401, 403))

    def test_manager_account_cancellation_requires_permission_transfer(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.post(
            "/api/me/cancel-account/",
            {
                "current_password": "Password123",
                "confirmation": "注销账户",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertTrue(User.objects.filter(id=self.admin.id).exists())

    def test_admin_cannot_hard_delete_active_user(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.post(f"/api/users/{self.normal_active.id}/hard_delete/")
        self.assertEqual(response.status_code, 400)

    def test_admin_bulk_action_can_ban_unban_and_reactivate_normal_users(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")

        ban_response = self.client.post(
            "/api/users/bulk-action/",
            {"ids": [self.normal_active.id], "action": "ban", "reason": "bulk reason"},
            format="json",
        )
        self.assertEqual(ban_response.status_code, 200)
        self.assertEqual(ban_response.data["success"], 1)
        self.normal_active.refresh_from_db()
        self.assertTrue(self.normal_active.is_banned)

        unban_response = self.client.post(
            "/api/users/bulk-action/",
            {"ids": [self.normal_active.id], "action": "unban"},
            format="json",
        )
        self.assertEqual(unban_response.status_code, 200)
        self.assertEqual(unban_response.data["success"], 1)
        self.normal_active.refresh_from_db()
        self.assertFalse(self.normal_active.is_banned)

        reactivate_response = self.client.post(
            "/api/users/bulk-action/",
            {"ids": [self.normal.id], "action": "reactivate"},
            format="json",
        )
        self.assertEqual(reactivate_response.status_code, 200)
        self.assertEqual(reactivate_response.data["success"], 1)
        self.normal.refresh_from_db()
        self.assertTrue(self.normal.is_active)

    def test_admin_bulk_action_rejects_self_and_super_admin_soft_delete(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")

        response = self.client.post(
            "/api/users/bulk-action/",
            {
                "ids": [
                    self.admin.id,
                    self.super_admin_target.id,
                    self.normal_active.id,
                ],
                "action": "soft_delete",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["success"], 1)
        self.assertEqual(response.data["failed"], 2)

        self.admin.refresh_from_db()
        self.super_admin_target.refresh_from_db()
        self.normal_active.refresh_from_db()
        self.assertTrue(self.admin.is_active)
        self.assertFalse(self.super_admin_target.is_active)
        self.assertFalse(self.normal_active.is_active)

    def test_admin_can_send_notification_to_single_user(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.post(
            f"/api/users/{self.normal_active.id}/send-notification/",
            {
                "title": "Manual notice",
                "content": "Please check your profile page.",
                "link": "/profile",
                "level": "warning",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        notification = UserNotification.objects.get(
            user=self.normal_active,
            title="Manual notice",
        )
        self.assertEqual(notification.actor_id, self.admin.id)
        self.assertEqual(notification.content, "Please check your profile page.")
        self.assertEqual(notification.link, "/profile")
        self.assertEqual(notification.level, UserNotification.Level.WARNING)

    def test_admin_bulk_set_role_is_forbidden(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.post(
            "/api/users/bulk-action/",
            {"ids": [self.normal_active.id], "action": "set_role", "role": "admin"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_super_admin_bulk_set_role_succeeds(self):
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {self.super_admin_token.key}"
        )
        response = self.client.post(
            "/api/users/bulk-action/",
            {"ids": [self.normal_active.id], "action": "set_role", "role": "school"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["success"], 1)
        self.normal_active.refresh_from_db()
        self.assertEqual(self.normal_active.role, User.Role.SCHOOL)

    def test_unban_writes_security_audit_log(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        self.client.post(
            f"/api/users/{self.normal_active.id}/ban/",
            {"reason": "temp"},
            format="json",
        )

        response = self.client.post(
            f"/api/users/{self.normal_active.id}/unban/", format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            SecurityAuditLog.objects.filter(
                event_type=SecurityAuditLog.EventType.USER_UNBANNED,
                username=self.normal_active.username,
                success=True,
            ).exists()
        )

    def test_bulk_unban_writes_security_audit_log(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        self.client.post(
            "/api/users/bulk-action/",
            {"ids": [self.normal_active.id], "action": "ban"},
            format="json",
        )

        response = self.client.post(
            "/api/users/bulk-action/",
            {"ids": [self.normal_active.id], "action": "unban"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            SecurityAuditLog.objects.filter(
                event_type=SecurityAuditLog.EventType.USER_UNBANNED,
                username=self.normal_active.username,
                success=True,
            ).exists()
        )


class ArticleSearchTests(APITestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Search", slug="search")
        self.author = User.objects.create_user(
            username="author3", password="Password123", role=User.Role.ADMIN
        )
        self.article = Article.objects.create(
            title="2. 常见术语",
            summary="术语总览",
            content_md="content",
            category=self.category,
            author=self.author,
            last_editor=self.author,
            status=Article.Status.PUBLISHED,
        )

    def test_search_without_space_still_hits(self):
        response = self.client.get("/api/articles/", {"search": "2.常见术语"})
        self.assertEqual(response.status_code, 200)
        ids = {item["id"] for item in response.data.get("results", response.data)}
        self.assertIn(self.article.id, ids)


class GlobalSearchApiTests(APITestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Global Search", slug="global-search")
        self.user = User.objects.create_user(
            username="global_user",
            email="global_user@example.com",
            password="Password123",
            role=User.Role.NORMAL,
        )
        self.admin = User.objects.create_user(
            username="global_admin",
            email="global_admin@example.com",
            password="Password123",
            role=User.Role.ADMIN,
        )
        self.phone_user = User.objects.create_user(
            username="phone_target",
            email="phone_target_private@example.com",
            password="Password123",
            role=User.Role.NORMAL,
            school_name="Needle School",
        )
        PhoneVerification.objects.create(
            user=self.phone_user,
            status=PhoneVerification.Status.VERIFIED,
            phone_masked="138****1234",
            phone_last4="1234",
            phone_digest="private-phone-digest",
        )
        self.public_article = Article.objects.create(
            title="Needle Public Article",
            summary="Visible global search article",
            content_md="Needle article body",
            category=self.category,
            author=self.admin,
            status=Article.Status.PUBLISHED,
        )
        self.hidden_article = Article.objects.create(
            title="Needle Hidden Article",
            summary="Hidden article should not leak",
            content_md="Needle hidden article body",
            category=self.category,
            author=self.admin,
            status=Article.Status.HIDDEN,
        )
        self.question = Question.objects.create(
            title="Needle Public Question",
            content_md="Needle question body",
            author=self.user,
            category=self.category,
            status=Question.Status.OPEN,
        )
        self.hidden_question = Question.objects.create(
            title="Needle Hidden Question",
            content_md="Needle hidden question body",
            author=self.user,
            category=self.category,
            status=Question.Status.HIDDEN,
        )
        self.trick = TrickEntry.objects.create(
            title="Needle Approved Trick",
            content_md="Needle approved trick body",
            keywords_text="needle",
            author=self.user,
            status=TrickEntry.Status.APPROVED,
        )
        self.pending_trick = TrickEntry.objects.create(
            title="Needle Pending Trick",
            content_md="Needle pending trick body",
            keywords_text="needle",
            author=self.user,
            status=TrickEntry.Status.PENDING,
        )
        self.published_moment = Moment.objects.create(
            author=self.user,
            content="Needle published moment",
            status=Moment.Status.PUBLISHED,
            published_at=timezone.now(),
        )
        self.deleted_moment = Moment.objects.create(
            author=self.user,
            content="Needle deleted moment",
            status=Moment.Status.DELETED,
        )
        self.archive = DeletedContentArchive.objects.create(
            target_type="Moment",
            target_id=self.deleted_moment.id,
            title="Needle Deleted Archive",
            summary="Needle archived deleted content",
            content_md="Needle archive body",
            original_author=self.user,
            original_author_name=self.user.username,
            deleted_by=self.admin,
            deleted_by_name=self.admin.username,
        )

    def group(self, response, key):
        for item in response.data.get("groups", []):
            if item.get("key") == key:
                return item
        return {"results": [], "count": 0}

    def result_ids(self, response, key, item_type):
        return {
            item.get("id")
            for item in self.group(response, key).get("results", [])
            if item.get("type") == item_type
        }

    def result_item(self, response, key, item_type, item_id):
        for item in self.group(response, key).get("results", []):
            if item.get("type") == item_type and item.get("id") == item_id:
                return item
        return None

    def test_public_search_only_returns_public_content(self):
        response = self.client.get("/api/search/", {"q": "Needle"})
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.public_article.id, self.result_ids(response, "wiki", "article"))
        self.assertNotIn(self.hidden_article.id, self.result_ids(response, "wiki", "article"))
        self.assertFalse(any(group.get("key") == "qa" for group in response.data["groups"]))
        self.assertNotIn("Needle Public Question", json.dumps(response.data))
        self.assertNotIn("Needle Hidden Question", json.dumps(response.data))
        self.assertIn(self.trick.id, self.result_ids(response, "tricks", "trick"))
        self.assertNotIn(self.pending_trick.id, self.result_ids(response, "tricks", "trick"))
        self.assertFalse(any(group.get("key") == "admin" for group in response.data["groups"]))
        self.assertNotIn("Needle Deleted Archive", json.dumps(response.data))
        trick_result = self.result_item(response, "tricks", "trick", self.trick.id)
        self.assertIsNotNone(trick_result)
        self.assertEqual(
            trick_result["url"],
            f"/competitions?tab=tricks&trick={self.trick.id}",
        )
        self.assertTrue(trick_result["location_label"])

    def test_public_search_cannot_force_admin_scope(self):
        response = self.client.get("/api/search/", {"q": "1234", "scope": "admin"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["groups"], [])

    def test_authenticated_search_can_find_published_moments_only(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/search/", {"q": "Needle"})
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.published_moment.id, self.result_ids(response, "moments", "moment"))
        self.assertNotIn(self.deleted_moment.id, self.result_ids(response, "moments", "moment"))

    def test_manager_search_includes_admin_group_without_secret_fields(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get("/api/search/", {"q": "1234", "scope": "admin"})
        self.assertEqual(response.status_code, 200)
        admin_group = self.group(response, "admin")
        user_results = [
            item for item in admin_group.get("results", []) if item.get("type") == "user"
        ]
        self.assertTrue(any(item.get("id") == self.phone_user.id for item in user_results))
        payload = json.dumps(response.data)
        self.assertIn("138****1234", payload)
        self.assertNotIn("private-phone-digest", payload)
        self.assertNotIn("phone_target_private@example.com", payload)
        user_result = next(
            item for item in user_results if item.get("id") == self.phone_user.id
        )
        self.assertEqual(user_result["url"], f"/manage/users?user={self.phone_user.id}")
        self.assertEqual(user_result["location_label"], "管理台 / 用户管理")

    def test_manager_search_can_find_deleted_archive(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get("/api/search/", {"q": "Archive", "scope": "admin"})
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            self.archive.id,
            self.result_ids(response, "admin", "deleted_archive"),
        )
        archive_result = self.result_item(
            response,
            "admin",
            "deleted_archive",
            self.archive.id,
        )
        self.assertIsNotNone(archive_result)
        self.assertEqual(
            archive_result["url"],
            f"/manage/deleted-content?archive={self.archive.id}",
        )
        self.assertEqual(archive_result["location_label"], "管理台 / 删除内容归档")


class AdminOverviewAndEventTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin4", password="Password123", role=User.Role.ADMIN
        )
        self.superadmin = User.objects.create_user(
            username="superadmin4",
            password="Password123",
            role=User.Role.SUPERADMIN,
        )
        self.normal = User.objects.create_user(
            username="normal4", password="Password123", role=User.Role.NORMAL
        )
        self.admin_token = Token.objects.create(user=self.admin)
        self.superadmin_token = Token.objects.create(user=self.superadmin)
        self.normal_token = Token.objects.create(user=self.normal)

    def test_admin_overview_permission_and_payload(self):
        pending_moment = Moment.objects.create(
            author=self.normal,
            content="pending admin overview moment",
            status=Moment.Status.PENDING,
        )
        MomentReport.objects.create(
            target_type=MomentReport.TargetType.MOMENT,
            moment=pending_moment,
            reporter=self.normal,
            target_author=self.normal,
            reason=MomentReport.Reason.SPAM,
            description="pending admin overview report",
        )

        response_unauth = self.client.get("/api/admin/overview/")
        self.assertIn(response_unauth.status_code, (401, 403))

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.normal_token.key}")
        response_forbidden = self.client.get("/api/admin/overview/")
        self.assertEqual(response_forbidden.status_code, 403)

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response_ok = self.client.get("/api/admin/overview/")
        self.assertEqual(response_ok.status_code, 200)
        self.assertIn("users", response_ok.data)
        self.assertIn("content", response_ok.data)
        self.assertIn("workflow", response_ok.data)
        self.assertIn("analytics", response_ok.data)
        self.assertIn("recent_events", response_ok.data)
        self.assertIn("event_type_counts", response_ok.data["analytics"])
        self.assertIn("daily_events", response_ok.data["analytics"])
        self.assertEqual(len(response_ok.data["analytics"]["daily_events"]), 7)
        self.assertIn("pending_summary", response_ok.data)
        pending_items = {
            item["key"]: item for item in response_ok.data["pending_summary"]["items"]
        }
        self.assertEqual(pending_items["moments"]["count"], 1)
        self.assertEqual(pending_items["moment_reports"]["count"], 1)
        self.assertGreaterEqual(response_ok.data["pending_summary"]["total"], 2)

    def test_site_visit_stats_requires_superadmin_and_tracks_views(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        forbidden_response = self.client.get("/api/site-visits/stats/")
        self.assertEqual(forbidden_response.status_code, 403)

        today = timezone.localdate()
        monday = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)
        expected_total = 0
        expected_week = 6
        expected_month = 6

        SiteVisitDailyStat.objects.create(date=today, page_views=5)
        expected_total += 5
        if monday < today:
            SiteVisitDailyStat.objects.create(
                date=monday,
                page_views=7,
            )
            expected_total += 7
            expected_week += 7
            expected_month += 7
        if month_start < monday:
            SiteVisitDailyStat.objects.create(
                date=month_start,
                page_views=9,
            )
            expected_total += 9
            expected_month += 9
        previous_month_day = month_start - timedelta(days=1)
        SiteVisitDailyStat.objects.create(date=previous_month_day, page_views=11)
        expected_total += 11

        track_response = self.client.post("/api/site-visits/track/", {}, format="json")
        self.assertEqual(track_response.status_code, 204)
        expected_total += 1

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.superadmin_token.key}")
        stats_response = self.client.get("/api/site-visits/stats/")
        self.assertEqual(stats_response.status_code, 200)
        self.assertEqual(stats_response.data["today"], 6)
        self.assertEqual(stats_response.data["week"], expected_week)
        self.assertEqual(stats_response.data["month"], expected_month)
        self.assertEqual(stats_response.data["total"], expected_total)
        self.assertEqual(len(stats_response.data["recent_days"]), 7)

    def test_event_filters_and_export(self):
        old_event = ContributionEvent.objects.create(
            user=self.admin,
            event_type=ContributionEvent.EventType.ADMIN,
            target_type="Article",
            target_id=1,
            payload={"action": "old"},
        )
        new_event = ContributionEvent.objects.create(
            user=self.admin,
            event_type=ContributionEvent.EventType.ADMIN,
            target_type="Article",
            target_id=2,
            payload={"action": "new"},
        )
        ContributionEvent.objects.filter(id=old_event.id).update(
            created_at=timezone.now() - timezone.timedelta(days=3)
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.get(
            "/api/events/",
            {
                "event_type": "admin",
                "start_at": (timezone.now() - timezone.timedelta(days=1)).isoformat(),
            },
        )
        self.assertEqual(response.status_code, 200)
        ids = {item["id"] for item in response.data.get("results", response.data)}
        self.assertIn(new_event.id, ids)
        self.assertNotIn(old_event.id, ids)

        export_response = self.client.get(
            "/api/events/export/", {"event_type": "admin"}
        )
        self.assertEqual(export_response.status_code, 200)
        self.assertIn("text/csv", export_response["Content-Type"])
        content = export_response.content.decode("utf-8")
        self.assertIn("event_type", content)
        self.assertIn("admin", content)


class RevisionFilterTests(APITestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Filter", slug="filter")
        self.admin = User.objects.create_user(
            username="admin5", password="Password123", role=User.Role.ADMIN
        )
        self.user_a = User.objects.create_user(
            username="user_a", password="Password123", role=User.Role.NORMAL
        )
        self.user_b = User.objects.create_user(
            username="user_b", password="Password123", role=User.Role.NORMAL
        )
        self.admin_token = Token.objects.create(user=self.admin)

        self.article = Article.objects.create(
            title="Filter Article",
            summary="summary",
            content_md="content",
            category=self.category,
            author=self.admin,
            last_editor=self.admin,
            status=Article.Status.PUBLISHED,
        )
        self.proposal_a = RevisionProposal.objects.create(
            article=self.article,
            proposer=self.user_a,
            proposed_title="A",
            proposed_summary="A",
            proposed_content_md="A",
            reason="A",
        )
        self.proposal_b = RevisionProposal.objects.create(
            article=self.article,
            proposer=self.user_b,
            proposed_title="B",
            proposed_summary="B",
            proposed_content_md="B",
            reason="B",
        )

    def test_admin_can_filter_revision_by_proposer(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.get(
            "/api/revisions/", {"proposer": self.user_a.id, "status": "pending"}
        )
        self.assertEqual(response.status_code, 200)
        ids = {item["id"] for item in response.data.get("results", response.data)}
        self.assertEqual(ids, {self.proposal_a.id})


class RevisionBulkReviewTests(APITestCase):
    def setUp(self):
        self.public_category = Category.objects.create(
            name="Public Rev", slug="public-rev"
        )
        self.school_category = Category.objects.create(
            name="School Rev",
            slug="school-rev",
            moderation_scope=Category.ModerationScope.SCHOOL,
        )

        self.admin = User.objects.create_user(
            username="bulk_rev_admin", password="Password123", role=User.Role.ADMIN
        )
        self.school = User.objects.create_user(
            username="bulk_rev_school", password="Password123", role=User.Role.SCHOOL
        )
        self.normal = User.objects.create_user(
            username="bulk_rev_normal", password="Password123", role=User.Role.NORMAL
        )
        self.admin_token = Token.objects.create(user=self.admin)
        self.school_token = Token.objects.create(user=self.school)

        self.public_article = Article.objects.create(
            title="Public Revision Article",
            summary="summary",
            content_md="old public",
            category=self.public_category,
            author=self.admin,
            last_editor=self.admin,
            status=Article.Status.PUBLISHED,
        )
        self.school_article = Article.objects.create(
            title="School Revision Article",
            summary="summary",
            content_md="old school",
            category=self.school_category,
            author=self.admin,
            last_editor=self.admin,
            status=Article.Status.PUBLISHED,
        )

        self.public_proposal = RevisionProposal.objects.create(
            article=self.public_article,
            proposer=self.normal,
            proposed_title="Public Revision Article Updated",
            proposed_summary="updated",
            proposed_content_md="new public content",
            reason="public update",
        )
        self.school_proposal = RevisionProposal.objects.create(
            article=self.school_article,
            proposer=self.normal,
            proposed_title="School Revision Article Updated",
            proposed_summary="updated",
            proposed_content_md="new school content",
            reason="school update",
        )

    def test_admin_bulk_review_can_approve_multiple_proposals(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.post(
            "/api/revisions/bulk-review/",
            {
                "ids": [self.public_proposal.id, self.school_proposal.id],
                "action": "approve",
                "review_note": "bulk approved",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["success"], 2)
        self.assertEqual(response.data["failed"], 0)

        self.public_proposal.refresh_from_db()
        self.school_proposal.refresh_from_db()
        self.public_article.refresh_from_db()
        self.school_article.refresh_from_db()

        self.assertEqual(self.public_proposal.status, RevisionProposal.Status.APPROVED)
        self.assertEqual(self.school_proposal.status, RevisionProposal.Status.APPROVED)
        self.assertEqual(self.public_article.content_md, "new public content")
        self.assertEqual(self.school_article.content_md, "new school content")

    def test_admin_bulk_review_can_clear_article_summary(self):
        self.public_proposal.proposed_summary = ""
        self.public_proposal.proposed_content_md = (
            "new public content with cleared summary"
        )
        self.public_proposal.save(
            update_fields=["proposed_summary", "proposed_content_md", "updated_at"]
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.post(
            "/api/revisions/bulk-review/",
            {
                "ids": [self.public_proposal.id],
                "action": "approve",
                "review_note": "bulk approved",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["success"], 1)

        self.public_proposal.refresh_from_db()
        self.public_article.refresh_from_db()
        self.assertEqual(self.public_proposal.status, RevisionProposal.Status.APPROVED)
        self.assertEqual(self.public_article.summary, "")
        self.assertEqual(
            self.public_article.content_md, "new public content with cleared summary"
        )

    def test_bulk_review_skips_conflicted_proposals(self):
        self.public_article.content_md = "old public changed by another editor"
        self.public_article.save(update_fields=["content_md", "updated_at"])
        self.public_proposal.base_title = "Public Revision Article"
        self.public_proposal.base_summary = "summary"
        self.public_proposal.base_content_md = "old public"
        self.public_proposal.base_updated_at = timezone.now() - timedelta(days=1)
        self.public_proposal.proposed_title = "Public Revision Article Updated"
        self.public_proposal.proposed_summary = "updated"
        self.public_proposal.proposed_content_md = "new public content"
        self.public_proposal.save(
            update_fields=[
                "base_title",
                "base_summary",
                "base_content_md",
                "base_updated_at",
                "proposed_title",
                "proposed_summary",
                "proposed_content_md",
                "updated_at",
            ]
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.post(
            "/api/revisions/bulk-review/",
            {
                "ids": [self.public_proposal.id, self.school_proposal.id],
                "action": "approve",
                "review_note": "bulk approved",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["success"], 1)
        self.assertEqual(response.data["failed"], 1)

        self.public_proposal.refresh_from_db()
        self.school_proposal.refresh_from_db()
        self.public_article.refresh_from_db()
        self.school_article.refresh_from_db()

        self.assertEqual(self.public_proposal.status, RevisionProposal.Status.PENDING)
        self.assertEqual(self.school_proposal.status, RevisionProposal.Status.APPROVED)
        self.assertEqual(self.public_article.content_md, "old public changed by another editor")
        self.assertEqual(self.school_article.content_md, "new school content")
        self.assertEqual(
            next(item for item in response.data["results"] if item["id"] == self.public_proposal.id)["code"],
            "revision_merge_conflict",
        )

    def test_school_bulk_review_is_forbidden(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.school_token.key}")
        response = self.client.post(
            "/api/revisions/bulk-review/",
            {
                "ids": [self.public_proposal.id, self.school_proposal.id],
                "action": "reject",
                "review_note": "school batch",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)

        self.public_proposal.refresh_from_db()
        self.school_proposal.refresh_from_db()
        self.assertEqual(self.public_proposal.status, RevisionProposal.Status.PENDING)
        self.assertEqual(self.school_proposal.status, RevisionProposal.Status.PENDING)

    def test_bulk_review_rejects_invalid_action(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.post(
            "/api/revisions/bulk-review/",
            {
                "ids": [self.public_proposal.id],
                "action": "archive",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)


@override_settings(QA_MODULE_ENABLED=True)
class ContentBulkModerationTests(APITestCase):
    def setUp(self):
        self.category = Category.objects.create(
            name="Bulk Content", slug="bulk-content"
        )
        self.admin = User.objects.create_user(
            username="bulk_content_admin", password="Password123", role=User.Role.ADMIN
        )
        self.admin_token = Token.objects.create(user=self.admin)
        self.normal = User.objects.create_user(
            username="bulk_content_normal",
            password="Password123",
            role=User.Role.NORMAL,
        )
        self.normal_token = Token.objects.create(user=self.normal)

        self.article_a = Article.objects.create(
            title="Bulk Article A",
            summary="summary",
            content_md="content",
            category=self.category,
            author=self.admin,
            last_editor=self.admin,
            status=Article.Status.PUBLISHED,
        )
        self.article_b = Article.objects.create(
            title="Bulk Article B",
            summary="summary",
            content_md="content",
            category=self.category,
            author=self.admin,
            last_editor=self.admin,
            status=Article.Status.HIDDEN,
        )
        self.comment_a = ArticleComment.objects.create(
            article=self.article_a,
            author=self.normal,
            content="comment a",
        )
        self.comment_b = ArticleComment.objects.create(
            article=self.article_a,
            author=self.normal,
            content="comment b",
        )
        self.question_a = Question.objects.create(
            title="Bulk Question A",
            content_md="q1",
            author=self.normal,
            category=self.category,
            status=Question.Status.OPEN,
        )
        self.question_b = Question.objects.create(
            title="Bulk Question B",
            content_md="q2",
            author=self.normal,
            category=self.category,
            status=Question.Status.CLOSED,
        )

    def test_admin_can_bulk_moderate_articles(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        publish_response = self.client.post(
            "/api/articles/bulk-moderate/",
            {"ids": [self.article_b.id], "action": "publish"},
            format="json",
        )
        self.assertEqual(publish_response.status_code, 200)
        self.assertEqual(publish_response.data["success"], 1)
        self.article_b.refresh_from_db()
        self.assertEqual(self.article_b.status, Article.Status.PUBLISHED)

        hide_response = self.client.post(
            "/api/articles/bulk-moderate/",
            {"ids": [self.article_a.id], "action": "hide"},
            format="json",
        )
        self.assertEqual(hide_response.status_code, 200)
        self.article_a.refresh_from_db()
        self.assertEqual(self.article_a.status, Article.Status.HIDDEN)

    def test_admin_can_bulk_delete_articles(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.post(
            "/api/articles/bulk-moderate/",
            {"ids": [self.article_a.id, self.article_b.id], "action": "delete"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["success"], 2)
        self.assertFalse(
            Article.objects.filter(
                id__in=[self.article_a.id, self.article_b.id]
            ).exists()
        )

    def test_admin_can_bulk_hide_comments(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.post(
            "/api/comments/bulk-hide/",
            {"ids": [self.comment_a.id, self.comment_b.id]},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["success"], 2)
        self.comment_a.refresh_from_db()
        self.comment_b.refresh_from_db()
        self.assertEqual(self.comment_a.status, ArticleComment.Status.HIDDEN)
        self.assertEqual(self.comment_b.status, ArticleComment.Status.HIDDEN)

    def test_admin_can_bulk_moderate_questions(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        close_response = self.client.post(
            "/api/questions/bulk-moderate/",
            {"ids": [self.question_a.id], "action": "close"},
            format="json",
        )
        self.assertEqual(close_response.status_code, 200)
        self.question_a.refresh_from_db()
        self.assertEqual(self.question_a.status, Question.Status.CLOSED)

        reopen_response = self.client.post(
            "/api/questions/bulk-moderate/",
            {"ids": [self.question_a.id, self.question_b.id], "action": "reopen"},
            format="json",
        )
        self.assertEqual(reopen_response.status_code, 200)
        self.question_a.refresh_from_db()
        self.question_b.refresh_from_db()
        self.assertEqual(self.question_a.status, Question.Status.OPEN)
        self.assertEqual(self.question_b.status, Question.Status.OPEN)

        hide_response = self.client.post(
            "/api/questions/bulk-moderate/",
            {"ids": [self.question_a.id], "action": "hide"},
            format="json",
        )
        self.assertEqual(hide_response.status_code, 200)
        self.question_a.refresh_from_db()
        self.assertEqual(self.question_a.status, Question.Status.HIDDEN)

    def test_normal_user_cannot_call_bulk_moderation_endpoints(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.normal_token.key}")
        article_response = self.client.post(
            "/api/articles/bulk-moderate/",
            {"ids": [self.article_a.id], "action": "hide"},
            format="json",
        )
        self.assertEqual(article_response.status_code, 200)
        self.assertEqual(article_response.data["success"], 0)
        self.assertEqual(article_response.data["failed"], 1)

        comment_response = self.client.post(
            "/api/comments/bulk-hide/",
            {"ids": [self.comment_a.id]},
            format="json",
        )
        self.assertEqual(comment_response.status_code, 403)

        question_response = self.client.post(
            "/api/questions/bulk-moderate/",
            {"ids": [self.question_a.id], "action": "hide"},
            format="json",
        )
        self.assertEqual(question_response.status_code, 403)


class ExtensionPageAccessTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="page_user",
            password="Password123",
            role=User.Role.NORMAL,
        )
        self.user_token = Token.objects.create(user=self.user)
        self.admin = User.objects.create_user(
            username="page_admin",
            password="Password123",
            role=User.Role.ADMIN,
        )
        self.admin_token = Token.objects.create(user=self.admin)

        from .models import ExtensionPage

        self.page_public = ExtensionPage.objects.create(
            title="Public Page",
            slug="public-page",
            access_level=ExtensionPage.AccessLevel.PUBLIC,
            is_enabled=True,
        )
        self.page_auth = ExtensionPage.objects.create(
            title="Auth Page",
            slug="auth-page",
            access_level=ExtensionPage.AccessLevel.AUTH,
            is_enabled=True,
        )
        self.page_admin = ExtensionPage.objects.create(
            title="Admin Page",
            slug="admin-page",
            access_level=ExtensionPage.AccessLevel.ADMIN,
            is_enabled=True,
        )
        self.page_disabled = ExtensionPage.objects.create(
            title="Disabled Page",
            slug="disabled-page",
            access_level=ExtensionPage.AccessLevel.PUBLIC,
            is_enabled=False,
        )

    def test_anonymous_only_sees_enabled_public_pages(self):
        response = self.client.get("/api/pages/")
        self.assertEqual(response.status_code, 200)
        slugs = {item["slug"] for item in response.data.get("results", response.data)}
        self.assertIn(self.page_public.slug, slugs)
        self.assertNotIn(self.page_auth.slug, slugs)
        self.assertNotIn(self.page_admin.slug, slugs)
        self.assertNotIn(self.page_disabled.slug, slugs)

    def test_authenticated_user_sees_public_and_auth_pages(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.user_token.key}")
        response = self.client.get("/api/pages/")
        self.assertEqual(response.status_code, 200)
        slugs = {item["slug"] for item in response.data.get("results", response.data)}
        self.assertIn(self.page_public.slug, slugs)
        self.assertIn(self.page_auth.slug, slugs)
        self.assertNotIn(self.page_admin.slug, slugs)
        self.assertNotIn(self.page_disabled.slug, slugs)

    def test_manager_include_disabled_can_see_all_pages(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.get("/api/pages/", {"include_disabled": "1"})
        self.assertEqual(response.status_code, 200)
        slugs = {item["slug"] for item in response.data.get("results", response.data)}
        self.assertIn(self.page_public.slug, slugs)
        self.assertIn(self.page_auth.slug, slugs)
        self.assertIn(self.page_admin.slug, slugs)
        self.assertIn(self.page_disabled.slug, slugs)


class DocumentPageSectionApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="doc_user",
            password="Password123",
            role=User.Role.NORMAL,
        )
        self.user_token = Token.objects.create(user=self.user)
        self.admin = User.objects.create_user(
            username="doc_admin",
            password="Password123",
            role=User.Role.ADMIN,
        )
        self.admin_token = Token.objects.create(user=self.admin)

        self.page_public = ExtensionPage.objects.create(
            title="Doc Public",
            slug="doc-public",
            access_level=ExtensionPage.AccessLevel.PUBLIC,
            is_enabled=True,
        )
        self.page_auth = ExtensionPage.objects.create(
            title="Doc Auth",
            slug="doc-auth",
            access_level=ExtensionPage.AccessLevel.AUTH,
            is_enabled=True,
        )
        self.page_admin = ExtensionPage.objects.create(
            title="Doc Admin",
            slug="doc-admin",
            access_level=ExtensionPage.AccessLevel.ADMIN,
            is_enabled=True,
        )
        self.page_disabled = ExtensionPage.objects.create(
            title="Doc Disabled",
            slug="doc-disabled",
            access_level=ExtensionPage.AccessLevel.PUBLIC,
            is_enabled=False,
        )

        self.section_public = DocumentPageSection.objects.create(
            title="公开文档",
            key="doc-public",
            page=self.page_public,
            display_order=10,
            is_visible=True,
        )
        self.section_auth = DocumentPageSection.objects.create(
            title="登录文档",
            key="doc-auth",
            page=self.page_auth,
            display_order=20,
            is_visible=True,
        )
        self.section_admin = DocumentPageSection.objects.create(
            title="管理员文档",
            key="doc-admin",
            page=self.page_admin,
            display_order=30,
            is_visible=True,
        )
        self.section_hidden = DocumentPageSection.objects.create(
            title="隐藏文档",
            key="doc-hidden",
            page=self.page_public,
            display_order=40,
            is_visible=False,
        )
        self.section_disabled = DocumentPageSection.objects.create(
            title="禁用页面文档",
            key="doc-disabled",
            page=self.page_disabled,
            display_order=50,
            is_visible=True,
        )

    def test_anonymous_only_sees_visible_public_document_sections(self):
        response = self.client.get("/api/document-page-sections/")
        self.assertEqual(response.status_code, 200)
        keys = {item["key"] for item in response.data.get("results", response.data)}
        self.assertIn(self.section_public.key, keys)
        self.assertNotIn(self.section_auth.key, keys)
        self.assertNotIn(self.section_admin.key, keys)
        self.assertNotIn(self.section_hidden.key, keys)
        self.assertNotIn(self.section_disabled.key, keys)

    def test_authenticated_user_sees_public_and_auth_document_sections(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.user_token.key}")
        response = self.client.get("/api/document-page-sections/")
        self.assertEqual(response.status_code, 200)
        keys = {item["key"] for item in response.data.get("results", response.data)}
        self.assertIn(self.section_public.key, keys)
        self.assertIn(self.section_auth.key, keys)
        self.assertNotIn(self.section_admin.key, keys)
        self.assertNotIn(self.section_hidden.key, keys)
        self.assertNotIn(self.section_disabled.key, keys)

    def test_manager_include_hidden_can_see_all_document_sections(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.get(
            "/api/document-page-sections/",
            {"include_hidden": "1"},
        )
        self.assertEqual(response.status_code, 200)
        keys = {item["key"] for item in response.data.get("results", response.data)}
        self.assertIn(self.section_public.key, keys)
        self.assertIn(self.section_auth.key, keys)
        self.assertIn(self.section_admin.key, keys)
        self.assertIn(self.section_hidden.key, keys)
        self.assertIn(self.section_disabled.key, keys)

    def test_delete_section_removes_orphan_page(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.delete(
            f"/api/document-page-sections/{self.section_auth.id}/"
        )
        self.assertEqual(response.status_code, 204)
        self.assertFalse(DocumentPageSection.objects.filter(id=self.section_auth.id).exists())
        self.assertFalse(ExtensionPage.objects.filter(id=self.page_auth.id).exists())


class AnnouncementFlowTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="announce_admin", password="Password123", role=User.Role.ADMIN
        )
        self.admin_token = Token.objects.create(user=self.admin)
        self.user = User.objects.create_user(
            username="announce_user", password="Password123", role=User.Role.NORMAL
        )
        self.user_token = Token.objects.create(user=self.user)
        now = timezone.now()

        self.announcement = Announcement.objects.create(
            title="A1",
            content_md="body",
            created_by=self.admin,
            is_published=True,
            priority=10,
        )
        self.expired_published = Announcement.objects.create(
            title="A-old",
            content_md="old body",
            created_by=self.admin,
            is_published=True,
            start_at=now - timedelta(days=10),
            end_at=now - timedelta(days=5),
        )
        self.unpublished = Announcement.objects.create(
            title="A-hidden",
            content_md="hidden body",
            created_by=self.admin,
            is_published=False,
        )

    def test_unread_requires_authentication(self):
        response = self.client.get("/api/announcements/unread/")
        self.assertIn(response.status_code, (401, 403))

    def test_unread_returns_active_announcements_for_logged_user(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.user_token.key}")
        response = self.client.get("/api/announcements/unread/")
        self.assertEqual(response.status_code, 200)
        ids = {item["id"] for item in response.data}
        self.assertIn(self.announcement.id, ids)

    def test_acknowledge_removes_item_from_unread(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.user_token.key}")

        unread_before = self.client.get("/api/announcements/unread/")
        ids_before = {item["id"] for item in unread_before.data}
        self.assertIn(self.announcement.id, ids_before)

        ack_response = self.client.post(
            f"/api/announcements/{self.announcement.id}/acknowledge/"
        )
        self.assertEqual(ack_response.status_code, 200)

        unread_after = self.client.get("/api/announcements/unread/")
        ids_after = {item["id"] for item in unread_after.data}
        self.assertNotIn(self.announcement.id, ids_after)

    def test_published_history_is_public_and_includes_published_records(self):
        response = self.client.get(
            "/api/announcements/published-history/", {"limit": 20}
        )
        self.assertEqual(response.status_code, 200)
        ids = {item["id"] for item in response.data}
        self.assertIn(self.announcement.id, ids)
        self.assertIn(self.expired_published.id, ids)
        self.assertNotIn(self.unpublished.id, ids)

    def test_manager_can_update_unpublished_announcement_without_all_param(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")

        response = self.client.patch(
            f"/api/announcements/{self.unpublished.id}/",
            {"is_published": True, "title": "A-hidden-updated"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.unpublished.refresh_from_db()
        self.assertTrue(self.unpublished.is_published)
        self.assertEqual(self.unpublished.title, "A-hidden-updated")

    def test_manager_can_delete_unpublished_announcement_without_all_param(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")

        response = self.client.delete(f"/api/announcements/{self.unpublished.id}/")

        self.assertEqual(response.status_code, 204)
        self.assertFalse(Announcement.objects.filter(id=self.unpublished.id).exists())


@override_settings(QA_MODULE_ENABLED=True)
class NotificationFlowTests(APITestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Notify", slug="notify")
        self.admin = User.objects.create_user(
            username="notify_admin", password="Password123", role=User.Role.ADMIN
        )
        self.school = User.objects.create_user(
            username="notify_school", password="Password123", role=User.Role.SCHOOL
        )
        self.author = User.objects.create_user(
            username="notify_author", password="Password123", role=User.Role.NORMAL
        )
        self.responder = User.objects.create_user(
            username="notify_responder", password="Password123", role=User.Role.NORMAL
        )

        self.admin_token = Token.objects.create(user=self.admin)
        self.school_token = Token.objects.create(user=self.school)
        self.author_token = Token.objects.create(user=self.author)
        self.responder_token = Token.objects.create(user=self.responder)

        self.article = Article.objects.create(
            title="Notify Article",
            summary="summary",
            content_md="content",
            category=self.category,
            author=self.admin,
            last_editor=self.admin,
            status=Article.Status.PUBLISHED,
        )
        self.question = Question.objects.create(
            title="Notify Question",
            content_md="question body",
            author=self.author,
            category=self.category,
        )
        self.revision = RevisionProposal.objects.create(
            article=self.article,
            proposer=self.author,
            proposed_title="Notify Article Updated",
            proposed_summary="updated",
            proposed_content_md="updated body",
            reason="improve wording",
        )
        self.issue = IssueTicket.objects.create(
            kind=IssueTicket.Kind.ISSUE,
            title="Notify Ticket",
            content="need help",
            author=self.author,
        )

    def test_notifications_endpoint_requires_authentication(self):
        response = self.client.get("/api/notifications/")
        self.assertIn(response.status_code, (401, 403))

    def test_answer_create_stays_pending_until_admin_review(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.responder_token.key}")
        response = self.client.post(
            "/api/answers/",
            {"question": self.question.id, "content_md": "new answer"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], Answer.Status.PENDING)
        self.assertFalse(
            UserNotification.objects.filter(
                user=self.author, target_type="Answer"
            ).exists()
        )

    def test_revision_review_notifies_proposer(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.post(
            f"/api/revisions/{self.revision.id}/approve/",
            {"review_note": "looks good"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            UserNotification.objects.filter(
                user=self.author,
                title__contains="修订提议已通过",
                target_type="RevisionProposal",
            ).exists()
        )

    def test_issue_assignment_notifies_author_and_assignee(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.post(
            f"/api/issues/{self.issue.id}/set_status/",
            {
                "status": IssueTicket.Status.IN_PROGRESS,
                "assign_to": self.school.id,
                "resolution_note": "please check",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            UserNotification.objects.filter(
                user=self.author,
                title__contains="工单状态已更新",
                target_id=self.issue.id,
            ).exists()
        )
        self.assertTrue(
            UserNotification.objects.filter(
                user=self.school,
                title__contains="你被指派处理工单",
                target_id=self.issue.id,
            ).exists()
        )

    def test_mark_read_and_mark_all_read(self):
        one = UserNotification.objects.create(
            user=self.author, title="n1", content="c1"
        )
        UserNotification.objects.create(user=self.author, title="n2", content="c2")

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.author_token.key}")

        list_response = self.client.get("/api/notifications/")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.data["count"], 2)

        mark_one = self.client.post(f"/api/notifications/{one.id}/mark-read/")
        self.assertEqual(mark_one.status_code, 200)
        one.refresh_from_db()
        self.assertTrue(one.is_read)

        unread_before = self.client.get("/api/notifications/unread-count/")
        self.assertEqual(unread_before.status_code, 200)
        self.assertEqual(unread_before.data["count"], 1)

        mark_all = self.client.post("/api/notifications/mark-all-read/")
        self.assertEqual(mark_all.status_code, 200)
        self.assertEqual(mark_all.data["updated"], 1)

        unread_after = self.client.get("/api/notifications/unread-count/")
        self.assertEqual(unread_after.status_code, 200)
        self.assertEqual(unread_after.data["count"], 0)

    def test_announcement_create_notifies_active_users_only(self):
        active_user = User.objects.create_user(
            username="notify_active",
            password="Password123",
            role=User.Role.NORMAL,
            is_active=True,
        )
        inactive_user = User.objects.create_user(
            username="notify_inactive",
            password="Password123",
            role=User.Role.NORMAL,
            is_active=False,
        )
        banned_user = User.objects.create_user(
            username="notify_banned",
            password="Password123",
            role=User.Role.NORMAL,
            is_active=True,
            is_banned=True,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.post(
            "/api/announcements/",
            {"title": "new announcement", "content_md": "body", "priority": 1},
            format="json",
        )
        self.assertEqual(response.status_code, 201)

        self.assertTrue(
            UserNotification.objects.filter(
                user=active_user, title__contains="新公告"
            ).exists()
        )
        self.assertFalse(
            UserNotification.objects.filter(
                user=inactive_user, title__contains="新公告"
            ).exists()
        )
        self.assertFalse(
            UserNotification.objects.filter(
                user=banned_user, title__contains="新公告"
            ).exists()
        )
        self.assertFalse(
            UserNotification.objects.filter(
                user=self.admin, title__contains="新公告"
            ).exists()
        )


class TeamMemberApiTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="team_admin",
            password="Password123",
            role=User.Role.ADMIN,
        )
        self.normal = User.objects.create_user(
            username="team_normal",
            password="Password123",
            role=User.Role.NORMAL,
        )
        self.admin_token = Token.objects.create(user=self.admin)
        self.normal_token = Token.objects.create(user=self.normal)

    def test_public_list_returns_team_members(self):
        response = self.client.get("/api/team-members/")
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.data), 1)
        self.assertIn("Null_Resot", [item["display_id"] for item in response.data])

    def test_admin_can_create_or_update_own_team_member(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        create_response = self.client.post(
            "/api/team-members/mine/",
            {
                "display_id": "AdminCard",
                "avatar_url": "https://example.com/a.png",
                "profile_url": "https://github.com/admin",
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(TeamMember.objects.filter(user=self.admin).count(), 1)

        update_response = self.client.patch(
            "/api/team-members/mine/",
            {
                "display_id": "AdminCardUpdated",
                "profile_url": "https://github.com/admin-new",
            },
            format="json",
        )
        self.assertEqual(update_response.status_code, 200)
        member = TeamMember.objects.get(user=self.admin)
        self.assertEqual(member.display_id, "AdminCardUpdated")
        self.assertEqual(member.profile_url, "https://github.com/admin-new")
        self.assertEqual(TeamMember.objects.filter(user=self.admin).count(), 1)

    def test_admin_can_delete_own_team_member(self):
        TeamMember.objects.create(
            user=self.admin,
            display_id="AdminCard",
            avatar_url="https://example.com/a.png",
            profile_url="https://github.com/admin",
            is_active=True,
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")

        delete_response = self.client.delete("/api/team-members/mine/")
        self.assertEqual(delete_response.status_code, 204)

        member = TeamMember.objects.get(user=self.admin)
        self.assertFalse(member.is_active)

        get_response = self.client.get("/api/team-members/mine/")
        self.assertEqual(get_response.status_code, 200)
        self.assertFalse(get_response.data["exists"])
        self.assertIsNone(get_response.data["member"])

    def test_normal_user_cannot_manage_team_member(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.normal_token.key}")
        response = self.client.get("/api/team-members/mine/")
        self.assertEqual(response.status_code, 403)

    def test_normal_user_cannot_delete_team_member(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.normal_token.key}")
        response = self.client.delete("/api/team-members/mine/")
        self.assertEqual(response.status_code, 403)


class CompetitionCalendarApiTests(APITestCase):
    def setUp(self):
        now = timezone.now()
        self.ongoing = CompetitionCalendarEvent.objects.create(
            source_site=CompetitionCalendarEvent.SourceSite.CODEFORCES,
            source_id="cf-ongoing",
            title="CF Ongoing",
            organizer="Codeforces",
            url="https://codeforces.com/contest/1",
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=1),
            duration_seconds=7200,
        )
        self.upcoming = CompetitionCalendarEvent.objects.create(
            source_site=CompetitionCalendarEvent.SourceSite.ATCODER,
            source_id="abc-upcoming",
            title="ABC Upcoming",
            organizer="AtCoder",
            url="https://atcoder.jp/contests/abc999",
            start_time=now + timedelta(days=1),
            end_time=now + timedelta(days=1, hours=2),
            duration_seconds=7200,
        )
        self.finished = CompetitionCalendarEvent.objects.create(
            source_site=CompetitionCalendarEvent.SourceSite.LUOGU,
            source_id="lg-finished",
            title="Luogu Finished",
            organizer="洛谷",
            url="https://www.luogu.com.cn/contest/100",
            start_time=now - timedelta(days=2, hours=2),
            end_time=now - timedelta(days=2),
            duration_seconds=7200,
        )
        self.old_finished = CompetitionCalendarEvent.objects.create(
            source_site=CompetitionCalendarEvent.SourceSite.NOWCODER,
            source_id="nc-finished-old",
            title="Nowcoder Finished Old",
            organizer="Nowcoder",
            url="https://ac.nowcoder.com/acm/contest/999",
            start_time=now - timedelta(days=45, hours=2),
            end_time=now - timedelta(days=45),
            duration_seconds=7200,
        )

    def test_public_calendar_list_supports_site_filter(self):
        response = self.client.get(
            "/api/competition-calendar/", {"sites": "codeforces,luogu"}
        )
        self.assertEqual(response.status_code, 200)
        items = response.data.get("results", response.data)
        source_ids = {item["source_id"] for item in items}
        self.assertIn(self.ongoing.source_id, source_ids)
        self.assertIn(self.finished.source_id, source_ids)
        self.assertNotIn(self.upcoming.source_id, source_ids)

    def test_public_calendar_list_supports_status_filter(self):
        response = self.client.get("/api/competition-calendar/", {"status": "upcoming"})
        self.assertEqual(response.status_code, 200)
        items = response.data.get("results", response.data)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["source_id"], self.upcoming.source_id)
        self.assertEqual(items[0]["status"], "upcoming")

    def test_calendar_taxonomy_returns_counts(self):
        response = self.client.get("/api/competition-calendar/taxonomy/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 3)
        count_map = {item["key"]: item["count"] for item in response.data["sources"]}
        self.assertEqual(count_map["codeforces"], 1)
        self.assertEqual(count_map["atcoder"], 1)
        self.assertEqual(count_map["luogu"], 1)
        self.assertEqual(count_map["nowcoder"], 0)

    def test_calendar_list_hides_finished_items_older_than_30_days(self):
        response = self.client.get("/api/competition-calendar/")
        self.assertEqual(response.status_code, 200)
        items = response.data.get("results", response.data)
        source_ids = {item["source_id"] for item in items}
        self.assertIn(self.ongoing.source_id, source_ids)
        self.assertIn(self.upcoming.source_id, source_ids)
        self.assertIn(self.finished.source_id, source_ids)
        self.assertNotIn(self.old_finished.source_id, source_ids)


class CompetitionScheduleApiTests(APITestCase):
    def setUp(self):
        self.school = User.objects.create_user(
            username="schedule_school",
            password="Password123",
            role=User.Role.SCHOOL,
        )
        self.admin = User.objects.create_user(
            username="schedule_admin",
            password="Password123",
            role=User.Role.ADMIN,
        )
        self.user = User.objects.create_user(
            username="schedule_user",
            password="Password123",
            role=User.Role.NORMAL,
        )
        self.school_token = Token.objects.create(user=self.school)
        self.admin_token = Token.objects.create(user=self.admin)
        self.user_token = Token.objects.create(user=self.user)
        self.notice = CompetitionNotice.objects.create(
            title="CCPC Regional Notice",
            content_md="notice body",
            series=CompetitionNotice.Series.CCPC,
            year=2026,
            stage=CompetitionNotice.Stage.REGIONAL,
            created_by=self.school,
            updated_by=self.school,
            is_visible=True,
        )

    def test_normal_user_can_submit_notice_for_admin_review(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.user_token.key}")
        create_response = self.client.post(
            "/api/competition-notices/",
            {
                "title": "User Notice",
                "content_md": "user submitted notice",
                "series": CompetitionNotice.Series.CCPC,
                "year": 2026,
                "stage": CompetitionNotice.Stage.REGIONAL,
                "is_visible": True,
            },
            format="json",
        )

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(create_response.data["status"], CompetitionNotice.Status.PENDING)
        self.assertFalse(create_response.data["is_visible"])
        notice_id = create_response.data["id"]

        list_response = self.client.get("/api/competition-notices/")
        items = list_response.data.get("results", list_response.data)
        self.assertNotIn(notice_id, {item["id"] for item in items})

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        review_response = self.client.post(
            f"/api/competition-notices/{notice_id}/approve/",
            {"review_note": "ok"},
            format="json",
        )
        self.assertEqual(review_response.status_code, 200)
        self.assertEqual(review_response.data["status"], CompetitionNotice.Status.APPROVED)
        self.assertTrue(review_response.data["is_visible"])

        self.client.credentials()
        public_response = self.client.get("/api/competition-notices/")
        public_items = public_response.data.get("results", public_response.data)
        self.assertIn(notice_id, {item["id"] for item in public_items})

    def test_notice_reject_sends_review_note_notification(self):
        notice = CompetitionNotice.objects.create(
            title="Pending User Notice",
            content_md="pending notice body",
            series=CompetitionNotice.Series.CCPC,
            year=2026,
            stage=CompetitionNotice.Stage.REGIONAL,
            created_by=self.user,
            updated_by=self.user,
            is_visible=False,
            status=CompetitionNotice.Status.PENDING,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.post(
            f"/api/competition-notices/{notice.id}/reject/",
            {"review_note": "Please add the official announcement URL."},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        notice.refresh_from_db()
        self.assertEqual(notice.status, CompetitionNotice.Status.REJECTED)
        self.assertEqual(notice.review_note, "Please add the official announcement URL.")
        notification = UserNotification.objects.get(
            user=self.user,
            target_type="CompetitionNotice",
            target_id=notice.id,
        )
        self.assertEqual(notification.level, UserNotification.Level.WARNING)
        self.assertIn("official announcement", notification.content)

    def test_normal_user_can_submit_schedule_for_admin_review(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.user_token.key}")
        create_response = self.client.post(
            "/api/competition-schedules/",
            {
                "event_date": (timezone.localdate() + timedelta(days=14)).isoformat(),
                "end_date": (timezone.localdate() + timedelta(days=16)).isoformat(),
                "competition_time_range": "09:00-12:00",
                "competition_type": "User Submitted Contest",
                "location": "Online",
                "qq_group": "123456",
                "announcement": self.notice.id,
            },
            format="json",
        )

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(
            create_response.data["status"], CompetitionScheduleEntry.Status.PENDING
        )
        entry_id = create_response.data["id"]

        list_response = self.client.get("/api/competition-schedules/")
        items = list_response.data.get("results", list_response.data)
        self.assertNotIn(entry_id, {item["id"] for item in items})

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        pending_response = self.client.get(
            "/api/competition-schedules/",
            {"include_hidden": 1, "status": CompetitionScheduleEntry.Status.PENDING},
        )
        pending_items = pending_response.data.get("results", pending_response.data)
        self.assertIn(entry_id, {item["id"] for item in pending_items})

        review_response = self.client.post(
            f"/api/competition-schedules/{entry_id}/approve/",
            {"review_note": "ok"},
            format="json",
        )
        self.assertEqual(review_response.status_code, 200)
        self.assertEqual(
            review_response.data["status"], CompetitionScheduleEntry.Status.APPROVED
        )

        self.client.credentials()
        public_response = self.client.get("/api/competition-schedules/")
        public_items = public_response.data.get("results", public_response.data)
        self.assertIn(entry_id, {item["id"] for item in public_items})

    def test_schedule_supports_date_range_and_defaults_end_date(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.school_token.key}")
        response = self.client.post(
            "/api/competition-schedules/",
            {
                "event_date": (timezone.localdate() + timedelta(days=20)).isoformat(),
                "end_date": (timezone.localdate() + timedelta(days=22)).isoformat(),
                "competition_time_range": "09:00-17:00",
                "competition_type": "Multi-day Contest",
                "location": "Jinan",
                "qq_group": "",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["end_date"], (timezone.localdate() + timedelta(days=22)).isoformat())

        list_response = self.client.get(
            "/api/competition-schedules/",
            {"year": timezone.localdate().year},
        )
        items = list_response.data.get("results", list_response.data)
        payload = next(item for item in items if item["id"] == response.data["id"])
        self.assertEqual(payload["end_date"], response.data["end_date"])

        invalid_response = self.client.post(
            "/api/competition-schedules/",
            {
                "event_date": (timezone.localdate() + timedelta(days=30)).isoformat(),
                "end_date": (timezone.localdate() + timedelta(days=29)).isoformat(),
                "competition_time_range": "09:00-17:00",
                "competition_type": "Invalid Contest",
                "location": "Online",
                "qq_group": "",
            },
            format="json",
        )
        self.assertEqual(invalid_response.status_code, 400)
        self.assertIn("end_date", invalid_response.data)

    def test_schedule_reject_sends_review_note_notification(self):
        entry = CompetitionScheduleEntry.objects.create(
            event_date=timezone.localdate() + timedelta(days=14),
            competition_time_range="09:00-12:00",
            competition_type="Pending Schedule Contest",
            location="Online",
            qq_group="123456",
            announcement=self.notice,
            created_by=self.user,
            updated_by=self.user,
            status=CompetitionScheduleEntry.Status.PENDING,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.post(
            f"/api/competition-schedules/{entry.id}/reject/",
            {"review_note": "Please confirm the contest date first."},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        entry.refresh_from_db()
        self.assertEqual(entry.status, CompetitionScheduleEntry.Status.REJECTED)
        self.assertEqual(entry.review_note, "Please confirm the contest date first.")
        notification = UserNotification.objects.get(
            user=self.user,
            target_type="CompetitionScheduleEntry",
            target_id=entry.id,
        )
        self.assertEqual(notification.level, UserNotification.Level.WARNING)
        self.assertIn("contest date", notification.content)

    def test_list_returns_notice_contributors(self):
        event = ContributionEvent.objects.create(
            user=self.admin,
            event_type=ContributionEvent.EventType.ADMIN,
            target_type="CompetitionNotice",
            target_id=self.notice.id,
            payload={"action": "update_competition_notice"},
        )
        ContributionEvent.objects.filter(id=event.id).update(
            created_at=self.notice.created_at + timedelta(minutes=5)
        )

        response = self.client.get("/api/competition-notices/")
        self.assertEqual(response.status_code, 200)
        items = response.data.get("results", response.data)
        payload = next(item for item in items if item["id"] == self.notice.id)
        contributors = payload["contributors"]

        self.assertEqual(
            [item["user"]["username"] for item in contributors],
            [self.school.username, self.admin.username],
        )
        self.assertTrue(contributors[0]["is_creator"])
        self.assertEqual(contributors[1]["approved_revision_count"], 1)

    def test_list_returns_schedule_contributors(self):
        entry = CompetitionScheduleEntry.objects.create(
            event_date=timezone.localdate() + timedelta(days=14),
            competition_time_range="10:00-16:00",
            competition_type="CCPC 区域赛",
            location="Nanjing",
            qq_group="",
            announcement=None,
            created_by=self.school,
            updated_by=self.admin,
            status=CompetitionScheduleEntry.Status.APPROVED,
            reviewer=self.school,
            reviewed_at=timezone.now(),
        )
        event = ContributionEvent.objects.create(
            user=self.admin,
            event_type=ContributionEvent.EventType.ADMIN,
            target_type="CompetitionScheduleEntry",
            target_id=entry.id,
            payload={"action": "update_competition_schedule"},
        )
        ContributionEvent.objects.filter(id=event.id).update(
            created_at=entry.created_at + timedelta(minutes=5)
        )

        response = self.client.get("/api/competition-schedules/", {"year": entry.event_date.year})
        self.assertEqual(response.status_code, 200)
        items = response.data.get("results", response.data)
        payload = next(item for item in items if item["id"] == entry.id)
        contributors = payload["contributors"]

        self.assertEqual(
            [item["user"]["username"] for item in contributors],
            [self.school.username, self.admin.username],
        )
        self.assertTrue(contributors[0]["is_creator"])
        self.assertEqual(contributors[1]["approved_revision_count"], 1)

    def test_school_user_can_patch_schedule_with_blank_fields_and_clear_announcement(
        self,
    ):
        entry = CompetitionScheduleEntry.objects.create(
            event_date=timezone.localdate() + timedelta(days=7),
            competition_time_range="09:00-17:00",
            competition_type="CCPC 区域赛",
            location="Main Campus",
            qq_group="123456",
            announcement=self.notice,
            created_by=self.school,
            updated_by=self.school,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.school_token.key}")
        response = self.client.patch(
            f"/api/competition-schedules/{entry.id}/",
            {
                "event_date": (timezone.localdate() + timedelta(days=8)).isoformat(),
                "competition_time_range": "",
                "competition_type": "CCPC 区域赛调整",
                "location": "Online",
                "qq_group": "",
                "announcement": None,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        entry.refresh_from_db()
        self.assertEqual(entry.event_date.isoformat(), response.data["event_date"])
        self.assertEqual(entry.competition_time_range, "")
        self.assertEqual(entry.competition_type, "CCPC 区域赛调整")
        self.assertEqual(entry.location, "Online")
        self.assertEqual(entry.qq_group, "")
        self.assertIsNone(entry.announcement)

    def test_school_user_can_patch_schedule_via_method_override_header(self):
        entry = CompetitionScheduleEntry.objects.create(
            event_date=timezone.localdate() + timedelta(days=7),
            competition_time_range="09:00-17:00",
            competition_type="CCPC 区域赛",
            location="Main Campus",
            qq_group="123456",
            announcement=self.notice,
            created_by=self.school,
            updated_by=self.school,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.school_token.key}")
        response = self.client.post(
            f"/api/competition-schedules/{entry.id}/",
            {
                "event_date": (timezone.localdate() + timedelta(days=9)).isoformat(),
                "competition_time_range": "",
                "competition_type": "CCPC 区域赛覆写",
                "location": "Updated Campus",
                "qq_group": "",
                "announcement": None,
            },
            format="json",
            HTTP_X_HTTP_METHOD_OVERRIDE="PATCH",
        )

        self.assertEqual(response.status_code, 200)
        entry.refresh_from_db()
        self.assertEqual(entry.event_date.isoformat(), response.data["event_date"])
        self.assertEqual(entry.competition_time_range, "")
        self.assertEqual(entry.competition_type, "CCPC 区域赛覆写")
        self.assertEqual(entry.location, "Updated Campus")
        self.assertEqual(entry.qq_group, "")
        self.assertIsNone(entry.announcement)

    def test_school_user_can_patch_schedule_without_announcement_field_when_entry_is_unlinked(
        self,
    ):
        entry = CompetitionScheduleEntry.objects.create(
            event_date=timezone.localdate() + timedelta(days=10),
            competition_time_range="13:00-18:00",
            competition_type="XCPC 训练赛",
            location="Lab 401",
            qq_group="654321",
            announcement=None,
            created_by=self.school,
            updated_by=self.school,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.school_token.key}")
        response = self.client.patch(
            f"/api/competition-schedules/{entry.id}/",
            {
                "event_date": (timezone.localdate() + timedelta(days=11)).isoformat(),
                "competition_time_range": "",
                "competition_type": "XCPC 周练",
                "location": "Lab 402",
                "qq_group": "",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        entry.refresh_from_db()
        self.assertEqual(entry.event_date.isoformat(), response.data["event_date"])
        self.assertEqual(entry.competition_time_range, "")
        self.assertEqual(entry.competition_type, "XCPC 周练")
        self.assertEqual(entry.location, "Lab 402")
        self.assertEqual(entry.qq_group, "")
        self.assertIsNone(entry.announcement)

    def test_deleted_schedule_is_stored_in_archive_and_listed_for_admin(self):
        entry = CompetitionScheduleEntry.objects.create(
            event_date=timezone.localdate() + timedelta(days=12),
            end_date=timezone.localdate() + timedelta(days=13),
            competition_time_range="09:00-17:00",
            competition_type="Archived Contest",
            location="Campus",
            qq_group="",
            announcement=None,
            created_by=self.school,
            updated_by=self.school,
            status=CompetitionScheduleEntry.Status.APPROVED,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        delete_response = self.client.delete(f"/api/competition-schedules/{entry.id}/")
        self.assertEqual(delete_response.status_code, 204)
        self.assertFalse(CompetitionScheduleEntry.objects.filter(id=entry.id).exists())

        archive = DeletedContentArchive.objects.get(
            target_type="CompetitionScheduleEntry",
            target_id=entry.id,
            delete_action=DeletedContentArchive.DeleteAction.DELETE,
        )
        self.assertEqual(archive.title, "Archived Contest")
        self.assertEqual(archive.original_author_id, self.school.id)
        self.assertEqual(archive.deleted_by_id, self.admin.id)
        self.assertEqual(archive.snapshot["end_date"], entry.end_date.isoformat())

        list_response = self.client.get(
            "/api/deleted-content-archives/",
            {"target_type": "CompetitionScheduleEntry"},
        )
        self.assertEqual(list_response.status_code, 200)
        items = list_response.data.get("results", list_response.data)
        self.assertIn(archive.id, {item["id"] for item in items})


class AssistantApiTests(APITestCase):
    def setUp(self):
        cache.clear()
        clear_public_corpus_cache()

        self.category = Category.objects.create(name="Assistant", slug="assistant")
        self.superadmin = User.objects.create_user(
            username="assistant_superadmin",
            password="Password123",
            role=User.Role.SUPERADMIN,
        )
        self.admin = User.objects.create_user(
            username="assistant_admin",
            password="Password123",
            role=User.Role.ADMIN,
        )
        self.user = User.objects.create_user(
            username="assistant_user",
            password="Password123",
            role=User.Role.NORMAL,
        )
        self.superadmin_token = Token.objects.create(user=self.superadmin)
        self.admin_token = Token.objects.create(user=self.admin)
        self.user_token = Token.objects.create(user=self.user)

        self.article = Article.objects.create(
            title="比赛日历入口",
            summary="赛事专区包含比赛日历和赛事公告。",
            content_md="在赛事专区可以查看比赛日历表、赛事公告和补题链接。",
            category=self.category,
            author=self.superadmin,
            last_editor=self.superadmin,
            status=Article.Status.PUBLISHED,
        )

        self.site_article = Article.objects.create(
            title="\u5173\u952e\u7f51\u7ad9",
            summary="\u6536\u96c6\u7ade\u8d5b\u8bad\u7ec3\u4e2d\u5e38\u7528\u7684\u7f51\u7ad9\u3002",
            content_md=(
                "## yuantiji.ac\n"
                "\u539f\u9898\u673a\uff0c\u53ef\u4ee5\u628a\u9898\u9762\u653e\u8fdb\u53bb\u641c\u7d22\uff0c"
                "\u627e\u5230\u9898\u76ee\u51fa\u5904\u6216\u76f8\u4f3c\u9898\u76ee\u3002"
            ),
            category=self.category,
            author=self.superadmin,
            last_editor=self.superadmin,
            status=Article.Status.PUBLISHED,
        )

        self.lanqiao_article = Article.objects.create(
            title="比赛介绍｜蓝桥杯",
            summary="蓝桥杯比赛介绍。",
            content_md=(
                "## 比赛介绍\n"
                "蓝桥杯大赛采用 **OI 赛制**，所有题目按最后一次提交判分，"
                "支持部分分，分数赛后统一公布。"
            ),
            category=self.category,
            author=self.superadmin,
            last_editor=self.superadmin,
            status=Article.Status.PUBLISHED,
        )

        self.calendar_event = CompetitionCalendarEvent.objects.create(
            source_site=CompetitionCalendarEvent.SourceSite.CODEFORCES,
            source_id="assistant-upcoming-online",
            title="Codeforces Round 999",
            organizer="Codeforces",
            url="https://codeforces.com/contest/999",
            start_time=timezone.now() + timedelta(days=1, hours=2),
            end_time=timezone.now() + timedelta(days=1, hours=4),
            duration_seconds=7200,
        )
        self.schedule_entry = CompetitionScheduleEntry.objects.create(
            event_date=timezone.localdate() + timedelta(days=3),
            competition_time_range="09:00-17:00",
            competition_type="CCPC 区域赛",
            location="南京",
            qq_group="",
            announcement=None,
            created_by=self.superadmin,
            updated_by=self.superadmin,
        )
        self.trick_term = TrickTerm.objects.create(name="gcd", slug="gcd")
        self.trick_entry = TrickEntry.objects.create(
            title="GCD parity trick",
            content_md="Use gcd(a, b) parity to prune impossible states.",
            author=self.superadmin,
            status=TrickEntry.Status.APPROVED,
        )
        self.trick_entry.terms.add(self.trick_term)

        self.config = AssistantProviderConfig.objects.create(
            label="DeepSeek Production",
            assistant_name="AlgoWiki 助手",
            provider=AssistantProviderConfig.Provider.DEEPSEEK,
            base_url="https://api.deepseek.com",
            model_name="deepseek-chat",
            is_enabled=True,
            is_default=True,
            show_launcher=True,
            created_by=self.superadmin,
            updated_by=self.superadmin,
            welcome_message="你好，这里是站内助手。",
            suggested_questions=["比赛日历在哪里看？"],
        )
        self.config.set_api_key("sk-test-123")
        self.config.save(update_fields=["api_key_encrypted", "updated_at"])

    def tearDown(self):
        clear_public_corpus_cache()
        super().tearDown()

    def assertHasBrattyTone(self, text):
        self.assertIn("师兄", text)
        self.assertTrue(
            any(
                marker in text
                for marker in ("杂鱼", "不会吧", "可别逗我", "就这", "菜", "不让人省心")
            ),
            msg=f"Expected bratty taunt marker in: {text}",
        )

    def test_public_config_and_admin_list_never_expose_api_key(self):
        public_response = self.client.get("/api/assistant/config/")
        self.assertEqual(public_response.status_code, 200)
        self.assertTrue(public_response.data["enabled"])
        self.assertEqual(public_response.data["assistant_name"], "AlgoWiki 助手")
        self.assertEqual(
            public_response.data["welcome_message"], "你好，这里是站内助手。"
        )
        self.assertEqual(
            public_response.data["teaser_message"],
            "杂鱼师兄，想要更方便地了解AlgoWiki，可以点击询问小小丛雨我哦~",
        )
        self.assertNotIn("api_key_encrypted", public_response.data)

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        admin_response = self.client.get("/api/assistant-configs/")
        self.assertEqual(admin_response.status_code, 200)
        items = admin_response.data.get("results", admin_response.data)
        self.assertEqual(len(items), 1)
        self.assertTrue(items[0]["has_api_key"])
        self.assertEqual(items[0]["api_key_masked"], "****************")
        self.assertNotIn("api_key_encrypted", items[0])
        self.assertNotIn("api_key_input", items[0])

    def test_chat_system_prompt_uses_brattish_tone(self):
        messages = build_chat_messages_compact(
            config=self.config,
            message="AlgoWiki 是什么？",
            history=[],
            sources=[],
        )

        self.assertTrue(messages)
        self.assertEqual(messages[0]["role"], "system")
        self.assertIn("师兄", messages[0]["content"])
        self.assertIn("雌小鬼", messages[0]["content"])
        self.assertIn("杂鱼师兄", messages[0]["content"])
        self.assertNotIn("主人", messages[0]["content"])
        self.assertNotIn("喵", messages[0]["content"])

    def test_admin_cannot_modify_assistant_config(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        patch_response = self.client.patch(
            f"/api/assistant-configs/{self.config.id}/",
            {"label": "Changed by admin"},
            format="json",
        )
        self.assertEqual(patch_response.status_code, 403)

        create_response = self.client.post(
            "/api/assistant-configs/",
            {
                "label": "New Config",
                "assistant_name": "AlgoWiki 助手",
                "provider": "deepseek",
                "base_url": "https://api.deepseek.com",
                "model_name": "deepseek-chat",
                "api_key_input": "sk-another",
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, 403)

    def test_superadmin_can_rotate_api_key_without_readback(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.superadmin_token.key}")
        response = self.client.patch(
            f"/api/assistant-configs/{self.config.id}/",
            {
                "label": "DeepSeek Primary",
                "api_key_input": "sk-updated-456",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["api_key_masked"], "****************")
        self.assertNotIn("api_key_input", response.data)

        self.config.refresh_from_db()
        self.assertEqual(self.config.label, "DeepSeek Primary")
        self.assertEqual(self.config.get_api_key(), "sk-updated-456")

    @override_settings(CAPTCHA_ENABLED=True, CAPTCHA_REQUIRED_FOR_AUTHENTICATED_USERS=True)
    def test_chat_does_not_require_captcha_when_global_captcha_is_enabled(self):
        with patch(
            "wiki.views.invoke_assistant_completion",
            return_value={
                "content": "比赛日历可以在赛事专区查看。",
                "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
                "model": "deepseek-chat",
            },
        ) as mocked_provider:
            response = self.client.post(
                "/api/assistant/chat/",
                {
                    "message": "比赛日历在哪里？",
                    "history": [],
                    "session_id": "captcha-not-required",
                },
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        mocked_provider.assert_called_once()
        self.assertFalse(CaptchaAuditLog.objects.filter(scene="assistant_chat").exists())

    def test_chat_endpoint_returns_sources_and_writes_interaction_log(self):
        with patch(
            "wiki.views.invoke_assistant_completion",
            return_value={
                "content": "比赛日历可以在赛事专区查看，入口位于赛事专区的比赛日历表。",
                "usage": {
                    "prompt_tokens": 11,
                    "completion_tokens": 22,
                    "total_tokens": 33,
                },
                "model": "deepseek-chat",
            },
        ) as mocked_provider:
            response = self.client.post(
                "/api/assistant/chat/",
                {
                    "message": "比赛日历在哪里看？",
                    "history": [],
                    "session_id": "session-1",
                },
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("比赛日历", response.data["answer"])
        self.assertHasBrattyTone(response.data["answer"])
        self.assertTrue(response.data["sources"])
        self.assertEqual(response.data["model"], "deepseek-chat")
        mocked_provider.assert_called_once()

        log = AssistantInteractionLog.objects.get()
        self.assertTrue(log.success)
        self.assertEqual(log.session_id, "session-1")
        self.assertEqual(log.total_tokens, 33)
        self.assertGreaterEqual(log.source_count, 1)

    def test_chat_endpoint_returns_brattish_fallback_when_no_sources_match(self):
        with patch("wiki.views.invoke_assistant_completion") as mocked_provider:
            response = self.client.post(
                "/api/assistant/chat/",
                {
                    "message": "zzqv_unique_token_94731",
                    "history": [],
                    "session_id": "session-no-source",
                },
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertHasBrattyTone(response.data["answer"])
        self.assertFalse(response.data["sources"])
        self.assertEqual(response.data["model"], "deepseek-chat")
        mocked_provider.assert_not_called()

        log = AssistantInteractionLog.objects.get(session_id="session-no-source")
        self.assertTrue(log.success)
        self.assertEqual(log.total_tokens, 0)
        self.assertEqual(log.source_count, 0)

    def test_recent_competition_query_uses_builtin_digest_without_calling_provider(
        self,
    ):
        with patch("wiki.views.invoke_assistant_completion") as mocked_provider:
            response = self.client.post(
                "/api/assistant/chat/",
                {
                    "message": "最近有哪些比赛？",
                    "history": [],
                    "session_id": "session-brief",
                },
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertHasBrattyTone(response.data["answer"])
        self.assertNotIn("主人", response.data["answer"])
        self.assertNotIn("喵", response.data["answer"])
        self.assertIn("线上", response.data["answer"])
        self.assertIn("线下", response.data["answer"])
        self.assertEqual(response.data["model"], "builtin-competition-brief")
        self.assertTrue(response.data["sources"])
        mocked_provider.assert_not_called()

        log = AssistantInteractionLog.objects.get(session_id="session-brief")
        self.assertTrue(log.success)
        self.assertEqual(log.total_tokens, 0)
        self.assertEqual(log.source_count, len(response.data["sources"]))

    def test_trick_query_uses_builtin_digest_without_calling_provider(self):
        with patch("wiki.views.invoke_assistant_completion") as mocked_provider:
            response = self.client.post(
                "/api/assistant/chat/",
                {
                    "message": "gcd trick",
                    "history": [],
                    "session_id": "session-trick",
                    "current_path": "/competitions?tab=tricks",
                    "current_title": "trick",
                },
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertHasBrattyTone(response.data["answer"])
        self.assertIn("GCD parity trick", response.data["answer"])
        self.assertEqual(response.data["model"], "builtin-trick-digest")
        self.assertTrue(response.data["sources"])
        self.assertEqual(response.data["sources"][0]["source_type"], "trick")
        self.assertIn("/competitions?tab=tricks", response.data["sources"][0]["url"])
        mocked_provider.assert_not_called()

        log = AssistantInteractionLog.objects.get(session_id="session-trick")
        self.assertTrue(log.success)
        self.assertEqual(log.total_tokens, 0)
        self.assertEqual(log.source_count, len(response.data["sources"]))

    def test_original_problem_site_query_uses_current_page_context(self):
        with patch("wiki.views.invoke_assistant_completion") as mocked_provider:
            response = self.client.post(
                "/api/assistant/chat/",
                {
                    "message": "我想要一个能根据题意找到原题的网站",
                    "history": [],
                    "session_id": "session-site-match",
                    "current_path": f"/wiki/{self.site_article.id}",
                    "current_title": "关键网站",
                },
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("yuantiji.ac", response.data["answer"])
        self.assertHasBrattyTone(response.data["answer"])
        self.assertNotIn("主人", response.data["answer"])
        self.assertNotIn("喵", response.data["answer"])
        self.assertEqual(response.data["model"], "builtin-site-match")
        self.assertEqual(len(response.data["sources"]), 1)
        self.assertIn(str(self.site_article.id), response.data["sources"][0]["url"])
        mocked_provider.assert_not_called()

        log = AssistantInteractionLog.objects.get(session_id="session-site-match")
        self.assertTrue(log.success)
        self.assertEqual(log.total_tokens, 0)
        self.assertEqual(log.source_count, 1)

    def test_competition_format_query_uses_builtin_digest(self):
        with patch("wiki.views.invoke_assistant_completion") as mocked_provider:
            response = self.client.post(
                "/api/assistant/chat/",
                {
                    "message": "蓝桥杯是什么赛制",
                    "history": [],
                    "session_id": "session-format",
                    "current_path": f"/wiki/{self.lanqiao_article.id}",
                    "current_title": self.lanqiao_article.title,
                },
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertHasBrattyTone(response.data["answer"])
        self.assertIn("OI 赛制", response.data["answer"])
        self.assertIn("最后一次提交", response.data["answer"])
        self.assertNotIn("主人", response.data["answer"])
        self.assertNotIn("喵", response.data["answer"])
        self.assertEqual(response.data["model"], "builtin-competition-format")
        self.assertEqual(len(response.data["sources"]), 1)
        self.assertIn(str(self.lanqiao_article.id), response.data["sources"][0]["url"])
        self.assertIn("OI 赛制", response.data["sources"][0]["excerpt"])
        mocked_provider.assert_not_called()

        log = AssistantInteractionLog.objects.get(session_id="session-format")
        self.assertTrue(log.success)
        self.assertEqual(log.total_tokens, 0)
        self.assertEqual(log.source_count, 1)

    def test_competition_format_query_ignores_homepage_title(self):
        with patch("wiki.views.invoke_assistant_completion") as mocked_provider:
            response = self.client.post(
                "/api/assistant/chat/",
                {
                    "message": "蓝桥杯是什么赛制",
                    "history": [],
                    "session_id": "session-format-home",
                    "current_path": "/",
                    "current_title": "欢迎来到 AlgoWiki!",
                },
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertHasBrattyTone(response.data["answer"])
        self.assertIn("蓝桥杯采用 OI 赛制", response.data["answer"])
        self.assertNotIn("欢迎来到 AlgoWiki", response.data["answer"])
        self.assertNotIn("主人", response.data["answer"])
        self.assertNotIn("喵", response.data["answer"])
        self.assertEqual(response.data["model"], "builtin-competition-format")
        mocked_provider.assert_not_called()

    def test_public_config_preserves_custom_welcome_message(self):
        self.config.welcome_message = "师兄你好，我是小丛雨喵~"
        self.config.teaser_message = "师兄，点我一下，本姑娘勉强给你带路。"
        self.config.assistant_name = "小小丛雨"
        self.config.save(
            update_fields=[
                "welcome_message",
                "teaser_message",
                "assistant_name",
                "updated_at",
            ]
        )

        response = self.client.get("/api/assistant/config/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["assistant_name"], "小小丛雨")




        self.assertEqual(response.data["welcome_message"], "师兄你好，我是小丛雨喵~")
        self.assertEqual(
            response.data["teaser_message"],
            "师兄，点我一下，本姑娘勉强给你带路。",
        )


@override_settings(QA_MODULE_ENABLED=True)
class AIModerationFlowTests(APITestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            username="ai_moderation_user",
            email="ai_moderation_user@example.com",
            password="Password123",
            role=User.Role.NORMAL,
        )
        self.admin = User.objects.create_user(
            username="ai_moderation_admin",
            email="ai_moderation_admin@example.com",
            password="Password123",
            role=User.Role.ADMIN,
        )
        self.superadmin = User.objects.create_user(
            username="ai_moderation_superadmin",
            email="ai_moderation_superadmin@example.com",
            password="Password123",
            role=User.Role.SUPERADMIN,
        )
        self.category = Category.objects.create(name="AI Moderation", slug="ai-moderation")
        self.article = Article.objects.create(
            title="AI Moderation Article",
            summary="summary",
            content_md="content",
            category=self.category,
            author=self.admin,
            status=Article.Status.PUBLISHED,
            allow_comments=True,
        )
        self.config = AIModerationConfig.get_solo()
        self.config.is_enabled = True
        self.config.comment_enabled = True
        self.config.question_enabled = True
        self.config.set_api_key("test-key")
        self.config.save()

    def provider_payload(self, risk_level="safe", suggested_action="approve"):
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "risk_level": risk_level,
                                "suggested_action": suggested_action,
                                "categories": [],
                                "summary": "测试审核通过",
                                "user_notice": "",
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            "model": "deepseek-test",
        }

    def test_ai_approves_pending_comment(self):
        self.client.force_authenticate(self.author)
        with patch(
            "wiki.ai_moderation.invoke_ai_moderation_completion",
            return_value=self.provider_payload(),
        ):
            response = self.client.post(
                "/api/comments/",
                {"article": self.article.id, "content": "这是一条正常评论"},
                format="json",
            )
        self.assertEqual(response.status_code, 201)
        comment = ArticleComment.objects.get(id=response.data["id"])
        self.assertEqual(comment.status, ArticleComment.Status.VISIBLE)
        record = AIModerationRecord.objects.get(
            target_type=AIModerationRecord.TargetType.COMMENT,
            target_id=comment.id,
        )
        self.assertEqual(record.decision, AIModerationRecord.Decision.APPROVE)
        self.assertEqual(record.status, AIModerationRecord.Status.APPLIED)
        self.assertTrue(
            UserNotification.objects.filter(
                user=self.author,
                target_type="ArticleComment",
                target_id=comment.id,
            ).exists()
        )

    def test_ai_rejects_question(self):
        self.client.force_authenticate(self.author)
        with patch(
            "wiki.ai_moderation.invoke_ai_moderation_completion",
            return_value=self.provider_payload(risk_level="reject", suggested_action="reject"),
        ):
            response = self.client.post(
                "/api/questions/",
                {
                    "title": "Spam question",
                    "content_md": "bad content",
                    "category": self.category.id,
                },
                format="json",
            )
        self.assertEqual(response.status_code, 201)
        question = Question.objects.get(id=response.data["id"])
        self.assertEqual(question.status, Question.Status.HIDDEN)
        record = AIModerationRecord.objects.get(
            target_type=AIModerationRecord.TargetType.QUESTION,
            target_id=question.id,
        )
        self.assertEqual(record.decision, AIModerationRecord.Decision.REJECT)
        self.assertEqual(record.status, AIModerationRecord.Status.APPLIED)

    def test_ai_can_directly_approve_suspicious_content(self):
        self.config.suspicious_action = AIModerationConfig.SuspiciousAction.APPROVE
        self.config.save(update_fields=["suspicious_action", "updated_at"])
        self.client.force_authenticate(self.author)
        with patch(
            "wiki.ai_moderation.invoke_ai_moderation_completion",
            return_value=self.provider_payload(risk_level="suspicious", suggested_action="manual"),
        ):
            response = self.client.post(
                "/api/comments/",
                {"article": self.article.id, "content": "前排，测试"},
                format="json",
            )
        self.assertEqual(response.status_code, 201)
        comment = ArticleComment.objects.get(id=response.data["id"])
        self.assertEqual(comment.status, ArticleComment.Status.VISIBLE)
        record = AIModerationRecord.objects.get(
            target_type=AIModerationRecord.TargetType.COMMENT,
            target_id=comment.id,
        )
        self.assertEqual(record.risk_level, AIModerationRecord.RiskLevel.SUSPICIOUS)
        self.assertEqual(record.decision, AIModerationRecord.Decision.APPROVE)
        self.assertEqual(record.status, AIModerationRecord.Status.APPLIED)

    def test_regular_admin_cannot_update_provider_fields(self):
        self.client.force_authenticate(self.admin)
        response = self.client.patch(
            "/api/ai-moderation-configs/current/",
            {
                "model_name": "should-not-change",
                "api_key_input": "should-not-save",
                "comment_enabled": False,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.config.refresh_from_db()
        self.assertNotEqual(self.config.model_name, "should-not-change")
        self.assertFalse(self.config.comment_enabled)
        self.assertIn("comment_enabled", response.data)


class CompetitionCalendarSyncCommandTests(APITestCase):
    def test_sync_command_creates_and_updates_calendar_events(self):
        now = timezone.now()
        initial_row = NormalizedCompetitionEvent(
            source_site=CompetitionCalendarEvent.SourceSite.CODEFORCES,
            source_id="2026-demo",
            title="Demo Contest",
            organizer="Codeforces",
            url="https://codeforces.com/contest/2026",
            start_time=now + timedelta(days=1),
            end_time=now + timedelta(days=1, hours=2),
            duration_seconds=7200,
            extra={"phase": "BEFORE"},
        )

        with patch.dict(
            "wiki.competition_calendar.SOURCE_FETCHERS",
            {CompetitionCalendarEvent.SourceSite.CODEFORCES: lambda: [initial_row]},
            clear=False,
        ):
            call_command(
                "sync_competition_calendar",
                sites="codeforces",
                future_days=30,
                past_days=30,
            )

        created = CompetitionCalendarEvent.objects.get(
            source_site=CompetitionCalendarEvent.SourceSite.CODEFORCES,
            source_id="2026-demo",
        )
        self.assertEqual(created.title, "Demo Contest")
        self.assertEqual(created.duration_seconds, 7200)

        updated_row = NormalizedCompetitionEvent(
            source_site=CompetitionCalendarEvent.SourceSite.CODEFORCES,
            source_id="2026-demo",
            title="Demo Contest Updated",
            organizer="Codeforces",
            url="https://codeforces.com/contest/2026",
            start_time=now + timedelta(days=1),
            end_time=now + timedelta(days=1, hours=3),
            duration_seconds=10800,
            extra={"phase": "BEFORE"},
        )

        with patch.dict(
            "wiki.competition_calendar.SOURCE_FETCHERS",
            {CompetitionCalendarEvent.SourceSite.CODEFORCES: lambda: [updated_row]},
            clear=False,
        ):
            call_command(
                "sync_competition_calendar",
                sites="codeforces",
                future_days=30,
                past_days=30,
            )

        created.refresh_from_db()
        self.assertEqual(created.title, "Demo Contest Updated")
        self.assertEqual(created.duration_seconds, 10800)
        self.assertEqual(
            CompetitionCalendarEvent.objects.filter(
                source_site=CompetitionCalendarEvent.SourceSite.CODEFORCES,
                source_id="2026-demo",
            ).count(),
            1,
        )

    def test_sync_command_removes_stale_future_events_but_keeps_finished_history(self):
        now = timezone.now()
        stale_upcoming = CompetitionCalendarEvent.objects.create(
            source_site=CompetitionCalendarEvent.SourceSite.CODEFORCES,
            source_id="cancelled-demo",
            title="Cancelled Contest",
            organizer="Codeforces",
            url="https://codeforces.com/contest/999999",
            start_time=now + timedelta(days=2),
            end_time=now + timedelta(days=2, hours=2),
            duration_seconds=7200,
            last_synced_at=now - timedelta(days=1),
        )
        finished_history = CompetitionCalendarEvent.objects.create(
            source_site=CompetitionCalendarEvent.SourceSite.CODEFORCES,
            source_id="finished-demo",
            title="Finished Contest",
            organizer="Codeforces",
            url="https://codeforces.com/contest/888888",
            start_time=now - timedelta(days=3, hours=2),
            end_time=now - timedelta(days=3),
            duration_seconds=7200,
            last_synced_at=now - timedelta(days=1),
        )
        replacement_row = NormalizedCompetitionEvent(
            source_site=CompetitionCalendarEvent.SourceSite.CODEFORCES,
            source_id="next-demo",
            title="Next Contest",
            organizer="Codeforces",
            url="https://codeforces.com/contest/777777",
            start_time=now + timedelta(days=1),
            end_time=now + timedelta(days=1, hours=2),
            duration_seconds=7200,
            extra={"phase": "BEFORE"},
        )

        with patch.dict(
            "wiki.competition_calendar.SOURCE_FETCHERS",
            {CompetitionCalendarEvent.SourceSite.CODEFORCES: lambda: [replacement_row]},
            clear=False,
        ):
            call_command(
                "sync_competition_calendar",
                sites="codeforces",
                future_days=30,
                past_days=30,
            )

        self.assertFalse(
            CompetitionCalendarEvent.objects.filter(id=stale_upcoming.id).exists()
        )
        self.assertTrue(
            CompetitionCalendarEvent.objects.filter(id=finished_history.id).exists()
        )
        self.assertTrue(
            CompetitionCalendarEvent.objects.filter(
                source_site=CompetitionCalendarEvent.SourceSite.CODEFORCES,
                source_id="next-demo",
            ).exists()
        )


@override_settings(
    ALIYUN_IDVERIFY={
        "ENABLED": True,
        "ACCESS_KEY_ID": "test-access-key-id",
        "ACCESS_KEY_SECRET": "test-access-key-secret",
        "SCENE_ID": "12345",
        "PRODUCT_CODE": "ID_PRO",
        "MODEL": "MOVE_ACTION",
        "CERT_TYPE": "IDENTITY_CARD",
        "CERTIFY_URL_TYPE": "H5",
        "CERTIFY_URL_STYLE": "",
        "PROCEDURE_PRIORITY": "url",
        "ENDPOINTS": ["cloudauth.cn-shanghai.aliyuncs.com"],
        "RETURN_URL": "https://test.algowiki.cn/moments?real_name_return=1",
        "CALLBACK_URL": "https://test.algowiki.cn/api/real-name-verifications/aliyun-callback/",
        "TIMEOUT_SECONDS": 15,
    }
)
class RealNameProviderTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="aliyun_user",
            email="aliyun_user@example.com",
            password="Password123",
            role=User.Role.NORMAL,
        )
        self.factory = APIRequestFactory()

    def _request(self):
        request = self.factory.get("/api/real-name-verifications/me/")
        request.user = self.user
        request.META["REMOTE_ADDR"] = "127.0.0.1"
        request.META["HTTP_X_FORWARDED_FOR"] = "127.0.0.1"
        return request

    def test_start_real_name_verification_persists_aliyun_trace(self):
        fake_response = SimpleNamespace(
            code="200",
            message="OK",
            request_id="req-1",
            result_object=SimpleNamespace(
                certify_id="certify-123",
                certify_url="https://aliyun.example/verify",
            ),
        )
        with patch("wiki.real_name_providers._call_with_failover", return_value=SimpleNamespace(body=fake_response)):
            instance, payload = start_aliyun_real_name_verification(
                user=self.user,
                real_name="张三",
                id_number="123456789012345678",
                meta_info={"ua": "Mozilla/5.0"},
                certify_url_type="H5",
                request=self._request(),
            )

        self.assertEqual(payload["certify_id"], "certify-123")
        self.assertEqual(payload["certify_url"], "https://aliyun.example/verify")
        self.assertEqual(instance.status, RealNameVerification.Status.PENDING)
        self.assertEqual(instance.provider, "aliyun")
        self.assertEqual(instance.provider_trace_id, "certify-123")
        self.assertEqual(instance.id_number_last4, "5678")
        self.assertTrue(instance.provider_started_at)
        self.assertTrue(instance.provider_expires_at)

    def test_sync_real_name_verification_marks_verified_and_rejected(self):
        instance = RealNameVerification.objects.create(
            user=self.user,
            status=RealNameVerification.Status.PENDING,
            provider="aliyun",
            provider_trace_id="certify-456",
            provider_certify_id="certify-456",
        )
        approve_response = SimpleNamespace(
            code="200",
            message="OK",
            request_id="req-2",
            result_object=SimpleNamespace(
                passed="T",
                success="true",
                sub_code="200",
                device_risk="low",
            ),
        )
        with patch("wiki.real_name_providers._call_with_failover", return_value=SimpleNamespace(body=approve_response)):
            verified = sync_aliyun_real_name_verification(instance)
        self.assertEqual(verified.status, RealNameVerification.Status.VERIFIED)
        self.assertTrue(verified.verified_at)
        self.assertEqual(verified.provider_sub_code, "200")

        instance.status = RealNameVerification.Status.PENDING
        instance.verified_at = None
        instance.provider_trace_id = "certify-789"
        instance.provider_certify_id = "certify-789"
        instance.save()
        reject_response = SimpleNamespace(
            code="200",
            message="OK",
            request_id="req-3",
            result_object=SimpleNamespace(
                passed="F",
                success="true",
                sub_code="400",
                device_risk="high",
            ),
        )
        with patch("wiki.real_name_providers._call_with_failover", return_value=SimpleNamespace(body=reject_response)):
            rejected = sync_aliyun_real_name_verification(instance)
        self.assertEqual(rejected.status, RealNameVerification.Status.REJECTED)
        self.assertEqual(rejected.provider_sub_code, "400")


@override_settings(
    ALIYUN_PNVS={
        "ENABLED": True,
        "ACCESS_KEY_ID": "test-access-key-id",
        "ACCESS_KEY_SECRET": "test-access-key-secret",
        "SIGN_NAME": "速通互联验证码",
        "TEMPLATE_CODE": "100001",
        "TEMPLATE_PARAM": "{\"code\":\"##code##\",\"min\":\"5\"}",
        "SCHEME_NAME": "AlgoWiki",
        "COUNTRY_CODE": "86",
        "CODE_LENGTH": 6,
        "VALID_TIME_SECONDS": 300,
        "INTERVAL_SECONDS": 60,
        "CODE_TYPE": 1,
        "DUPLICATE_POLICY": 1,
        "AUTO_RETRY": 0,
        "RETURN_VERIFY_CODE": False,
        "SMS_UP_EXTEND_CODE": "",
        "OUT_ID_PREFIX": "algowiki",
        "ENDPOINTS": ["dypnsapi.aliyuncs.com"],
        "TIMEOUT_SECONDS": 15,
    },
    PHONE_VERIFICATION_WINDOW_MINUTES=60,
    PHONE_VERIFICATION_MAX_SENDS_PER_WINDOW=5,
    PHONE_VERIFICATION_RESEND_SECONDS=60,
    PHONE_VERIFICATION_MAX_VERIFY_ATTEMPTS=5,
)
class PhoneProviderTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="phone_user",
            email="phone_user@example.com",
            password="Password123",
            role=User.Role.NORMAL,
        )
        self.factory = APIRequestFactory()

    def _request(self):
        request = self.factory.post("/api/phone-verifications/me/")
        request.user = self.user
        request.META["REMOTE_ADDR"] = "127.0.0.1"
        return request

    def _send_response(self):
        return SimpleNamespace(
            body=SimpleNamespace(
                code="200",
                message="OK",
                request_id="req-phone-send",
                success=True,
                model=SimpleNamespace(
                    biz_id="biz-phone-send",
                    out_id="out-phone-send",
                    verify_code="123456",
                ),
            )
        )

    def _check_response(self):
        return SimpleNamespace(
            body=SimpleNamespace(
                code="200",
                message="OK",
                request_id="req-phone-check",
                success=True,
                model=SimpleNamespace(
                    biz_id="biz-phone-send",
                    out_id="out-phone-send",
                    verify_result="PASS",
                ),
            )
        )

    def test_start_phone_verification_persists_pending_record_and_ticket(self):
        with patch(
            "wiki.phone_verification_providers._call_with_failover",
            return_value=self._send_response(),
        ):
            verification, ticket, payload = start_aliyun_phone_verification(
                user=self.user,
                phone_number="13800001234",
                country_code="86",
                request=self._request(),
            )

        self.assertEqual(verification.status, PhoneVerification.Status.PENDING)
        self.assertEqual(verification.phone_masked, "138****1234")
        self.assertEqual(verification.phone_last4, "1234")
        self.assertEqual(verification.provider, "aliyun_pnvs")
        self.assertEqual(verification.provider_out_id, "out-phone-send")
        self.assertEqual(verification.provider_biz_id, "biz-phone-send")
        self.assertEqual(verification.provider_request_id, "req-phone-send")
        self.assertTrue(verification.provider_result["verify_code_returned"])
        self.assertEqual(ticket.phone_masked, "138****1234")
        self.assertEqual(ticket.phone_last4, "1234")
        self.assertTrue(payload["ticket_token"])
        self.assertEqual(payload["masked_phone"], "138****1234")
        self.assertEqual(payload["expires_in_seconds"], 300)
        self.assertEqual(PhoneVerification.objects.count(), 1)
        self.assertEqual(PhoneVerificationTicket.objects.count(), 1)

    def test_check_phone_verification_marks_verified(self):
        with patch(
            "wiki.phone_verification_providers._call_with_failover",
            side_effect=[self._send_response(), self._check_response()],
        ):
            _, ticket, payload = start_aliyun_phone_verification(
                user=self.user,
                phone_number="13800001234",
                country_code="86",
                request=self._request(),
            )
            loaded_ticket = load_phone_ticket_from_token(payload["ticket_token"])
            verification = check_aliyun_phone_verification(
                ticket=loaded_ticket,
                phone_number="13800001234",
                verify_code="123456",
            )

        ticket.refresh_from_db()
        self.assertEqual(loaded_ticket.id, ticket.id)
        self.assertEqual(verification.status, PhoneVerification.Status.VERIFIED)
        self.assertTrue(verification.verified_at)
        self.assertEqual(verification.provider_status_message, "OK")
        self.assertEqual(verification.provider_out_id, "out-phone-send")
        self.assertIsNotNone(ticket.consumed_at)

    def test_start_phone_verification_allows_legacy_verified_record_to_reverify(self):
        country_code, phone_number = normalize_phone_context(
            country_code="86",
            phone_number="13800001234",
        )
        PhoneVerification.objects.create(
            user=self.user,
            status=PhoneVerification.Status.VERIFIED,
            phone_country_code=country_code,
            phone_masked="138****1234",
            phone_last4="1234",
            phone_digest=build_phone_digest(country_code, phone_number),
            verified_at=timezone.now(),
        )

        with patch(
            "wiki.phone_verification_providers._call_with_failover",
            return_value=self._send_response(),
        ) as provider_call:
            verification, ticket, payload = start_aliyun_phone_verification(
                user=self.user,
                phone_number=phone_number,
                country_code=country_code,
                request=self._request(),
            )

        self.assertTrue(provider_call.called)
        self.assertEqual(verification.status, PhoneVerification.Status.PENDING)
        self.assertTrue(ticket)
        self.assertTrue(payload["ticket_token"])

    def test_provider_permission_error_is_actionable(self):
        cfg = {"ENDPOINTS": ["dypnsapi.aliyuncs.com"]}
        with patch(
            "wiki.phone_verification_providers._client",
            side_effect=Exception(
                "Forbidden.NoPermission: You are not authorized to perform this action. "
                "AuthAction: dypns:SendSmsVerifyCode"
            ),
        ):
            with self.assertRaises(PhoneVerificationProviderError) as context:
                _call_with_failover(cfg, "send_sms_verify_code_with_options", object())

        self.assertIn("AliyunDypnsFullAccess", context.exception.message)
        self.assertIn("dypns:CheckSmsVerifyCode", context.exception.message)


class MomentApiTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_user(
            username="moment_admin",
            email="moment_admin@example.com",
            password="Password123",
            role=User.Role.ADMIN,
        )
        self.admin_token = Token.objects.create(user=self.admin)
        self.user = User.objects.create_user(
            username="moment_user",
            email="moment_user@example.com",
            password="Password123",
            role=User.Role.NORMAL,
        )
        self.user_token = Token.objects.create(user=self.user)
        settings_obj = MomentSettings.get_solo()
        settings_obj.is_enabled = True
        settings_obj.publishing_enabled = True
        settings_obj.require_real_name = False
        settings_obj.require_manual_review_for_new_users = True
        settings_obj.new_user_manual_review_count = 3
        settings_obj.save()

    def _image(self):
        return make_test_image_upload("proof.png")

    def upload_captcha(self, token="moment-upload-token"):
        return json.dumps({"scene": "upload_image", "turnstile_token": token})

    def moment_image_payload(self, content, *, token="moment-upload-token"):
        return {
            "content": content,
            "images": [self._image()],
            "captcha": self.upload_captcha(token),
        }

    def test_admin_moment_with_image_runs_ai_and_can_publish(self):
        def publish_side_effect(moment, target_type):
            moment.status = Moment.Status.PUBLISHED
            moment.published_at = timezone.now()
            moment.save(update_fields=["status", "published_at", "updated_at"])
            moment.images.update(status=MomentImage.Status.APPROVED)
            return None

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        with patch("wiki.views.apply_moment_ai_review", side_effect=publish_side_effect) as mocked:
            response = self.client.post(
                "/api/moments/",
                self.moment_image_payload("admin safe post"),
                format="multipart",
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], Moment.Status.PUBLISHED)
        self.assertEqual(mocked.call_count, 1)
        moment = Moment.objects.get(author=self.admin)
        self.assertEqual(moment.status, Moment.Status.PUBLISHED)
        self.assertEqual(moment.images.get().status, MomentImage.Status.APPROVED)

    def test_normal_user_moment_with_image_stays_pending_for_manual_image_review(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.user_token.key}")
        with patch("wiki.views.apply_moment_ai_review") as mocked:
            response = self.client.post(
                "/api/moments/",
                self.moment_image_payload("user image post"),
                format="multipart",
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], Moment.Status.PENDING)
        self.assertEqual(response.data["images"][0]["status"], MomentImage.Status.PENDING)
        self.assertEqual(mocked.call_count, 0)
        moment = Moment.objects.get(author=self.user)
        self.assertEqual(moment.status, Moment.Status.PENDING)

    def test_moment_image_upload_generates_thumbnail_and_public_url(self):
        temp_media_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_media_dir.cleanup)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")

        def publish_side_effect(moment, target_type):
            moment.status = Moment.Status.PUBLISHED
            moment.published_at = timezone.now()
            moment.save(update_fields=["status", "published_at", "updated_at"])
            moment.images.update(status=MomentImage.Status.APPROVED)
            return None

        with override_settings(MEDIA_ROOT=temp_media_dir.name, MEDIA_URL="/media/"):
            with patch("wiki.views.apply_moment_ai_review", side_effect=publish_side_effect):
                response = self.client.post(
                    "/api/moments/",
                    self.moment_image_payload("thumbnail moment"),
                    format="multipart",
                )

        self.assertEqual(response.status_code, 201)
        image_row = response.data["images"][0]
        self.assertIn("thumbnail_url", image_row)
        self.assertTrue(image_row["thumbnail_url"].startswith("/media/"))
        self.assertIn("/media/moments-thumbs/", image_row["thumbnail_url"])
        moment = Moment.objects.get(author=self.admin)
        image = moment.images.get()
        self.assertTrue(image.thumbnail)
        self.assertTrue((Path(temp_media_dir.name) / image.thumbnail.name).exists())
        self.assertTrue((Path(temp_media_dir.name) / image.image.name).exists())

    def test_admin_can_review_moment_images(self):
        temp_media_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_media_dir.cleanup)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.user_token.key}")
        with override_settings(MEDIA_ROOT=temp_media_dir.name, MEDIA_URL="/media/"):
            with patch("wiki.views.apply_moment_ai_review"):
                response = self.client.post(
                    "/api/moments/",
                    self.moment_image_payload("reviewable image"),
                    format="multipart",
                )
        self.assertEqual(response.status_code, 201)
        image_id = response.data["images"][0]["id"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        list_response = self.client.get("/api/moment-images/", {"status": "pending", "search": "reviewable"})
        self.assertEqual(list_response.status_code, 200)
        rows = list_response.data.get("results", list_response.data)
        self.assertTrue(any(item["id"] == image_id for item in rows))

        approve_response = self.client.post(
            f"/api/moment-images/{image_id}/approve/",
            {"review_note": "通过"},
            format="json",
        )
        self.assertEqual(approve_response.status_code, 200)
        self.assertEqual(approve_response.data["status"], MomentImage.Status.APPROVED)
        self.assertEqual(approve_response.data["moderation_summary"], "通过")

    def test_purge_expired_media_removes_moment_image_files(self):
        temp_media_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_media_dir.cleanup)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.user_token.key}")
        with override_settings(MEDIA_ROOT=temp_media_dir.name, MEDIA_URL="/media/"):
            with patch(
                "wiki.views.moderate_image_url",
                return_value=SimpleNamespace(
                    provider="aliyun_green",
                    decision="reject",
                    risk_level="high",
                    categories=["violence"],
                    summary="reject",
                    raw_response={},
                    error_message="",
                ),
            ):
                response = self.client.post(
                    "/api/moments/",
                    self.moment_image_payload("cleanup image"),
                    format="multipart",
                )

        self.assertEqual(response.status_code, 201)
        image = MomentImage.objects.get(pk=response.data["images"][0]["id"])
        image.delete_after = timezone.now() - timedelta(days=1)
        image.save(update_fields=["delete_after", "updated_at"])
        original_path = Path(temp_media_dir.name) / image.image.name
        thumbnail_path = Path(temp_media_dir.name) / image.thumbnail.name
        self.assertTrue(original_path.exists())
        self.assertTrue(thumbnail_path.exists())

        with override_settings(MEDIA_ROOT=temp_media_dir.name, MEDIA_URL="/media/"):
            call_command("purge_expired_media", verbosity=0)

        self.assertFalse(original_path.exists())
        self.assertFalse(thumbnail_path.exists())
        self.assertFalse(MomentImage.objects.filter(pk=image.pk).exists())

    def test_moment_feed_exposes_public_author_avatar(self):
        self.user.avatar_url = "/media/avatars/2/avatar.webp"
        self.user.save(update_fields=["avatar_url"])
        moment = Moment.objects.create(
            author=self.user,
            content="avatar moment",
            status=Moment.Status.PUBLISHED,
            published_at=timezone.now(),
        )
        MomentComment.objects.create(
            moment=moment,
            author=self.user,
            content="avatar comment",
            status=MomentComment.Status.VISIBLE,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.get("/api/moments/")
        self.assertEqual(response.status_code, 200)
        rows = response.data.get("results", response.data)
        row = next(item for item in rows if item["id"] == moment.id)
        self.assertEqual(row["author"]["avatar_url"], "/media/avatars/2/avatar.webp")

        comments_response = self.client.get("/api/moment-comments/", {"moment": moment.id})
        self.assertEqual(comments_response.status_code, 200)
        comment_rows = comments_response.data.get("results", comments_response.data)
        self.assertEqual(comment_rows[0]["author"]["avatar_url"], "/media/avatars/2/avatar.webp")

    def test_resolving_moment_report_deletes_moment_and_comments_with_archives(self):
        moment = Moment.objects.create(
            author=self.user,
            content="reported moment",
            status=Moment.Status.PUBLISHED,
            published_at=timezone.now(),
            comment_count=2,
        )
        first_comment = MomentComment.objects.create(
            moment=moment,
            author=self.user,
            content="first comment",
            status=MomentComment.Status.VISIBLE,
        )
        second_comment = MomentComment.objects.create(
            moment=moment,
            author=self.admin,
            content="second comment",
            status=MomentComment.Status.VISIBLE,
        )
        report = MomentReport.objects.create(
            target_type=MomentReport.TargetType.MOMENT,
            moment=moment,
            reporter=self.admin,
            target_author=self.user,
            reason=MomentReport.Reason.ABUSE,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.post(
            f"/api/moment-reports/{report.id}/resolve/",
            {"resolution_note": "违规删除"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        report.refresh_from_db()
        moment.refresh_from_db()
        first_comment.refresh_from_db()
        second_comment.refresh_from_db()
        self.assertEqual(report.status, MomentReport.Status.RESOLVED)
        self.assertEqual(report.resolution_action, "delete_moment")
        self.assertEqual(moment.status, Moment.Status.DELETED)
        self.assertFalse(moment.is_featured)
        self.assertFalse(moment.allow_hot)
        self.assertEqual(first_comment.status, MomentComment.Status.DELETED)
        self.assertEqual(second_comment.status, MomentComment.Status.DELETED)
        self.assertEqual(
            DeletedContentArchive.objects.filter(
                target_type="Moment", target_id=moment.id
            ).count(),
            1,
        )
        self.assertEqual(
            DeletedContentArchive.objects.filter(
                target_type="MomentComment", target_id__in=[first_comment.id, second_comment.id]
            ).count(),
            2,
        )

    def test_resolving_comment_report_deletes_only_comment(self):
        moment = Moment.objects.create(
            author=self.user,
            content="published moment",
            status=Moment.Status.PUBLISHED,
            published_at=timezone.now(),
        )
        target_comment = MomentComment.objects.create(
            moment=moment,
            author=self.user,
            content="reported comment",
            status=MomentComment.Status.VISIBLE,
        )
        other_comment = MomentComment.objects.create(
            moment=moment,
            author=self.admin,
            content="safe comment",
            status=MomentComment.Status.VISIBLE,
        )
        report = MomentReport.objects.create(
            target_type=MomentReport.TargetType.COMMENT,
            moment=moment,
            comment=target_comment,
            reporter=self.admin,
            target_author=self.user,
            reason=MomentReport.Reason.ABUSE,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.post(f"/api/moment-reports/{report.id}/resolve/")

        self.assertEqual(response.status_code, 200)
        report.refresh_from_db()
        moment.refresh_from_db()
        target_comment.refresh_from_db()
        other_comment.refresh_from_db()
        self.assertEqual(report.status, MomentReport.Status.RESOLVED)
        self.assertEqual(report.resolution_action, "delete_comment")
        self.assertEqual(moment.status, Moment.Status.PUBLISHED)
        self.assertEqual(target_comment.status, MomentComment.Status.DELETED)
        self.assertEqual(other_comment.status, MomentComment.Status.VISIBLE)
        self.assertEqual(moment.comment_count, 1)
        self.assertTrue(
            DeletedContentArchive.objects.filter(
                target_type="MomentComment", target_id=target_comment.id
            ).exists()
        )

    def test_manager_regular_comment_list_only_shows_visible_comments(self):
        moment = Moment.objects.create(
            author=self.user,
            content="published moment",
            status=Moment.Status.PUBLISHED,
            published_at=timezone.now(),
        )
        visible = MomentComment.objects.create(
            moment=moment,
            author=self.user,
            content="visible",
            status=MomentComment.Status.VISIBLE,
        )
        MomentComment.objects.create(
            moment=moment,
            author=self.user,
            content="rejected",
            status=MomentComment.Status.REJECTED,
        )
        MomentComment.objects.create(
            moment=moment,
            author=self.user,
            content="deleted",
            status=MomentComment.Status.DELETED,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        public_response = self.client.get(f"/api/moment-comments/?moment={moment.id}")
        self.assertEqual(public_response.status_code, 200)
        self.assertEqual(public_response.data["count"], 1)
        self.assertEqual(public_response.data["results"][0]["id"], visible.id)

        all_response = self.client.get(
            f"/api/moment-comments/?moment={moment.id}&include_all=1"
        )
        self.assertEqual(all_response.status_code, 200)
        self.assertEqual(all_response.data["count"], 3)

    def test_user_can_filter_own_moments_and_moment_comments_by_id(self):
        moment = Moment.objects.create(
            author=self.user,
            content="mine searchable",
            status=Moment.Status.PUBLISHED,
            published_at=timezone.now(),
        )
        comment = MomentComment.objects.create(
            moment=moment,
            author=self.user,
            content="mine comment",
            status=MomentComment.Status.REJECTED,
        )
        Moment.objects.create(
            author=self.admin,
            content="not mine",
            status=Moment.Status.PUBLISHED,
            published_at=timezone.now(),
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.user_token.key}")
        moment_response = self.client.get(f"/api/moments/?mine=1&search={moment.id}")
        self.assertEqual(moment_response.status_code, 200)
        self.assertEqual(moment_response.data["count"], 1)
        self.assertEqual(moment_response.data["results"][0]["id"], moment.id)

        comment_response = self.client.get(
            f"/api/moment-comments/?mine=1&search={comment.id}"
        )
        self.assertEqual(comment_response.status_code, 200)
        self.assertEqual(comment_response.data["count"], 1)
        self.assertEqual(comment_response.data["results"][0]["id"], comment.id)

    def test_author_can_delete_own_pending_moment_and_rejected_comment(self):
        pending_moment = Moment.objects.create(
            author=self.user,
            content="pending own moment",
            status=Moment.Status.PENDING,
        )
        published_moment = Moment.objects.create(
            author=self.user,
            content="published moment",
            status=Moment.Status.PUBLISHED,
            published_at=timezone.now(),
        )
        rejected_comment = MomentComment.objects.create(
            moment=published_moment,
            author=self.user,
            content="rejected own comment",
            status=MomentComment.Status.REJECTED,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.user_token.key}")
        moment_response = self.client.delete(f"/api/moments/{pending_moment.id}/")
        comment_response = self.client.delete(f"/api/moment-comments/{rejected_comment.id}/")

        self.assertEqual(moment_response.status_code, 204)
        self.assertEqual(comment_response.status_code, 204)
        self.assertEqual(self.client.get(f"/api/moments/{pending_moment.id}/").status_code, 404)
        self.assertEqual(
            self.client.get(f"/api/moment-comments/{rejected_comment.id}/").status_code,
            404,
        )
        pending_moment.refresh_from_db()
        rejected_comment.refresh_from_db()
        self.assertEqual(pending_moment.status, Moment.Status.DELETED)
        self.assertEqual(rejected_comment.status, MomentComment.Status.DELETED)
        self.assertTrue(
            DeletedContentArchive.objects.filter(
                target_type="Moment", target_id=pending_moment.id
            ).exists()
        )
        self.assertTrue(
            DeletedContentArchive.objects.filter(
                target_type="MomentComment", target_id=rejected_comment.id
            ).exists()
        )

    def test_author_cannot_retrieve_comment_when_parent_moment_is_deleted(self):
        moment = Moment.objects.create(
            author=self.user,
            content="deleted parent",
            status=Moment.Status.PUBLISHED,
            published_at=timezone.now(),
        )
        comment = MomentComment.objects.create(
            moment=moment,
            author=self.user,
            content="visible but parent deleted",
            status=MomentComment.Status.VISIBLE,
        )
        Moment.objects.filter(id=moment.id).update(
            status=Moment.Status.DELETED,
            deleted_at=timezone.now(),
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.user_token.key}")
        response = self.client.get(f"/api/moment-comments/{comment.id}/")
        self.assertEqual(response.status_code, 404)
