from rest_framework.permissions import BasePermission

from core.api.permissions import HasRole
from core.utils.constants import RoleSlug

TicketCreatePermission = HasRole.as_any(
    RoleSlug.MASTER,
    RoleSlug.SUPER_ADMIN,
    RoleSlug.TECHNICIAN,
)


class TicketEditPermission(BasePermission):
    admin_roles = {RoleSlug.MASTER, RoleSlug.SUPER_ADMIN}
    allowed_roles = admin_roles | {RoleSlug.TECHNICIAN}

    @staticmethod
    def _role_slugs(request) -> set[str]:
        user = request.user
        if not user or not user.is_authenticated:
            return set()
        if user.is_superuser:
            return {RoleSlug.SUPER_ADMIN}

        role_slugs: set[str] = set()
        if hasattr(request, "auth") and request.auth:
            role_slugs_from_token = request.auth.get("role_slugs", [])
            if role_slugs_from_token:
                role_slugs = set(role_slugs_from_token)

        if not role_slugs:
            role_slugs = set(user.roles.values_list("slug", flat=True))
        return role_slugs

    def has_permission(self, request, view) -> bool:  # type: ignore[override]
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        return bool(self._role_slugs(request) & self.allowed_roles)

    def has_object_permission(self, request, view, obj) -> bool:  # type: ignore[override]
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        return bool(self._role_slugs(request) & self.allowed_roles)


TicketAssignPermission = HasRole.as_any(
    RoleSlug.MASTER,
    RoleSlug.SUPER_ADMIN,
)
TicketReviewPermission = HasRole.as_any(
    RoleSlug.MASTER,
    RoleSlug.SUPER_ADMIN,
)
TicketDeletePermission = TicketReviewPermission
TicketManualMetricsPermission = TicketReviewPermission
TicketWorkPermission = HasRole.as_any(RoleSlug.TECHNICIAN)
TicketQCPermission = HasRole.as_any(
    RoleSlug.QC_INSPECTOR,
    RoleSlug.SUPER_ADMIN,
)
