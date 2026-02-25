from django.urls import path

from api.v1.core.views.analytics import (
    AnalyticsFleetAPIView,
    AnalyticsTeamAPIView,
    PublicTechnicianDetailAPIView,
    PublicTechnicianLeaderboardAPIView,
    PublicTechnicianPhotoAPIView,
)

app_name = "analytics"

urlpatterns = [
    path("fleet/", AnalyticsFleetAPIView.as_view(), name="analytics-fleet-api"),
    path("team/", AnalyticsTeamAPIView.as_view(), name="analytics-team-api"),
    path(
        "public/leaderboard/",
        PublicTechnicianLeaderboardAPIView.as_view(),
        name="public-technician-leaderboard-api",
    ),
    path(
        "public/technicians/<int:user_id>/",
        PublicTechnicianDetailAPIView.as_view(),
        name="public-technician-detail-api",
    ),
    path(
        "public/technicians/<int:user_id>/photo/",
        PublicTechnicianPhotoAPIView.as_view(),
        name="public-technician-photo-api",
    ),
]
