from django.urls import path

from api.v1.gamification.views import XPAdjustmentCreateAPIView, XPTransactionListAPIView

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
]
