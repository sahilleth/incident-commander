"""API authentication tests."""

import pytest
from httpx import ASGITransport, AsyncClient

from incident_commander.api.app import app
from incident_commander.config import Settings
from tests.conftest import setup_app_state


@pytest.fixture
async def auth_client(tmp_path):
    settings = Settings(
        incident_db_path=tmp_path / "auth.db",
        groq_api_key="",
        groq_api_key_fallback="",
        api_auth_token="secret-api-token",
        alertmanager_webhook_token="webhook-secret",
        verify_max_attempts=1,
        verify_interval_seconds=0,
    )
    await setup_app_state(settings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, settings


@pytest.mark.asyncio
async def test_auth_disabled_no_header_ok(api_client):
    client, _ = api_client
    health = await client.get("/api/health")
    assert health.status_code == 200

    listed = await client.get("/api/incidents")
    assert listed.status_code == 200


@pytest.mark.asyncio
async def test_auth_enabled_missing_header_401(auth_client):
    client, _ = auth_client
    resp = await client.get("/api/incidents")
    assert resp.status_code == 401
    assert "Authorization" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_auth_enabled_wrong_token_401(auth_client):
    client, _ = auth_client
    resp = await client.get(
        "/api/incidents",
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid API token"


@pytest.mark.asyncio
async def test_auth_enabled_valid_token_ok(auth_client):
    client, settings = auth_client
    headers = {"Authorization": f"Bearer {settings.api_auth_token}"}
    resp = await client.get("/api/incidents", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_health_open_when_auth_enabled(auth_client):
    client, _ = auth_client
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_webhook_token_required_when_configured(auth_client):
    client, settings = auth_client
    payload = {
        "alerts": [
            {
                "status": "firing",
                "labels": {"deployment": "payment-api", "alertname": "HighErrorRate"},
            }
        ]
    }

    missing = await client.post("/webhooks/alertmanager", json=payload)
    assert missing.status_code == 401

    wrong = await client.post(
        "/webhooks/alertmanager",
        json=payload,
        headers={settings.alertmanager_webhook_header: "bad"},
    )
    assert wrong.status_code == 401

    ok = await client.post(
        "/webhooks/alertmanager",
        json=payload,
        headers={settings.alertmanager_webhook_header: settings.alertmanager_webhook_token},
    )
    assert ok.status_code == 200
    assert ok.json()["count"] >= 1


@pytest.mark.asyncio
async def test_webhook_token_independent_of_bearer(auth_client):
    client, settings = auth_client
    payload = {
        "alerts": [
            {
                "status": "firing",
                "labels": {"deployment": "api", "alertname": "Test"},
            }
        ]
    }
    # Bearer token should NOT satisfy webhook auth
    resp = await client.post(
        "/webhooks/alertmanager",
        json=payload,
        headers={"Authorization": f"Bearer {settings.api_auth_token}"},
    )
    assert resp.status_code == 401
