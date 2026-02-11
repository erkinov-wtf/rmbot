import pytest

from attendance.models import AttendanceRecord
from core.utils.constants import XPLedgerEntryType
from gamification.models import XPLedger

pytestmark = pytest.mark.django_db


CHECKIN_URL = "/api/v1/attendance/checkin/"
CHECKOUT_URL = "/api/v1/attendance/checkout/"
TODAY_URL = "/api/v1/attendance/today/"


@pytest.fixture
def attendance_client(authed_client_factory, user_factory):
    user = user_factory(
        username="attendance_user",
        first_name="Attendance",
        email="attendance@example.com",
    )
    return authed_client_factory(user), user


def test_checkin_creates_record_and_xp_entry(attendance_client):
    client, _user = attendance_client

    resp = client.post(CHECKIN_URL, {}, format="json")

    assert resp.status_code == 200
    assert AttendanceRecord.objects.count() == 1
    assert XPLedger.objects.count() == 1

    entry = XPLedger.objects.first()
    assert entry.entry_type == XPLedgerEntryType.ATTENDANCE_PUNCTUALITY
    assert "attendance_checkin" in entry.reference
    assert "xp_awarded" in resp.data["data"]


def test_checkin_twice_fails(attendance_client):
    client, _user = attendance_client
    client.post(CHECKIN_URL, {}, format="json")
    second = client.post(CHECKIN_URL, {}, format="json")

    assert second.status_code == 400
    assert second.data["success"] is False
    assert "already checked in" in second.data["error"]["detail"].lower()


def test_checkout_requires_checkin(attendance_client):
    client, _user = attendance_client
    resp = client.post(CHECKOUT_URL, {}, format="json")

    assert resp.status_code == 400
    assert "before check in" in resp.data["error"]["detail"].lower()


def test_checkout_after_checkin_succeeds(attendance_client):
    client, user = attendance_client
    client.post(CHECKIN_URL, {}, format="json")
    resp = client.post(CHECKOUT_URL, {}, format="json")

    assert resp.status_code == 200
    record = AttendanceRecord.objects.get(user=user)
    assert record.check_out_at is not None


def test_today_endpoint_returns_current_record(attendance_client):
    client, user = attendance_client

    before = client.get(TODAY_URL)
    assert before.status_code == 200
    assert before.data["data"] is None

    client.post(CHECKIN_URL, {}, format="json")
    after = client.get(TODAY_URL)

    assert after.status_code == 200
    assert after.data["data"]["user"] == user.id
