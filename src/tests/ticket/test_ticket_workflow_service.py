from __future__ import annotations

import uuid

import pytest

from account.models import Role, User
from core.api.exceptions import DomainValidationError
from core.utils.constants import (
    RoleSlug,
    TicketColor,
    TicketStatus,
    TicketTransitionAction,
    WorkSessionStatus,
)
from inventory.models import (
    Inventory,
    InventoryItem,
    InventoryItemCategory,
    InventoryItemPart,
)
from ticket.models import (
    Ticket,
    TicketPartQCFailure,
    TicketPartSpec,
    TicketTransition,
    WorkSession,
)
from ticket.services_work_session import TicketWorkSessionService
from ticket.services_workflow import TicketWorkflowService


@pytest.fixture
def role_cache(db):
    return {}


def _role(*, slug: str, cache: dict[str, Role]) -> Role:
    if slug not in cache:
        cache[slug], _ = Role.objects.get_or_create(
            slug=slug,
            defaults={"name": slug.replace("_", " ").title()},
        )
    return cache[slug]


def _user(*, username: str, role_slug: str, cache: dict[str, Role]) -> User:
    user = User.objects.create_user(
        username=username,
        password="pass1234",
        first_name=username,
        is_active=True,
    )
    user.roles.add(_role(slug=role_slug, cache=cache))
    return user


def _ticket_with_two_parts(
    *,
    master: User,
) -> tuple[Ticket, TicketPartSpec, TicketPartSpec]:
    suffix = uuid.uuid4().hex[:6]
    inventory = Inventory.objects.create(name=f"Main-{suffix}")
    category = InventoryItemCategory.objects.create(name=f"Category-{suffix}")
    item = InventoryItem.objects.create(
        inventory=inventory,
        category=category,
        name=f"Item-{suffix}",
        serial_number=f"RM-{suffix.upper()}",
    )
    part_a = InventoryItemPart.objects.create(category=category, name=f"PartA-{suffix}")
    part_b = InventoryItemPart.objects.create(category=category, name=f"PartB-{suffix}")

    ticket = Ticket.objects.create(
        inventory_item=item,
        master=master,
        status=TicketStatus.NEW,
        title="New workflow test ticket",
    )
    spec_a = TicketPartSpec.objects.create(
        ticket=ticket,
        inventory_item_part=part_a,
        color=TicketColor.GREEN,
        minutes=10,
    )
    spec_b = TicketPartSpec.objects.create(
        ticket=ticket,
        inventory_item_part=part_b,
        color=TicketColor.YELLOW,
        minutes=15,
    )
    return ticket, spec_a, spec_b


@pytest.mark.django_db
def test_technician_can_claim_ticket_from_common_pool(role_cache):
    master = _user(
        username="master_claim",
        role_slug=RoleSlug.MASTER,
        cache=role_cache,
    )
    tech_1 = _user(
        username="tech_claim_1",
        role_slug=RoleSlug.TECHNICIAN,
        cache=role_cache,
    )
    tech_2 = _user(
        username="tech_claim_2",
        role_slug=RoleSlug.TECHNICIAN,
        cache=role_cache,
    )
    ticket, _spec_a, _spec_b = _ticket_with_two_parts(master=master)

    claimable_for_tech_1 = (
        TicketWorkflowService.claimable_tickets_queryset_for_technician(
            technician_id=tech_1.id
        )
    )
    assert claimable_for_tech_1.filter(pk=ticket.pk).exists()

    TicketWorkflowService.claim_ticket(ticket=ticket, actor_user_id=tech_1.id)

    ticket.refresh_from_db()
    assert ticket.status == TicketStatus.ASSIGNED
    assert ticket.technician_id == tech_1.id

    claimable_for_tech_2 = (
        TicketWorkflowService.claimable_tickets_queryset_for_technician(
            technician_id=tech_2.id
        )
    )
    assert not claimable_for_tech_2.filter(pk=ticket.pk).exists()

    transition = TicketTransition.objects.filter(
        ticket=ticket,
        action=TicketTransitionAction.CLAIMED,
    ).latest("id")
    assert transition.metadata.get("claim_source") == "technician_pool"


