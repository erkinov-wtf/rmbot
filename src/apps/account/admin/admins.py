from django.contrib import admin

from account.models import User, Role, TelegramProfile, AccessRequest
from core.admin import BaseModelAdmin


@admin.register(User)
class UserAdmin(BaseModelAdmin):
    list_display = ("id", "phone", "first_name", "last_name", "patronymic", "is_active")
    search_fields = ("phone", "first_name", "last_name", "patronymic")
    ordering = ("-created_at",)
    exclude = ("last_login", "deleted_at")
    list_display_links = ("id", "phone")


@admin.register(Role)
class RoleAdmin(BaseModelAdmin):
    list_display = ("id", "name", "slug", "created_at")
    search_fields = ("name", "slug")


@admin.register(TelegramProfile)
class TelegramProfileAdmin(BaseModelAdmin):
    list_display = ("id", "telegram_id", "username", "user", "verified_at", "created_at")
    search_fields = ("telegram_id", "username")
    list_filter = ("verified_at",)


@admin.register(AccessRequest)
class AccessRequestAdmin(BaseModelAdmin):
    list_display = ("id", "telegram_id", "username", "status", "user", "created_at", "resolved_at")
    search_fields = ("telegram_id", "username", "first_name", "last_name")
    list_filter = ("status",)
