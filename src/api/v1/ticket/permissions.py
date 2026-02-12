from core.api.permissions import HasRole
from core.utils.constants import RoleSlug

TicketCreatePermission = HasRole.as_any(RoleSlug.MASTER, RoleSlug.SUPER_ADMIN)
TicketAssignPermission = HasRole.as_any(
    RoleSlug.SUPER_ADMIN, RoleSlug.OPS_MANAGER, RoleSlug.MASTER
)
TicketWorkPermission = HasRole.as_any(RoleSlug.TECHNICIAN, RoleSlug.SUPER_ADMIN)
TicketQCPermission = HasRole.as_any(RoleSlug.QC_INSPECTOR, RoleSlug.SUPER_ADMIN)
