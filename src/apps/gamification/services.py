from django.db import IntegrityError

from gamification.models import XPLedger


def append_xp_entry(
    *,
    user_id: int,
    amount: int,
    entry_type: str,
    reference: str,
    description: str | None = None,
    payload: dict | None = None,
) -> tuple[XPLedger, bool]:
    try:
        entry = XPLedger.objects.create(
            user_id=user_id,
            amount=amount,
            entry_type=entry_type,
            reference=reference,
            description=description,
            payload=payload or {},
        )
        return entry, True
    except IntegrityError:
        # Idempotent behavior for repeated operations with same reference.
        existing = XPLedger.objects.get(reference=reference)
        return existing, False
