from django.urls import path

from api.v1.rules.views import (
    RulesConfigAPIView,
    RulesConfigHistoryAPIView,
    RulesConfigRollbackAPIView,
)

app_name = "rules"

urlpatterns = [
    path("config/", RulesConfigAPIView.as_view(), name="rules-config"),
    path(
        "config/history/",
        RulesConfigHistoryAPIView.as_view(),
        name="rules-config-history",
    ),
    path(
        "config/rollback/",
        RulesConfigRollbackAPIView.as_view(),
        name="rules-config-rollback",
    ),
]
