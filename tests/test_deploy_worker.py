"""Tests for DeployCorrelatorWorker LLM-first planning."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from incident_commander.config import Settings
from incident_commander.models.incident import Incident, IncidentStatus
from incident_commander.workers.deploy import DeployCorrelatorWorker
from tests.fakes import fake_tool_clients
from tests.llm_mocks import text_response, tool_call_response


@pytest.fixture
def llm_settings(tmp_path) -> Settings:
    return Settings(
        incident_db_path=tmp_path / "test.db",
        groq_api_key="test-key",
        groq_api_key_fallback="",
        verify_max_attempts=1,
        verify_interval_seconds=0,
    )


@pytest.fixture
def sample_incident() -> Incident:
    return Incident(
        incident_id="INC-TEST-DEPLOY",
        status=IncidentStatus.INVESTIGATING,
        opened_at=datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc),
        trigger="test",
        service="payment-api",
        namespace="default",
    )


@pytest.mark.asyncio
async def test_deploy_worker_llm_chooses_tool_order(llm_settings, sample_incident):
    """LLM tool-call sequence should drive fetch order, not the hardcoded deterministic order."""
    clients = fake_tool_clients()
    worker = DeployCorrelatorWorker(clients, llm_settings)
    call_order: list[str] = []

    async def track_recent(service, since, namespace):
        call_order.append("recent_deploys_since_incident")
        return []

    async def track_history_wrapped(*_args, **_kwargs):
        call_order.append("rollout_history")
        return "REVISION  CHANGE-CAUSE\n42"

    responses = [
        tool_call_response("rollout_history", {}),
        tool_call_response("recent_deploys_since_incident", {}),
        text_response("Found rollout history context; no recent deploys."),
    ]

    with patch.object(
        worker.react._pool,
        "chat_completion",
        new=AsyncMock(side_effect=responses),
    ):
        with patch.object(clients.deploy, "rollout_history_text", side_effect=track_history_wrapped):
            with patch.object(clients.deploy, "recent_deploys", side_effect=track_recent):
                result = await worker.run(sample_incident)

    assert call_order == ["rollout_history", "recent_deploys_since_incident"]
    assert result.tools_called == ["rollout_history", "recent_deploys_since_incident"]
    assert len(result.steps) >= 2
