from django.db.models import Q

from .models import (
    Article,
    Category,
    CompetitionNotice,
    CompetitionScheduleEntry,
    User,
)


def article_visibility_q(user) -> Q:
    is_active_user = bool(
        user
        and user.is_authenticated
        and user.is_active
        and not user.is_banned
    )
    if is_active_user and user.role in {
        User.Role.ADMIN,
        User.Role.SUPERADMIN,
    }:
        return Q()
    if is_active_user and user.role == User.Role.SCHOOL:
        return (
            Q(status=Article.Status.PUBLISHED)
            | Q(author=user)
            | Q(category__moderation_scope=Category.ModerationScope.SCHOOL)
        )
    if is_active_user:
        return Q(status=Article.Status.PUBLISHED) | Q(author=user)
    return Q(status=Article.Status.PUBLISHED)


def filter_articles_visible_to(queryset, user):
    return queryset.filter(article_visibility_q(user))


def can_view_article(user, article: Article) -> bool:
    if not article or not article.pk:
        return False
    return filter_articles_visible_to(Article.objects.filter(pk=article.pk), user).exists()


def public_competition_notices(queryset=None):
    queryset = queryset if queryset is not None else CompetitionNotice.objects.all()
    return queryset.filter(
        revision_of__isnull=True,
        is_visible=True,
        status=CompetitionNotice.Status.APPROVED,
    )


def public_competition_schedules(queryset=None):
    queryset = queryset if queryset is not None else CompetitionScheduleEntry.objects.all()
    return queryset.filter(status=CompetitionScheduleEntry.Status.APPROVED).filter(
        Q(announcement__isnull=True)
        | Q(
            announcement__revision_of__isnull=True,
            announcement__is_visible=True,
            announcement__status=CompetitionNotice.Status.APPROVED,
        )
    )
