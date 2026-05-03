from starlette.testclient import TestClient

from health_mcp.config import Settings
from health_mcp.server import create_app


def test_health_endpoint_returns_503_when_schema_init_fails(monkeypatch):
    def fail_initialize_schema(self):
        raise RuntimeError("db unavailable")

    monkeypatch.setattr("health_mcp.service.HealthService.initialize_schema", fail_initialize_schema)

    app = create_app(
        Settings(
            host="0.0.0.0",
            port=8099,
            db_password="test-password",
            api_key=None,
            auto_migrate=True,
        )
    )

    with TestClient(app) as client:
        response = client.get("/health")
        root_response = client.get("/")

    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
    assert "db unavailable" in response.json()["error"]
    assert root_response.status_code == 200
    assert root_response.json()["status"] == "degraded"
    assert "db unavailable" in root_response.json()["error"]
