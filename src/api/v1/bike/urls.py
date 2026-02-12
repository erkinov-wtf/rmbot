from django.urls import path

from api.v1.bike.views import BikeCreateAPIView, BikeListAPIView, BikeSuggestAPIView

app_name = "bike"

urlpatterns = [
    path("", BikeListAPIView.as_view(), name="bike-list"),
    path("suggest/", BikeSuggestAPIView.as_view(), name="bike-suggest"),
    path("create/", BikeCreateAPIView.as_view(), name="bike-create"),
]
