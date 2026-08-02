"""Tests for hypothesis synthesizer critique."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from incident_commander.config import Settings
from incident_commander.llm.synthesizer import HypothesisSynthesizer
from incident_commander.models.incident import Hypothesis, Incident, IncidentStatus, TimelineEvent
from tests.llm_mocks import tool_call_response


@pytest.fixture
def llm_settings(tmp_path) -> Settings:
    return Settings(
        incident_db_path=tmp_path / "test.db",
        groq_api_key="test-key",
        groq_api_key_fallback="",
    )


@pytest.mark.asyncio
async def test_critique_lowers_confidence(llm_settings):
    synth = HypothesisSynthesizer(llm_settings)
    incident = Incident(
        incident_id="INC-CRIT",
        status=IncidentStatus.INVESTIGATING,
        opened_at=datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc),
        trigger="test",
        service="api",
        timeline=[
            TimelineEvent(
                id="e1",
                at=datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc),
                source="deploy_correlator",
                event="Deploy revision 2",
                confidence="high",
            )
        ],
    )
    hypothesis = Hypothesis(
        id="H1",
        description="Bad deploy caused outage",
        confidence=0.8,
        evidence_event_ids=["e1"],
    )

    with patch.object(
        synth._pool,
        "chat_completion",
        new=AsyncMock(
            return_value=tool_call_response(
                "submit_critique",
                {
                    "supported": False,
                    "reasoning": "Deploy alone is weak evidence.",
                    "confidence_adjustment": -0.3,
                },
            )
        ),
    ):
        result = await synth.critique(incident, hypothesis)

    assert result is not None
    assert result.confidence_adjustment == -0.3
    assert not result.supported


@pytest.mark.asyncio
async def test_critique_failure_returns_none(llm_settings):
    synth = HypothesisSynthesizer(llm_settings)
    incident = Incident(
        incident_id="INC-CRIT2",
        status=IncidentStatus.INVESTIGATING,
        opened_at=datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc),
        trigger="test",
        service="api",
    )
    hypothesis = Hypothesis(id="H1", description="test", confidence=0.7)

    with patch.object(
        synth._pool,
        "chat_completion",
        new=AsyncMock(side_effect=RuntimeError("LLM down")),
    ):
        result = await synth.critique(incident, hypothesis)

    assert result is None


@pytest.mark.asyncio
async def test_critique_skipped_below_threshold_no_llm_call(heuristic_settings, tmp_path):
    from incident_commander.orchestrator.commander import IncidentCommander
    from incident_commander.state.store import IncidentStore

    settings = heuristic_settings
    settings.groq_api_key = "test-key"
    store = IncidentStore(settings.incident_db_path)
    await store.init()
    cmd = IncidentCommander(settings, store)

    incident = Incident(
        incident_id="INC-LOW-SYN",
        status=IncidentStatus.INVESTIGATING,
        opened_at=datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc),
        trigger="test",
        service="api",
        hypotheses=[
            Hypothesis(id="H1", description="weak", confidence=0.4, evidence_event_ids=[]),
        ],
    )

    with patch.object(cmd.synthesizer._pool, "chat_completion", new=AsyncMock()) as mock_chat:
        await cmd._apply_critique(incident)

    mock_chat.assert_not_awaited()
    assert not any(e.source == "critique_agent" for e in incident.timeline)


@pytest.mark.asyncio
async def test_critique_failure_does_not_abort_investigate(heuristic_settings, tmp_path):
    from incident_commander.llm.llm_client import LLMClientPool
    from incident_commander.orchestrator.commander import IncidentCommander
    from incident_commander.state.store import IncidentStore
    from tests.fakes import fake_tool_clients
    from tests.llm_mocks import text_response, tool_call_response

    settings = heuristic_settings
    settings.groq_api_key = "test-key"
    settings.groq_api_key_fallback = ""
    store = IncidentStore(settings.incident_db_path)
    await store.init()
    cmd = IncidentCommander(settings, store)
    cmd.clients = fake_tool_clients()

    deploy_done = text_response("ok", prompt_tokens=10, completion_tokens=5)
    synth = tool_call_response(
        "submit_hypotheses",
        {
            "hypotheses": [
                {
                    "id": "H1",
                    "description": "Deploy issue",
                    "confidence": 0.7,
                    "suggested_actions": [],
                }
            ]
        },
    )
    call_idx = 0

    async def chat_with_usage(self, **kwargs):
        nonlocal call_idx
        tools = kwargs.get("tools") or []
        names = [t.get("function", {}).get("name") for t in tools]
        if "submit_critique" in names:
            raise RuntimeError("critique failed")
        result = deploy_done if call_idx == 0 else synth
        call_idx += 1
        self._record_usage(self.settings.resolved_llm_model(), result)
        return result

    with patch.object(LLMClientPool, "chat_completion", chat_with_usage):
        incident = await cmd.open_incident(service="payment-api", trigger="critique-fail")

    assert incident.hypotheses[0].confidence == 0.7
    assert not any(e.source == "critique_agent" for e in incident.timeline)
