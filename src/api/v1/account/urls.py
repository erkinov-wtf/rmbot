from django.urls import path

from api.v1.account.views import (
    AccessRequestApproveAPIView,
    AccessRequestListAPIView,
    AccessRequestRejectAPIView,
    MeAPIView,
    UserOptionListAPIView,
)

app_name = "account"

urlpatterns = [
    path("me/", MeAPIView.as_view(), name="me"),
    path("options/", UserOptionListAPIView.as_view(), name="user-options"),
    path(
        "access-requests/", AccessRequestListAPIView.as_view(), name="access-requests"
    ),
    path(
        "access-requests/<int:pk>/approve/",
        AccessRequestApproveAPIView.as_view(),
        name="access-request-approve",
    ),
    path(
        "access-requests/<int:pk>/reject/",
        AccessRequestRejectAPIView.as_view(),
        name="access-request-reject",
    ),
]
