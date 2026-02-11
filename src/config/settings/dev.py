from datetime import timedelta

from . import base as base_settings

BOT_MODE = "polling"
DEBUG = base_settings.DEBUG
INSTALLED_APPS = [*base_settings.INSTALLED_APPS]
MIDDLEWARE = [*base_settings.MIDDLEWARE]


if DEBUG:
    INSTALLED_APPS += [
        "debug_toolbar",
        "django_extensions",
        "query_counter",
    ]

    MIDDLEWARE += [
        "debug_toolbar.middleware.DebugToolbarMiddleware",
        "query_counter.middleware.DjangoQueryCounterMiddleware",
    ]

    INTERNAL_IPS = ["127.0.0.1"]

    SIMPLE_JWT = {
        "ACCESS_TOKEN_LIFETIME": timedelta(days=1),
        "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
        "ROTATE_REFRESH_TOKENS": True,
        "BLACKLIST_AFTER_ROTATION": True,
        "AUTH_HEADER_TYPES": ("Bearer",),
    }

    CORS_ALLOW_ALL_ORIGINS = True

for setting_name in dir(base_settings):
    if setting_name.isupper() and setting_name not in globals():
        globals()[setting_name] = getattr(base_settings, setting_name)
