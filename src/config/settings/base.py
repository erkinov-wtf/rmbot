import os
import sys
from importlib.util import find_spec
from pathlib import Path
from urllib.parse import urlparse

import dj_database_url
from decouple import config

HAS_DRF_SPECTACULAR = find_spec("drf_spectacular") is not None
HAS_CELERY = find_spec("celery") is not None
HAS_DJANGO_CELERY_BEAT = find_spec("django_celery_beat") is not None
HAS_REDIS_PACKAGE = find_spec("redis") is not None
HAS_SENTRY_SDK = find_spec("sentry_sdk") is not None

if HAS_SENTRY_SDK:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    if HAS_CELERY:
        from sentry_sdk.integrations.celery import CeleryIntegration

BASE_DIR = Path(__file__).resolve().parent.parent.parent
IS_TEST_RUN = (
    "test" in sys.argv
    or "PYTEST_CURRENT_TEST" in os.environ
    or any("pytest" in arg for arg in sys.argv)
)
LOGS_ROOT = Path(config("LOGS_ROOT", default=BASE_DIR / "logs"))
DEBUG = config("DEBUG", default=False, cast=bool)
if IS_TEST_RUN:
    # Keep tests deterministic and avoid debug-only middleware/tooling side effects.
    DEBUG = False
SECRET_KEY = config(
    "DJANGO_SECRET_KEY",
    default="django-insecure-change-me-please-use-a-long-secret-key-for-local-dev",
)


def _split_csv_env(name: str, *, default: str = "") -> list[str]:
    raw_value = config(name, default=default)
    return [item.strip() for item in str(raw_value).split(",") if item.strip()]


ALLOWED_HOSTS = _split_csv_env("ALLOWED_HOSTS")
CORS_ALLOWED_ORIGINS = _split_csv_env("CORS_ALLOWED_ORIGINS")
CORS_ALLOW_ALL_ORIGINS = config("CORS_ALLOW_ALL_ORIGINS", default=False, cast=bool)
CORS_ALLOW_CREDENTIALS = config("CORS_ALLOW_CREDENTIALS", default=True, cast=bool)

DATABASE_URL = config("DATABASE_URL", default="")
TEST_DATABASE_URL = config("TEST_DATABASE_URL", default="sqlite:///:memory:")

if IS_TEST_RUN:
    ACTIVE_DATABASE_URL = TEST_DATABASE_URL
else:
    if not DATABASE_URL:
        DATABASE_URL = (
            f"postgres://{config('POSTGRES_USER')}:{config('POSTGRES_PASSWORD')}"
            f"@{config('POSTGRES_HOST')}/{config('POSTGRES_DB')}"
        )
    ACTIVE_DATABASE_URL = DATABASE_URL

REDIS_HOST = config("REDIS_HOST", default="localhost")
REDIS_PORT = config("REDIS_PORT", default=6379, cast=int)
REDIS_DB = config("REDIS_DB", default=0, cast=int)
REDIS_CACHE_DB = config("REDIS_CACHE_DB", default=1, cast=int)
REDIS_URL = config(
    "REDIS_URL",
    default=f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}",
)
REDIS_CACHE_URL = config(
    "REDIS_CACHE_URL",
    default=f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_CACHE_DB}",
)

UNFOLD_APPS = [
    "unfold",
    "unfold.contrib.filters",
    "unfold.contrib.forms",
    "unfold.contrib.inlines",
    "unfold.contrib.import_export",
    "unfold.contrib.guardian",
    "unfold.contrib.simple_history",
    "unfold.contrib.location_field",
    # 'unfold.contrib.constance',
]

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "django_filters",
    "corsheaders",
]
if HAS_DRF_SPECTACULAR:
    THIRD_PARTY_APPS.append("drf_spectacular")
if HAS_DJANGO_CELERY_BEAT:
    THIRD_PARTY_APPS.append("django_celery_beat")

