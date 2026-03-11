import os
import tempfile
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent


def _load_env_file():
    env_file = os.getenv("ALGOWIKI_ENV_FILE", "").strip()
    env_path = Path(env_file) if env_file else BASE_DIR / ".env"
    if not env_path.exists():
        return

    for encoding in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            lines = env_path.read_text(encoding=encoding).splitlines()
            break
        except UnicodeDecodeError:
            continue
    else:
        return

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _csv_env(name: str, default: str = ""):
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


_load_env_file()

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-secret-key-change-in-production")
DEBUG = os.getenv("DJANGO_DEBUG", "1") == "1"
if not DEBUG and SECRET_KEY == "dev-secret-key-change-in-production":
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be explicitly configured when DJANGO_DEBUG=0.")

ALLOWED_HOSTS = _csv_env("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost")
CSRF_TRUSTED_ORIGINS = _csv_env("DJANGO_CSRF_TRUSTED_ORIGINS", "")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework.authtoken",
    "wiki",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "config.middleware.RequestContextMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DB_ENGINE = os.getenv("DB_ENGINE", "mysql").lower()
if DB_ENGINE == "sqlite":
    default_sqlite_name = str((PROJECT_ROOT / "storage" / "db_live.sqlite3").resolve())
    legacy_temp_sqlite_name = str((Path(tempfile.gettempdir()) / "algowiki_working.sqlite3").resolve())
    configured_sqlite_name = os.getenv("SQLITE_NAME", "").strip()
    if not configured_sqlite_name:
        sqlite_name = default_sqlite_name
    else:
        try:
            configured_resolved = str(Path(configured_sqlite_name).resolve())
        except Exception:
            configured_resolved = configured_sqlite_name
        # Ignore stale legacy temp-path value from old startup scripts.
        sqlite_name = default_sqlite_name if configured_resolved == legacy_temp_sqlite_name else configured_sqlite_name
    Path(sqlite_name).parent.mkdir(parents=True, exist_ok=True)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": sqlite_name,
        }
    }
else:
    try:
        import pymysql

        # Django 6+ validates MySQLdb client version (expects mysqlclient>=2.2.1).
        # When using PyMySQL via install_as_MySQLdb, report a compatible version.
        pymysql.version_info = (2, 2, 1, "final", 0)
        pymysql.__version__ = "2.2.1"
        pymysql.install_as_MySQLdb()
    except Exception:
        # mysqlclient can also satisfy the MySQLdb dependency.
        pass

    db_options = {"charset": os.getenv("DB_CHARSET", "utf8mb4")}
    db_init_command = os.getenv("DB_INIT_COMMAND", "").strip()
    if db_init_command:
        db_options["init_command"] = db_init_command

    db_ssl_ca = os.getenv("DB_SSL_CA", "").strip()
    if db_ssl_ca:
        ssl_config = {"ca": db_ssl_ca}
        db_ssl_cert = os.getenv("DB_SSL_CERT", "").strip()
        db_ssl_key = os.getenv("DB_SSL_KEY", "").strip()
        if db_ssl_cert:
            ssl_config["cert"] = db_ssl_cert
        if db_ssl_key:
            ssl_config["key"] = db_ssl_key
        db_options["ssl"] = ssl_config

    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": os.getenv("DB_NAME", "algowiki"),
            "USER": os.getenv("DB_USER", "root"),
            "PASSWORD": os.getenv("DB_PASSWORD", ""),
            "HOST": os.getenv("DB_HOST", "127.0.0.1"),
            "PORT": os.getenv("DB_PORT", "3306"),
            "CONN_MAX_AGE": int(os.getenv("DB_CONN_MAX_AGE", "60")),
            "OPTIONS": db_options,
        }
    }

AUTH_USER_MODEL = "wiki.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = os.getenv("MEDIA_URL", "/media/")
MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", str(BASE_DIR / "media")))
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
configured_frontend_dist_dir = os.getenv("FRONTEND_DIST_DIR", "").strip()
if configured_frontend_dist_dir:
    FRONTEND_DIST_DIR = Path(configured_frontend_dist_dir).resolve()
else:
    FRONTEND_DIST_DIR = (PROJECT_ROOT / "frontend" / "dist").resolve()
SERVE_FRONTEND = _bool_env(
    "DJANGO_SERVE_FRONTEND",
    default=(not DEBUG) and (FRONTEND_DIST_DIR / "index.html").exists(),
)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
WHITENOISE_AUTOREFRESH = DEBUG
WHITENOISE_USE_FINDERS = DEBUG
WHITENOISE_ALLOW_ALL_ORIGINS = True

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "algowiki-default-cache",
    }
}

