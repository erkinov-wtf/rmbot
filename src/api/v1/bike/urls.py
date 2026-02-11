from django.urls import path

from api.v1.bike.views import BikeCreateAPIView, BikeListAPIView

app_name = "bike"

urlpatterns = [
    path("", BikeListAPIView.as_view(), name="bike-list"),
    path("create/", BikeCreateAPIView.as_view(), name="bike-create"),
]