LOCAL_APPS = [
    "account",
    "attendance",
    "inventory",
    "core",
    "gamification",
    "rules",
    "api",
    "bot",
    "ticket",
]

INSTALLED_APPS = UNFOLD_APPS + DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "core.middlewares.request_id.RequestIDMiddleware",
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
        "DIRS": [BASE_DIR / "templates"],
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

ASGI_APPLICATION = "config.server.asgi.application"
WSGI_APPLICATION = "config.server.wsgi.application"

DATABASES = {
    "default": dj_database_url.parse(
        url=ACTIVE_DATABASE_URL,
        conn_max_age=600,
        conn_health_checks=True,
    )
}

if IS_TEST_RUN or not HAS_REDIS_PACKAGE:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "rent-market-test-cache",
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_CACHE_URL,
            "TIMEOUT": None,
        }
    }

CELERY_BROKER_URL = config("CELERY_BROKER_URL", default=REDIS_URL)
CELERY_RESULT_BACKEND = config("CELERY_RESULT_BACKEND", default=CELERY_BROKER_URL)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "Asia/Tashkent"
CELERY_ENABLE_UTC = True
CELERY_TASK_IGNORE_RESULT = True
if HAS_DJANGO_CELERY_BEAT:
    CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

CELERY_BEAT_SCHEDULE = {}
if HAS_CELERY:
    CELERY_BEAT_SCHEDULE = {
        "enforce-daily-work-session-pause-limits": {
            "task": "ticket.tasks.enforce_daily_pause_limits",
            "schedule": 60.0,
        },
    }

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
LOCALE_PATHS = [BASE_DIR / "locales"]

STATIC_URL = "static/"
MEDIA_URL = "media/"

STATIC_ROOT = BASE_DIR.parent / "cdn/static"
MEDIA_ROOT = BASE_DIR.parent / "cdn/media"

# Logging
LOGGING_TELEGRAM_BOT_TOKEN = config("LOGGING_TELEGRAM_BOT_TOKEN", default="")
LOGGING_TELEGRAM_CHAT_ID = config("LOGGING_TELEGRAM_CHAT_ID", default="")

# Telegram Bot
BOT_TOKEN = config("BOT_TOKEN", default="")
BOT_MODE = config("BOT_MODE", default="polling")
BOT_WEBHOOK_BASE_URL = config("BOT_WEBHOOK_BASE_URL", default="")
BOT_WEBHOOK_PATH = config("BOT_WEBHOOK_PATH", default="/bot/webhook/")
BOT_WEBHOOK_SECRET = config("BOT_WEBHOOK_SECRET", default="")
BOT_PARSE_MODE = config("BOT_PARSE_MODE", default="HTML")
BOT_DEFAULT_LOCALE = config("BOT_DEFAULT_LOCALE", default="uz")
BOT_FALLBACK_LOCALE = config("BOT_FALLBACK_LOCALE", default="uz")
BOT_MINIAPP_URL = config("BOT_MINIAPP_URL", default="")
TMA_INIT_DATA_MAX_AGE_SECONDS = config(
    "TMA_INIT_DATA_MAX_AGE_SECONDS", default=300, cast=int
)
TMA_INIT_DATA_MAX_FUTURE_SKEW_SECONDS = config(
    "TMA_INIT_DATA_MAX_FUTURE_SKEW_SECONDS", default=30, cast=int
)
TMA_INIT_DATA_REPLAY_TTL_SECONDS = config(
    "TMA_INIT_DATA_REPLAY_TTL_SECONDS", default=300, cast=int
)
SENTRY_DSN = config("SENTRY_DSN", default="")
SENTRY_ENVIRONMENT = config(
    "SENTRY_ENVIRONMENT",
    default="development" if DEBUG else "production",
)
SENTRY_RELEASE = config("SENTRY_RELEASE", default="")
SENTRY_TRACES_SAMPLE_RATE = config(
    "SENTRY_TRACES_SAMPLE_RATE",
    default=0.0,
    cast=float,
)
SENTRY_PROFILES_SAMPLE_RATE = config(
    "SENTRY_PROFILES_SAMPLE_RATE",
    default=0.0,
    cast=float,
)
SENTRY_SEND_DEFAULT_PII = config(
    "SENTRY_SEND_DEFAULT_PII",
    default=False,
    cast=bool,
)


