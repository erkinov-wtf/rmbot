from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from random import Random
from typing import Any

from django.core.management import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from account.models import Role, User, UserRole
from core.utils.constants import (
    InventoryItemStatus,
    RoleSlug,
    TicketColor,
    TicketStatus,
    TicketTransitionAction,
    XPTransactionEntryType,
)
from gamification.models import XPTransaction
from inventory.models import (
    Inventory,
    InventoryItem,
    InventoryItemCategory,
    InventoryItemPart,
)
from ticket.models import Ticket, TicketPartSpec, TicketTransition


@dataclass(frozen=True)
class UserSeedSpec:
    username: str
    first_name: str
    last_name: str
    role_slugs: tuple[str, ...]


@dataclass(frozen=True)
class SeedOptions:
    users: int
    items: int
    tickets: int
    parts_per_item: int
    categories: int
    lookback_days: int
    seed: int
    run_tag: str
    batch_size: int


class Command(BaseCommand):
    help = "Generate large historical mock data for users, inventory, parts, tickets, transitions, and XP."

    USER_CAP = 10

    ROLE_NAME_BY_SLUG: dict[str, str] = {
        RoleSlug.SUPER_ADMIN: "Super Admin",
        RoleSlug.OPS_MANAGER: "Ops Manager",
        RoleSlug.MASTER: "Master",
        RoleSlug.TECHNICIAN: "Technician",
        RoleSlug.QC_INSPECTOR: "QC Inspector",
    }

    USER_SEEDS: tuple[UserSeedSpec, ...] = (
        UserSeedSpec(
            username="mock_super_admin",
            first_name="Mock",
            last_name="SuperAdmin",
            role_slugs=(RoleSlug.SUPER_ADMIN,),
        ),
        UserSeedSpec(
            username="mock_ops_1",
            first_name="Mock",
            last_name="OpsOne",
            role_slugs=(RoleSlug.OPS_MANAGER,),
        ),
        UserSeedSpec(
            username="mock_master_1",
            first_name="Mock",
            last_name="MasterOne",
            role_slugs=(RoleSlug.MASTER,),
        ),
        UserSeedSpec(
            username="mock_tech_1",
            first_name="Mock",
            last_name="TechOne",
            role_slugs=(RoleSlug.TECHNICIAN,),
        ),
        UserSeedSpec(
            username="mock_qc_1",
            first_name="Mock",
            last_name="QCOne",
            role_slugs=(RoleSlug.QC_INSPECTOR,),
        ),
        UserSeedSpec(
            username="mock_master_2",
            first_name="Mock",
            last_name="MasterTwo",
            role_slugs=(RoleSlug.MASTER,),
        ),
        UserSeedSpec(
            username="mock_tech_2",
            first_name="Mock",
            last_name="TechTwo",
            role_slugs=(RoleSlug.TECHNICIAN,),
        ),
        UserSeedSpec(
            username="mock_tech_3",
            first_name="Mock",
            last_name="TechThree",
            role_slugs=(RoleSlug.TECHNICIAN,),
        ),
        UserSeedSpec(
            username="mock_tech_4",
            first_name="Mock",
            last_name="TechFour",
            role_slugs=(RoleSlug.TECHNICIAN,),
        ),
        UserSeedSpec(
            username="mock_qc_2",
            first_name="Mock",
            last_name="QCTwo",
            role_slugs=(RoleSlug.QC_INSPECTOR,),
        ),
    )

    TICKET_STATUSES: tuple[str, ...] = (
        TicketStatus.UNDER_REVIEW,
        TicketStatus.NEW,
        TicketStatus.ASSIGNED,
        TicketStatus.IN_PROGRESS,
        TicketStatus.WAITING_QC,
        TicketStatus.REWORK,
        TicketStatus.DONE,
    )

    ACTIVE_TICKET_STATUSES: set[str] = {
        TicketStatus.UNDER_REVIEW,
        TicketStatus.NEW,
        TicketStatus.ASSIGNED,
        TicketStatus.IN_PROGRESS,
        TicketStatus.WAITING_QC,
        TicketStatus.REWORK,
    }

    INVENTORY_STATUSES: tuple[str, ...] = (
        InventoryItemStatus.READY,
        InventoryItemStatus.IN_SERVICE,
        InventoryItemStatus.RENTED,
        InventoryItemStatus.BLOCKED,
        InventoryItemStatus.WRITE_OFF,
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--users",
            type=int,
            default=10,
            help="Requested mock user count (hard-capped to 10).",
        )
        parser.add_argument(
            "--items",
            type=int,
            default=5000,
            help="Inventory item count to generate.",
        )
        parser.add_argument(
            "--tickets",
            type=int,
            default=5000,
            help="Ticket count to generate.",
        )
        parser.add_argument(
            "--parts-per-item",
            type=int,
            default=6,
            help="Inventory parts per inventory item.",
        )
        parser.add_argument(
            "--categories",
            type=int,
            default=24,
            help="Inventory category count.",
        )
        parser.add_argument(
            "--lookback-days",
            type=int,
            default=720,
            help="How far back to spread historical timestamps uniformly.",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=42,
            help="Random seed for reproducible generation.",
        )
        parser.add_argument(
            "--run-tag",
            type=str,
            required=False,
            help="Optional run tag used in generated names/references.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=2000,
            help="Bulk insert batch size.",
        )

    def handle(self, *args, **options) -> None:
        requested_users = self._positive_int(options.get("users"), "users")
        resolved_users = min(requested_users, self.USER_CAP)
        if requested_users > self.USER_CAP:
            self.stdout.write(
                self.style.WARNING(
                    f"Requested {requested_users} users, capped to {self.USER_CAP}."
                )
            )

        seed_options = SeedOptions(
            users=resolved_users,
            items=self._positive_int(options.get("items"), "items"),
            tickets=self._positive_int(options.get("tickets"), "tickets"),
            parts_per_item=self._positive_int(
                options.get("parts_per_item"), "parts-per-item"
            ),
            categories=self._positive_int(options.get("categories"), "categories"),
            lookback_days=self._positive_int(
                options.get("lookback_days"), "lookback-days"
            ),
            seed=int(options.get("seed", 42)),
            run_tag=self._resolve_run_tag(options.get("run_tag")),
            batch_size=self._positive_int(options.get("batch_size"), "batch-size"),
        )

        try:
            summary = self._generate(seed_options=seed_options)
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Mock data generation completed: tag={summary['run_tag']} "
                f"seed={summary['seed']} users_used={summary['users_used']}"
            )
        )
        self.stdout.write(
            "Created: "
            f"inventory={summary['inventories_created']} "
            f"categories={summary['categories_created']} "
            f"items={summary['items_created']} "
            f"parts={summary['parts_created']}"
        )
        self.stdout.write(
            "Tickets: "
            f"tickets={summary['tickets_created']} "
            f"transitions={summary['ticket_transitions_created']} "
            f"ticket_part_specs={summary['ticket_part_specs_created']}"
        )
        self.stdout.write(
            f"Gamification: xp_transactions={summary['xp_transactions_created']}"
        )
        self.stdout.write("Ticket status distribution:")
        for status in self.TICKET_STATUSES:
            self.stdout.write(
                f"  - {status}: {summary['status_counts'].get(status, 0)}"
            )

    @staticmethod
    def _positive_int(value: int | None, option_name: str) -> int:
        try:
            parsed = int(value or 0)
        except (TypeError, ValueError) as exc:
            raise CommandError(f"{option_name} must be an integer.") from exc
        if parsed <= 0:
            raise CommandError(f"{option_name} must be greater than zero.")
        return parsed

    @staticmethod
    def _resolve_run_tag(raw_tag: str | None) -> str:
        if raw_tag:
            normalized = re.sub(r"[^A-Za-z0-9]+", "", str(raw_tag)).upper()
            if not normalized:
                raise CommandError(
                    "run-tag must include at least one alphanumeric char."
                )
            return normalized[:18]
        return timezone.now().strftime("M%Y%m%d%H%M%S")

    @staticmethod
    def _uniform_dt(*, rng: Random, start: datetime, end: datetime) -> datetime:
        if end <= start:
            return start
        total_seconds = (end - start).total_seconds()
        return start + timedelta(seconds=rng.uniform(0.0, total_seconds))

    @classmethod
    def _next_dt(
        cls,
        *,
        rng: Random,
        base: datetime,
        min_minutes: int,
        max_minutes: int,
        range_end: datetime,
    ) -> datetime:
        low = base + timedelta(minutes=min_minutes)
        if low >= range_end:
            return range_end
        high = min(base + timedelta(minutes=max_minutes), range_end)
        if high <= low:
            return low
        return cls._uniform_dt(rng=rng, start=low, end=high)

    @staticmethod
    def _ticket_color(total_minutes: int) -> str:
        if total_minutes <= 30:
            return TicketColor.GREEN
        if total_minutes <= 60:
            return TicketColor.YELLOW
        return TicketColor.RED

    def _generate(self, *, seed_options: SeedOptions) -> dict[str, Any]:
        rng = Random(seed_options.seed)
        now_dt = timezone.now()
        start_dt = now_dt - timedelta(days=seed_options.lookback_days)
        ticket_created_end = now_dt - timedelta(minutes=15)

        serial_token = seed_options.run_tag[-10:]
        serial_prefix = f"RM-{serial_token}"
        category_prefix = f"{seed_options.run_tag}-CAT-"

        with transaction.atomic():
            if InventoryItem.all_objects.filter(
                serial_number__startswith=f"{serial_prefix}-"
            ).exists():
                raise CommandError(
                    "Detected existing inventory serials for this run-tag. Use a different --run-tag."
                )
            if InventoryItemCategory.all_objects.filter(
                name__startswith=category_prefix
            ).exists():
                raise CommandError(
                    "Detected existing categories for this run-tag. Use a different --run-tag."
                )

            roles_by_slug = self._ensure_roles()
            user_payload = self._ensure_users(
                roles_by_slug=roles_by_slug,
                users_limit=seed_options.users,
            )

            all_user_ids: list[int] = user_payload["all_user_ids"]
            users_by_role: dict[str, list[int]] = user_payload["users_by_role"]

            master_ids = users_by_role.get(RoleSlug.MASTER, []) or all_user_ids
            technician_ids = users_by_role.get(RoleSlug.TECHNICIAN, []) or all_user_ids
            qc_ids = users_by_role.get(RoleSlug.QC_INSPECTOR, []) or all_user_ids
            ops_manager_ids = (
                users_by_role.get(RoleSlug.OPS_MANAGER, []) or all_user_ids
            )

            inventory = Inventory.objects.create(
                name=f"{seed_options.run_tag}-INVENTORY"
            )

            category_objs: list[InventoryItemCategory] = []
            for idx in range(seed_options.categories):
                created_at = self._uniform_dt(rng=rng, start=start_dt, end=now_dt)
                category_objs.append(
                    InventoryItemCategory(
                        name=f"{seed_options.run_tag}-CAT-{idx:03d}",
                        created_at=created_at,
                        updated_at=self._uniform_dt(
                            rng=rng,
                            start=created_at,
                            end=now_dt,
                        ),
                    )
                )
            InventoryItemCategory.objects.bulk_create(
                category_objs,
                batch_size=seed_options.batch_size,
            )
            category_ids = list(
                InventoryItemCategory.objects.filter(name__startswith=category_prefix)
                .order_by("id")
                .values_list("id", flat=True)
            )

            item_objs: list[InventoryItem] = []
            for idx in range(seed_options.items):
                category_id = rng.choice(category_ids)
                created_at = self._uniform_dt(rng=rng, start=start_dt, end=now_dt)
                item_objs.append(
                    InventoryItem(
                        inventory=inventory,
                        category_id=category_id,
                        serial_number=f"{serial_prefix}-{idx:05d}",
                        name=f"{seed_options.run_tag}-ITEM-{idx:05d}",
                        status=rng.choice(self.INVENTORY_STATUSES),
                        is_active=rng.random() < 0.92,
                        created_at=created_at,
                        updated_at=self._uniform_dt(
                            rng=rng,
                            start=created_at,
                            end=now_dt,
                        ),
                    )
                )
            InventoryItem.objects.bulk_create(
                item_objs, batch_size=seed_options.batch_size
            )

            item_rows: list[tuple[int, int, datetime]] = list(
                InventoryItem.objects.filter(
                    serial_number__startswith=f"{serial_prefix}-"
                )
                .order_by("id")
                .values_list("id", "category_id", "created_at")
            )
            item_ids = [row[0] for row in item_rows]

            part_objs: list[InventoryItemPart] = []
            for item_id, category_id, item_created_at in item_rows:
                for part_idx in range(seed_options.parts_per_item):
                    part_created_at = self._uniform_dt(
                        rng=rng,
                        start=item_created_at,
                        end=now_dt,
                    )
                    part_objs.append(
                        InventoryItemPart(
                            category_id=category_id,
                            inventory_item_id=item_id,
                            name=f"{seed_options.run_tag}-PART-{part_idx:02d}",
                            created_at=part_created_at,
                            updated_at=self._uniform_dt(
                                rng=rng,
                                start=part_created_at,
                                end=now_dt,
                            ),
                        )
                    )
            InventoryItemPart.objects.bulk_create(
                part_objs,
                batch_size=seed_options.batch_size,
            )

            parts_by_item: dict[int, list[int]] = defaultdict(list)
            for item_id, part_id in InventoryItemPart.objects.filter(
                name__startswith=f"{seed_options.run_tag}-PART-"
            ).values_list("inventory_item_id", "id"):
                parts_by_item[int(item_id)].append(int(part_id))

            if seed_options.tickets <= len(item_ids):
                unique_item_ids = rng.sample(item_ids, seed_options.tickets)
            else:
                unique_item_ids = None

            active_item_ids: set[int] = set()
            status_counts: Counter[str] = Counter()
            ticket_objs: list[Ticket] = []
            ticket_plan: dict[str, dict[str, Any]] = {}

            for idx in range(seed_options.tickets):
                item_id = (
                    unique_item_ids[idx]
                    if unique_item_ids is not None
                    else rng.choice(item_ids)
                )
                status = rng.choice(self.TICKET_STATUSES)

                if (
                    unique_item_ids is None
                    and status in self.ACTIVE_TICKET_STATUSES
                    and item_id in active_item_ids
                ):
                    status = TicketStatus.DONE
                if status in self.ACTIVE_TICKET_STATUSES:
                    active_item_ids.add(item_id)

                master_id = rng.choice(master_ids)
                ops_id = rng.choice(ops_manager_ids)
                technician_id = (
                    rng.choice(technician_ids)
                    if status
                    in {
                        TicketStatus.ASSIGNED,
                        TicketStatus.IN_PROGRESS,
                        TicketStatus.WAITING_QC,
                        TicketStatus.REWORK,
                        TicketStatus.DONE,
                    }
                    else None
                )
                qc_id = (
                    rng.choice(qc_ids)
                    if status
                    in {
                        TicketStatus.WAITING_QC,
                        TicketStatus.REWORK,
                        TicketStatus.DONE,
                    }
                    else None
                )

                created_at = self._uniform_dt(
                    rng=rng,
                    start=start_dt,
                    end=ticket_created_end,
                )
                approved_at = (
                    self._next_dt(
                        rng=rng,
                        base=created_at,
                        min_minutes=5,
                        max_minutes=72 * 60,
                        range_end=now_dt,
                    )
                    if status != TicketStatus.UNDER_REVIEW
                    else None
                )

                assigned_at = None
                started_at = None
                waiting_1_at = None
                qc_fail_at = None
                rework_started_at = None
                waiting_2_at = None
                qc_pass_at = None
                had_rework = False

                if technician_id is not None:
                    assigned_at = self._next_dt(
                        rng=rng,
                        base=approved_at or created_at,
                        min_minutes=5,
                        max_minutes=72 * 60,
                        range_end=now_dt,
                    )

                if status in {
                    TicketStatus.IN_PROGRESS,
                    TicketStatus.WAITING_QC,
                    TicketStatus.REWORK,
                    TicketStatus.DONE,
                }:
                    started_at = self._next_dt(
                        rng=rng,
                        base=assigned_at or created_at,
                        min_minutes=5,
                        max_minutes=24 * 60,
                        range_end=now_dt,
                    )

                if status in {
                    TicketStatus.WAITING_QC,
                    TicketStatus.REWORK,
                    TicketStatus.DONE,
                }:
                    waiting_1_at = self._next_dt(
                        rng=rng,
                        base=started_at or created_at,
                        min_minutes=10,
                        max_minutes=24 * 60,
                        range_end=now_dt,
                    )

                if status == TicketStatus.REWORK:
                    qc_fail_at = self._next_dt(
                        rng=rng,
                        base=waiting_1_at or created_at,
                        min_minutes=5,
                        max_minutes=8 * 60,
                        range_end=now_dt,
                    )

                if status == TicketStatus.DONE:
                    had_rework = rng.random() < 0.35
                    if had_rework:
                        qc_fail_at = self._next_dt(
                            rng=rng,
                            base=waiting_1_at or created_at,
                            min_minutes=5,
                            max_minutes=8 * 60,
                            range_end=now_dt,
                        )
                        rework_started_at = self._next_dt(
                            rng=rng,
                            base=qc_fail_at,
                            min_minutes=10,
                            max_minutes=24 * 60,
                            range_end=now_dt,
                        )
                        waiting_2_at = self._next_dt(
                            rng=rng,
                            base=rework_started_at,
                            min_minutes=10,
                            max_minutes=24 * 60,
                            range_end=now_dt,
                        )
                        qc_pass_at = self._next_dt(
                            rng=rng,
                            base=waiting_2_at,
                            min_minutes=5,
                            max_minutes=8 * 60,
                            range_end=now_dt,
                        )
                    else:
                        qc_pass_at = self._next_dt(
                            rng=rng,
                            base=waiting_1_at or created_at,
                            min_minutes=5,
                            max_minutes=8 * 60,
                            range_end=now_dt,
                        )

                finished_at = qc_pass_at if status == TicketStatus.DONE else None
                total_duration = (
                    max(1, int((qc_pass_at - started_at).total_seconds() // 60))
                    if status == TicketStatus.DONE and started_at and qc_pass_at
                    else rng.randint(15, 240)
                )
                flag_color = self._ticket_color(total_duration)
                xp_amount = max(1, math.ceil(total_duration / 20))
                is_manual = rng.random() < 0.2

                max_event = max(
                    dt
                    for dt in [
                        created_at,
                        approved_at,
                        assigned_at,
                        started_at,
                        waiting_1_at,
                        qc_fail_at,
                        rework_started_at,
                        waiting_2_at,
                        qc_pass_at,
                    ]
                    if dt is not None
                )
                updated_at = self._uniform_dt(rng=rng, start=max_event, end=now_dt)

                title = f"{seed_options.run_tag}-T-{idx:06d}"
                ticket_objs.append(
                    Ticket(
                        inventory_item_id=item_id,
                        master_id=master_id,
                        technician_id=technician_id,
                        title=title,
                        total_duration=total_duration,
                        approved_by_id=(
                            ops_id if status != TicketStatus.UNDER_REVIEW else None
                        ),
                        approved_at=approved_at,
                        flag_minutes=total_duration,
                        flag_color=flag_color,
                        xp_amount=xp_amount,
                        is_manual=is_manual,
                        status=status,
                        assigned_at=assigned_at,
                        started_at=started_at,
                        finished_at=finished_at,
                        created_at=created_at,
                        updated_at=updated_at,
                    )
                )
                status_counts[status] += 1
                ticket_plan[title] = {
                    "status": status,
                    "master_id": master_id,
                    "ops_id": ops_id,
                    "tech_id": technician_id,
                    "qc_id": qc_id,
                    "assigned_at": assigned_at,
                    "started_at": started_at,
                    "waiting_1_at": waiting_1_at,
                    "qc_fail_at": qc_fail_at,
                    "rework_started_at": rework_started_at,
                    "waiting_2_at": waiting_2_at,
                    "qc_pass_at": qc_pass_at,
                    "had_rework": had_rework,
                }

            Ticket.objects.bulk_create(ticket_objs, batch_size=seed_options.batch_size)

            tickets = list(
                Ticket.objects.filter(title__startswith=f"{seed_options.run_tag}-T-")
                .only(
                    "id",
                    "title",
                    "inventory_item_id",
                    "technician_id",
                    "xp_amount",
                    "created_at",
                    "updated_at",
                )
                .order_by("id")
            )

            transition_objs: list[TicketTransition] = []
            xp_objs: list[XPTransaction] = []
            spec_objs: list[TicketPartSpec] = []

            def add_transition(
                *,
                ticket_id: int,
                action: str,
                from_status: str | None,
                to_status: str,
                actor_id: int | None,
                event_at: datetime | None,
            ) -> None:
                if event_at is None:
                    return
                transition_objs.append(
                    TicketTransition(
                        ticket_id=ticket_id,
                        from_status=from_status,
                        to_status=to_status,
                        action=action,
                        actor_id=actor_id,
                        note=None,
                        metadata={"mock_run": seed_options.run_tag},
                        created_at=event_at,
                        updated_at=event_at,
                    )
                )

            for ticket in tickets:
                meta = ticket_plan[ticket.title]
                status = str(meta["status"])

                created_to = (
                    TicketStatus.UNDER_REVIEW
                    if status == TicketStatus.UNDER_REVIEW
                    else TicketStatus.NEW
                )
                add_transition(
                    ticket_id=ticket.id,
                    action=TicketTransitionAction.CREATED,
                    from_status=None,
                    to_status=created_to,
                    actor_id=meta["master_id"],
                    event_at=ticket.created_at,
                )

                if status not in {TicketStatus.UNDER_REVIEW, TicketStatus.NEW}:
                    add_transition(
                        ticket_id=ticket.id,
                        action=TicketTransitionAction.ASSIGNED,
                        from_status=created_to,
                        to_status=TicketStatus.ASSIGNED,
                        actor_id=meta["ops_id"],
                        event_at=meta["assigned_at"],
                    )

                if status in {
                    TicketStatus.IN_PROGRESS,
                    TicketStatus.WAITING_QC,
                    TicketStatus.REWORK,
                    TicketStatus.DONE,
                }:
                    add_transition(
                        ticket_id=ticket.id,
                        action=TicketTransitionAction.STARTED,
                        from_status=TicketStatus.ASSIGNED,
                        to_status=TicketStatus.IN_PROGRESS,
                        actor_id=meta["tech_id"],
                        event_at=meta["started_at"],
                    )

                if status in {
                    TicketStatus.WAITING_QC,
                    TicketStatus.REWORK,
                    TicketStatus.DONE,
                }:
                    add_transition(
                        ticket_id=ticket.id,
                        action=TicketTransitionAction.TO_WAITING_QC,
                        from_status=TicketStatus.IN_PROGRESS,
                        to_status=TicketStatus.WAITING_QC,
                        actor_id=meta["tech_id"],
                        event_at=meta["waiting_1_at"],
                    )

                if status == TicketStatus.REWORK:
                    add_transition(
                        ticket_id=ticket.id,
                        action=TicketTransitionAction.QC_FAIL,
                        from_status=TicketStatus.WAITING_QC,
                        to_status=TicketStatus.REWORK,
                        actor_id=meta["qc_id"],
                        event_at=meta["qc_fail_at"],
                    )

                if status == TicketStatus.DONE:
                    if bool(meta["had_rework"]):
                        add_transition(
                            ticket_id=ticket.id,
                            action=TicketTransitionAction.QC_FAIL,
                            from_status=TicketStatus.WAITING_QC,
                            to_status=TicketStatus.REWORK,
                            actor_id=meta["qc_id"],
                            event_at=meta["qc_fail_at"],
                        )
                        add_transition(
                            ticket_id=ticket.id,
                            action=TicketTransitionAction.STARTED,
                            from_status=TicketStatus.REWORK,
                            to_status=TicketStatus.IN_PROGRESS,
                            actor_id=meta["tech_id"],
                            event_at=meta["rework_started_at"],
                        )
                        add_transition(
                            ticket_id=ticket.id,
                            action=TicketTransitionAction.TO_WAITING_QC,
                            from_status=TicketStatus.IN_PROGRESS,
                            to_status=TicketStatus.WAITING_QC,
                            actor_id=meta["tech_id"],
                            event_at=meta["waiting_2_at"],
                        )

                    add_transition(
                        ticket_id=ticket.id,
                        action=TicketTransitionAction.QC_PASS,
                        from_status=TicketStatus.WAITING_QC,
                        to_status=TicketStatus.DONE,
                        actor_id=meta["qc_id"],
                        event_at=meta["qc_pass_at"],
                    )

                if ticket.technician_id and status == TicketStatus.DONE:
                    base_event_at = meta["qc_pass_at"] or ticket.updated_at
                    xp_objs.append(
                        XPTransaction(
                            user_id=ticket.technician_id,
                            amount=max(int(ticket.xp_amount or 0), 1),
                            entry_type=XPTransactionEntryType.TICKET_BASE_XP,
                            reference=f"mock:{seed_options.run_tag}:base:{ticket.id}",
                            description="Mock ticket base XP",
                            payload={
                                "ticket_id": ticket.id,
                                "mock_run": seed_options.run_tag,
                            },
                            created_at=base_event_at,
                            updated_at=base_event_at,
                        )
                    )
                    if not bool(meta["had_rework"]):
                        bonus_at = base_event_at + timedelta(seconds=1)
                        xp_objs.append(
                            XPTransaction(
                                user_id=ticket.technician_id,
                                amount=1,
                                entry_type=XPTransactionEntryType.TICKET_QC_FIRST_PASS_BONUS,
                                reference=f"mock:{seed_options.run_tag}:first_pass:{ticket.id}",
                                description="Mock first-pass bonus XP",
                                payload={
                                    "ticket_id": ticket.id,
                                    "mock_run": seed_options.run_tag,
                                },
                                created_at=bonus_at,
                                updated_at=bonus_at,
                            )
                        )

                if meta["qc_id"] and meta["qc_fail_at"] is not None:
                    fail_at = meta["qc_fail_at"]
                    xp_objs.append(
                        XPTransaction(
                            user_id=meta["qc_id"],
                            amount=1,
                            entry_type=XPTransactionEntryType.TICKET_QC_STATUS_UPDATE,
                            reference=f"mock:{seed_options.run_tag}:qc_fail:{ticket.id}",
                            description="Mock QC status update XP (fail)",
                            payload={
                                "ticket_id": ticket.id,
                                "action": "qc_fail",
                                "mock_run": seed_options.run_tag,
                            },
                            created_at=fail_at,
                            updated_at=fail_at,
                        )
                    )

                if meta["qc_id"] and meta["qc_pass_at"] is not None:
                    pass_at = meta["qc_pass_at"]
                    xp_objs.append(
                        XPTransaction(
                            user_id=meta["qc_id"],
                            amount=1,
                            entry_type=XPTransactionEntryType.TICKET_QC_STATUS_UPDATE,
                            reference=f"mock:{seed_options.run_tag}:qc_pass:{ticket.id}",
                            description="Mock QC status update XP (pass)",
                            payload={
                                "ticket_id": ticket.id,
                                "action": "qc_pass",
                                "mock_run": seed_options.run_tag,
                            },
                            created_at=pass_at,
                            updated_at=pass_at,
                        )
                    )

                part_ids = parts_by_item.get(ticket.inventory_item_id, [])
                if part_ids:
                    selected_count = min(len(part_ids), rng.randint(1, 3))
                    selected_part_ids = rng.sample(part_ids, selected_count)
                    for part_id in selected_part_ids:
                        spec_created_at = self._uniform_dt(
                            rng=rng,
                            start=ticket.created_at,
                            end=ticket.updated_at,
                        )
                        spec_objs.append(
                            TicketPartSpec(
                                ticket_id=ticket.id,
                                inventory_item_part_id=part_id,
                                color=rng.choice(
                                    [
                                        TicketColor.GREEN,
                                        TicketColor.YELLOW,
                                        TicketColor.RED,
                                    ]
                                ),
                                comment=f"mock:{seed_options.run_tag}",
                                minutes=rng.randint(5, 90),
                                created_at=spec_created_at,
                                updated_at=self._uniform_dt(
                                    rng=rng,
                                    start=spec_created_at,
                                    end=now_dt,
                                ),
                            )
                        )

            TicketTransition.objects.bulk_create(
                transition_objs,
                batch_size=seed_options.batch_size,
            )
            XPTransaction.objects.bulk_create(
                xp_objs, batch_size=seed_options.batch_size
            )
            TicketPartSpec.objects.bulk_create(
                spec_objs, batch_size=seed_options.batch_size
            )

        return {
            "run_tag": seed_options.run_tag,
            "seed": seed_options.seed,
            "users_used": seed_options.users,
            "users_created": user_payload["users_created"],
            "inventories_created": 1,
            "categories_created": len(category_objs),
            "items_created": len(item_objs),
            "parts_created": len(part_objs),
            "tickets_created": len(ticket_objs),
            "ticket_transitions_created": len(transition_objs),
            "ticket_part_specs_created": len(spec_objs),
            "xp_transactions_created": len(xp_objs),
            "status_counts": dict(status_counts),
        }

    def _ensure_roles(self) -> dict[str, Role]:
        roles_by_slug: dict[str, Role] = {}
        for slug, name in self.ROLE_NAME_BY_SLUG.items():
            role, _ = Role.all_objects.update_or_create(
                slug=slug,
                defaults={"name": name, "deleted_at": None},
            )
            roles_by_slug[slug] = role
        return roles_by_slug

    def _ensure_users(
        self,
        *,
        roles_by_slug: dict[str, Role],
        users_limit: int,
    ) -> dict[str, Any]:
        all_user_ids: list[int] = []
        users_by_role: dict[str, list[int]] = defaultdict(list)
        users_created = 0

        for index, seed in enumerate(self.USER_SEEDS[:users_limit], start=1):
            user = User.all_objects.filter(username=seed.username).first()
            level_value = ((index - 1) % 5) + 1

            if user is None:
                user = User.objects.create_user(
                    username=seed.username,
                    password="mockpass123",
                    first_name=seed.first_name,
                    last_name=seed.last_name,
                    is_active=True,
                    level=level_value,
                )
                users_created += 1
            else:
                User.all_objects.filter(pk=user.pk).update(
                    first_name=seed.first_name,
                    last_name=seed.last_name,
                    is_active=True,
                    deleted_at=None,
                    level=level_value,
                )
                user.refresh_from_db()

            all_user_ids.append(user.id)

            for role_slug in seed.role_slugs:
                role = roles_by_slug[role_slug]
                user_role, _ = UserRole.all_objects.get_or_create(
                    user_id=user.id,
                    role_id=role.id,
                    defaults={"deleted_at": None},
                )
                if user_role.deleted_at is not None:
                    UserRole.all_objects.filter(pk=user_role.pk).update(deleted_at=None)
                users_by_role[role_slug].append(user.id)

        return {
            "all_user_ids": all_user_ids,
            "users_by_role": dict(users_by_role),
            "users_created": users_created,
        }
