import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from wiki.models import Article, Category, User


class Command(BaseCommand):
    help = "Import a large markdown file and split it into wiki articles by heading level."

    def add_arguments(self, parser):
        parser.add_argument("--file", type=str, required=True, help="Path to markdown file")
        parser.add_argument("--author", type=str, default="superadmin", help="Author username")
        parser.add_argument("--default-category", type=str, default="xcpc-preface", help="Fallback category slug")
        parser.add_argument("--split-level", type=int, default=2, help="Heading level used to split sections")
        parser.add_argument("--dry-run", action="store_true", help="Only parse and print plan, do not write database")

    @transaction.atomic
    def handle(self, *args, **options):
        source_file = Path(options["file"])
        if not source_file.exists():
            raise CommandError(f"File not found: {source_file}")

        split_level = options["split_level"]
        if split_level < 1 or split_level > 6:
            raise CommandError("--split-level must be between 1 and 6")

        try:
            author = User.objects.get(username=options["author"])
        except User.DoesNotExist as exc:
            raise CommandError(f"Author not found: {options['author']}") from exc

        default_category = Category.objects.filter(slug=options["default_category"]).first()
        if not default_category:
            raise CommandError(f"Default category not found: {options['default_category']}")

        text = self._read_markdown(source_file)
        sections = self._split_sections(text, split_level)
        if not sections:
            raise CommandError("No sections parsed from markdown file")

        self.stdout.write(f"Parsed {len(sections)} sections from markdown.")

        if options["dry_run"]:
            for index, section in enumerate(sections[:20], start=1):
                category = self._guess_category(section["title"], default_category)
                self.stdout.write(f"[{index}] {section['title']} -> {category.slug}")
            self.stdout.write(self.style.SUCCESS("Dry run completed, no data written."))
            transaction.set_rollback(True)
            return

        created_count = 0
        updated_count = 0
        for section in sections:
            category = self._guess_category(
                section["title"],
                default_category,
                section.get("parent_h2"),
            )
            summary = self._extract_summary(section["content"])
            existing = Article.objects.filter(title=section["title"]).first()
            slug = existing.slug if existing else self._unique_slug(section["title"])

            defaults = {
                "title": section["title"],
                "summary": summary,
                "content_md": section["content"],
                "category": category,
                "author": author,
                "last_editor": author,
                "status": Article.Status.PUBLISHED,
                "slug": slug,
            }

            if existing:
                for key, value in defaults.items():
                    setattr(existing, key, value)
                existing.save()
                article = existing
                created = False
            else:
                article = Article.objects.create(**defaults)
                created = True
            if created:
                created_count += 1
            else:
                updated_count += 1

            self.stdout.write(f"Imported: {article.title} [{category.slug}]")

        self.stdout.write(self.style.SUCCESS(f"Import completed: created {created_count}, updated {updated_count}."))

    def _read_markdown(self, source_file: Path) -> str:
        for encoding in ("utf-8", "utf-8-sig", "gb18030"):
            try:
                return source_file.read_text(encoding=encoding)
            except UnicodeDecodeError:
                continue
        raise CommandError("Could not decode markdown file with utf-8/utf-8-sig/gb18030")

    def _split_sections(self, text: str, split_level: int):
        heading_pattern = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
        headings = list(heading_pattern.finditer(text))
        if not headings:
            return []

        sections = []
        for idx, heading in enumerate(headings):
            level = len(heading.group(1))
            if level != split_level:
                continue

            start = heading.start()
            end = len(text)
            for next_heading in headings[idx + 1 :]:
                if len(next_heading.group(1)) <= split_level:
                    end = next_heading.start()
                    break

            block = text[start:end].strip()
            title = heading.group(2).strip()
            if not title or not block:
                continue

            parent_h2 = None
            for prev_heading in reversed(headings[: idx + 1]):
                if len(prev_heading.group(1)) == 2:
                    parent_h2 = prev_heading.group(2).strip()
                    break

            sections.append(
                {
                    "title": title,
                    "content": block,
                    "parent_h2": parent_h2,
                }
            )

        return sections

    def _extract_summary(self, content: str) -> str:
        lines = [line.strip() for line in content.splitlines()]
        body = [line for line in lines if line and not line.startswith("#") and not line.startswith(">")]
        if not body:
            return ""
        return body[0][:220]

    def _unique_slug(self, title: str) -> str:
        base = slugify(title)[:120] or "article"
        candidate = base
        suffix = 1
        while Article.objects.filter(slug=candidate).exists():
            suffix += 1
            candidate = f"{base}-{suffix}"
        return candidate

    def _guess_category(self, title: str, default_category: Category, parent_h2: str | None = None) -> Category:
        if parent_h2:
            parent_checks = [
                ("xcpc-preface", ["阅前须知", "文章大纲", "阅读索引"]),
                ("xcpc-academic-integrity", ["学术诚信"]),
                ("xcpc-common-terms", ["常见术语"]),
                ("xcpc-concepts", ["竞赛概念"]),
                ("xcpc-contests", ["比赛介绍"]),
                ("xcpc-sites", ["关键网站"]),
                ("xcpc-tools", ["代码工具"]),
                ("xcpc-stages", ["阶段任务"]),
                ("xcpc-training", ["关于训练"]),
                ("xcpc-closing", ["结语与致谢"]),
            ]
            for slug, keywords in parent_checks:
                if any(keyword in parent_h2 for keyword in keywords):
                    category = Category.objects.filter(slug=slug).first()
                    if category:
                        return category

        checks = [
            ("xcpc-preface", ["阅前", "须知", "入门", "简介"]),
            ("xcpc-academic-integrity", ["学术诚信", "诚信", "违规", "抄袭"]),
            ("xcpc-common-terms", ["术语", "缩写", "ac", "wa", "tle", "mle", "re", "ce"]),
            ("xcpc-concepts", ["竞赛概念", "赛制", "分工", "模型"]),
            ("xcpc-contests", ["icpc", "ccpc", "蓝桥杯", "天梯赛", "百度之星", "比赛", "多校"]),
            ("xcpc-sites", ["codeforces", "atcoder", "牛客", "洛谷", "qoj", "vjudge", "网站"]),
            ("xcpc-tools", ["vscode", "clion", "工具", "编译", "调试", "对拍", "markdown", "latex"]),
            ("xcpc-stages", ["阶段", "路线图", "成长", "阶段任务"]),
            ("xcpc-training", ["训练", "刷题", "补题", "vp", "复盘", "提问"]),
            ("xcpc-closing", ["结语", "致谢", "路线图", "维护"]),
        ]

        title_lower = title.lower()
        for slug, keywords in checks:
            for keyword in keywords:
                if keyword in title_lower or keyword in title:
                    category = Category.objects.filter(slug=slug).first()
                    if category:
                        return category

        return default_category
