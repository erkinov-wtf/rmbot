from api.v1.bike.serializers import BikeSerializer
from bike.models import Bike
from core.api.permissions import HasRole
from core.api.schema import extend_schema
from core.api.views import CreateAPIView, ListAPIView
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
