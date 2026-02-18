from core.api.permissions import HasRole
from core.utils.constants import RoleSlug

RulesReadPermission = HasRole.as_any(RoleSlug.SUPER_ADMIN, RoleSlug.OPS_MANAGER)
RulesWritePermission = HasRole.as_any(RoleSlug.SUPER_ADMIN)
