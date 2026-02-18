from django.urls import path

from api.v1.account.views import (
    AccessRequestApproveAPIView,
    AccessRequestListAPIView,
    AccessRequestRejectAPIView,
    MeAPIView,
    RoleListAPIView,
    UserManagementDetailAPIView,
    UserManagementListAPIView,
    UserOptionListAPIView,
)

app_name = "account"

urlpatterns = [
    path("me/", MeAPIView.as_view(), name="me"),
    path("options/", UserOptionListAPIView.as_view(), name="user-options"),
    path("roles/", RoleListAPIView.as_view(), name="roles"),
    path("management/", UserManagementListAPIView.as_view(), name="management-list"),
    path(
        "management/<int:pk>/",
        UserManagementDetailAPIView.as_view(),
        name="management-detail",
    ),
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
