from django.contrib import admin

from account.models import AccessRequest, Role, TelegramProfile, User, UserRole
from core.admin import SoftDeleteModelAdmin


class UserRoleInline(admin.TabularInline):
    model = UserRole
    extra = 0
    autocomplete_fields = ("role",)
    exclude = ("deleted_at",)


@admin.register(User)
class UserAdmin(SoftDeleteModelAdmin):
    list_display = ("id", "phone", "first_name", "last_name", "patronymic", "is_active")
    search_fields = ("phone", "first_name", "last_name", "patronymic")
    ordering = ("-created_at",)
    exclude = ("last_login", "deleted_at")
    list_display_links = ("id", "phone")
    inlines = (UserRoleInline,)


@admin.register(Role)
class RoleAdmin(SoftDeleteModelAdmin):
    list_display = ("id", "name", "slug", "created_at")
    search_fields = ("name", "slug")


@admin.register(UserRole)
class UserRoleAdmin(SoftDeleteModelAdmin):
    list_display = ("id", "user", "role", "created_at")
    search_fields = ("user__username", "user__phone", "role__name", "role__slug")
    list_filter = ("role",)
    autocomplete_fields = ("user", "role")


@admin.register(TelegramProfile)
class TelegramProfileAdmin(SoftDeleteModelAdmin):
    list_display = (
        "id",
        "telegram_id",
        "username",
        "user",
        "verified_at",
        "created_at",
    )
    search_fields = ("telegram_id", "username")
    list_filter = ("verified_at",)


@admin.register(AccessRequest)
class AccessRequestAdmin(SoftDeleteModelAdmin):
    list_display = (
        "id",
        "telegram_id",
        "username",
        "status",
        "user",
        "created_at",
        "resolved_at",
    )
    search_fields = ("telegram_id", "username", "first_name", "last_name")
    list_filter = ("status",)
