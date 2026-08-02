"""Tests for LogsWorker."""

from datetime import datetime, timedelta, timezone

import pytest

from incident_commander.config import Settings
from incident_commander.models.incident import Incident, IncidentStatus
from incident_commander.workers.logs import LogsWorker
from tests.fakes import FakeLogsClient, fake_tool_clients


@pytest.fixture
def llm_settings(tmp_path) -> Settings:
    return Settings(
        incident_db_path=tmp_path / "test.db",
        groq_api_key="",
        groq_api_key_fallback="",
        verify_max_attempts=1,
        verify_interval_seconds=0,
    )


@pytest.fixture
def sample_incident() -> Incident:
    return Incident(
        incident_id="INC-TEST-LOGS",
        status=IncidentStatus.INVESTIGATING,
        opened_at=datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc),
        trigger="test",
        service="payment-api",
        namespace="default",
    )


@pytest.mark.asyncio
async def test_logs_worker_deterministic_timeline(llm_settings, sample_incident):
    worker = LogsWorker(fake_tool_clients(), llm_settings)
    result = await worker.run(sample_incident)

    assert len(result.timeline_events) >= 1
    assert result.timeline_events[0].source == "logs_worker"
    assert "NullPointerException" in result.timeline_events[0].event


@pytest.mark.asyncio
async def test_logs_worker_uses_deploy_at_window(llm_settings, sample_incident):
    FakeLogsClient.last_since = None
    deploy_at = sample_incident.opened_at + timedelta(minutes=30)
    worker = LogsWorker(fake_tool_clients(), llm_settings)
    await worker.run(sample_incident, context={"deploy_at": deploy_at})

    expected = deploy_at - timedelta(minutes=2)
    assert FakeLogsClient.last_since is not None
    assert FakeLogsClient.last_since.replace(tzinfo=timezone.utc) == expected


@pytest.mark.asyncio
async def test_logs_worker_context_none(llm_settings, sample_incident):
    worker = LogsWorker(fake_tool_clients(), llm_settings)
    result = await worker.run(sample_incident, context=None)
    assert result.summary