def _clamp_sample_rate(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _is_valid_sentry_dsn(value: str) -> bool:
    parsed = urlparse(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


SENTRY_TRACES_SAMPLE_RATE = _clamp_sample_rate(SENTRY_TRACES_SAMPLE_RATE)
SENTRY_PROFILES_SAMPLE_RATE = _clamp_sample_rate(SENTRY_PROFILES_SAMPLE_RATE)
SENTRY_ENABLED = bool(HAS_SENTRY_SDK and _is_valid_sentry_dsn(SENTRY_DSN))
if SENTRY_ENABLED:
    sentry_integrations = [DjangoIntegration()]
    if HAS_CELERY:
        sentry_integrations.append(CeleryIntegration())

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=SENTRY_ENVIRONMENT,
        release=SENTRY_RELEASE or None,
        traces_sample_rate=SENTRY_TRACES_SAMPLE_RATE,
        profiles_sample_rate=SENTRY_PROFILES_SAMPLE_RATE,
        send_default_pii=SENTRY_SEND_DEFAULT_PII,
        integrations=sentry_integrations,
    )

# Ensure logs directory exists
os.makedirs(LOGS_ROOT, exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "request_context": {
            "()": "core.utils.logging.RequestContextFilter",
        },
    },
    "formatters": {
        "colored": {
            "()": "colorlog.ColoredFormatter",
            "format": (
                "%(log_color)s[%(asctime)s] [%(levelname)s] [request_id=%(request_id)s] "
                "%(name)s:%(module)s:%(filename)s:%(lineno)d "
                "%(funcName)s | %(message)s"
            ),
            "datefmt": "%Y-%m-%d %H:%M:%S",
            "log_colors": {
                "DEBUG": "white",
                "INFO": "green",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "bold_red",
            },
        },
        "verbose": {
            "format": (
                "[%(asctime)s] [%(levelname)s] [request_id=%(request_id)s] "
                "%(name)s:%(module)s:%(filename)s:%(lineno)d "
                "%(funcName)s | %(message)s"
            ),
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "telegram": {
            "format": (
                "🚨 <b>Django Error Alert</b>\n"
                "🔴 <b>Level:</b> %(levelname)s\n"
                "💬 <b>Message:</b> %(message)s\n\n"
                "📍 <b>Location</b>\n"
                "• Module: <code>%(module)s:%(filename)s:%(lineno)d</code>\n"
                "• Function: <code>%(funcName)s</code>\n\n"
                "🌐 <b>Request Context</b>\n"
                "• User: %(user)s\n"
                "• Method: %(method)s\n"
                "• Path: %(path)s\n"
                "• IP: %(ip)s\n"
                "• Request ID: <code>%(request_id)s</code>\n\n"
                "🧵 <b>Traceback</b>\n<pre>%(traceback)s</pre>"
            )
        },
    },
    "handlers": {
        # Console
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "colored",
            "filters": ["request_context"],
        },
        # Main app log (rotating)
        "app_file": {
            "level": "INFO",
            "class": "logging.handlers.TimedRotatingFileHandler",
            "filename": LOGS_ROOT / "app.log",
            "when": "midnight",
            "backupCount": 30,
            "formatter": "verbose",
            "filters": ["request_context"],
        },
        # Error log (rotating)
        "error_file": {
            "level": "ERROR",
            "class": "logging.handlers.TimedRotatingFileHandler",
            "filename": LOGS_ROOT / "error.log",
            "when": "midnight",
            "backupCount": 60,
            "formatter": "verbose",
            "filters": ["request_context"],
        },
        # Slow queries
        "slow_queries_file": {
            "level": "WARNING",
            "class": "logging.handlers.TimedRotatingFileHandler",
            "filename": LOGS_ROOT / "slow_queries.log",
            "when": "midnight",
            "backupCount": 30,
            "formatter": "verbose",
            "filters": ["request_context"],
        },
        # Telegram alerts
        "telegram_errors": {
            "level": "ERROR",
            "class": "core.utils.logging.TelegramErrorHandler",
            "bot_token": LOGGING_TELEGRAM_BOT_TOKEN,
            "chat_id": LOGGING_TELEGRAM_CHAT_ID,
            "filters": ["request_context"],
            "formatter": "telegram",
        },
    },
    "loggers": {
        # Django internal logs
        "django": {
            "handlers": ["app_file", "console"],
            "level": "INFO",
            "propagate": False,
        },
        # Django request errors → TELEGRAM!
        "django.request": {
            "handlers": ["telegram_errors", "error_file"],
            "level": "ERROR",
            "propagate": False,
        },
        # Slow queries
        "django.db.backends": {
            "handlers": ["slow_queries_file"],
            "level": "WARNING",
            "propagate": False,
        },
        # Universal logger (entire project)
        "": {
            "handlers": ["app_file", "console"],
            "level": "INFO",
        },
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication"
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "core.utils.pagination.CustomPagination",
    "PAGE_SIZE": 10,
    "EXCEPTION_HANDLER": "core.api.exceptions.custom_exception_handler",  # noqa
}
if HAS_DRF_SPECTACULAR:
    REST_FRAMEWORK["DEFAULT_SCHEMA_CLASS"] = "drf_spectacular.openapi.AutoSchema"

if HAS_DRF_SPECTACULAR:
    SPECTACULAR_SETTINGS = {
        "TITLE": "Rent Market API",
        "DESCRIPTION": (
            "Versioned API documentation for operations, rules, and bot-linked auth."
        ),
        "VERSION": "v1",
        "SERVE_INCLUDE_SCHEMA": False,
        "SCHEMA_PATH_PREFIX": r"/api/v[0-9]",
        "TAGS": [
            {
                "name": "Auth",
                "description": "JWT and Telegram Mini App authentication endpoints.",
            },
            {
                "name": "Users / Profile",
                "description": "Authenticated user profile endpoints.",
            },
            {
                "name": "Users / Access Requests",
                "description": "Onboarding requests and moderation workflow.",
            },
            {
                "name": "Attendance",
                "description": "Daily check-in/check-out and attendance state.",
            },
            {
                "name": "Inventory",
                "description": "Inventory structure and item lifecycle endpoints.",
            },
            {
                "name": "Analytics",
                "description": "Operational fleet and team KPI snapshots.",
            },
            {
                "name": "Tickets / Workflow",
                "description": "Ticket lifecycle and transition endpoints.",
            },
            {
                "name": "Tickets / Work Sessions",
                "description": "Technician timer workflow endpoints per ticket.",
            },
            {
                "name": "XP Transactions",
                "description": "Gamification XP transaction query surface.",
            },
            {
                "name": "Rules Engine",
                "description": "Rules config management, history, and rollback.",
            },
            {
                "name": "System / Health",
                "description": "System health and connectivity checks.",
            },
            {
                "name": "System / Audit Feed",
                "description": "Operational feed combining transitions, XP and attendance.",
            },
        ],
    }

AUTH_USER_MODEL = "account.User"  # noqa

UNFOLD = {
    "SITE_URL": "/admin/",
    "SITE_TITLE": "DJANGO REST Template",
    "SITE_HEADER": "DJANGO REST Template",
    "SITE_SUBHEADER": lambda request: (
        request.user.get_navigation_title()
        if request.user.is_authenticated
        else "Unknown User"
    ),
    "SIDEBAR": {
        "show_search": False,
    },
}

CORS_URLS_REGEX = r"^/api/.*$"
