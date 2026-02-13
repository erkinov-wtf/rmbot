from django.urls import path

from api.v1.payroll.views import (
    PayrollMonthAllowanceDecisionAPIView,
    PayrollMonthApproveAPIView,
    PayrollMonthCloseAPIView,
    PayrollMonthDetailAPIView,
)

app_name = "payroll"

urlpatterns = [
    path(
        "<str:month>/", PayrollMonthDetailAPIView.as_view(), name="payroll-month-detail"
    ),
    path(
        "<str:month>/close/",
        PayrollMonthCloseAPIView.as_view(),
        name="payroll-month-close",
    ),
    path(
        "<str:month>/approve/",
        PayrollMonthApproveAPIView.as_view(),
        name="payroll-month-approve",
    ),
    path(
        "<str:month>/allowance-gate/decision/",
        PayrollMonthAllowanceDecisionAPIView.as_view(),
        name="payroll-month-allowance-gate-decision",
    ),
]
