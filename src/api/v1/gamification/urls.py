from django.urls import path

from api.v1.gamification.views import (
    LevelControlOverviewAPIView,
    LevelControlSetLevelAPIView,
    LevelControlUserHistoryAPIView,
    WeeklyLevelEvaluationRunAPIView,
    XPAdjustmentCreateAPIView,
    XPTransactionListAPIView,
)

app_name = "gamification"

urlpatterns = [
    path(
        "transactions/",
        XPTransactionListAPIView.as_view(),
        name="xp-transaction-list",
    ),
    path(
        "adjustments/",
        XPAdjustmentCreateAPIView.as_view(),
        name="xp-adjustment-create",
    ),
    path(
        "levels/overview/",
        LevelControlOverviewAPIView.as_view(),
        name="level-control-overview",
    ),
    path(
        "levels/evaluate/",
        WeeklyLevelEvaluationRunAPIView.as_view(),
        name="weekly-level-evaluation-run",
    ),
    path(
        "levels/users/<int:user_id>/history/",
        LevelControlUserHistoryAPIView.as_view(),
        name="level-control-user-history",
    ),
    path(
        "levels/users/<int:user_id>/set-level/",
        LevelControlSetLevelAPIView.as_view(),
        name="level-control-user-set-level",
    ),
]
