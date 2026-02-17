from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

from rest_framework.permissions import BasePermission

from account.models import User
from api.v1.ticket.permissions import (
    TicketAssignPermission,
    TicketCreatePermission,
    TicketManualMetricsPermission,
    TicketQCPermission,
    TicketReviewPermission,
)


@dataclass(frozen=True)
class TicketBotPermissionSet:
    can_create: bool = False
    can_review: bool = False
    can_assign: bool = False
    can_manual_metrics: bool = False
    can_qc: bool = False

    @property
    def can_open_review_panel(self) -> bool:
        return self.can_review or self.can_assign or self.can_manual_metrics

    @property
    def can_approve_and_assign(self) -> bool:
        return self.can_review and self.can_assign


def _has_permission(
    *,
    user: User,
    permission_class: type[BasePermission],
) -> bool:
    request = SimpleNamespace(user=user)
    return bool(permission_class().has_permission(request=request, view=None))


def resolve_ticket_bot_permissions(*, user: User | None) -> TicketBotPermissionSet:
    if user is None or not user.is_active:
        return TicketBotPermissionSet()

    return TicketBotPermissionSet(
        can_create=_has_permission(
            user=user,
            permission_class=TicketCreatePermission,
        ),
        can_review=_has_permission(
            user=user,
            permission_class=TicketReviewPermission,
        ),
        can_assign=_has_permission(
            user=user,
            permission_class=TicketAssignPermission,
        ),
        can_manual_metrics=_has_permission(
            user=user,
            permission_class=TicketManualMetricsPermission,
        ),
        can_qc=_has_permission(
            user=user,
            permission_class=TicketQCPermission,
        ),
    )
