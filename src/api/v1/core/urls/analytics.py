from django.urls import path

from api.v1.core.views.analytics import AnalyticsFleetAPIView, AnalyticsTeamAPIView

app_name = "analytics"

urlpatterns = [
    path("fleet/", AnalyticsFleetAPIView.as_view(), name="analytics-fleet-api"),
    path("team/", AnalyticsTeamAPIView.as_view(), name="analytics-team-api"),
]
