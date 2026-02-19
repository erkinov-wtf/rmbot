from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path


def _normalize_webhook_route(raw_path: str) -> str:
    route = str(raw_path or "").strip().strip("/")
    if not route:
        return "bot/webhook/"
    return f"{route}/"


webhook_route = _normalize_webhook_route(settings.BOT_WEBHOOK_PATH)

urlpatterns = [
    path(webhook_route, include("bot.webhook.urls", namespace="bot_webhook")),
#     path("admin/", admin.site.urls),
    path("api/", include("api.url_router"), name="url_router"),
    *static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT),
    *static(settings.STATIC_URL, document_root=settings.STATIC_ROOT),
]

if settings.DEBUG:
    from config.urls import dev

    urlpatterns += dev.urlpatterns