@pytest.mark.django_db
def test_partial_completion_returns_ticket_to_pool_and_final_part_moves_to_waiting_qc(
    role_cache,
):
    master = _user(
        username="master_part_cycle",
        role_slug=RoleSlug.MASTER,
        cache=role_cache,
    )
    tech_1 = _user(
        username="tech_part_cycle_1",
        role_slug=RoleSlug.TECHNICIAN,
        cache=role_cache,
    )
    tech_2 = _user(
        username="tech_part_cycle_2",
        role_slug=RoleSlug.TECHNICIAN,
        cache=role_cache,
    )
    ticket, spec_a, spec_b = _ticket_with_two_parts(master=master)

    TicketWorkflowService.claim_ticket(ticket=ticket, actor_user_id=tech_1.id)
    TicketWorkflowService.complete_ticket_parts(
        ticket=ticket,
        actor_user_id=tech_1.id,
        part_payloads=[{"part_spec_id": spec_a.id, "note": "Fixed A"}],
    )

    ticket.refresh_from_db()
    spec_a.refresh_from_db()
    spec_b.refresh_from_db()

    assert ticket.status == TicketStatus.NEW
    assert ticket.technician_id is None
    assert spec_a.is_completed is True
    assert spec_a.completed_by_id == tech_1.id
    assert spec_a.completion_note == "Fixed A"
    assert spec_b.is_completed is False

    TicketWorkflowService.claim_ticket(ticket=ticket, actor_user_id=tech_2.id)
    TicketWorkflowService.complete_ticket_parts(
        ticket=ticket,
        actor_user_id=tech_2.id,
        part_payloads=[{"part_spec_id": spec_b.id, "note": "Fixed B"}],
    )

    ticket.refresh_from_db()
    spec_b.refresh_from_db()
    assert ticket.status == TicketStatus.WAITING_QC
    assert ticket.technician_id == tech_2.id
    assert spec_b.is_completed is True
    assert spec_b.completed_by_id == tech_2.id


@pytest.mark.django_db
def test_qc_fail_targets_only_failed_part_technicians(role_cache):
    master = _user(
        username="master_qc_fail",
        role_slug=RoleSlug.MASTER,
        cache=role_cache,
    )
    qc_user = _user(
        username="qc_qc_fail",
        role_slug=RoleSlug.QC_INSPECTOR,
        cache=role_cache,
    )
    tech_1 = _user(
        username="tech_qc_fail_1",
        role_slug=RoleSlug.TECHNICIAN,
        cache=role_cache,
    )
    tech_2 = _user(
        username="tech_qc_fail_2",
        role_slug=RoleSlug.TECHNICIAN,
        cache=role_cache,
    )
    tech_3 = _user(
        username="tech_qc_fail_3",
        role_slug=RoleSlug.TECHNICIAN,
        cache=role_cache,
    )
    ticket, spec_a, spec_b = _ticket_with_two_parts(master=master)

    TicketWorkflowService.claim_ticket(ticket=ticket, actor_user_id=tech_1.id)
    TicketWorkflowService.complete_ticket_parts(
        ticket=ticket,
        actor_user_id=tech_1.id,
        part_payloads=[{"part_spec_id": spec_a.id, "note": "Done by tech1"}],
    )
    TicketWorkflowService.claim_ticket(ticket=ticket, actor_user_id=tech_2.id)
    TicketWorkflowService.complete_ticket_parts(
        ticket=ticket,
        actor_user_id=tech_2.id,
        part_payloads=[{"part_spec_id": spec_b.id, "note": "Done by tech2"}],
    )

    ticket.refresh_from_db()
    assert ticket.status == TicketStatus.WAITING_QC

    TicketWorkflowService.qc_fail_ticket(
        ticket=ticket,
        actor_user_id=qc_user.id,
        failed_part_spec_ids=[spec_a.id, spec_b.id],
        note="Redo both parts",
    )

    ticket.refresh_from_db()
    spec_a.refresh_from_db()
    spec_b.refresh_from_db()

    assert ticket.status == TicketStatus.REWORK
    assert ticket.technician_id is None

    assert spec_a.is_completed is False
    assert spec_a.completed_by_id is None
    assert spec_a.completed_at is None
    assert spec_a.completion_note == ""
    assert spec_a.needs_rework is True
    assert spec_a.rework_for_technician_id == tech_1.id

    assert spec_b.is_completed is False
    assert spec_b.completed_by_id is None
    assert spec_b.completed_at is None
    assert spec_b.completion_note == ""
    assert spec_b.needs_rework is True
    assert spec_b.rework_for_technician_id == tech_2.id

    mappings = TicketPartQCFailure.all_objects.filter(ticket=ticket)
    assert mappings.count() == 2
    assert set(mappings.values_list("technician_id", flat=True)) == {
        tech_1.id,
        tech_2.id,
    }

    claimable_for_tech_1 = (
        TicketWorkflowService.claimable_tickets_queryset_for_technician(
            technician_id=tech_1.id
        )
    )
    claimable_for_tech_2 = (
        TicketWorkflowService.claimable_tickets_queryset_for_technician(
            technician_id=tech_2.id
        )
    )
    claimable_for_tech_3 = (
        TicketWorkflowService.claimable_tickets_queryset_for_technician(
            technician_id=tech_3.id
        )
    )

    assert claimable_for_tech_1.filter(pk=ticket.pk).exists()
    assert claimable_for_tech_2.filter(pk=ticket.pk).exists()
    assert not claimable_for_tech_3.filter(pk=ticket.pk).exists()

    with pytest.raises(DomainValidationError):
        TicketWorkflowService.claim_ticket(ticket=ticket, actor_user_id=tech_3.id)


