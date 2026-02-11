from core.api.permissions import HasRole
from core.api.views import CreateAPIView, ListAPIView
from core.utils.constants import RoleSlug
from bike.models import Bike

from api.v1.bike.serializers import BikeSerializer


BikeManagePermission = HasRole.as_any(RoleSlug.SUPER_ADMIN, RoleSlug.OPS_MANAGER, RoleSlug.MASTER)


class BikeListAPIView(ListAPIView):
    serializer_class = BikeSerializer
    queryset = Bike.objects.all().order_by("-created_at")


class BikeCreateAPIView(CreateAPIView):
    serializer_class = BikeSerializer
    queryset = Bike.objects.all()
    permission_classes = (BikeManagePermission,)
