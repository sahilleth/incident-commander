"""FastAPI endpoint tests."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from incident_commander.api.app import app
from incident_commander.config import Settings
from incident_commander.models.incident import (
    ActionRisk,
    Incident,
    IncidentStatus,
    PendingApproval,
    SuggestedAction,
)
from incident_commander.orchestrator.commander import IncidentCommander
from tests.conftest import setup_app_state
from tests.fakes import fake_tool_clients


@pytest.mark.asyncio
async def test_create_incident(api_client):
    client, _ = api_client
    resp = await client.post(
        "/api/incidents",
        json={
            "service": "payment-api",
            "namespace": "default",
            "trigger": "api-test",
            "severity": "SEV2",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["incident_id"].startswith("INC-")
    assert body["service"] == "payment-api"


@pytest.mark.asyncio
async def test_get_incident_not_found(api_client):
    client, _ = api_client
    resp = await client.get("/api/incidents/INC-NONEXISTENT")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Incident not found"


@pytest.mark.asyncio
async def test_list_incidents_with_limit(api_client):
    client, _ = api_client
    await client.post(
        "/api/incidents",
        json={"service": "svc-a", "trigger": "t1", "namespace": "default"},
    )
    resp = await client.get("/api/incidents?limit=1")
    assert resp.status_code == 200
    rows = resp.json()
    assert isinstance(rows, list)
    assert len(rows) <= 1


@pytest.mark.asyncio
async def test_investigate_endpoint(api_client):
    client, settings = api_client
    commander = IncidentCommander(settings, app.state.store)
    commander.clients = fake_tool_clients()
    app.state.commander = commander

    created = await client.post(
        "/api/incidents",
        json={"service": "payment-api", "trigger": "t", "namespace": "default"},
    )
    incident_id = created.json()["incident_id"]

    with patch.object(
        commander,
        "investigate",
        new=AsyncMock(side_effect=commander.investigate),
    ):
        resp = await client.post(f"/api/incidents/{incident_id}/investigate")
    assert resp.status_code == 200
    assert resp.json()["incident_id"] == incident_id


@pytest.mark.asyncio
async def test_approve_pending_and_missing_approval(api_client):
    client, settings = api_client
    commander = IncidentCommander(settings, app.state.store)
    commander.clients = fake_tool_clients()
    app.state.commander = commander

    incident = Incident(
        incident_id="INC-APPROVE-TEST",
        status=IncidentStatus.INVESTIGATING,
        opened_at=datetime.now(timezone.utc),
        trigger="test",
        service="payment-api",
        namespace="default",
        approvals_pending=[
            PendingApproval(
                id="APR-test01",
                action=SuggestedAction(
                    type="rollback",
                    description="rollback",
                    risk=ActionRisk.MEDIUM,
                    requires_approval=True,
                    params={"service": "payment-api", "namespace": "default"},
                ),
                hypothesis_id="H1",
                requested_at=datetime.now(timezone.utc),
            )
        ],
    )
    await app.state.store.save(incident)

    with patch.object(commander, "approve_action", new=AsyncMock(side_effect=commander.approve_action)):
        ok = await client.post(
            f"/api/incidents/{incident.incident_id}/approve",
            json={"approval_id": "APR-test01"},
        )
    assert ok.status_code == 200

    missing = await client.post(
        f"/api/incidents/{incident.incident_id}/approve",
        json={"approval_id": "APR-not-real"},
    )
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_postmortem_markdown_content_type(api_client):
    client, settings = api_client
    incident = Incident(
        incident_id="INC-PM-TEST",
        status=IncidentStatus.INVESTIGATING,
        opened_at=datetime.now(timezone.utc),
        trigger="test",
        service="payment-api",
        namespace="default",
        summary="test summary",
    )
    await app.state.store.save(incident)

    resp = await client.get(f"/api/incidents/{incident.incident_id}/postmortem.md")
    assert resp.status_code == 200
    assert "text/markdown" in resp.headers.get("content-type", "")
    assert "Post-incident report" in resp.text


@pytest.mark.asyncio
async def test_alertmanager_webhook_valid_payload(api_client):
    client, _ = api_client
    resp = await client.post(
        "/webhooks/alertmanager",
        json={
            "alerts": [
                {
                    "status": "firing",
                    "labels": {
                        "deployment": "payment-api",
                        "namespace": "default",
                        "alertname": "HighErrorRate",
                    },
                }
            ]
        },
    )
    assert resp.status_code == 200
    assert resp.json()["count"] == 1


@pytest.mark.asyncio
async def test_alertmanager_webhook_malformed_alerts_400(api_client):
    client, _ = api_client
    resp = await client.post(
        "/webhooks/alertmanager",
        json={"alerts": "not-a-list"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "alerts must be a list"
