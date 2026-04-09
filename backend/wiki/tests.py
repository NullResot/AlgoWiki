import json
import re
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase
from django.utils import timezone

from .models import (
    Announcement,
    Answer,
    Article,
    ArticleComment,
    Category,
    CompetitionCalendarEvent,
    CompetitionNotice,
    CompetitionPracticeLink,
    CompetitionPracticeLinkProposal,
    CompetitionScheduleEntry,
    ContributionEvent,
    EmailVerificationTicket,
    FriendlyLink,
    IssueTicket,
    Question,
    RevisionProposal,
    SecurityAuditLog,
    TeamMember,
    TrickEntry,
    PasswordHistory,
    UserNotification,
    LoginAttempt,
    User,
)
from .competition_calendar import NormalizedCompetitionEvent


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

    def fetch_register_challenge(self):
        response = self.client.get("/api/auth/register-challenge/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("prompt", response.data)
        self.assertIn("token", response.data)
        return response.data

    def solve_register_challenge(self):
        challenge = self.fetch_register_challenge()
        match = re.search(r"(\d+)\s*([+\-x])\s*(\d+)", challenge["prompt"])
        self.assertIsNotNone(match)
        left = int(match.group(1))
        operator = match.group(2)
        right = int(match.group(3))
        if operator == "+":
            answer = left + right
        elif operator == "-":
            answer = left - right
        else:
            answer = left * right
        return {
            "captcha_token": challenge["token"],
            "captcha_answer": str(answer),
        }

    def extract_code_from_last_email(self):
        self.assertTrue(mail.outbox)
        message = mail.outbox[-1]
        match = re.search(r"验证码[:：]\s*(\d+)", message.body)
        self.assertIsNotNone(match)
        return match.group(1)

    def test_login_returns_serialized_user_payload(self):
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
        self.assertTrue(
            SecurityAuditLog.objects.filter(
                event_type=SecurityAuditLog.EventType.LOGIN_SUCCESS,
                username="login_user",
                success=True,
            ).exists()
        )

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

    def test_register_code_and_complete_registration(self):
        captcha_payload = self.solve_register_challenge()
        request_response = self.client.post(
            "/api/auth/register-email-code/",
            {
                "username": "new_user",
                "email": "new_user@example.com",
                "password": "StrongPass123!",
                "school_name": "Algo University",
                **captcha_payload,
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

    def test_register_rejects_duplicate_email(self):
        captcha_payload = self.solve_register_challenge()
        response = self.client.post(
            "/api/auth/register-email-code/",
            {
                "username": "new_user2",
                "email": "LOGIN_USER@example.com",
                "password": "StrongPass123!",
                **captcha_payload,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.data)

    def test_register_rejects_invalid_captcha_answer(self):
        challenge = self.fetch_register_challenge()
        response = self.client.post(
            "/api/auth/register-email-code/",
            {
                "username": "captcha_fail_user",
                "email": "captcha_fail_user@example.com",
                "password": "StrongPass123!",
                "captcha_token": challenge["token"],
                "captcha_answer": "99999",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("captcha_answer", response.data)

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
        self.assertEqual(response.headers.get("X-Request-ID"), response.data["request_id"])


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


class CostControlApiTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.category = Category.objects.create(name="Cost Control", slug="cost-control")
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
        article_markdown = self.client.get(f"/api/articles/{self.article.id}/export-markdown-bundle/")
        collection_pdf = self.client.get("/api/articles/export-collection-pdf/")
        collection_markdown = self.client.get("/api/articles/export-collection-markdown-bundle/")

        for response in (article_pdf, article_markdown, collection_pdf, collection_markdown):
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

        self.assertEqual([response.status_code for response in responses[:3]], [200, 200, 200])
        self.assertEqual(responses[3].status_code, 429)

    def test_question_submission_is_rate_limited(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.user_token.key}")

        responses = [
            self.client.post(
                "/api/questions/",
                {"title": f"Q{index}", "content_md": "body", "category": self.category.id},
                format="json",
            )
            for index in range(1, 5)
        ]

        self.assertEqual([response.status_code for response in responses[:3]], [201, 201, 201])
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

        self.assertEqual([response.status_code for response in responses[:3]], [200, 200, 200])
        self.assertEqual(responses[3].status_code, 429)


class ImageUploadApiTests(APITestCase):
    def setUp(self):
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
        self.override = override_settings(MEDIA_ROOT=self.temp_media_dir.name, MEDIA_URL="/media/")
        self.override.enable()

    def tearDown(self):
        self.override.disable()
        self.temp_media_dir.cleanup()

    def test_normal_user_cannot_upload_image(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.user_token.key}")
        image_bytes = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00"
            b"\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01\xe5'\xd4"
            b"\xa2\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        upload = SimpleUploadedFile("tiny.png", image_bytes, content_type="image/png")
        response = self.client.post("/api/uploads/image/", {"image": upload}, format="multipart")
        self.assertEqual(response.status_code, 403)
        self.assertIn("Only admins can upload images", response.data["detail"])

    def test_admin_user_can_upload_image(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        image_bytes = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00"
            b"\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01\xe5'\xd4"
            b"\xa2\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        upload = SimpleUploadedFile("tiny.png", image_bytes, content_type="image/png")
        response = self.client.post("/api/uploads/image/", {"image": upload}, format="multipart")
        self.assertEqual(response.status_code, 201)
        self.assertIn("url", response.data)
        self.assertIn("/media/wiki-uploads/", response.data["url"])
        self.assertIn("markdown", response.data)
        self.assertTrue(response.data["markdown"].startswith("![tiny]("))

        stored = Path(self.temp_media_dir.name) / response.data["path"]
        self.assertTrue(stored.exists())

    def test_upload_rejects_non_image_extension(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        bad_file = SimpleUploadedFile("notes.txt", b"not-image", content_type="text/plain")
        response = self.client.post("/api/uploads/image/", {"image": bad_file}, format="multipart")
        self.assertEqual(response.status_code, 400)
        self.assertIn("image", response.data)


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
        self.assertEqual(response.headers.get("X-Request-ID"), response.data["request_id"])

    def test_health_endpoint_uses_client_request_id_header(self):
        response = self.client.get("/api/health/", HTTP_X_REQUEST_ID="manual-health-check")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["request_id"], "manual-health-check")
        self.assertEqual(response.headers.get("X-Request-ID"), "manual-health-check")

    def test_frontend_dist_is_served_when_enabled(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            dist_dir = Path(temp_dir)
            (dist_dir / "index.html").write_text("<html><body>algowiki frontend</body></html>", encoding="utf-8")
            (dist_dir / "assets").mkdir()
            (dist_dir / "assets" / "app.js").write_text("console.log('algowiki');", encoding="utf-8")

            with override_settings(SERVE_FRONTEND=True, FRONTEND_DIST_DIR=str(dist_dir)):
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
            self.assertEqual(item["event_type"], SecurityAuditLog.EventType.LOGIN_FAILED)
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
        self.assertEqual(items[0]["event_type"], SecurityAuditLog.EventType.LOGIN_FAILED)

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
        tmp_file = tempfile.NamedTemporaryFile("w", suffix=".md", encoding="utf-8", delete=False)
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

        self.assertTrue(TeamMember.objects.filter(display_id="Null_Resot", is_active=True).exists())
        self.assertGreaterEqual(FriendlyLink.objects.filter(is_enabled=True).count(), 6)
        self.assertGreaterEqual(CompetitionNotice.objects.filter(is_visible=True).count(), 4)
        self.assertGreaterEqual(CompetitionScheduleEntry.objects.count(), 4)
        self.assertGreaterEqual(
            TrickEntry.objects.filter(status=TrickEntry.Status.APPROVED).count(),
            2,
        )

    def test_seed_xcpc_reference_content_syncs_bundled_snapshot_and_prunes_stale_articles(self):
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

        self.normal_user = User.objects.create_user(username="normal", password="Password123", role=User.Role.NORMAL)
        self.school_user = User.objects.create_user(username="school", password="Password123", role=User.Role.SCHOOL)
        self.admin_user = User.objects.create_user(username="admin", password="Password123", role=User.Role.ADMIN)

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
        self.user = User.objects.create_user(username="u1", password="Password123", role=User.Role.NORMAL)
        self.token = Token.objects.create(user=self.user)
        self.author = User.objects.create_user(username="author", password="Password123", role=User.Role.ADMIN)
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
        ids = {item["id"] for item in response_starred.data.get("results", response_starred.data)}
        self.assertEqual(ids, set())

    def test_starred_endpoint_returns_only_current_user_collection(self):
        other_user = User.objects.create_user(username="u2", password="Password123", role=User.Role.NORMAL)
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
        other_ids = {item["id"] for item in other_response.data.get("results", other_response.data)}
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
        search_ids = {item["id"] for item in search_response.data.get("results", search_response.data)}
        self.assertEqual(search_ids, {self.article2.id})

        category_response = self.client.get("/api/articles/starred/", {"category": self.category.slug})
        self.assertEqual(category_response.status_code, 200)
        category_ids = {item["id"] for item in category_response.data.get("results", category_response.data)}
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
        self.creator = User.objects.create_user(username="creator", password="Password123", role=User.Role.ADMIN)
        self.alice = User.objects.create_user(username="alice", password="Password123", role=User.Role.NORMAL)
        self.bob = User.objects.create_user(username="bob", password="Password123", role=User.Role.NORMAL)
        self.reviewer = User.objects.create_user(username="reviewer", password="Password123", role=User.Role.ADMIN)

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
        self.assertEqual([item["user"]["username"] for item in contributors], ["creator", "alice", "bob"])

        def parse_api_datetime(value):
            return timezone.datetime.fromisoformat(str(value).replace("Z", "+00:00"))

        def assert_api_datetime_equal(serialized_value, expected):
            parsed = parse_api_datetime(serialized_value)
            self.assertEqual(parsed, expected.astimezone(parsed.tzinfo))

        creator_payload = contributors[0]
        self.assertTrue(creator_payload["is_creator"])
        self.assertEqual(creator_payload["approved_revision_count"], 0)
        assert_api_datetime_equal(creator_payload["first_contributed_at"], self.creator_time)
        assert_api_datetime_equal(creator_payload["last_contributed_at"], self.creator_time)

        alice_payload = contributors[1]
        self.assertFalse(alice_payload["is_creator"])
        self.assertEqual(alice_payload["approved_revision_count"], 2)
        assert_api_datetime_equal(alice_payload["first_contributed_at"], self.alice_first_time)
        assert_api_datetime_equal(alice_payload["last_contributed_at"], self.alice_second_time)

        bob_payload = contributors[2]
        self.assertFalse(bob_payload["is_creator"])
        self.assertEqual(bob_payload["approved_revision_count"], 1)
        assert_api_datetime_equal(bob_payload["first_contributed_at"], self.bob_approved_time)
        assert_api_datetime_equal(bob_payload["last_contributed_at"], self.bob_approved_time)


class QuestionSecurityTests(APITestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Basic", slug="basic")
        self.author = User.objects.create_user(username="author2", password="Password123", role=User.Role.NORMAL)
        self.other = User.objects.create_user(username="other2", password="Password123", role=User.Role.NORMAL)
        self.admin = User.objects.create_user(username="admin_q", password="Password123", role=User.Role.ADMIN)
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

    def test_owner_delete_hides_question(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.author_token.key}")
        response = self.client.delete(f"/api/questions/{self.question.id}/")
        self.assertEqual(response.status_code, 204)
        self.question.refresh_from_db()
        self.assertEqual(self.question.status, Question.Status.HIDDEN)

        list_response = self.client.get("/api/questions/")
        list_ids = {item["id"] for item in list_response.data.get("results", list_response.data)}
        self.assertNotIn(self.question.id, list_ids)

        mine_response = self.client.get("/api/questions/", {"mine": "1"})
        mine_ids = {item["id"] for item in mine_response.data.get("results", mine_response.data)}
        self.assertNotIn(self.question.id, mine_ids)

        deleted_response = self.client.get("/api/questions/", {"mine": "1", "status": Question.Status.HIDDEN})
        deleted_ids = {item["id"] for item in deleted_response.data.get("results", deleted_response.data)}
        self.assertIn(self.question.id, deleted_ids)

    def test_owner_can_restore_hidden_question_back_to_pending(self):
        self.question.status = Question.Status.HIDDEN
        self.question.save(update_fields=["status", "updated_at"])

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.author_token.key}")
        response = self.client.post(f"/api/questions/{self.question.id}/restore/", format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], Question.Status.PENDING)

        self.question.refresh_from_db()
        self.assertEqual(self.question.status, Question.Status.PENDING)

    def test_hidden_question_archive_keeps_latest_thirty_for_owner(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.author_token.key}")

        Question.objects.filter(id=self.question.id).update(status=Question.Status.HIDDEN)
        for index in range(35):
            Question.objects.create(
                title=f"Hidden {index}",
                content_md="archived",
                author=self.author,
                category=self.category,
                status=Question.Status.HIDDEN,
            )

        response = self.client.get("/api/questions/", {"mine": "1", "status": Question.Status.HIDDEN})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 30)
        items = list(response.data.get("results", response.data))
        if response.data.get("next"):
            page2 = self.client.get("/api/questions/", {"mine": "1", "status": Question.Status.HIDDEN, "page": 2})
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

    def test_manager_default_question_list_hides_hidden_questions_but_allows_hidden_filter(self):
        self.question.status = Question.Status.HIDDEN
        self.question.save(update_fields=["status", "updated_at"])

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")

        default_response = self.client.get("/api/questions/")
        default_ids = {item["id"] for item in default_response.data.get("results", default_response.data)}
        self.assertNotIn(self.question.id, default_ids)

        hidden_response = self.client.get("/api/questions/", {"status": Question.Status.HIDDEN})
        hidden_ids = {item["id"] for item in hidden_response.data.get("results", hidden_response.data)}
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
            {"title": "Pending question", "content_md": "please review", "category": self.category.id},
            format="json",
        )
        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(create_response.data["status"], Question.Status.PENDING)
        question_id = create_response.data["id"]

        self.client.credentials()
        public_response = self.client.get("/api/questions/")
        public_ids = {item["id"] for item in public_response.data.get("results", public_response.data)}
        self.assertNotIn(question_id, public_ids)

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.author_token.key}")
        own_response = self.client.get("/api/questions/")
        own_ids = {item["id"] for item in own_response.data.get("results", own_response.data)}
        self.assertIn(question_id, own_ids)

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        approve_response = self.client.post(f"/api/questions/{question_id}/approve/", format="json")
        self.assertEqual(approve_response.status_code, 200)

        self.client.credentials()
        visible_response = self.client.get("/api/questions/")
        visible_ids = {item["id"] for item in visible_response.data.get("results", visible_response.data)}
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
        public_ids = {item["id"] for item in public_response.data.get("results", public_response.data)}
        self.assertNotIn(self.question.id, public_ids)


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
        public_response = self.client.get("/api/answers/", {"question": self.question.id})
        public_ids = {item["id"] for item in public_response.data.get("results", public_response.data)}
        self.assertNotIn(answer_id, public_ids)

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.responder_token.key}")
        owner_response = self.client.get("/api/answers/", {"question": self.question.id})
        owner_ids = {item["id"] for item in owner_response.data.get("results", owner_response.data)}
        self.assertIn(answer_id, owner_ids)

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        approve_response = self.client.post(f"/api/answers/{answer_id}/approve/", format="json")
        self.assertEqual(approve_response.status_code, 200)

        self.client.credentials()
        visible_response = self.client.get("/api/answers/", {"question": self.question.id})
        visible_ids = {item["id"] for item in visible_response.data.get("results", visible_response.data)}
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
        public_response = self.client.get("/api/answers/", {"question": self.question.id})
        public_ids = {item["id"] for item in public_response.data.get("results", public_response.data)}
        self.assertNotIn(self.answer.id, public_ids)


class ArticleCommentFlowTests(APITestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Comment", slug="comment")
        self.author = User.objects.create_user(username="article_author", password="Password123", role=User.Role.ADMIN)
        self.author_token = Token.objects.create(user=self.author)
        self.user = User.objects.create_user(username="comment_user", password="Password123", role=User.Role.NORMAL)
        self.other = User.objects.create_user(username="comment_other", password="Password123", role=User.Role.NORMAL)
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
        public_list_response = self.client.get("/api/comments/", {"article": self.article_a.id})
        self.assertEqual(public_list_response.status_code, 200)
        public_ids = {item["id"] for item in public_list_response.data.get("results", public_list_response.data)}
        self.assertNotIn(pending_id, public_ids)

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        owner_list_response = self.client.get("/api/comments/", {"article": self.article_a.id})
        self.assertEqual(owner_list_response.status_code, 200)
        owner_ids = {item["id"] for item in owner_list_response.data.get("results", owner_list_response.data)}
        self.assertIn(pending_id, owner_ids)

    def test_admin_can_approve_pending_comment(self):
        pending = ArticleComment.objects.create(
            article=self.article_a,
            author=self.user,
            content="pending for approve",
            status=ArticleComment.Status.PENDING,
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.author_token.key}")
        response = self.client.post(f"/api/comments/{pending.id}/approve/", {"review_note": "ok"}, format="json")
        self.assertEqual(response.status_code, 200)
        pending.refresh_from_db()
        self.assertEqual(pending.status, ArticleComment.Status.VISIBLE)

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
        public_response = self.client.get("/api/comments/", {"article": self.article_a.id})
        public_ids = {item["id"] for item in public_response.data.get("results", public_response.data)}
        self.assertNotIn(self.parent.id, public_ids)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
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

    def request_and_confirm_password_change(self, *, token: str, old_password: str, new_password: str):
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
                "school_name": "Algo University",
                "bio": "Competitive programming learner",
                "avatar_url": "https://example.com/avatar.png",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("profile_settings", response.data)
        self.assertEqual(response.data["user"]["school_name"], "Algo University")
        self.assertEqual(response.data["user"]["bio"], "Competitive programming learner")
        self.assertEqual(response.data["user"]["avatar_url"], "https://example.com/avatar.png")
        self.assertEqual(response.data["profile_settings"]["school_name"], "Algo University")
        self.user.refresh_from_db()
        self.assertEqual(self.user.school_name, "Algo University")
        self.assertEqual(self.user.bio, "Competitive programming learner")
        self.assertEqual(self.user.avatar_url, "https://example.com/avatar.png")

    def test_get_me_contains_profile_settings(self):
        self.user.school_name = "Algo University"
        self.user.bio = "Competitive programming learner"
        self.user.avatar_url = "https://example.com/avatar.png"
        self.user.save(update_fields=["school_name", "bio", "avatar_url"])
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        response = self.client.get("/api/me/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["user"]["school_name"], "Algo University")
        self.assertEqual(response.data["user"]["bio"], "Competitive programming learner")
        self.assertEqual(response.data["user"]["avatar_url"], "https://example.com/avatar.png")
        self.assertIn("profile_settings", response.data)
        self.assertEqual(response.data["profile_settings"]["email"], "student@example.com")
        self.assertFalse(response.data["profile_settings"]["email_verified"])

    def test_public_question_author_profile_fields_are_hidden(self):
        self.other.school_name = "Hidden University"
        self.other.bio = "Should stay private"
        self.other.avatar_url = "https://example.com/hidden.png"
        self.other.save(update_fields=["school_name", "bio", "avatar_url"])

        response = self.client.get("/api/questions/")
        self.assertEqual(response.status_code, 200)
        items = response.data.get("results", response.data)
        question_payload = next(item for item in items if item["id"] == self.other_question.id)

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
        default_ids = {item["id"] for item in default_response.data.get("results", default_response.data)}
        self.assertNotIn(self.my_question.id, default_ids)

        hidden_response = self.client.get("/api/questions/mine/", {"status": Question.Status.HIDDEN})
        hidden_ids = {item["id"] for item in hidden_response.data.get("results", hidden_response.data)}
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
        self.assertGreaterEqual(PasswordHistory.objects.filter(user=self.user).count(), 2)

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
        self.assertFalse(RevisionProposal.objects.filter(id=self.my_revision.id).exists())

    def test_user_cannot_cancel_non_pending_revision(self):
        self.my_revision.status = RevisionProposal.Status.REJECTED
        self.my_revision.save(update_fields=["status", "updated_at"])
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        response = self.client.delete(f"/api/revisions/{self.my_revision.id}/")
        self.assertEqual(response.status_code, 400)
        self.assertTrue(RevisionProposal.objects.filter(id=self.my_revision.id).exists())

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
        self.assertEqual(self.revision_article.content_md, "content after clearing summary")
        self.assertEqual(self.revision_article.last_editor_id, admin.id)


class TrickEntryFlowTests(APITestCase):
    def setUp(self):
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

        self.approved = TrickEntry.objects.create(
            title="??? trick",
            content_md="?? `x & -x` ???? lowbit?",
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

    def test_public_list_only_returns_approved_entries(self):
        response = self.client.get("/api/tricks/")
        self.assertEqual(response.status_code, 200)
        items = response.data.get("results", response.data)
        ids = {item["id"] for item in items}
        self.assertIn(self.approved.id, ids)
        self.assertNotIn(self.pending.id, ids)
        self.assertNotIn(self.rejected.id, ids)

    def test_authenticated_author_can_see_own_pending_entries(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        response = self.client.get("/api/tricks/")
        self.assertEqual(response.status_code, 200)
        items = response.data.get("results", response.data)
        ids = {item["id"] for item in items}
        self.assertIn(self.approved.id, ids)
        self.assertIn(self.pending.id, ids)
        self.assertNotIn(self.rejected.id, ids)

    def test_authenticated_user_can_create_trick_entry_with_pending_status(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        response = self.client.post(
            "/api/tricks/",
            {
                "content_md": "sample trick\\n\\n![img](/wiki-assets/debug.png)",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["author"]["username"], self.user.username)
        self.assertEqual(response.data["status"], TrickEntry.Status.PENDING)
        self.assertTrue(response.data["title"])

    def test_admin_can_create_trick_entry_with_approved_status(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.post(
            "/api/tricks/",
            {
                "content_md": "admin trick content",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], TrickEntry.Status.APPROVED)
        self.assertEqual(response.data["author"]["username"], self.admin.username)

    def test_author_can_update_and_delete_own_entry(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        update_response = self.client.patch(
            f"/api/tricks/{self.approved.id}/",
            {"content_md": "??????????"},
            format="json",
        )
        self.assertEqual(update_response.status_code, 200)
        self.approved.refresh_from_db()
        self.assertEqual(self.approved.status, TrickEntry.Status.PENDING)

        delete_response = self.client.delete(f"/api/tricks/{self.pending.id}/")
        self.assertEqual(delete_response.status_code, 204)

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

    def test_admin_default_list_hides_rejected_entries(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.get("/api/tricks/")
        self.assertEqual(response.status_code, 200)
        items = response.data.get("results", response.data)
        ids = {item["id"] for item in items}
        self.assertIn(self.approved.id, ids)
        self.assertIn(self.pending.id, ids)
        self.assertNotIn(self.rejected.id, ids)

    def test_admin_can_filter_pending_entries(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.get("/api/tricks/", {"include_all": 1, "status": TrickEntry.Status.PENDING})
        self.assertEqual(response.status_code, 200)
        items = response.data.get("results", response.data)
        ids = {item["id"] for item in items}
        self.assertIn(self.pending.id, ids)
        self.assertNotIn(self.approved.id, ids)
        self.assertNotIn(self.rejected.id, ids)


class IssueTicketAdminTests(APITestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Ops", slug="ops")
        self.admin = User.objects.create_user(username="ticket_admin", password="Password123", role=User.Role.ADMIN)
        self.admin_token = Token.objects.create(user=self.admin)

        self.author_a = User.objects.create_user(username="ticket_author_a", password="Password123", role=User.Role.NORMAL)
        self.author_b = User.objects.create_user(username="ticket_author_b", password="Password123", role=User.Role.NORMAL)
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
        list_ids = {item["id"] for item in list_response.data.get("results", list_response.data)}
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
        visible_ids = {item["id"] for item in visible_response.data.get("results", visible_response.data)}
        self.assertIn(pending_id, visible_ids)

    def test_admin_can_filter_tickets_by_author_assignee(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.get(
            "/api/issues/",
            {"author": self.author_a.username, "assignee": self.school_assignee.id, "order": "created_oldest"},
        )
        self.assertEqual(response.status_code, 200)
        ids = {item["id"] for item in response.data.get("results", response.data)}
        self.assertEqual(ids, {self.ticket_assigned.id})

        unassigned_response = self.client.get("/api/issues/", {"assignee": "none"})
        self.assertEqual(unassigned_response.status_code, 200)
        unassigned_ids = {item["id"] for item in unassigned_response.data.get("results", unassigned_response.data)}
        self.assertIn(self.ticket_unassigned.id, unassigned_ids)
        self.assertNotIn(self.ticket_assigned.id, unassigned_ids)

    def test_set_status_supports_assign_and_clear(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")

        assign_response = self.client.post(
            f"/api/issues/{self.ticket_unassigned.id}/set_status/",
            {"status": "in_progress", "assign_to": self.school_assignee.id, "resolution_note": "accepted"},
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
        list_ids = {item["id"] for item in list_response.data.get("results", list_response.data)}
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
        self.assertFalse(IssueTicket.objects.filter(id=self.ticket_assigned.id).exists())

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
        own_ids = {item["id"] for item in own_response.data.get("results", own_response.data)}
        self.assertIn(private_ticket.id, own_ids)

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.author_b_token.key}")
        other_response = self.client.get("/api/issues/", {"scope": "all"})
        other_ids = {item["id"] for item in other_response.data.get("results", other_response.data)}
        self.assertNotIn(private_ticket.id, other_ids)

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        admin_response = self.client.get("/api/issues/", {"visibility": IssueTicket.Visibility.PRIVATE})
        admin_ids = {item["id"] for item in admin_response.data.get("results", admin_response.data)}
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
        self.assertTrue(all(item["visibility"] == IssueTicket.Visibility.PRIVATE for item in items))

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
            {"status": IssueTicket.Status.IN_PROGRESS, "assign_to": self.school_assignee.id},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Private tickets can only be handled by admins.", str(response.data))

    def test_author_cannot_switch_assigned_school_ticket_to_private(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.author_a_token.key}")
        response = self.client.patch(
            f"/api/issues/{self.ticket_assigned.id}/",
            {"visibility": IssueTicket.Visibility.PRIVATE},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.ticket_assigned.refresh_from_db()
        self.assertEqual(self.ticket_assigned.visibility, IssueTicket.Visibility.PRIVATE)
        self.assertEqual(self.ticket_assigned.status, IssueTicket.Status.PENDING)
        self.assertIsNone(self.ticket_assigned.assignee_id)


class CompetitionPracticeLinkApiTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="practice_admin", password="Password123", role=User.Role.ADMIN)
        self.proposer = User.objects.create_user(username="practice_user", password="Password123", role=User.Role.NORMAL)
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
            practice_links=[{"label": "GYM", "url": "https://codeforces.com/gym/104787"}],
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
        self.assertEqual(items[0]["practice_links_text"], "QOJ https://qoj.ac/contest/1797")

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
        self.assertEqual(response.data["status"], CompetitionPracticeLinkProposal.Status.PENDING)
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
        self.assertEqual(proposal.status, CompetitionPracticeLinkProposal.Status.APPROVED)
        self.assertEqual(self.entry.short_name, "网络预选赛(I)")
        self.assertEqual(len(self.entry.practice_links), 2)
        self.assertTrue(
            UserNotification.objects.filter(
                user=self.proposer,
                target_type="CompetitionPracticeLinkProposal",
                target_id=proposal.id,
            ).exists()
        )

    def test_admin_can_remove_entry(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.delete(f"/api/competition-practice-links/{self.entry.id}/remove/")
        self.assertEqual(response.status_code, 204)
        self.assertFalse(CompetitionPracticeLink.objects.filter(id=self.entry.id).exists())

    def test_normal_user_cannot_remove_entry(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.proposer_token.key}")
        response = self.client.delete(f"/api/competition-practice-links/{self.entry.id}/remove/")
        self.assertEqual(response.status_code, 403)
        self.assertTrue(CompetitionPracticeLink.objects.filter(id=self.entry.id).exists())

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
                "practice_links": [{"label": "GYM", "url": "https://codeforces.com/gym/123456"}],
                "practice_links_note": "",
                "source_file": "01 - 省赛与邀请赛.md",
                "source_section": "测试赛季",
                "display_order": 9,
            }
        ]
        tmp_file = tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False)
        try:
            json.dump(snapshot, tmp_file, ensure_ascii=False)
            tmp_file.close()
            call_command("import_competition_practice_links", snapshot=tmp_file.name, replace_missing=True)
            self.assertTrue(CompetitionPracticeLink.objects.filter(source_key="manual-import-1").exists())
        finally:
            Path(tmp_file.name).unlink(missing_ok=True)


class UserManagementRecoveryTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="recover_admin", password="Password123", role=User.Role.ADMIN)
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
        self.category = Category.objects.create(name="Recover Category", slug="recover-category")
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

    def test_admin_cannot_reactivate_super_admin(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.post(f"/api/users/{self.super_admin_target.id}/reactivate/")
        self.assertEqual(response.status_code, 403)

    def test_super_admin_can_reactivate_super_admin(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.super_admin_token.key}")
        response = self.client.post(f"/api/users/{self.super_admin_target.id}/reactivate/")
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
        self.assertTrue(
            SecurityAuditLog.objects.filter(
                event_type=SecurityAuditLog.EventType.USER_HARD_DELETED,
                username="recover_normal",
                success=True,
            ).exists()
        )

        recreated = User.objects.create_user(username="recover_normal", password="Password123", role=User.Role.NORMAL)
        self.assertIsNotNone(recreated.id)

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
                "ids": [self.admin.id, self.super_admin_target.id, self.normal_active.id],
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

    def test_admin_bulk_set_role_is_forbidden(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.post(
            "/api/users/bulk-action/",
            {"ids": [self.normal_active.id], "action": "set_role", "role": "admin"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_super_admin_bulk_set_role_succeeds(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.super_admin_token.key}")
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
        self.client.post(f"/api/users/{self.normal_active.id}/ban/", {"reason": "temp"}, format="json")

        response = self.client.post(f"/api/users/{self.normal_active.id}/unban/", format="json")
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
        self.client.post("/api/users/bulk-action/", {"ids": [self.normal_active.id], "action": "ban"}, format="json")

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
        self.author = User.objects.create_user(username="author3", password="Password123", role=User.Role.ADMIN)
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

class AdminOverviewAndEventTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="admin4", password="Password123", role=User.Role.ADMIN)
        self.normal = User.objects.create_user(username="normal4", password="Password123", role=User.Role.NORMAL)
        self.admin_token = Token.objects.create(user=self.admin)
        self.normal_token = Token.objects.create(user=self.normal)

    def test_admin_overview_permission_and_payload(self):
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
        ContributionEvent.objects.filter(id=old_event.id).update(created_at=timezone.now() - timezone.timedelta(days=3))

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

        export_response = self.client.get("/api/events/export/", {"event_type": "admin"})
        self.assertEqual(export_response.status_code, 200)
        self.assertIn("text/csv", export_response["Content-Type"])
        content = export_response.content.decode("utf-8")
        self.assertIn("event_type", content)
        self.assertIn("admin", content)


class RevisionFilterTests(APITestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Filter", slug="filter")
        self.admin = User.objects.create_user(username="admin5", password="Password123", role=User.Role.ADMIN)
        self.user_a = User.objects.create_user(username="user_a", password="Password123", role=User.Role.NORMAL)
        self.user_b = User.objects.create_user(username="user_b", password="Password123", role=User.Role.NORMAL)
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
        response = self.client.get("/api/revisions/", {"proposer": self.user_a.id, "status": "pending"})
        self.assertEqual(response.status_code, 200)
        ids = {item["id"] for item in response.data.get("results", response.data)}
        self.assertEqual(ids, {self.proposal_a.id})


class RevisionBulkReviewTests(APITestCase):
    def setUp(self):
        self.public_category = Category.objects.create(name="Public Rev", slug="public-rev")
        self.school_category = Category.objects.create(
            name="School Rev",
            slug="school-rev",
            moderation_scope=Category.ModerationScope.SCHOOL,
        )

        self.admin = User.objects.create_user(username="bulk_rev_admin", password="Password123", role=User.Role.ADMIN)
        self.school = User.objects.create_user(username="bulk_rev_school", password="Password123", role=User.Role.SCHOOL)
        self.normal = User.objects.create_user(username="bulk_rev_normal", password="Password123", role=User.Role.NORMAL)
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
        self.public_proposal.proposed_content_md = "new public content with cleared summary"
        self.public_proposal.save(update_fields=["proposed_summary", "proposed_content_md", "updated_at"])

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
        self.assertEqual(self.public_article.content_md, "new public content with cleared summary")

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


class ContentBulkModerationTests(APITestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Bulk Content", slug="bulk-content")
        self.admin = User.objects.create_user(username="bulk_content_admin", password="Password123", role=User.Role.ADMIN)
        self.admin_token = Token.objects.create(user=self.admin)
        self.normal = User.objects.create_user(username="bulk_content_normal", password="Password123", role=User.Role.NORMAL)
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
        self.assertFalse(Article.objects.filter(id__in=[self.article_a.id, self.article_b.id]).exists())

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


class AnnouncementFlowTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="announce_admin", password="Password123", role=User.Role.ADMIN)
        self.admin_token = Token.objects.create(user=self.admin)
        self.user = User.objects.create_user(username="announce_user", password="Password123", role=User.Role.NORMAL)
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

        ack_response = self.client.post(f"/api/announcements/{self.announcement.id}/acknowledge/")
        self.assertEqual(ack_response.status_code, 200)

        unread_after = self.client.get("/api/announcements/unread/")
        ids_after = {item["id"] for item in unread_after.data}
        self.assertNotIn(self.announcement.id, ids_after)

    def test_published_history_is_public_and_includes_published_records(self):
        response = self.client.get("/api/announcements/published-history/", {"limit": 20})
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


class NotificationFlowTests(APITestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Notify", slug="notify")
        self.admin = User.objects.create_user(username="notify_admin", password="Password123", role=User.Role.ADMIN)
        self.school = User.objects.create_user(username="notify_school", password="Password123", role=User.Role.SCHOOL)
        self.author = User.objects.create_user(username="notify_author", password="Password123", role=User.Role.NORMAL)
        self.responder = User.objects.create_user(username="notify_responder", password="Password123", role=User.Role.NORMAL)

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
        self.assertFalse(UserNotification.objects.filter(user=self.author, target_type="Answer").exists())

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
        one = UserNotification.objects.create(user=self.author, title="n1", content="c1")
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

        self.assertTrue(UserNotification.objects.filter(user=active_user, title__contains="新公告").exists())
        self.assertFalse(UserNotification.objects.filter(user=inactive_user, title__contains="新公告").exists())
        self.assertFalse(UserNotification.objects.filter(user=banned_user, title__contains="新公告").exists())
        self.assertFalse(UserNotification.objects.filter(user=self.admin, title__contains="新公告").exists())


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
        response = self.client.get("/api/competition-calendar/", {"sites": "codeforces,luogu"})
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
        self.school_token = Token.objects.create(user=self.school)
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

    def test_school_user_can_patch_schedule_with_blank_fields_and_clear_announcement(self):
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

    def test_school_user_can_patch_schedule_without_announcement_field_when_entry_is_unlinked(self):
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
            call_command("sync_competition_calendar", sites="codeforces", future_days=30, past_days=30)

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
            call_command("sync_competition_calendar", sites="codeforces", future_days=30, past_days=30)

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
