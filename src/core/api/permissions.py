from rest_framework.permissions import BasePermission

from core.utils.constants import RoleSlug


class HasRole(BasePermission):
    """
    Permission that grants access if user has at least one of the required roles.

    Usage:
        permission_classes = [HasRole.as_any(RoleSlug.SUPER_ADMIN, RoleSlug.OPS_MANAGER)]
    """

    required_roles: tuple[RoleSlug, ...] = ()

    def has_permission(self, request, view) -> bool:  # type: ignore[override]
        user = request.user
        if not user or not user.is_authenticated:
            return False
        role_slugs = set(user.roles.values_list("slug", flat=True))
        return any(slug in role_slugs for slug in self.required_roles)

    @classmethod
    def as_any(cls, *roles: RoleSlug) -> "HasRole":
        class _Inner(cls):
            required_roles = roles

        _Inner.__name__ = f"HasRole_{'_'.join(roles) or 'None'}"
        return _Inner
