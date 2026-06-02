DELETED_USER_PLACEHOLDER_USERNAME = "system_deleted_user"
DELETED_USER_DISPLAY_NAME = "已注销用户"


def is_deleted_user_placeholder(user) -> bool:
    return bool(
        user
        and getattr(user, "username", "") == DELETED_USER_PLACEHOLDER_USERNAME
    )


def get_public_username(user) -> str:
    if is_deleted_user_placeholder(user):
        return DELETED_USER_DISPLAY_NAME
    return getattr(user, "username", "") or ""
