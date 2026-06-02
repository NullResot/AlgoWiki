from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from wiki.models import (
    Announcement,
    Answer,
    Article,
    ArticleComment,
    AssistantProviderConfig,
    Category,
    CompetitionCalendarEvent,
    CompetitionNotice,
    CompetitionPracticeLink,
    CompetitionPracticeLinkProposal,
    CompetitionScheduleEntry,
    CompetitionZoneSection,
    DeletedContentArchive,
    DocumentPageSection,
    ExtensionPage,
    FriendlyLink,
    HeaderNavigationItem,
    IssueTicket,
    Question,
    RevisionProposal,
    SecurityAuditLog,
    SiteVisitDailyStat,
    TeamMember,
    TrickContributionEvent,
    TrickEntry,
    TrickEntryDownvote,
    TrickEntryLike,
    TrickTerm,
    User,
    UserNotification,
)
from wiki.trick_terms import FIXED_TRICK_TERM_DEFINITIONS


DEMO_PREFIX = "demo"


class Command(BaseCommand):
    help = "Seed non-production demo data for develop/test visual checks."

    def add_arguments(self, parser):
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Required confirmation flag.",
        )
        parser.add_argument(
            "--allow-non-test",
            action="store_true",
            help="Allow seeding a database whose name does not look like test/dev/demo.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        self._guard(options)

        now = timezone.now()
        today = timezone.localdate()
        year = today.year
        users = self._seed_users()
        terms = self._seed_trick_terms()
        categories = self._seed_wiki_content(users, now)

        self._seed_navigation()
        self._seed_documents()
        self._seed_competition_sections()
        notices = self._seed_competition_notices(users, year, now)
        self._seed_competition_schedules(users, notices, today)
        self._seed_competition_calendar(today)
        self._seed_practice_links(users, year, today, now)
        tricks = self._seed_tricks(users, terms)
        self._seed_trick_votes_and_scores(users, tricks)
        if getattr(settings, "QA_MODULE_ENABLED", False):
            self._seed_questions(users, categories, now)
        self._seed_home_and_links(users, now)
        self._seed_admin_visible_data(users, tricks, now, today)
        self._seed_ai_assistant(users)

        self.stdout.write(self.style.SUCCESS("Demo data has been seeded safely."))

    def _guard(self, options):
        if not options["yes"]:
            raise CommandError("Refuse to run without --yes.")

        db_name = str(settings.DATABASES["default"].get("NAME") or "").lower()
        looks_safe = any(token in db_name for token in ("test", "dev", "demo"))
        if settings.DEBUG or looks_safe or options["allow_non_test"]:
            return
        raise CommandError(
            "Refuse to seed a non-debug database whose name does not contain "
            "test/dev/demo. Pass --allow-non-test only when you are certain."
        )

    def _seed_users(self):
        specs = [
            ("demo_admin", User.Role.ADMIN, "Demo Admin", 80),
            ("demo_writer", User.Role.NORMAL, "Demo Writer", 36),
            ("demo_solver", User.Role.NORMAL, "Demo Solver", 18),
            ("demo_school", User.Role.SCHOOL, "Demo University", 52),
            ("demo_voter_a", User.Role.NORMAL, "Demo Voter A", 65),
            ("demo_voter_b", User.Role.NORMAL, "Demo Voter B", 62),
            ("demo_voter_c", User.Role.NORMAL, "Demo Voter C", 58),
        ]
        users = {}
        for username, role, school_name, score in specs:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": f"{username}@example.test",
                    "role": role,
                    "school_name": school_name,
                    "is_staff": role in {User.Role.ADMIN, User.Role.SUPERADMIN},
                    "is_superuser": False,
                    "trick_contribution_score": score,
                },
            )
            update_fields = []
            expected_email = f"{username}@example.test"
            if user.email != expected_email:
                user.email = expected_email
                update_fields.append("email")
            if user.role != role:
                user.role = role
                update_fields.append("role")
            if user.school_name != school_name:
                user.school_name = school_name
                update_fields.append("school_name")
            expected_staff = role in {User.Role.ADMIN, User.Role.SUPERADMIN}
            if user.is_staff != expected_staff:
                user.is_staff = expected_staff
                update_fields.append("is_staff")
            if user.trick_contribution_score < score:
                user.trick_contribution_score = score
                update_fields.append("trick_contribution_score")
            if not user.is_active:
                user.is_active = True
                update_fields.append("is_active")
            if created or not user.has_usable_password():
                user.set_unusable_password()
                update_fields.append("password")
            if update_fields:
                user.save(update_fields=sorted(set(update_fields)))
            users[username] = user
        return users

    def _seed_trick_terms(self):
        terms = {}
        for item in FIXED_TRICK_TERM_DEFINITIONS:
            term, _ = TrickTerm.objects.update_or_create(
                slug=item["slug"],
                defaults={
                    "name": item["name"],
                    "description": f"{item['name']} 相关测试分类",
                    "is_active": True,
                    "is_builtin": True,
                },
            )
            terms[item["name"]] = term
        return terms

    def _seed_navigation(self):
        nav_specs = [
            (HeaderNavigationItem.NavKey.HOME, "首页", 10),
            (HeaderNavigationItem.NavKey.COMPETITION_WIKI, "竞赛Wiki", 20),
            (HeaderNavigationItem.NavKey.COMPETITIONS, "赛事专区", 30),
            (HeaderNavigationItem.NavKey.ABOUT, "文档", 40),
            (HeaderNavigationItem.NavKey.FRIENDLY_LINKS, "友链", 50),
        ]
        if getattr(settings, "QA_MODULE_ENABLED", False):
            nav_specs.insert(3, (HeaderNavigationItem.NavKey.QUESTIONS, "问答", 35))
        for key, title, order in nav_specs:
            HeaderNavigationItem.objects.update_or_create(
                key=key,
                defaults={
                    "title": title,
                    "display_order": order,
                    "is_visible": True,
                },
            )

    def _seed_documents(self):
        page_specs = [
            (
                "about",
                "关于 AlgoWiki",
                "用于测试文档页 Markdown 与 LaTeX 渲染。",
                "# 关于 AlgoWiki\n\n这是测试环境的展示内容。\n\n- 支持 **Markdown**\n- 支持行内公式 $ a^2 + b^2 = c^2 $\n- 支持块级公式\n\n$$\n\\sum_{i=1}^{n} i = \\frac{n(n+1)}{2}\n$$\n",
                "关于AlgoWiki",
                10,
            ),
            (
                "trick-guide",
                "Trick 规范手册",
                "用于测试 Trick 提交规范文档。",
                "# Trick 规范手册\n\n提交 Trick 时请写清楚适用条件、结论和例题链接。\n\n示例：`[例题](https://example.com)`。\n",
                "trick 规范手册",
                20,
            ),
            (
                "trick-regulation",
                "Trick 页面贡献值与投票规则",
                "用于测试贡献值规则文档。",
                "# Trick 页面贡献值与投票规则\n\n测试环境规则摘要：通过审核加分，点赞增加贡献值，点踩触发删除审核。\n",
                "Trick 页面贡献值与投票规则",
                25,
            ),
            (
                "announcement-guide",
                "赛事公告手册",
                "用于测试公告填写说明。",
                "# 赛事公告手册\n\n公告建议包含比赛名称、比赛时间、承办方、邀请函链接、中文题面情况和特殊说明。\n",
                "公告手册",
                30,
            ),
            (
                "admin-guide",
                "管理员手册",
                "用于测试管理员说明文档。",
                "# 管理员手册\n\n测试数据包含待审核、已通过、已驳回、删除归档和日志入口。\n",
                "管理员手册",
                40,
            ),
            (
                "demo-docs",
                "测试文档子页面",
                "专门用于 develop/test 环境的额外文档页。",
                "# 测试文档子页面\n\n这个页面用于检查文档页面管理中的新增、排序、隐藏和删除效果。\n",
                "测试文档子页面",
                50,
            ),
        ]
        for slug, title, desc, content, section_title, order in page_specs:
            page, created = ExtensionPage.objects.get_or_create(
                slug=slug,
                defaults={
                    "title": title,
                    "description": desc,
                    "content_md": content,
                    "access_level": ExtensionPage.AccessLevel.PUBLIC,
                    "is_enabled": True,
                },
            )
            page_updates = []
            if not page.title:
                page.title = title
                page_updates.append("title")
            if not page.description:
                page.description = desc
                page_updates.append("description")
            if created or not str(page.content_md or "").strip():
                page.content_md = content
                page_updates.append("content_md")
            if page.access_level != ExtensionPage.AccessLevel.PUBLIC:
                page.access_level = ExtensionPage.AccessLevel.PUBLIC
                page_updates.append("access_level")
            if not page.is_enabled:
                page.is_enabled = True
                page_updates.append("is_enabled")
            if page_updates:
                page.save(update_fields=sorted(set(page_updates + ["updated_at"])))

            DocumentPageSection.objects.update_or_create(
                key=slug,
                defaults={
                    "title": section_title,
                    "page": page,
                    "display_order": order,
                    "is_visible": True,
                },
            )

    def _seed_competition_sections(self):
        specs = [
            ("calendar", "常规赛", CompetitionZoneSection.BuiltinView.CALENDAR, 1),
            ("tricks", "trick技巧", CompetitionZoneSection.BuiltinView.TRICKS, 2),
            ("schedule", "锦标赛", CompetitionZoneSection.BuiltinView.SCHEDULE, 3),
            ("notice", "赛事公告", CompetitionZoneSection.BuiltinView.NOTICE, 4),
            ("practice", "补题链接", CompetitionZoneSection.BuiltinView.PRACTICE, 5),
        ]
        for key, title, builtin_view, order in specs:
            CompetitionZoneSection.objects.update_or_create(
                key=key,
                defaults={
                    "title": title,
                    "target_type": CompetitionZoneSection.TargetType.BUILTIN,
                    "builtin_view": builtin_view,
                    "page": None,
                    "display_order": order,
                    "is_visible": True,
                },
            )

        page, _ = ExtensionPage.objects.get_or_create(
            slug="competition-zone-demo-note",
            defaults={
                "title": "赛事专区测试说明",
                "description": "用于测试赛事专区自定义子页面。",
                "content_md": "# 赛事专区测试说明\n\n这是一个自定义子页面，用来检查赛事专区菜单管理效果。",
                "access_level": ExtensionPage.AccessLevel.PUBLIC,
                "is_enabled": True,
            },
        )
        CompetitionZoneSection.objects.update_or_create(
            key="demo-note",
            defaults={
                "title": "测试说明",
                "target_type": CompetitionZoneSection.TargetType.PAGE,
                "builtin_view": "",
                "page": page,
                "display_order": 6,
                "is_visible": True,
            },
        )

    def _seed_wiki_content(self, users, now):
        root, _ = Category.objects.update_or_create(
            slug="demo-wiki",
            defaults={
                "name": "测试内容展示",
                "description": "develop/test 环境用的竞赛 Wiki 测试目录。",
                "parent": None,
                "order": 900,
                "moderation_scope": Category.ModerationScope.PUBLIC,
                "is_visible": True,
            },
        )
        child, _ = Category.objects.update_or_create(
            slug="demo-wiki-training",
            defaults={
                "name": "测试训练路径",
                "description": "用于测试二级目录与文章跳转。",
                "parent": root,
                "order": 910,
                "moderation_scope": Category.ModerationScope.PUBLIC,
                "is_visible": True,
            },
        )
        article_specs = [
            (
                "demo-xcpc-overview",
                "测试条目：算法竞赛入门概览",
                root,
                "用于检查 Wiki 列表、目录、标题跳转和 LaTeX。",
                "# 测试条目：算法竞赛入门概览\n\n这是一篇测试文章，用于观察竞赛 Wiki 页面展示效果。\n\n## 赛制\n\nICPC 常见为团队赛，蓝桥杯常见为 OI 赛制。\n\n## 公式测试\n\n$ f(n) = f(n-1) + f(n-2) $\n",
                10,
            ),
            (
                "demo-training-route",
                "测试条目：训练路线示例",
                child,
                "用于检查二级目录下文章展示。",
                "# 测试条目：训练路线示例\n\n1. 先补语言基础。\n2. 再练数据结构与图论。\n3. 最后通过模拟赛复盘。\n\n## 例题链接\n\n[示例题目](https://example.com/problem/demo)\n",
                20,
            ),
        ]
        articles = {}
        for slug, title, category, summary, content, order in article_specs:
            article, _ = Article.objects.update_or_create(
                slug=slug,
                defaults={
                    "title": title,
                    "summary": summary,
                    "content_md": content,
                    "category": category,
                    "display_order": order,
                    "author": users["demo_writer"],
                    "last_editor": users["demo_admin"],
                    "status": Article.Status.PUBLISHED,
                    "is_featured": slug == "demo-xcpc-overview",
                    "published_at": now,
                },
            )
            articles[slug] = article

        RevisionProposal.objects.update_or_create(
            article=articles["demo-xcpc-overview"],
            proposer=users["demo_solver"],
            proposed_title="测试审核：补充蓝桥杯说明",
            defaults={
                "base_title": articles["demo-xcpc-overview"].title,
                "base_summary": articles["demo-xcpc-overview"].summary,
                "base_content_md": articles["demo-xcpc-overview"].content_md,
                "base_updated_at": articles["demo-xcpc-overview"].updated_at,
                "proposed_summary": "增加一段关于蓝桥杯 OI 赛制的说明。",
                "proposed_content_md": articles["demo-xcpc-overview"].content_md
                + "\n\n## 测试修订\n\n蓝桥杯通常按 OI 赛制组织，提交后以最终得分排名。\n",
                "reason": "测试修订审核队列。",
                "status": RevisionProposal.Status.PENDING,
            },
        )
        ArticleComment.objects.update_or_create(
            article=articles["demo-xcpc-overview"],
            author=users["demo_solver"],
            content="这是一条等待审核的测试评论，用于检查评论审核入口。",
            defaults={"status": ArticleComment.Status.PENDING},
        )
        IssueTicket.objects.update_or_create(
            title="测试工单：希望补充更多训练路线",
            author=users["demo_solver"],
            defaults={
                "kind": IssueTicket.Kind.REQUEST,
                "content": "这是一个公开测试工单，用于检查审核和处理流程。",
                "related_article": articles["demo-training-route"],
                "visibility": IssueTicket.Visibility.PUBLIC,
                "status": IssueTicket.Status.PENDING,
            },
        )
        return {"root": root, "child": child, "articles": articles}

    def _seed_competition_notices(self, users, year, now):
        notice_specs = [
            (
                "测试公告：ICPC 区域赛报名提醒",
                CompetitionNotice.Series.ICPC,
                CompetitionNotice.Stage.REGIONAL,
                CompetitionNotice.Status.APPROVED,
                True,
                "# 测试公告：ICPC 区域赛报名提醒\n\n比赛名称：测试 ICPC 区域赛\n\n比赛时间：{year} 年 11 月 16 日\n\n是否有中文：是\n\n其他特殊说明：这是测试环境数据。",
            ),
            (
                "测试公告：CCPC 邀请赛信息汇总",
                CompetitionNotice.Series.CCPC,
                CompetitionNotice.Stage.INVITATIONAL,
                CompetitionNotice.Status.APPROVED,
                True,
                "# 测试公告：CCPC 邀请赛信息汇总\n\n承办方学校：测试大学\n\n邀请函链接：[测试邀请函](https://example.com/ccpc-demo)\n\n是否有外榜：否",
            ),
            (
                "待审核公告：蓝桥杯省赛补充说明",
                CompetitionNotice.Series.LANQIAO,
                CompetitionNotice.Stage.PROVINCIAL,
                CompetitionNotice.Status.PENDING,
                False,
                "# 待审核公告：蓝桥杯省赛补充说明\n\n这条公告用于检查赛事公告审核入口。",
            ),
            (
                "已驳回公告：缺少必要信息示例",
                CompetitionNotice.Series.ICPC,
                CompetitionNotice.Stage.GENERAL,
                CompetitionNotice.Status.REJECTED,
                False,
                "# 已驳回公告：缺少必要信息示例\n\n这条公告用于检查已驳回记录和追加批注。",
            ),
        ]
        notices = {}
        for title, series, stage, status, visible, template in notice_specs:
            notice, _ = CompetitionNotice.objects.update_or_create(
                title=title,
                defaults={
                    "content_md": template.format(year=year),
                    "series": series,
                    "year": year,
                    "stage": stage,
                    "created_by": users["demo_school"],
                    "updated_by": users["demo_admin"],
                    "is_visible": visible,
                    "status": status,
                    "reviewer": (
                        users["demo_admin"]
                        if status != CompetitionNotice.Status.PENDING
                        else None
                    ),
                    "review_note": (
                        "测试驳回批注：请补充比赛时间和邀请函。"
                        if status == CompetitionNotice.Status.REJECTED
                        else ""
                    ),
                    "reviewed_at": (
                        now if status != CompetitionNotice.Status.PENDING else None
                    ),
                    "published_at": now - timedelta(days=2),
                },
            )
            notices[title] = notice
        return notices

    def _seed_competition_schedules(self, users, notices, today):
        schedule_specs = [
            (
                today + timedelta(days=18),
                today + timedelta(days=19),
                "09:00-14:00",
                "测试 ICPC 区域赛",
                "测试大学机房",
                "1094808529",
                "测试公告：ICPC 区域赛报名提醒",
                CompetitionScheduleEntry.Status.APPROVED,
            ),
            (
                today + timedelta(days=45),
                today + timedelta(days=45),
                "13:00-18:00",
                "测试 CCPC 邀请赛",
                "测试城市体育馆",
                "123456789",
                "测试公告：CCPC 邀请赛信息汇总",
                CompetitionScheduleEntry.Status.APPROVED,
            ),
            (
                today + timedelta(days=70),
                today + timedelta(days=70),
                "待定",
                "待审核锦标赛示例",
                "待定",
                "",
                "",
                CompetitionScheduleEntry.Status.PENDING,
            ),
        ]
        for event_date, end_date, time_range, ctype, location, qq_group, notice_title, status in schedule_specs:
            CompetitionScheduleEntry.objects.update_or_create(
                event_date=event_date,
                competition_type=ctype,
                defaults={
                    "end_date": end_date,
                    "competition_time_range": time_range,
                    "location": location,
                    "qq_group": qq_group,
                    "announcement": notices.get(notice_title),
                    "created_by": users["demo_school"],
                    "updated_by": users["demo_admin"],
                    "status": status,
                    "reviewer": (
                        users["demo_admin"]
                        if status != CompetitionScheduleEntry.Status.PENDING
                        else None
                    ),
                    "review_note": "",
                    "reviewed_at": (
                        timezone.now()
                        if status != CompetitionScheduleEntry.Status.PENDING
                        else None
                    ),
                },
            )

    def _seed_competition_calendar(self, today):
        base = timezone.make_aware(
            timezone.datetime.combine(today, timezone.datetime.min.time())
        )
        events = [
            (
                CompetitionCalendarEvent.SourceSite.CODEFORCES,
                "demo-codeforces-round",
                "Codeforces Round 测试赛",
                "https://codeforces.com/contests",
                base + timedelta(days=2, hours=22),
                7200,
            ),
            (
                CompetitionCalendarEvent.SourceSite.ATCODER,
                "demo-atcoder-abc",
                "AtCoder Beginner Contest 测试赛",
                "https://atcoder.jp/contests/",
                base + timedelta(days=4, hours=20),
                6000,
            ),
            (
                CompetitionCalendarEvent.SourceSite.NOWCODER,
                "demo-nowcoder-practice",
                "牛客周赛测试场",
                "https://ac.nowcoder.com/",
                base + timedelta(days=6, hours=19),
                7200,
            ),
            (
                CompetitionCalendarEvent.SourceSite.LUOGU,
                "demo-luogu-training",
                "洛谷公开赛测试场",
                "https://www.luogu.com.cn/contest/list",
                base + timedelta(days=8, hours=14),
                10800,
            ),
        ]
        for source_site, source_id, title, url, start_time, duration_seconds in events:
            CompetitionCalendarEvent.objects.update_or_create(
                source_site=source_site,
                source_id=source_id,
                defaults={
                    "title": title,
                    "organizer": "AlgoWiki 测试数据",
                    "url": url,
                    "start_time": start_time,
                    "end_time": start_time + timedelta(seconds=duration_seconds),
                    "duration_seconds": duration_seconds,
                    "last_synced_at": timezone.now(),
                    "extra": {"demo": True},
                },
            )

    def _seed_practice_links(self, users, year, today, now):
        link_specs = [
            {
                "source_key": "demo-practice-icpc-regional",
                "year": year,
                "series": CompetitionPracticeLink.Series.ICPC,
                "stage": CompetitionPracticeLink.Stage.REGIONAL,
                "short_name": "测试 ICPC 区域赛",
                "official_name": f"{year} ICPC 测试区域赛补题链接",
                "official_url": "https://example.com/icpc-demo",
                "event_date": today - timedelta(days=30),
                "organizer": "测试大学",
                "practice_links": [
                    {"label": "QOJ", "url": "https://qoj.ac/contest/demo"},
                    {"label": "VJudge", "url": "https://vjudge.net/contest/demo"},
                ],
                "practice_links_note": "测试补题链接，可用于检查表格和贡献者名单。",
                "display_order": 10,
            },
            {
                "source_key": "demo-practice-ccpc-invitational",
                "year": year,
                "series": CompetitionPracticeLink.Series.CCPC,
                "stage": CompetitionPracticeLink.Stage.INVITATIONAL,
                "short_name": "测试 CCPC 邀请赛",
                "official_name": f"{year} CCPC 测试邀请赛补题链接",
                "official_url": "https://example.com/ccpc-demo",
                "event_date": today - timedelta(days=12),
                "organizer": "测试学院",
                "practice_links": [
                    {"label": "官方题目", "url": "https://example.com/problems"},
                ],
                "practice_links_note": "用于测试搜索、筛选和补题链接展示。",
                "display_order": 20,
            },
        ]
        entries = {}
        for item in link_specs:
            entry, _ = CompetitionPracticeLink.objects.update_or_create(
                source_key=item["source_key"],
                defaults={
                    **item,
                    "event_date_text": item["event_date"].isoformat(),
                    "source_file": "demo",
                    "source_section": "测试补题链接",
                    "created_by": users["demo_writer"],
                    "updated_by": users["demo_admin"],
                },
            )
            entries[item["source_key"]] = entry

        CompetitionPracticeLinkProposal.objects.update_or_create(
            target_entry=entries["demo-practice-icpc-regional"],
            proposer=users["demo_solver"],
            proposed_short_name="测试 ICPC 区域赛（补充镜像）",
            defaults={
                "proposed_year": year,
                "proposed_series": CompetitionPracticeLink.Series.ICPC,
                "proposed_stage": CompetitionPracticeLink.Stage.REGIONAL,
                "proposed_official_name": f"{year} ICPC 测试区域赛补题链接补充",
                "proposed_official_url": "https://example.com/icpc-demo-extra",
                "proposed_event_date": today - timedelta(days=30),
                "proposed_event_date_text": (today - timedelta(days=30)).isoformat(),
                "proposed_organizer": "测试大学",
                "proposed_practice_links": [
                    {"label": "补充链接", "url": "https://example.com/extra"},
                ],
                "proposed_practice_links_note": "等待审核的补题链接修改。",
                "reason": "测试补题链接审核入口。",
                "status": CompetitionPracticeLinkProposal.Status.PENDING,
            },
        )
        CompetitionPracticeLinkProposal.objects.update_or_create(
            target_entry=entries["demo-practice-ccpc-invitational"],
            proposer=users["demo_writer"],
            proposed_short_name="已驳回补题链接示例",
            defaults={
                "proposed_year": year,
                "proposed_series": CompetitionPracticeLink.Series.CCPC,
                "proposed_stage": CompetitionPracticeLink.Stage.INVITATIONAL,
                "proposed_official_name": "已驳回补题链接示例",
                "proposed_official_url": "",
                "proposed_event_date": today - timedelta(days=12),
                "proposed_event_date_text": (today - timedelta(days=12)).isoformat(),
                "proposed_organizer": "测试学院",
                "proposed_practice_links": [],
                "proposed_practice_links_note": "缺少链接。",
                "reason": "测试已驳回记录。",
                "status": CompetitionPracticeLinkProposal.Status.REJECTED,
                "reviewer": users["demo_admin"],
                "review_note": "测试驳回批注：请提供有效链接。",
                "reviewed_at": now,
            },
        )

    def _seed_tricks(self, users, terms):
        specs = [
            (
                "测试 Trick：完全平方数约数个数",
                "数学 约数 平方数",
                "# 测试 Trick：完全平方数约数个数\n\n一个正整数的约数个数为奇数，当且仅当它是完全平方数。\n\n因为非平方约数会成对出现：$d$ 与 $n/d$。",
                ["数学"],
                TrickEntry.Status.APPROVED,
                users["demo_writer"],
            ),
            (
                "测试 Trick：树状数组单点还原",
                "树状数组 lowbit 单点查询",
                "# 测试 Trick：树状数组单点还原\n\n利用 `lowbit` 的区间覆盖关系，可以在某些维护方式下减少一次前缀查询。\n\n适合用来测试代码块和关键词显示。",
                ["数据结构"],
                TrickEntry.Status.APPROVED,
                users["demo_solver"],
            ),
            (
                "测试 Trick：竞赛图哈密顿路径",
                "竞赛图 哈密顿 图论",
                "# 测试 Trick：竞赛图哈密顿路径\n\n任意竞赛图都存在哈密顿路径。\n\n这条数据用于检查卡片、弹窗和复制 Markdown 按钮。",
                ["图论"],
                TrickEntry.Status.APPROVED,
                users["demo_school"],
            ),
            (
                "待审核 Trick：字符串哈希冲突说明",
                "字符串 哈希 冲突",
                "# 待审核 Trick：字符串哈希冲突说明\n\n这是等待管理员审核的测试 Trick。",
                ["字符串"],
                TrickEntry.Status.PENDING,
                users["demo_writer"],
            ),
            (
                "已驳回 Trick：缺少适用条件示例",
                "其他 待完善",
                "# 已驳回 Trick：缺少适用条件示例\n\n这条数据用于检查已驳回列表和追加批注。",
                ["其他"],
                TrickEntry.Status.REJECTED,
                users["demo_solver"],
            ),
        ]
        tricks = {}
        for title, keywords, content, term_names, status, author in specs:
            trick, _ = TrickEntry.objects.update_or_create(
                title=title,
                defaults={
                    "content_md": content,
                    "keywords_text": keywords,
                    "author": author,
                    "status": status,
                    "reviewer": (
                        users["demo_admin"] if status != TrickEntry.Status.PENDING else None
                    ),
                    "review_note": (
                        "测试驳回批注：请补充适用范围和例题。"
                        if status == TrickEntry.Status.REJECTED
                        else ""
                    ),
                    "reviewed_at": (
                        timezone.now() if status != TrickEntry.Status.PENDING else None
                    ),
                },
            )
            trick.terms.set([terms[name] for name in term_names if name in terms])
            tricks[title] = trick
        return tricks

    def _seed_trick_votes_and_scores(self, users, tricks):
        like_plan = {
            "测试 Trick：完全平方数约数个数": ["demo_voter_a", "demo_voter_b", "demo_voter_c"],
            "测试 Trick：树状数组单点还原": ["demo_voter_a", "demo_voter_b"],
            "测试 Trick：竞赛图哈密顿路径": ["demo_voter_a"],
        }
        for title, voter_names in like_plan.items():
            trick = tricks[title]
            for voter_name in voter_names:
                TrickEntryLike.objects.get_or_create(
                    user=users[voter_name],
                    trick_entry=trick,
                )

        downvote_trick = tricks["测试 Trick：竞赛图哈密顿路径"]
        for voter_name in ("demo_voter_b", "demo_voter_c"):
            TrickEntryDownvote.objects.get_or_create(
                user=users[voter_name],
                trick_entry=downvote_trick,
            )

        for trick in tricks.values():
            if trick.status != TrickEntry.Status.APPROVED:
                continue
            self._ensure_trick_score_event(
                user=trick.author,
                actor=users["demo_admin"],
                trick=trick,
                delta=10,
                action_type=TrickContributionEvent.ActionType.TRICK_APPROVED,
                event_key=f"{DEMO_PREFIX}:trick-approved:{trick.title}",
            )
            like_count = TrickEntryLike.objects.filter(trick_entry=trick).count()
            if like_count:
                self._ensure_trick_score_event(
                    user=trick.author,
                    actor=None,
                    trick=trick,
                    delta=like_count,
                    action_type=TrickContributionEvent.ActionType.TRICK_RECEIVED_LIKE,
                    event_key=f"{DEMO_PREFIX}:trick-likes:{trick.title}",
                    metadata={"like_count": like_count},
                )

    def _ensure_trick_score_event(
        self,
        *,
        user,
        actor,
        trick,
        delta,
        action_type,
        event_key,
        metadata=None,
    ):
        if TrickContributionEvent.objects.filter(event_key=event_key).exists():
            return
        user.trick_contribution_score = int(user.trick_contribution_score or 0) + int(delta)
        user.save(update_fields=["trick_contribution_score"])
        TrickContributionEvent.objects.create(
            user=user,
            actor=actor,
            trick_entry=trick,
            trick_title=trick.title,
            action_type=action_type,
            delta=delta,
            balance_after=user.trick_contribution_score,
            event_key=event_key,
            metadata=metadata or {"demo": True},
        )

    def _seed_questions(self, users, categories, now):
        q1, _ = Question.objects.update_or_create(
            title="测试问答：近期应该先打哪些比赛？",
            author=users["demo_solver"],
            defaults={
                "content_md": "想测试问答页的展开、折叠和回答显示。可以结合常规赛和锦标赛数据回答。",
                "category": categories["root"],
                "status": Question.Status.OPEN,
                "auto_close_at": now + timedelta(days=7),
                "reviewer": users["demo_admin"],
                "reviewed_at": now,
            },
        )
        Answer.objects.update_or_create(
            question=q1,
            author=users["demo_writer"],
            content_md="可以先看常规赛中的 Codeforces / AtCoder 测试赛，再看锦标赛中的 ICPC 测试区域赛。",
            defaults={
                "is_accepted": True,
                "status": Answer.Status.VISIBLE,
                "reviewer": users["demo_admin"],
                "reviewed_at": now,
            },
        )
        q2, _ = Question.objects.update_or_create(
            title="待审核问答：如何提交 Trick？",
            author=users["demo_writer"],
            defaults={
                "content_md": "这条问题用于检查问答审核队列。",
                "category": categories["child"],
                "status": Question.Status.PENDING,
            },
        )
        Answer.objects.update_or_create(
            question=q2,
            author=users["demo_solver"],
            content_md="这条回答用于检查回答审核队列。",
            defaults={"status": Answer.Status.PENDING},
        )
        Question.objects.update_or_create(
            title="已关闭问答：测试自动关闭状态",
            author=users["demo_school"],
            defaults={
                "content_md": "这条问题用于检查关闭状态展示。",
                "category": categories["root"],
                "status": Question.Status.CLOSED,
                "auto_close_at": None,
            },
        )

    def _seed_home_and_links(self, users, now):
        Announcement.objects.update_or_create(
            title="测试公告：develop/test 环境数据已填充",
            defaults={
                "content_md": "这是一条测试站内公告，用于检查首页公告弹窗和公告列表。",
                "created_by": users["demo_admin"],
                "priority": 200,
                "is_published": True,
                "start_at": now - timedelta(days=1),
                "end_at": now + timedelta(days=14),
            },
        )
        FriendlyLink.objects.update_or_create(
            name="测试友链：AlgoWiki Demo",
            defaults={
                "description": "用于测试友链卡片显示、排序和启停状态。",
                "url": "https://example.com/algowiki-demo",
                "created_by": users["demo_admin"],
                "is_enabled": True,
                "order": 900,
            },
        )
        TeamMember.objects.update_or_create(
            display_id="DemoContributor",
            defaults={
                "user": users["demo_writer"],
                "avatar_url": "/wiki-assets/resot.png",
                "profile_url": "https://github.com/NullResot/AlgoWiki",
                "is_active": True,
                "sort_order": 900,
            },
        )

    def _seed_admin_visible_data(self, users, tricks, now, today):
        for offset, views in enumerate((120, 168, 96, 210, 180, 132, 240)):
            SiteVisitDailyStat.objects.update_or_create(
                date=today - timedelta(days=6 - offset),
                defaults={"page_views": views},
            )
        SecurityAuditLog.objects.get_or_create(
            event_type=SecurityAuditLog.EventType.LOGIN_SUCCESS,
            username=users["demo_admin"].username,
            defaults={
                "user": users["demo_admin"],
                "ip_address": "127.0.0.1",
                "user_agent": "AlgoWiki demo seed",
                "success": True,
                "detail": "测试登录成功日志",
                "metadata": {"demo": True},
            },
        )
        SecurityAuditLog.objects.get_or_create(
            event_type=SecurityAuditLog.EventType.LOGIN_FAILED,
            username="demo_unknown",
            defaults={
                "user": None,
                "ip_address": "127.0.0.1",
                "user_agent": "AlgoWiki demo seed",
                "success": False,
                "detail": "测试登录失败日志",
                "metadata": {"demo": True},
            },
        )
        UserNotification.objects.get_or_create(
            user=users["demo_writer"],
            title="测试通知：你的 Trick 已收到审核备注",
            defaults={
                "actor": users["demo_admin"],
                "content": "这条通知用于检查通知弹框完整内容展示。",
                "link": "/profile",
                "level": UserNotification.Level.INFO,
                "target_type": "TrickEntry",
                "target_id": tricks["测试 Trick：完全平方数约数个数"].id,
            },
        )
        DeletedContentArchive.objects.get_or_create(
            target_type="TrickEntry",
            target_id=900001,
            title="测试删除归档：被删除的 Trick",
            defaults={
                "delete_action": DeletedContentArchive.DeleteAction.DELETE,
                "summary": "用于测试删除内容管理入口。",
                "content_md": "# 测试删除归档\n\n这条内容模拟被删除的 Trick。",
                "snapshot": {"demo": True, "model": "TrickEntry"},
                "original_author": users["demo_writer"],
                "original_author_name": users["demo_writer"].username,
                "deleted_by": users["demo_admin"],
                "deleted_by_name": users["demo_admin"].username,
            },
        )
        if getattr(settings, "QA_MODULE_ENABLED", False):
            DeletedContentArchive.objects.get_or_create(
                target_type="Question",
                target_id=900002,
                title="测试删除归档：被隐藏的问答",
                defaults={
                    "delete_action": DeletedContentArchive.DeleteAction.HIDE,
                    "summary": "用于测试问答删除/隐藏归档。",
                    "content_md": "这条内容模拟被隐藏的问答。",
                    "snapshot": {"demo": True, "model": "Question"},
                    "original_author": users["demo_solver"],
                    "original_author_name": users["demo_solver"].username,
                    "deleted_by": users["demo_admin"],
                    "deleted_by_name": users["demo_admin"].username,
                },
            )

    def _seed_ai_assistant(self, users):
        AssistantProviderConfig.objects.update_or_create(
            label="Demo DeepSeek Chat",
            defaults={
                "assistant_name": "小小丛雨",
                "provider": AssistantProviderConfig.Provider.DEEPSEEK,
                "base_url": "https://api.deepseek.com",
                "model_name": "deepseek-chat",
                "api_key_encrypted": "",
                "is_enabled": False,
                "is_default": False,
                "show_launcher": True,
                "temperature": 0.3,
                "max_output_tokens": 800,
                "request_timeout_seconds": 30,
                "welcome_message": "师兄可以问我站内内容、比赛安排和 Trick 检索。",
                "teaser_message": "杂鱼师兄，想要更方便地了解 AlgoWiki，可以点击询问小小丛雨我哦~",
                "suggested_questions": [
                    "最近有哪些线上比赛？",
                    "有哪些测试 Trick？",
                    "蓝桥杯是什么赛制？",
                ],
                "system_prompt": "仅作为测试配置，不包含真实 API Key。",
                "daily_request_limit": 50,
                "daily_token_limit": 100000,
                "created_by": users["demo_admin"],
                "updated_by": users["demo_admin"],
            },
        )
