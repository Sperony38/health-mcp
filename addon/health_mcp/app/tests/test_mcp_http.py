from starlette.testclient import TestClient

from health_mcp.config import Settings
from health_mcp.server import create_app


def test_mcp_endpoint_accepts_non_localhost_host_header_without_api_key():
    app = create_app(
        Settings(
            host="0.0.0.0",
            port=8099,
            db_password="test-password",
            api_key=None,
            auto_migrate=False,
        )
    )

    with TestClient(app) as client:
        response = client.post(
            "/mcp",
            headers={
                "host": "raspberrypi.local:8099",
                "accept": "application/json",
                "content-type": "application/json",
            },
            content="{}",
        )

    assert response.status_code == 400
    assert "Invalid Host header" not in response.text
