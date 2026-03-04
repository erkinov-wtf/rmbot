from core.api.permissions import HasRole
from core.utils.constants import RoleSlug

TicketCreatePermission = HasRole.as_any(
    RoleSlug.MASTER,
    RoleSlug.SUPER_ADMIN,
)
TicketAssignPermission = HasRole.as_any(
    RoleSlug.MASTER,
    RoleSlug.SUPER_ADMIN,
)
TicketReviewPermission = HasRole.as_any(
    RoleSlug.MASTER,
    RoleSlug.SUPER_ADMIN,
)
TicketManualMetricsPermission = TicketReviewPermission
TicketWorkPermission = HasRole.as_any(RoleSlug.TECHNICIAN)
TicketQCPermission = HasRole.as_any(
    RoleSlug.QC_INSPECTOR,
    RoleSlug.SUPER_ADMIN,
)
