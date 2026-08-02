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
