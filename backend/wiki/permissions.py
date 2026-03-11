from rest_framework.permissions import BasePermission

from .models import Category, User


class AuthenticatedAndNotBanned(BasePermission):
    message = "You must be authenticated and not banned."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active and not user.is_banned)


class AdminOrSuperAdmin(BasePermission):
    message = "Admin role required."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and not user.is_banned
            and user.role in {User.Role.ADMIN, User.Role.SUPERADMIN}
        )


class SuperAdminOnly(BasePermission):
    message = "Super admin role required."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and not user.is_banned
            and user.role == User.Role.SUPERADMIN
        )


def can_moderate_category(user, category: Category | None) -> bool:
    if not user or not user.is_authenticated or not user.is_active or user.is_banned:
        return False

    if user.role in {User.Role.ADMIN, User.Role.SUPERADMIN}:
        return True

    if user.role == User.Role.SCHOOL and category:
        return category.moderation_scope == Category.ModerationScope.SCHOOL

    return False


def is_normal_authenticated_user(user) -> bool:
    return bool(user and user.is_authenticated and user.is_active and not user.is_banned)
