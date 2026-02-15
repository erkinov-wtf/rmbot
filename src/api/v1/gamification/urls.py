from django.urls import path

from api.v1.gamification.views import XPTransactionListAPIView

app_name = "gamification"

urlpatterns = [
    path(
        "transactions/",
        XPTransactionListAPIView.as_view(),
        name="xp-transaction-list",
    ),
]
