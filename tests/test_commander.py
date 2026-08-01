"""Tests for incident commander."""

import pytest

from incident_commander.models.incident import Incident, IncidentStatus, TimelineEvent
from incident_commander.orchestrator.commander import IncidentCommander
from incident_commander.state.store import IncidentStore
from tests.fakes import fake_tool_clients


@pytest.fixture
async def commander(heuristic_settings, tmp_path):
    settings = heuristic_settings
    settings.incident_db_path = tmp_path / "test.db"
    store = IncidentStore(settings.incident_db_path)
    await store.init()
    cmd = IncidentCommander(settings, store)
    cmd.clients = fake_tool_clients()
    cmd.runbook = __import__(
        "incident_commander.orchestrator.runbook", fromlist=["RunbookExecutor"]
    ).RunbookExecutor(cmd.clients)
    cmd.verifier = __import__(
        "incident_commander.orchestrator.verifier", fromlist=["MitigationVerifier"]
    ).MitigationVerifier(settings, cmd.clients)
    return cmd, store


@pytest.mark.asyncio
async def test_open_incident_investigates(commander):
    cmd, store = commander
    incident = await cmd.open_incident(
        service="payment-api",
        trigger="test",
        namespace="default",
    )

    assert incident.incident_id.startswith("INC-")
    assert len(incident.timeline) > 0
    assert len(incident.worker_runs) == 4
    assert all(run.status == "complete" for run in incident.worker_runs)
    assert len(incident.hypotheses) > 0
    assert incident.hypotheses[0].confidence >= 0.5

    loaded = await store.get(incident.incident_id)
    assert loaded is not None
    assert loaded.service == "payment-api"


@pytest.mark.asyncio
async def test_dedupe_open_incidents(commander):
    cmd, _ = commander
    first = await cmd.open_incident(service="api", trigger="t1")
    second = await cmd.open_incident(service="api", trigger="t2")
    assert first.incident_id == second.incident_id


@pytest.mark.asyncio
async def test_approve_executes_rollback(commander):
    cmd, _ = commander
    incident = await cmd.open_incident(service="payment-api", trigger="test")
    if not incident.approvals_pending:
        pytest.skip("No approvals in this scenario")

    approval_id = incident.approvals_pending[0].id
    resolved = await cmd.approve_action(incident.incident_id, approval_id)
    assert resolved.status.value in ("resolved", "escalated")
    assert any("verifier" in e.source for e in resolved.timeline)


@pytest.mark.asyncio
async def test_no_rollback_without_error_signals(commander):
    cmd, _ = commander
    incident = Incident(
        incident_id="INC-TEST",
        status=IncidentStatus.INVESTIGATING,
        opened_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        trigger="manual",
        service="payment-api",
        namespace="default",
        timeline=[
            TimelineEvent(
                id="e1",
                at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
                source="deploy_correlator",
                event="Deployment payment-api revision 1 rolled out",
                confidence="high",
            )
        ],
        hypotheses=[],
    )
    incident.hypotheses = await cmd.synthesizer.synthesize(incident)
    incident.approvals_pending = cmd._queue_approvals(incident)
    rollback_pending = [
        a for a in incident.approvals_pending if a.action.type == "rollback"
    ]
    assert rollback_pending == []
