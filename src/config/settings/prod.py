from datetime import timedelta

from . import base as base_settings

DEBUG = False
BOT_MODE = "webhook"

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=6),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

for setting_name in dir(base_settings):
    if setting_name.isupper() and setting_name not in globals():
        globals()[setting_name] = getattr(base_settings, setting_name)
