from django.urls import path

from api.v1.bike.views import BikeViewSet

app_name = "bike"

bike_list = BikeViewSet.as_view({"get": "list", "post": "create"})
bike_detail = BikeViewSet.as_view(
    {
        "get": "retrieve",
        "put": "update",
        "patch": "partial_update",
        "delete": "destroy",
    }
)

urlpatterns = [
    path("", bike_list, name="bike-list"),
    path("<int:pk>/", bike_detail, name="bike-detail"),
]