# Security baseline
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = (not DEBUG) and os.getenv("SESSION_COOKIE_SECURE", "1") == "1"
CSRF_COOKIE_SECURE = (not DEBUG) and os.getenv("CSRF_COOKIE_SECURE", "1") == "1"
SECURE_SSL_REDIRECT = (not DEBUG) and os.getenv("SECURE_SSL_REDIRECT", "1") == "1"
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "0" if DEBUG else "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = os.getenv("SECURE_HSTS_INCLUDE_SUBDOMAINS", "1") == "1"
SECURE_HSTS_PRELOAD = os.getenv("SECURE_HSTS_PRELOAD", "1") == "1"
USE_X_FORWARDED_HOST = _bool_env("DJANGO_USE_X_FORWARDED_HOST", default=False)
USE_X_FORWARDED_PORT = _bool_env("DJANGO_USE_X_FORWARDED_PORT", default=False)

secure_proxy_ssl_header = os.getenv("DJANGO_SECURE_PROXY_SSL_HEADER", "").strip()
if secure_proxy_ssl_header:
    header_name, _, header_value = secure_proxy_ssl_header.partition(",")
    header_name = header_name.strip()
    header_value = header_value.strip()
    if header_name and header_value:
        SECURE_PROXY_SSL_HEADER = (header_name, header_value)

AUTH_SECURITY = {
    "TOKEN_TTL_HOURS": int(os.getenv("AUTH_TOKEN_TTL_HOURS", "168")),
    "LOGIN_MAX_FAILURES": int(os.getenv("LOGIN_MAX_FAILURES", "5")),
    "LOGIN_FAILURE_WINDOW_MINUTES": int(os.getenv("LOGIN_FAILURE_WINDOW_MINUTES", "15")),
    "LOGIN_LOCK_MINUTES": int(os.getenv("LOGIN_LOCK_MINUTES", "15")),
    "PASSWORD_HISTORY_COUNT": int(os.getenv("PASSWORD_HISTORY_COUNT", "5")),
}

DATA_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv("DATA_UPLOAD_MAX_MEMORY_SIZE", str(10 * 1024 * 1024)))
FILE_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv("FILE_UPLOAD_MAX_MEMORY_SIZE", str(4 * 1024 * 1024)))
DATA_UPLOAD_MAX_NUMBER_FIELDS = int(os.getenv("DATA_UPLOAD_MAX_NUMBER_FIELDS", "2000"))
FILE_UPLOAD_PERMISSIONS = 0o640
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o750

REQUEST_LOG_ENABLED = _bool_env("DJANGO_REQUEST_LOG_ENABLED", default=True)
SLOW_REQUEST_MS = float(os.getenv("DJANGO_SLOW_REQUEST_MS", "1500"))
REQUEST_LOG_EXCLUDE_PREFIXES = tuple(
    prefix
    for prefix in {
        STATIC_URL,
        MEDIA_URL,
    }
    if prefix
)
HEALTH_MIN_DISK_FREE_MB = int(os.getenv("HEALTH_MIN_DISK_FREE_MB", "512"))
APP_RELEASE = os.getenv("ALGOWIKI_RELEASE", "").strip()

LOG_DIR = Path(os.getenv("DJANGO_LOG_DIR", str((PROJECT_ROOT / "storage" / "logs").resolve())))
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_LEVEL = os.getenv("DJANGO_LOG_LEVEL", "INFO").strip().upper() or "INFO"
DJANGO_LOG_SQL_QUERIES = _bool_env("DJANGO_LOG_SQL_QUERIES", default=False)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "request_id": {
            "()": "config.request_context.RequestIdFilter",
        }
    },
    "formatters": {
        "verbose": {
            "format": "%(asctime)s %(levelname)s [%(name)s] [request_id=%(request_id)s] %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "filters": ["request_id"],
            "formatter": "verbose",
        },
        "app_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_DIR / "algowiki.log"),
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 5,
            "encoding": "utf-8",
            "filters": ["request_id"],
            "formatter": "verbose",
        },
        "security_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_DIR / "security.log"),
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 10,
            "encoding": "utf-8",
            "filters": ["request_id"],
            "formatter": "verbose",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console", "app_file"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console", "app_file"],
            "level": "WARNING",
            "propagate": False,
        },
        "django.db.backends": {
            "handlers": ["console", "app_file"],
            "level": "DEBUG" if DJANGO_LOG_SQL_QUERIES else "INFO",
            "propagate": False,
        },
        "algowiki.request": {
            "handlers": ["console", "app_file"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "algowiki.api": {
            "handlers": ["console", "app_file"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "algowiki.security": {
            "handlers": ["console", "security_file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "wiki.authentication.ExpiringTokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.AllowAny",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "login": os.getenv("THROTTLE_LOGIN", "20/hour"),
        "register": os.getenv("THROTTLE_REGISTER", "10/hour"),
        "password_change": os.getenv("THROTTLE_PASSWORD_CHANGE", "6/hour"),
    },
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "EXCEPTION_HANDLER": "wiki.api.custom_exception_handler",
}

if os.getenv("MIGRATION_MODULES_WIKI"):
    MIGRATION_MODULES = {"wiki": os.getenv("MIGRATION_MODULES_WIKI")}
