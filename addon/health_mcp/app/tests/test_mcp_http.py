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


def test_tools_list_exposes_service_user_discovery_tool():
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
        initialize = client.post(
            "/mcp",
            headers={
                "host": "raspberrypi.local:8099",
                "accept": "application/json, text/event-stream",
                "content-type": "application/json",
            },
            json={
                "jsonrpc": "2.0",
                "id": "init-1",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "pytest", "version": "1.0"},
                },
            },
        )
        assert initialize.status_code == 200

        response = client.post(
            "/mcp",
            headers={
                "host": "raspberrypi.local:8099",
                "accept": "application/json, text/event-stream",
                "content-type": "application/json",
            },
            json={
                "jsonrpc": "2.0",
                "id": "tools-1",
                "method": "tools/list",
                "params": {},
            },
        )

    assert response.status_code == 200
    tool_names = [item["name"] for item in response.json()["result"]["tools"]]
    assert "list_service_users" in tool_names
