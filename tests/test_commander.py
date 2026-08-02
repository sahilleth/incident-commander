"""Tests for incident commander."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from incident_commander.llm.llm_client import LLMClientPool
from incident_commander.models.incident import Incident, IncidentStatus, TimelineEvent
from incident_commander.orchestrator.commander import IncidentCommander
from incident_commander.state.store import IncidentStore
from incident_commander.tools.clients import DeployEvent
from tests.fakes import FakeDeployClient, FakeLogsClient, fake_tool_clients
from tests.llm_mocks import text_response, tool_call_response


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
    FakeLogsClient.last_since = None
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
    assert any(len(run.steps) > 0 for run in incident.worker_runs)

    loaded = await store.get(incident.incident_id)
    assert loaded is not None
    assert loaded.service == "payment-api"


@pytest.mark.asyncio
async def test_logs_worker_narrows_window_around_deploy(commander):
    cmd, _ = commander
    opened = datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc)
    deploy_at = opened + timedelta(minutes=30)

    async def deploys_after_delay(service, since, namespace):
        return [
            DeployEvent(
                at=deploy_at,
                service=service,
                revision="99",
                description=f"Deployment {service} revision 99",
            )
        ]

    cmd.clients.deploy.recent_deploys = deploys_after_delay
    FakeLogsClient.last_since = None

    incident = Incident(
        incident_id="INC-PHASE",
        status=IncidentStatus.INVESTIGATING,
        opened_at=opened,
        trigger="test",
        service="payment-api",
        namespace="default",
    )
    await cmd.store.save(incident)
    await cmd.investigate(incident.incident_id)

    expected_since = deploy_at - timedelta(minutes=2)
    assert FakeLogsClient.last_since is not None
    assert FakeLogsClient.last_since.replace(tzinfo=timezone.utc) == expected_since


@pytest.mark.asyncio
async def test_llm_usage_tracked_when_configured(heuristic_settings, tmp_path):
    settings = heuristic_settings
    settings.groq_api_key = "test-key"
    settings.groq_api_key_fallback = ""
    settings.incident_db_path = tmp_path / "usage.db"
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

    synth_response = tool_call_response(
        "submit_hypotheses",
        {
            "hypotheses": [
                {
                    "id": "H1",
                    "description": "Deploy regression",
                    "confidence": 0.65,
                    "suggested_actions": [],
                }
            ]
        },
        prompt_tokens=200,
        completion_tokens=100,
    )
    critique_response = tool_call_response(
        "submit_critique",
        {
            "supported": True,
            "reasoning": "Evidence aligns.",
            "confidence_adjustment": 0.0,
        },
        prompt_tokens=50,
        completion_tokens=25,
    )

    deploy_done = text_response("No deploy changes found.", prompt_tokens=30, completion_tokens=20)
    responses = [deploy_done, synth_response, critique_response]
    call_idx = 0

    async def chat_with_usage(self, **kwargs):
        nonlocal call_idx
        result = responses[min(call_idx, len(responses) - 1)]
        call_idx += 1
        model = str(kwargs.get("model", self.settings.resolved_llm_model()))
        self._record_usage(model, result)
        return result

    with patch.object(LLMClientPool, "chat_completion", chat_with_usage):
        incident = await cmd.open_incident(service="payment-api", trigger="test")

    assert incident.llm_usage.calls >= 1
    assert incident.llm_usage.total_tokens > 0


@pytest.mark.asyncio
async def test_critique_skipped_below_threshold(commander):
    cmd, _ = commander
    incident = Incident(
        incident_id="INC-LOW",
        status=IncidentStatus.INVESTIGATING,
        opened_at=datetime.now(timezone.utc),
        trigger="test",
        service="payment-api",
        namespace="default",
        timeline=[
            TimelineEvent(
                id="e1",
                at=datetime.now(timezone.utc),
                source="deploy_correlator",
                event="Deploy revision 1",
                confidence="high",
            )
        ],
        hypotheses=[
            __import__(
                "incident_commander.models.incident", fromlist=["Hypothesis"]
            ).Hypothesis(
                id="H1",
                description="Weak hypothesis",
                confidence=0.4,
                evidence_event_ids=["e1"],
            )
        ],
    )
    await cmd._apply_critique(incident)
    assert not any(e.source == "critique_agent" for e in incident.timeline)


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
