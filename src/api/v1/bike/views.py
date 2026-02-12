from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.v1.bike.serializers import BikeSerializer, BikeSuggestionQuerySerializer
from bike.models import Bike
from bike.services import BikeService
from core.api.permissions import HasRole
from core.api.schema import extend_schema
from core.api.views import BaseAPIView, CreateAPIView, ListAPIView
from core.utils.constants import RoleSlug

BikeManagePermission = HasRole.as_any(
    RoleSlug.SUPER_ADMIN, RoleSlug.OPS_MANAGER, RoleSlug.MASTER
)


@extend_schema(
    tags=["Bikes"],
    summary="List bikes",
    description="Returns the fleet bike list ordered by newest records first.",
)
class BikeListAPIView(ListAPIView):
    serializer_class = BikeSerializer
    queryset = Bike.objects.all().order_by("-created_at")


@extend_schema(
    tags=["Bikes"],
    summary="Create bike",
    description="Creates a new bike record for operational tracking in the fleet.",
)
class BikeCreateAPIView(CreateAPIView):
    serializer_class = BikeSerializer
    queryset = Bike.objects.all()
    permission_classes = (BikeManagePermission,)


@extend_schema(
    tags=["Bikes"],
    summary="Suggest bike codes",
    description=(
        "Returns bike-code suggestions for intake lookups. Query requires at least 2 "
        "characters."
    ),
    parameters=[BikeSuggestionQuerySerializer],
)
class BikeSuggestAPIView(BaseAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = BikeSuggestionQuerySerializer

    def get(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        query = serializer.validated_data["q"]
        suggestions = BikeService.suggest_codes(query)
        return Response({"query": query, "suggestions": suggestions})