@pytest.mark.django_db
def test_complete_ticket_parts_accepts_legacy_inventory_part_ids(role_cache):
    master = _user(
        username="master_complete_legacy_ids",
        role_slug=RoleSlug.MASTER,
        cache=role_cache,
    )
    tech = _user(
        username="tech_complete_legacy_ids",
        role_slug=RoleSlug.TECHNICIAN,
        cache=role_cache,
    )
    ticket, spec_a, spec_b = _ticket_with_two_parts(master=master)

    TicketWorkflowService.claim_ticket(ticket=ticket, actor_user_id=tech.id)
    TicketWorkflowService.complete_ticket_parts(
        ticket=ticket,
        actor_user_id=tech.id,
        part_payloads=[
            {
                "part_spec_id": spec_a.inventory_item_part_id,
                "note": "legacy id payload",
            }
        ],
    )

    ticket.refresh_from_db()
    spec_a.refresh_from_db()
    spec_b.refresh_from_db()

    assert ticket.status == TicketStatus.NEW
    assert spec_a.is_completed is True
    assert spec_a.completed_by_id == tech.id
    assert spec_b.is_completed is False


@pytest.mark.django_db
def test_qc_fail_accepts_legacy_inventory_part_ids(role_cache):
    master = _user(
        username="master_qc_fail_legacy_ids",
        role_slug=RoleSlug.MASTER,
        cache=role_cache,
    )
    qc_user = _user(
        username="qc_qc_fail_legacy_ids",
        role_slug=RoleSlug.QC_INSPECTOR,
        cache=role_cache,
    )
    tech_1 = _user(
        username="tech_qc_fail_legacy_ids_1",
        role_slug=RoleSlug.TECHNICIAN,
        cache=role_cache,
    )
    tech_2 = _user(
        username="tech_qc_fail_legacy_ids_2",
        role_slug=RoleSlug.TECHNICIAN,
        cache=role_cache,
    )
    ticket, spec_a, spec_b = _ticket_with_two_parts(master=master)

    TicketWorkflowService.claim_ticket(ticket=ticket, actor_user_id=tech_1.id)
    TicketWorkflowService.complete_ticket_parts(
        ticket=ticket,
        actor_user_id=tech_1.id,
        part_payloads=[{"part_spec_id": spec_a.id}],
    )

    TicketWorkflowService.claim_ticket(ticket=ticket, actor_user_id=tech_2.id)
    TicketWorkflowService.complete_ticket_parts(
        ticket=ticket,
        actor_user_id=tech_2.id,
        part_payloads=[{"part_spec_id": spec_b.id}],
    )

    ticket.refresh_from_db()
    assert ticket.status == TicketStatus.WAITING_QC

    TicketWorkflowService.qc_fail_ticket(
        ticket=ticket,
        actor_user_id=qc_user.id,
        failed_part_spec_ids=[spec_a.inventory_item_part_id],
    )

    ticket.refresh_from_db()
    spec_a.refresh_from_db()
    spec_b.refresh_from_db()

    assert ticket.status == TicketStatus.REWORK
    assert spec_a.is_completed is False
    assert spec_a.completed_by_id is None
    assert spec_a.completed_at is None
    assert spec_a.completion_note == ""
    assert spec_a.needs_rework is True
    assert spec_a.rework_for_technician_id == tech_1.id

    assert spec_b.is_completed is True
    assert spec_b.needs_rework is False

    mappings = TicketPartQCFailure.all_objects.filter(ticket=ticket)
    assert mappings.count() == 1
    assert mappings.first().technician_id == tech_1.id


