from django.urls import path

from api.v1.core.views.auth import (
    LoginAPIView,
    MiniAppPhoneLoginAPIView,
    RefreshAPIView,
    TMAInitDataVerifyAPIView,
    TokenVerifyAPIView,
)

app_name = "auth"

urlpatterns = [
    path("login/", LoginAPIView.as_view(), name="login"),
    path(
        "miniapp/phone-login/",
        MiniAppPhoneLoginAPIView.as_view(),
        name="miniapp_phone_login",
    ),
    path("refresh/", RefreshAPIView.as_view(), name="token_refresh"),
    path("verify/", TokenVerifyAPIView.as_view(), name="token_verify"),
    path("tma/verify/", TMAInitDataVerifyAPIView.as_view(), name="tma_verify"),
]
