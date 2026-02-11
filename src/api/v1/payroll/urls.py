from django.urls import path

from api.v1.payroll.views import (
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
]
