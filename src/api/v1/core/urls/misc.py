from django.urls import path

from api.v1.core.views.misc import (
    AuditFeedAPIView,
    HealthAPIView,
)

app_name = "misc"

urlpatterns = [
    path("health/", HealthAPIView.as_view(), name="health-api"),
    path("audit-feed/", AuditFeedAPIView.as_view(), name="audit-feed-api"),
]
