from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed


class ExpiringTokenAuthentication(TokenAuthentication):
    keyword = "Token"

    def authenticate_credentials(self, key):
        user_auth_tuple = super().authenticate_credentials(key)
        user, token = user_auth_tuple

        ttl_hours = int((getattr(settings, "AUTH_SECURITY", {}) or {}).get("TOKEN_TTL_HOURS", 168))
        if ttl_hours > 0:
            now = timezone.now()
            if token.created < now - timedelta(hours=ttl_hours):
                token.delete()
                raise AuthenticationFailed("Token expired, please login again.")

        return user, token

