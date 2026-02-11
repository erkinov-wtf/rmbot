from django.test import TestCase
from rest_framework.test import APIClient

from account.models import AccessRequest, Role, TelegramProfile, User
from core.utils.constants import AccessRequestStatus, RoleSlug


class AccessRequestModerationAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.list_url = "/api/v1/users/access-requests/"
        self.pending = AccessRequest.objects.create(
            telegram_id=999001,
            username="new_tech",
            first_name="New",
            last_name="Tech",
        )
        self.target_user = User.objects.create_user(
            username="worker",
            password="pass1234",
            first_name="Worker",
            email="worker@example.com",
        )

        self.regular_user = User.objects.create_user(
            username="regular",
            password="pass1234",
            first_name="Regular",
            email="regular@example.com",
        )
        self.moderator = User.objects.create_user(
            username="ops",
            password="pass1234",
            first_name="Ops",
            email="ops@example.com",
        )

        ops_role, _ = Role.objects.update_or_create(
            slug=RoleSlug.OPS_MANAGER,
            defaults={"name": "Ops Manager"},
        )
        technician_role, _ = Role.objects.update_or_create(
            slug=RoleSlug.TECHNICIAN,
            defaults={"name": "Technician"},
        )
        self.technician_role_slug = technician_role.slug
        self.moderator.roles.add(ops_role)

    def test_list_requires_privileged_role(self):
        self.client.force_authenticate(user=self.regular_user)
        forbidden = self.client.get(self.list_url)
        self.assertEqual(forbidden.status_code, 403)

        self.client.force_authenticate(user=self.moderator)
        allowed = self.client.get(self.list_url)
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(len(allowed.data["data"]), 1)
        self.assertEqual(allowed.data["data"][0]["status"], AccessRequestStatus.PENDING)

    def test_approve_links_profile_and_assigns_roles(self):
        self.client.force_authenticate(user=self.moderator)
        url = f"/api/v1/users/access-requests/{self.pending.id}/approve/"
        resp = self.client.post(
            url,
            {"user_id": self.target_user.id, "role_slugs": [self.technician_role_slug]},
            format="json",
        )

        self.assertEqual(resp.status_code, 200)
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, AccessRequestStatus.APPROVED)
        self.assertEqual(self.pending.user_id, self.target_user.id)
        self.assertIsNotNone(self.pending.resolved_at)

        profile = TelegramProfile.objects.get(telegram_id=self.pending.telegram_id)
        self.assertEqual(profile.user_id, self.target_user.id)
        self.assertTrue(self.target_user.roles.filter(slug=self.technician_role_slug).exists())

    def test_approve_can_create_user_and_link(self):
        self.client.force_authenticate(user=self.moderator)
        url = f"/api/v1/users/access-requests/{self.pending.id}/approve/"
        resp = self.client.post(
            url,
            {
                "user": {
                    "username": "created_worker",
                    "first_name": "Created",
                    "email": "created_worker@example.com",
                    "phone": "+998990001122",
                },
                "role_slugs": [self.technician_role_slug],
            },
            format="json",
        )

        self.assertEqual(resp.status_code, 200)
        created_user = User.objects.get(username="created_worker")
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, AccessRequestStatus.APPROVED)
        self.assertEqual(self.pending.user_id, created_user.id)

        profile = TelegramProfile.objects.get(telegram_id=self.pending.telegram_id)
        self.assertEqual(profile.user_id, created_user.id)
        self.assertTrue(created_user.roles.filter(slug=self.technician_role_slug).exists())

    def test_approve_requires_user_reference_or_payload(self):
        self.client.force_authenticate(user=self.moderator)
        url = f"/api/v1/users/access-requests/{self.pending.id}/approve/"
        resp = self.client.post(url, {"role_slugs": [self.technician_role_slug]}, format="json")

        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.data["success"])
        self.assertIn("exactly one", resp.data["message"].lower())

    def test_reject_marks_request_as_rejected(self):
        self.client.force_authenticate(user=self.moderator)
        url = f"/api/v1/users/access-requests/{self.pending.id}/reject/"
        resp = self.client.post(url, {}, format="json")

        self.assertEqual(resp.status_code, 200)
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, AccessRequestStatus.REJECTED)
        self.assertIsNotNone(self.pending.resolved_at)
