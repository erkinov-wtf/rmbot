from rest_framework.permissions import BasePermission

from core.utils.constants import RoleSlug


class HasRole(BasePermission):
    """
    Permission that grants access if user has at least one of the required roles.

    Checks roles from:
    1. JWT token claim 'role_slugs' (set by attach_user_role_claims during auth)
    2. Database user.roles relationship (loaded by select_related/prefetch_related)
    3. User is_superuser flag

    Usage:
        permission_classes = [HasRole.as_any(RoleSlug.SUPER_ADMIN, RoleSlug.OPS_MANAGER)]
    """

    required_roles: tuple[RoleSlug, ...] = ()

    def has_permission(self, request, view) -> bool:  # type: ignore[override]
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True

        # Try to get roles from JWT token first (set by attach_user_role_claims)
        role_slugs = set()
        if hasattr(request, "auth") and request.auth:
            role_slugs_from_token = request.auth.get("role_slugs", [])
            if role_slugs_from_token:
                role_slugs = set(role_slugs_from_token)

        # Fall back to database relationship (requires select_related/prefetch_related)
        if not role_slugs:
            role_slugs = set(user.roles.values_list("slug", flat=True))

        return any(slug in role_slugs for slug in self.required_roles)

    @classmethod
    def as_any(cls, *roles: RoleSlug) -> "HasRole":
        class _Inner(cls):
            required_roles = roles

        _Inner.__name__ = f"HasRole_{'_'.join(roles) or 'None'}"
        return _Inner
