from django.urls import include, path

app_name = "url_router"

urlpatterns = [
    path("users/", include("api.v1.account.urls", namespace="account")),
    path("auth/", include("api.v1.core.urls.auth", namespace="auth")),
    path("analytics/", include("api.v1.core.urls.analytics", namespace="analytics")),
    path("rules/", include("api.v1.rules.urls", namespace="rules")),
    path("attendance/", include("api.v1.attendance.urls", namespace="attendance")),
    path("xp/", include("api.v1.gamification.urls", namespace="gamification")),
    path("payroll/", include("api.v1.payroll.urls", namespace="payroll")),
    path("inventory/", include("api.v1.inventory.urls", namespace="inventory")),
    path("tickets/", include("api.v1.ticket.urls", namespace="ticket")),
    path("misc/", include("api.v1.core.urls.misc", namespace="health")),
]
