from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from wiki.models import Article, Category, User
from wiki.seed_content.xcpc_articles import ARTICLE_DEFS, CATEGORY_DEFS, LEGACY_CATEGORY_SLUGS


class Command(BaseCommand):
    help = "Seed structured XCPC onboarding content referenced from NullResot/xcpc README and xcpc-wiki."

    def add_arguments(self, parser):
        parser.add_argument("--author", type=str, default="superadmin", help="Author username used for seeded content")
        parser.add_argument(
            "--prune",
            action="store_true",
            help="Hide legacy xcpc-* articles that are not included in the current content pack",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        author = self._resolve_author(options["author"])
        categories = self._sync_categories()
        created_count, updated_count = self._sync_articles(categories, author)
        hidden_count = self._prune_articles() if options["prune"] else 0

        summary = f"XCPC reference content seeded: created {created_count}, updated {updated_count}."
        if options["prune"]:
            summary += f" hidden stale articles {hidden_count}."
        self.stdout.write(self.style.SUCCESS(summary))

    def _resolve_author(self, username: str) -> User:
        author = User.objects.filter(username=username).first()
        if author:
            return author

        fallback = (
            User.objects.filter(role=User.Role.SUPERADMIN).order_by("id").first()
            or User.objects.filter(role=User.Role.ADMIN).order_by("id").first()
        )
        if fallback:
            return fallback

        raise CommandError(
            f"Author '{username}' not found, and no superadmin/admin is available. "
            "Please run seed_initial_data first or create an admin account."
        )

    def _sync_categories(self):
        categories = {}
        for name, slug, parent_slug, order, scope in CATEGORY_DEFS:
            parent = categories.get(parent_slug) if parent_slug else None
            category, _ = Category.objects.update_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "parent": parent,
                    "order": order,
                    "moderation_scope": scope,
                    "is_visible": True,
                },
            )
            categories[slug] = category

        Category.objects.filter(slug__in=LEGACY_CATEGORY_SLUGS).update(is_visible=False)
        return categories

    def _sync_articles(self, categories, author: User):
        created_count = 0
        updated_count = 0

        for item in ARTICLE_DEFS:
            defaults = {
                "title": item["title"],
                "summary": item["summary"],
                "content_md": item["content_md"],
                "category": categories[item["category"]],
                "author": author,
                "last_editor": author,
                "status": Article.Status.PUBLISHED,
                "is_featured": bool(item.get("featured", False)),
            }
            article, created = Article.objects.update_or_create(slug=item["slug"], defaults=defaults)
            if created:
                created_count += 1
            else:
                updated_count += 1
            self.stdout.write(f"Synced article: {article.title}")

        return created_count, updated_count

    def _prune_articles(self):
        active_slugs = [item["slug"] for item in ARTICLE_DEFS]
        stale_queryset = Article.objects.filter(slug__startswith="xcpc-").exclude(slug__in=active_slugs)
        count = stale_queryset.count()
        stale_queryset.update(status=Article.Status.HIDDEN, is_featured=False)
        return count
