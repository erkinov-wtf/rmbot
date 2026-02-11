from django.test import TestCase
from rest_framework.test import APIClient

from account.models import Role, User
from bike.models import Bike
from core.utils.constants import RoleSlug


class BikeAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.list_url = "/api/v1/bikes/"
        self.create_url = "/api/v1/bikes/create/"

        self.manager_user = User.objects.create_user(
            username="ops_bike",
            password="pass1234",
            first_name="Ops",
            email="ops_bike@example.com",
        )
        self.regular_user = User.objects.create_user(
            username="regular_bike",
            password="pass1234",
            first_name="Regular",
            email="regular_bike@example.com",
        )

        ops_role, _ = Role.objects.update_or_create(
            slug=RoleSlug.OPS_MANAGER,
            defaults={"name": "Ops Manager"},
        )
        self.manager_user.roles.add(ops_role)

    def test_list_requires_auth(self):
        resp = self.client.get(self.list_url)
        self.assertEqual(resp.status_code, 401)

    def test_create_requires_bike_manager_role(self):
        self.client.force_authenticate(user=self.regular_user)
        resp = self.client.post(self.create_url, {"bike_code": "RM-0200"}, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_ops_manager_can_create_bike(self):
        self.client.force_authenticate(user=self.manager_user)
        resp = self.client.post(self.create_url, {"bike_code": "RM-0200"}, format="json")

        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["data"]["bike_code"], "RM-0200")
        self.assertEqual(Bike.objects.count(), 1)
