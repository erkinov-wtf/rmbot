def test_health_endpoint_ok(api_client):
    resp = api_client.get("/api/v1/misc/health/")
    assert resp.status_code == 200
    assert resp.json().get("status") == "ok"


def test_health_endpoint_sets_request_id_header(api_client):
    resp = api_client.get("/api/v1/misc/health/")
    assert resp.status_code == 200
    assert resp.headers.get("X-Request-ID")


def test_health_endpoint_echoes_incoming_request_id(api_client):
    resp = api_client.get(
        "/api/v1/misc/health/",
        HTTP_X_REQUEST_ID="integration-health-check-id",
    )
    assert resp.status_code == 200
    assert resp.headers.get("X-Request-ID") == "integration-health-check-id"
