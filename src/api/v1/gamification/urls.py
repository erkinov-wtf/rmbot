from django.urls import path

from api.v1.gamification.views import XPLedgerListAPIView

app_name = "gamification"

urlpatterns = [
    path("ledger/", XPLedgerListAPIView.as_view(), name="xp-ledger-list"),
]
