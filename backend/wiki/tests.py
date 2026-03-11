import tempfile
from datetime import timedelta
from pathlib import Path

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
    ContributionEvent,
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


class AuthApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="login_user",
            email="login_user@example.com",
            password="Password123",
            role=User.Role.NORMAL,
        )

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

    def test_register_creates_password_history_and_security_log(self):
        response = self.client.post(
            "/api/auth/register/",
            {"username": "new_user", "email": "new_user@example.com", "password": "StrongPass123!"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(username="new_user")
        self.assertTrue(PasswordHistory.objects.filter(user=user).exists())
        self.assertTrue(
            SecurityAuditLog.objects.filter(
                event_type=SecurityAuditLog.EventType.REGISTER_SUCCESS,
                user=user,
                success=True,
            ).exists()
        )

    def test_register_rejects_duplicate_email(self):
        response = self.client.post(
            "/api/auth/register/",
            {"username": "new_user2", "email": "LOGIN_USER@example.com", "password": "StrongPass123!"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.data)

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


class ImageUploadApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="upload_user",
            password="Password123",
            role=User.Role.NORMAL,
        )
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        self.temp_media_dir = tempfile.TemporaryDirectory()
        self.override = override_settings(MEDIA_ROOT=self.temp_media_dir.name, MEDIA_URL="/media/")
        self.override.enable()

    def tearDown(self):
        self.override.disable()
        self.temp_media_dir.cleanup()

    def test_authenticated_user_can_upload_image(self):
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

    def test_school_user_can_approve_revision_in_school_scope(self):
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
        self.assertEqual(response.status_code, 200)
        proposal.refresh_from_db()
        article.refresh_from_db()
        self.assertEqual(proposal.status, RevisionProposal.Status.APPROVED)
        self.assertEqual(article.title, "Contest Article Updated")

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

    def test_questions_list_mine_filter(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.author_token.key}")
        response = self.client.get("/api/questions/", {"mine": "1"})
        self.assertEqual(response.status_code, 200)
        ids = {item["id"] for item in response.data.get("results", response.data)}
        self.assertEqual(ids, {self.question.id})

    def test_manager_can_filter_questions_by_author(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.get("/api/questions/", {"author": self.author.username})
        self.assertEqual(response.status_code, 200)
        ids = {item["id"] for item in response.data.get("results", response.data)}
        self.assertEqual(ids, {self.question.id})


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


class ProfileAndMineEndpointsTests(APITestCase):
    def setUp(self):
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
        self.assertEqual(response.data["profile_settings"]["school_name"], "Algo University")
        self.user.refresh_from_db()
        self.assertEqual(self.user.school_name, "Algo University")
        self.assertEqual(self.user.bio, "Competitive programming learner")
        self.assertEqual(self.user.avatar_url, "https://example.com/avatar.png")

    def test_get_me_contains_profile_settings(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        response = self.client.get("/api/me/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("profile_settings", response.data)
        self.assertEqual(response.data["profile_settings"]["email"], "student@example.com")

    def test_patch_me_rejects_duplicate_email(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        response = self.client.patch(
            "/api/me/",
            {"email": "OTHER@example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.data)

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

    def test_change_password_rotates_token_and_accepts_new_password(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        response = self.client.post(
            "/api/me/change-password/",
            {
                "old_password": "Password123",
                "new_password": "Password456",
                "confirm_password": "Password456",
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
            "/api/me/change-password/",
            {
                "old_password": "WrongPassword",
                "new_password": "Password456",
                "confirm_password": "Password456",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_change_password_rejects_recent_password_reuse(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        first_change = self.client.post(
            "/api/me/change-password/",
            {
                "old_password": "Password123",
                "new_password": "ReuseStrongPass1!",
                "confirm_password": "ReuseStrongPass1!",
            },
            format="json",
        )
        self.assertEqual(first_change.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {first_change.data['token']}")

        second_change = self.client.post(
            "/api/me/change-password/",
            {
                "old_password": "ReuseStrongPass1!",
                "new_password": "ReuseStrongPass2!",
                "confirm_password": "ReuseStrongPass2!",
            },
            format="json",
        )
        self.assertEqual(second_change.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {second_change.data['token']}")

        third_change = self.client.post(
            "/api/me/change-password/",
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

    def test_school_assignee_can_handle_assigned_ticket_but_cannot_reassign(self):
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
        self.assertEqual(update_response.status_code, 200)
        self.ticket_assigned.refresh_from_db()
        self.assertEqual(self.ticket_assigned.status, IssueTicket.Status.IN_PROGRESS)
        self.assertEqual(self.ticket_assigned.resolution_note, "started")

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
        response = self.client.patch(
            f"/api/issues/{self.ticket_assigned.id}/",
            {"title": "updated by author"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.ticket_assigned.refresh_from_db()
        self.assertEqual(self.ticket_assigned.title, "updated by author")

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

    def test_bulk_set_status_for_school_user_cannot_reassign(self):
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
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["success"], 0)
        self.assertEqual(response.data["failed"], 1)
        self.assertIn("Only admins can change assignee.", response.data["results"][0]["detail"])

        self.ticket_assigned.refresh_from_db()
        self.assertNotEqual(self.ticket_assigned.status, IssueTicket.Status.RESOLVED)


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

    def test_school_bulk_review_only_handles_school_scope_proposals(self):
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
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["success"], 1)
        self.assertEqual(response.data["failed"], 1)

        self.public_proposal.refresh_from_db()
        self.school_proposal.refresh_from_db()
        self.assertEqual(self.public_proposal.status, RevisionProposal.Status.PENDING)
        self.assertEqual(self.school_proposal.status, RevisionProposal.Status.REJECTED)

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

    def test_answer_create_notifies_question_author(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.responder_token.key}")
        response = self.client.post(
            "/api/answers/",
            {"question": self.question.id, "content_md": "new answer"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            UserNotification.objects.filter(
                user=self.author,
                title__contains="新回答",
                target_type="Answer",
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

    def test_normal_user_cannot_manage_team_member(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.normal_token.key}")
        response = self.client.get("/api/team-members/mine/")
        self.assertEqual(response.status_code, 403)
