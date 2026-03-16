from __future__ import annotations

from django.db import transaction


class TicketDeleteService:
    @classmethod
    @transaction.atomic
    def delete_ticket(cls, *, ticket) -> None:
        ticket.delete()

    @classmethod
    @transaction.atomic
    def delete_queryset(cls, *, queryset) -> dict[str, int]:
        deleted_ticket_count = 0

        for ticket in queryset.order_by("id").iterator(chunk_size=200):
            cls.delete_ticket(ticket=ticket)
            deleted_ticket_count += 1

        return {"deleted_ticket_count": deleted_ticket_count}
