from django.urls import include, path

app_name = "url_router"

urlpatterns = [
    path("v1/", include("api.v1.urls", namespace="v1")),
    # path("v2/", include("api.v2.urls", namespace="v2")),
]

try:
    from drf_spectacular.views import (
        SpectacularAPIView,
        SpectacularRedocView,
        SpectacularSwaggerView,
    )
except ModuleNotFoundError:
    # Schema/docs endpoints are enabled automatically once drf-spectacular is installed.
    SpectacularAPIView = SpectacularSwaggerView = SpectacularRedocView = None
else:
    urlpatterns = [
        path("schema/", SpectacularAPIView.as_view(), name="schema"),
        path(
            "docs/",
            SpectacularSwaggerView.as_view(url_name="url_router:schema"),
            name="swagger-ui",
        ),
        path(
            "redoc/",
            SpectacularRedocView.as_view(url_name="url_router:schema"),
            name="redoc",
        ),
        *urlpatterns,
    ]
