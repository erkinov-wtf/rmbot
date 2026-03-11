from __future__ import annotations

from collections import defaultdict

from django.core.management.base import BaseCommand
from django.utils import timezone

from ticket.models import WorkSession
from ticket.services_work_session import TicketWorkSessionService


class Command(BaseCommand):
    help = (
        "Stop stale open work sessions whose ticket is not IN_PROGRESS or no longer "
        "owned by the same technician."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--technician-id",
            type=int,
            dest="technician_id",
            default=None,
            help="Limit reconciliation to one technician id.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show stale sessions only, do not stop them.",
        )

    def handle(self, *args, **options):
        technician_id = options["technician_id"]
        dry_run = bool(options["dry_run"])

        open_sessions_qs = (
            WorkSession.domain.get_queryset().open().select_related("ticket")
        )
        if technician_id is not None:
            open_sessions_qs = open_sessions_qs.for_technician(
                technician_id=technician_id
            )

        open_sessions = list(open_sessions_qs.order_by("technician_id", "id"))
        stale_sessions = [
            session
            for session in open_sessions
            if not TicketWorkSessionService.is_open_session_consistent(session=session)
        ]

        self.stdout.write(f"Open sessions scanned: {len(open_sessions)}")
        self.stdout.write(f"Stale sessions found: {len(stale_sessions)}")

        if not stale_sessions:
            self.stdout.write(self.style.SUCCESS("No stale open work sessions detected."))
            return

        stale_by_technician: dict[int, list[WorkSession]] = defaultdict(list)
        for session in stale_sessions:
            stale_by_technician[int(session.technician_id)].append(session)

        for tech_id in sorted(stale_by_technician):
            session_ids = ", ".join(
                str(session.id) for session in stale_by_technician[tech_id]
            )
            self.stdout.write(f"Technician #{tech_id}: stale session ids [{session_ids}]")

        if dry_run:
            self.stdout.write(
                self.style.WARNING("Dry run enabled, no sessions were modified.")
            )
            return

        now = timezone.now()
        stopped_total = 0
        for tech_id in sorted(stale_by_technician):
            stopped_total += (
                TicketWorkSessionService.reconcile_open_sessions_for_technician(
                    technician_id=tech_id,
                    actor_user_id=tech_id,
                    now_dt=now,
                )
            )

        self.stdout.write(
            self.style.SUCCESS(f"Stopped stale open sessions: {stopped_total}")
        )
