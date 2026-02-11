def test_health_endpoint_ok(api_client):
    resp = api_client.get("/api/v1/misc/health/")
    assert resp.status_code == 200
    assert resp.json().get("status") == "ok"
