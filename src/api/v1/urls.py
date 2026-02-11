from django.urls import path, include

app_name = "url_router"

urlpatterns = [
    path("users/", include("api.v1.account.urls", namespace="account")),
    path("auth/", include("api.v1.core.urls.auth", namespace="auth")),
    path("attendance/", include("api.v1.attendance.urls", namespace="attendance")),
    path("xp/", include("api.v1.gamification.urls", namespace="gamification")),
    path("bikes/", include("api.v1.bike.urls", namespace="bike")),
    path("tickets/", include("api.v1.ticket.urls", namespace="ticket")),
    path("misc/", include("api.v1.core.urls.misc", namespace="health")),
]
