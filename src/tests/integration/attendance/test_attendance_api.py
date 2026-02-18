from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from attendance.models import AttendanceRecord
from core.utils.constants import RoleSlug, XPTransactionEntryType
from gamification.models import XPTransaction

pytestmark = pytest.mark.django_db


CHECKIN_URL = "/api/v1/attendance/checkin/"
CHECKOUT_URL = "/api/v1/attendance/checkout/"
RECORDS_URL = "/api/v1/attendance/records/"


@pytest.fixture
def attendance_context(authed_client_factory, user_factory, assign_roles):
    manager = user_factory(
        username="attendance_manager",
        first_name="Manager",
    )
    assign_roles(manager, RoleSlug.MASTER)

    technician = user_factory(
        username="attendance_user",
        first_name="Attendance",
    )
    assign_roles(technician, RoleSlug.TECHNICIAN)

    return {
        "manager": manager,
        "technician": technician,
        "client": authed_client_factory(manager),
        "technician_client": authed_client_factory(technician),
        "user_factory": user_factory,
        "assign_roles": assign_roles,
    }


def test_checkin_creates_record_and_xp_entry(attendance_context):
    client = attendance_context["client"]
    technician = attendance_context["technician"]

    resp = client.post(CHECKIN_URL, {"technician_id": technician.id}, format="json")

    assert resp.status_code == 200
    assert AttendanceRecord.objects.count() == 1
    assert XPTransaction.objects.count() == 1

    entry = XPTransaction.objects.first()
    assert entry.entry_type == XPTransactionEntryType.ATTENDANCE_PUNCTUALITY
    assert "attendance_checkin" in entry.reference
    assert "xp_awarded" in resp.data["data"]


def test_checkin_twice_fails(attendance_context):
    client = attendance_context["client"]
    technician = attendance_context["technician"]
    payload = {"technician_id": technician.id}
    client.post(CHECKIN_URL, payload, format="json")
    second = client.post(CHECKIN_URL, payload, format="json")

    assert second.status_code == 400
    assert second.data["success"] is False
    assert "already checked in" in second.data["message"].lower()


def test_checkout_requires_checkin(attendance_context):
    client = attendance_context["client"]
    technician = attendance_context["technician"]
    resp = client.post(CHECKOUT_URL, {"technician_id": technician.id}, format="json")

    assert resp.status_code == 400
    assert "before check in" in resp.data["message"].lower()


def test_checkout_after_checkin_succeeds(attendance_context):
    client = attendance_context["client"]
    technician = attendance_context["technician"]
    payload = {"technician_id": technician.id}

    client.post(CHECKIN_URL, payload, format="json")
    resp = client.post(CHECKOUT_URL, payload, format="json")

    assert resp.status_code == 200
    record = AttendanceRecord.objects.get(user=technician)
    assert record.check_out_at is not None


def test_today_endpoint_returns_current_records(attendance_context):
    client = attendance_context["client"]
    technician = attendance_context["technician"]

    before = client.get(RECORDS_URL)
    assert before.status_code == 200
    assert before.data["results"] == []

    client.post(CHECKIN_URL, {"technician_id": technician.id}, format="json")
    after = client.get(RECORDS_URL)

    assert after.status_code == 200
    assert len(after.data["results"]) == 1
    assert after.data["results"][0]["user"] == technician.id
    assert after.data["results"][0]["punctuality_status"] in {
        "early",
        "on_time",
        "late",
    }


def test_today_endpoint_supports_date_technician_and_punctuality_filters(
    attendance_context,
):
    client = attendance_context["client"]
    user_factory = attendance_context["user_factory"]
    assign_roles = attendance_context["assign_roles"]

    early_technician = attendance_context["technician"]
    on_time_technician = user_factory(
        username="attendance_on_time",
        first_name="OnTime",
    )
    late_technician = user_factory(
        username="attendance_late",
        first_name="Late",
    )
    assign_roles(on_time_technician, RoleSlug.TECHNICIAN)
    assign_roles(late_technician, RoleSlug.TECHNICIAN)

    target_date = date(2026, 2, 15)
    local_tz = ZoneInfo("Asia/Tashkent")

    AttendanceRecord.objects.create(
        user=early_technician,
        work_date=target_date,
        check_in_at=datetime(2026, 2, 15, 9, 45, tzinfo=local_tz),
    )
    AttendanceRecord.objects.create(
        user=on_time_technician,
        work_date=target_date,
        check_in_at=datetime(2026, 2, 15, 10, 10, tzinfo=local_tz),
    )
    AttendanceRecord.objects.create(
        user=late_technician,
        work_date=target_date,
        check_in_at=datetime(2026, 2, 15, 10, 30, tzinfo=local_tz),
    )
    AttendanceRecord.objects.create(
        user=late_technician,
        work_date=date(2026, 2, 14),
        check_in_at=datetime(2026, 2, 14, 9, 0, tzinfo=local_tz),
    )

    early_resp = client.get(
        f"{RECORDS_URL}?work_date={target_date.isoformat()}&punctuality=early"
    )
    assert early_resp.status_code == 200
    assert len(early_resp.data["results"]) == 1
    assert early_resp.data["results"][0]["user"] == early_technician.id
    assert early_resp.data["results"][0]["punctuality_status"] == "early"

    technician_resp = client.get(
        f"{RECORDS_URL}?work_date={target_date.isoformat()}&technician_id={on_time_technician.id}"
    )
    assert technician_resp.status_code == 200
    assert len(technician_resp.data["results"]) == 1
    assert technician_resp.data["results"][0]["user"] == on_time_technician.id
    assert technician_resp.data["results"][0]["punctuality_status"] == "on_time"


def test_attendance_actions_require_privileged_role(attendance_context):
    technician_client = attendance_context["technician_client"]
    technician = attendance_context["technician"]

    resp = technician_client.post(
        CHECKIN_URL,
        {"technician_id": technician.id},
        format="json",
    )

    assert resp.status_code == 403


def test_today_endpoint_rejects_invalid_punctuality_filter(attendance_context):
    client = attendance_context["client"]
    resp = client.get(f"{RECORDS_URL}?punctuality=invalid")

    assert resp.status_code == 400
