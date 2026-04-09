from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class LoginRateThrottle(AnonRateThrottle):
    scope = "login"


class RegisterRateThrottle(AnonRateThrottle):
    scope = "register"


class RegisterVerifyRateThrottle(AnonRateThrottle):
    scope = "register_verify"


class RegisterChallengeRateThrottle(AnonRateThrottle):
    scope = "register_challenge"


class PasswordResetRequestRateThrottle(AnonRateThrottle):
    scope = "password_reset_request"


class PasswordResetConfirmRateThrottle(AnonRateThrottle):
    scope = "password_reset_confirm"


class PasswordChangeRateThrottle(UserRateThrottle):
    scope = "password_change"


class PasswordChangeRequestRateThrottle(UserRateThrottle):
    scope = "password_change_request"


class PasswordChangeConfirmRateThrottle(UserRateThrottle):
    scope = "password_change_confirm"


class ProfileUpdateRateThrottle(UserRateThrottle):
    scope = "profile_update"


class EmailChangeRequestRateThrottle(UserRateThrottle):
    scope = "email_change_request"


class EmailChangeConfirmRateThrottle(UserRateThrottle):
    scope = "email_change_confirm"


class ContentCreateRateThrottle(UserRateThrottle):
    scope = "content_create"


class ContentUpdateRateThrottle(UserRateThrottle):
    scope = "content_update"


class ContentDeleteRateThrottle(UserRateThrottle):
    scope = "content_delete"
