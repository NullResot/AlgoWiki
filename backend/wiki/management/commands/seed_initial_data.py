import os
import secrets
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from wiki.models import Announcement, Article, Category, ExtensionPage, User
from wiki.security import record_password_history

LEGACY_CATEGORY_SLUGS = [
    "language-basics",
    "data-structures",
    "graph",
    "dynamic-programming",
    "math",
    "string",
    "contest-zone",
    "icpc",
    "ccpc",
    "experience",
]

INSECURE_PLACEHOLDER_PASSWORDS = {
    "",
    "changeme123!",
    "replace-me",
    "replace-with-a-random-password",
    "<set-a-strong-superadmin-password>",
}


def resolve_seed_password(candidate: str, *, prefix: str) -> str:
    value = (candidate or "").strip()
    if value.lower() in INSECURE_PLACEHOLDER_PASSWORDS:
        return f"{prefix}{secrets.token_urlsafe(12)}!"
    return value


class Command(BaseCommand):
    help = "Seed initial categories, extension pages, super admin account, and starter content."

    def add_arguments(self, parser):
        parser.add_argument("--content-file", type=str, default="")
        parser.add_argument(
            "--skip-markdown-section-import",
            action="store_true",
            help="Only use content file for welcome article, skip sectionized markdown import.",
        )
        parser.add_argument(
            "--section-levels",
            type=str,
            default="3,2",
            help="Heading levels used by import_markdown_sections, comma-separated (default: 3,2).",
        )
        parser.add_argument(
            "--section-default-category",
            type=str,
            default="xcpc-preface",
            help="Fallback category slug for markdown section import.",
        )
        parser.add_argument(
            "--superadmin-username",
            type=str,
            default=os.getenv("SUPERADMIN_USERNAME", "superadmin"),
        )
        parser.add_argument(
            "--superadmin-password",
            type=str,
            default=os.getenv("SUPERADMIN_PASSWORD", ""),
        )
        parser.add_argument(
            "--superadmin-email",
            type=str,
            default=os.getenv("SUPERADMIN_EMAIL", "admin@example.com"),
        )
        parser.add_argument(
            "--reset-superadmin-password",
            action="store_true",
            help="Reset super admin password even when the account already exists.",
        )
        parser.add_argument(
            "--skip-demo-users",
            action="store_true",
            help="Skip creating demo role accounts (normal/school/admin).",
        )
        parser.add_argument(
            "--demo-password",
            type=str,
            default=os.getenv("DEMO_PASSWORD", ""),
            help="Password used by demo role accounts.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        superadmin_username = options["superadmin_username"]
        superadmin_password = resolve_seed_password(
            options["superadmin_password"],
            prefix="AlgoWiki-SuperAdmin-",
        )
        superadmin_email = options["superadmin_email"]
        reset_password = options["reset_superadmin_password"]

        superadmin, created = User.objects.get_or_create(
            username=superadmin_username,
            defaults={
                "email": superadmin_email,
                "role": User.Role.SUPERADMIN,
                "is_staff": True,
                "is_superuser": True,
            },
        )

        if created or reset_password:
            superadmin.set_password(superadmin_password)
            if created:
                superadmin.save()
                self.stdout.write(self.style.SUCCESS(f"Created super admin: {superadmin_username}"))
            else:
                superadmin.save(update_fields=["password"])
                self.stdout.write(self.style.SUCCESS(f"Reset super admin password: {superadmin_username}"))
            record_password_history(superadmin)
        else:
            updated_fields = []
            if superadmin.role != User.Role.SUPERADMIN:
                superadmin.role = User.Role.SUPERADMIN
                updated_fields.append("role")
            if not superadmin.is_staff:
                superadmin.is_staff = True
                updated_fields.append("is_staff")
            if not superadmin.is_superuser:
                superadmin.is_superuser = True
                updated_fields.append("is_superuser")
            if superadmin.email != superadmin_email:
                superadmin.email = superadmin_email
                updated_fields.append("email")
            if updated_fields:
                superadmin.save(update_fields=updated_fields)

        category_defs = [
            ("0. 阅前须知", "xcpc-preface", None, Category.ModerationScope.PUBLIC, 10, True),
            ("1. 学术诚信", "xcpc-academic-integrity", None, Category.ModerationScope.PUBLIC, 20, True),
            ("2. 常见术语", "xcpc-common-terms", None, Category.ModerationScope.PUBLIC, 30, True),
            ("3. 竞赛概念", "xcpc-concepts", None, Category.ModerationScope.PUBLIC, 40, True),
            ("4. 比赛介绍", "xcpc-contests", None, Category.ModerationScope.SCHOOL, 50, True),
            ("5. 关键网站", "xcpc-sites", None, Category.ModerationScope.PUBLIC, 60, True),
            ("6. 代码工具", "xcpc-tools", None, Category.ModerationScope.PUBLIC, 70, True),
            ("7. 阶段任务", "xcpc-stages", None, Category.ModerationScope.PUBLIC, 80, True),
            ("8. 关于训练", "xcpc-training", None, Category.ModerationScope.PUBLIC, 90, True),
            ("9. 结语与致谢", "xcpc-closing", None, Category.ModerationScope.PUBLIC, 100, True),
            ("Getting Started", "getting-started", None, Category.ModerationScope.PUBLIC, 1000, False),
        ]

        categories = {}
        for name, slug, parent_slug, scope, order, is_visible in category_defs:
            parent = categories.get(parent_slug) if parent_slug else None
            category, _ = Category.objects.update_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "parent": parent,
                    "moderation_scope": scope,
                    "order": order,
                    "is_visible": is_visible,
                },
            )
            categories[slug] = category

        Category.objects.filter(slug__in=LEGACY_CATEGORY_SLUGS).update(is_visible=False)

        ExtensionPage.objects.update_or_create(
            slug="about",
            defaults={
                "title": "关于 AlgoWiki",
                "description": "项目介绍与路线图。",
                "content_md": "# 关于 AlgoWiki\n\nAlgoWiki 是一个面向程序设计竞赛学习者的结构化知识库与社区协作平台。",
                "access_level": ExtensionPage.AccessLevel.PUBLIC,
                "is_enabled": True,
            },
        )
        ExtensionPage.objects.update_or_create(
            slug="labs",
            defaults={
                "title": "实验室",
                "description": "预留给后续交互工具与训练辅助功能。",
                "content_md": "# 实验室\n\n该页面保留用于后续功能扩展。",
                "access_level": ExtensionPage.AccessLevel.PUBLIC,
                "is_enabled": True,
            },
        )
        ExtensionPage.objects.update_or_create(
            slug="operations",
            defaults={
                "title": "运维面板",
                "description": "仅管理员可访问的扩展页。",
                "content_md": "# 运维面板\n\n该页面保留用于后续内部运维工具。",
                "access_level": ExtensionPage.AccessLevel.ADMIN,
                "is_enabled": True,
            },
        )

        Announcement.objects.update_or_create(
            title="欢迎来到 AlgoWiki",
            defaults={
                "content_md": "站点已上线，可浏览知识条目、提交修订、发起问答与工单协作。",
                "created_by": superadmin,
                "priority": 100,
                "is_published": True,
            },
        )

        content = self._load_content(options["content_file"])
        Article.objects.update_or_create(
            slug="welcome",
            defaults={
                "title": "欢迎来到 AlgoWiki",
                "summary": "项目概览与使用说明。",
                "content_md": content,
                "category": categories["xcpc-preface"],
                "author": superadmin,
                "last_editor": superadmin,
                "status": Article.Status.PUBLISHED,
                "is_featured": True,
            },
        )

        if options["content_file"] and not options["skip_markdown_section_import"]:
            self._import_markdown_sections(
                content_file=options["content_file"],
                author=superadmin_username,
                default_category=options["section_default_category"],
                section_levels=options["section_levels"],
            )

        demo_accounts = []
        if not options["skip_demo_users"]:
            demo_accounts = self._ensure_demo_users(
                resolve_seed_password(options["demo_password"], prefix="AlgoWiki-Demo-")
            )

        self.stdout.write(self.style.SUCCESS("Initial data has been seeded."))
        self.stdout.write(
            self.style.WARNING(
                f"Super admin credential -> username: {superadmin_username}, password: {superadmin_password}"
            )
        )
        if demo_accounts:
            self.stdout.write(self.style.WARNING("Demo credentials (for role testing):"))
            for account in demo_accounts:
                self.stdout.write(
                    self.style.WARNING(
                        f"- {account['username']} ({account['role']}): {account['password']}"
                    )
                )

    def _load_content(self, content_file: str) -> str:
        default_content = (
            "# AlgoWiki\n\n"
            "AlgoWiki 是一个面向算法竞赛学习者的结构化知识库与社区协作平台。\n\n"
            "- 浏览分类条目并系统学习\n"
            "- 提交 issue/request 与修订提议\n"
            "- 在问答区讨论训练问题\n"
            "- 在个人中心追踪贡献历史\n"
        )

        if not content_file:
            return default_content

        source_path = Path(content_file)
        if not source_path.exists():
            self.stdout.write(self.style.WARNING(f"Content file not found: {source_path}"))
            return default_content

        for encoding in ("utf-8", "utf-8-sig", "gb18030"):
            try:
                return source_path.read_text(encoding=encoding)
            except UnicodeDecodeError:
                continue

        self.stdout.write(self.style.WARNING("Could not decode content file, using fallback content."))
        return default_content

    def _import_markdown_sections(
        self,
        *,
        content_file: str,
        author: str,
        default_category: str,
        section_levels: str,
    ) -> None:
        source_path = Path(content_file)
        if not source_path.exists():
            self.stdout.write(self.style.WARNING(f"Section import skipped, content file not found: {source_path}"))
            return

        levels = []
        for item in str(section_levels).split(","):
            token = item.strip()
            if not token:
                continue
            try:
                level = int(token)
            except ValueError:
                self.stdout.write(self.style.WARNING(f"Ignore invalid section level: {token}"))
                continue
            if 1 <= level <= 6 and level not in levels:
                levels.append(level)
            else:
                self.stdout.write(self.style.WARNING(f"Ignore unsupported section level: {token}"))

        if not levels:
            self.stdout.write(self.style.WARNING("Section import skipped, no valid heading levels configured."))
            return

        for level in levels:
            self.stdout.write(
                f"Import markdown sections: level={level}, default_category={default_category}, author={author}"
            )
            call_command(
                "import_markdown_sections",
                file=str(source_path),
                author=author,
                default_category=default_category,
                split_level=level,
            )

    def _ensure_demo_users(self, default_password: str):
        demo_specs = [
            {
                "username": os.getenv("DEMO_NORMAL_USERNAME", "demo_normal"),
                "email": os.getenv("DEMO_NORMAL_EMAIL", "demo_normal@example.com"),
                "role": User.Role.NORMAL,
                "school_name": "Demo University",
                "is_staff": False,
                "is_superuser": False,
            },
            {
                "username": os.getenv("DEMO_SCHOOL_USERNAME", "demo_school"),
                "email": os.getenv("DEMO_SCHOOL_EMAIL", "demo_school@example.com"),
                "role": User.Role.SCHOOL,
                "school_name": "Demo University",
                "is_staff": False,
                "is_superuser": False,
            },
            {
                "username": os.getenv("DEMO_ADMIN_USERNAME", "demo_admin"),
                "email": os.getenv("DEMO_ADMIN_EMAIL", "demo_admin@example.com"),
                "role": User.Role.ADMIN,
                "school_name": "Demo University",
                "is_staff": True,
                "is_superuser": False,
            },
        ]

        created_accounts = []
        for spec in demo_specs:
            user, created = User.objects.get_or_create(
                username=spec["username"],
                defaults={
                    "email": spec["email"],
                    "role": spec["role"],
                    "school_name": spec["school_name"],
                    "is_staff": spec["is_staff"],
                    "is_superuser": spec["is_superuser"],
                },
            )

            update_fields = []
            if user.email != spec["email"]:
                user.email = spec["email"]
                update_fields.append("email")
            if user.role != spec["role"]:
                user.role = spec["role"]
                update_fields.append("role")
            if user.school_name != spec["school_name"]:
                user.school_name = spec["school_name"]
                update_fields.append("school_name")
            if user.is_staff != spec["is_staff"]:
                user.is_staff = spec["is_staff"]
                update_fields.append("is_staff")
            if user.is_superuser != spec["is_superuser"]:
                user.is_superuser = spec["is_superuser"]
                update_fields.append("is_superuser")
            if user.is_banned:
                user.is_banned = False
                user.banned_reason = ""
                user.banned_at = None
                update_fields.append("is_banned")
                update_fields.append("banned_reason")
                update_fields.append("banned_at")
            if not user.is_active:
                user.is_active = True
                update_fields.append("is_active")

            user.set_password(default_password)
            update_fields.append("password")

            if created:
                user.save()
            else:
                user.save(update_fields=sorted(set(update_fields)))
            record_password_history(user)

            created_accounts.append(
                {
                    "username": spec["username"],
                    "role": spec["role"],
                    "password": default_password,
                }
            )

        return created_accounts
