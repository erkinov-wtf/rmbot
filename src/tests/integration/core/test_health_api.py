from django.test import TestCase
from rest_framework.test import APIClient


class HealthAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_health_endpoint_ok(self):
        resp = self.client.get("/api/v1/misc/health/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json().get("status"), "ok")