@pytest.mark.django_db
def test_move_to_waiting_qc_requires_all_parts_completed(role_cache):
    master = _user(
        username="master_waiting_qc_guard",
        role_slug=RoleSlug.MASTER,
        cache=role_cache,
    )
    tech = _user(
        username="tech_waiting_qc_guard",
        role_slug=RoleSlug.TECHNICIAN,
        cache=role_cache,
    )
    ticket, _spec_a, _spec_b = _ticket_with_two_parts(master=master)

    TicketWorkflowService.claim_ticket(ticket=ticket, actor_user_id=tech.id)
    TicketWorkflowService.start_ticket(ticket=ticket, actor_user_id=tech.id)
    ticket.refresh_from_db()

    with pytest.raises(DomainValidationError):
        ticket.move_to_waiting_qc(actor_user_id=tech.id)


@pytest.mark.django_db
def test_start_ticket_reconciles_stale_open_session(role_cache):
    master = _user(
        username="master_stale_open",
        role_slug=RoleSlug.MASTER,
        cache=role_cache,
    )
    tech = _user(
        username="tech_stale_open",
        role_slug=RoleSlug.TECHNICIAN,
        cache=role_cache,
    )
    stale_ticket, _spec_a, _spec_b = _ticket_with_two_parts(master=master)
    TicketWorkflowService.claim_ticket(ticket=stale_ticket, actor_user_id=tech.id)
    TicketWorkflowService.start_ticket(ticket=stale_ticket, actor_user_id=tech.id)

    stale_session = WorkSession.domain.get_open_for_ticket_and_technician(
        ticket=stale_ticket,
        technician_id=tech.id,
    )
    assert stale_session is not None
    assert stale_session.status == WorkSessionStatus.RUNNING

    Ticket.all_objects.filter(pk=stale_ticket.pk).update(status=TicketStatus.DONE)

    next_ticket, _next_spec_a, _next_spec_b = _ticket_with_two_parts(master=master)
    TicketWorkflowService.claim_ticket(ticket=next_ticket, actor_user_id=tech.id)
    TicketWorkflowService.start_ticket(ticket=next_ticket, actor_user_id=tech.id)

    stale_session.refresh_from_db()
    assert stale_session.status == WorkSessionStatus.STOPPED
    assert stale_session.ended_at is not None

    open_sessions = (
        WorkSession.domain.get_queryset().for_technician(technician_id=tech.id).open()
    )
    assert open_sessions.count() == 1
    assert open_sessions.first().ticket_id == next_ticket.id


@pytest.mark.django_db
def test_auto_resume_stops_inconsistent_paused_session(role_cache, monkeypatch):
    master = _user(
        username="master_auto_resume_stale",
        role_slug=RoleSlug.MASTER,
        cache=role_cache,
    )
    tech = _user(
        username="tech_auto_resume_stale",
        role_slug=RoleSlug.TECHNICIAN,
        cache=role_cache,
    )
    ticket, _spec_a, _spec_b = _ticket_with_two_parts(master=master)
    TicketWorkflowService.claim_ticket(ticket=ticket, actor_user_id=tech.id)
    TicketWorkflowService.start_ticket(ticket=ticket, actor_user_id=tech.id)
    paused_session = TicketWorkSessionService.pause_work_session(
        ticket=ticket,
        actor_user_id=tech.id,
    )
    assert paused_session.status == WorkSessionStatus.PAUSED

    Ticket.all_objects.filter(pk=ticket.pk).update(status=TicketStatus.DONE)

    monkeypatch.setattr(
        TicketWorkSessionService,
        "get_remaining_pause_seconds_today",
        classmethod(lambda cls, *, technician_id, now_dt=None: 0),
    )
    resumed_count = (
        TicketWorkSessionService.auto_resume_paused_sessions_if_limit_reached(
            technician_id=tech.id
        )
    )

    paused_session.refresh_from_db()
    assert resumed_count == 0
    assert paused_session.status == WorkSessionStatus.STOPPED
    assert paused_session.ended_at is not None
