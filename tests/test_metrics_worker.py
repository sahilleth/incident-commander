"""Tests for MetricsWorker."""

from datetime import datetime, timezone

import pytest

from incident_commander.config import Settings
from incident_commander.models.incident import Incident, IncidentStatus
from incident_commander.workers.metrics import MetricsWorker
from tests.fakes import fake_tool_clients


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
        incident_id="INC-TEST-METRICS",
        status=IncidentStatus.INVESTIGATING,
        opened_at=datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc),
        trigger="test",
        service="payment-api",
        namespace="default",
    )


@pytest.mark.asyncio
async def test_metrics_worker_deterministic_timeline(llm_settings, sample_incident):
    worker = MetricsWorker(fake_tool_clients(), llm_settings)
    result = await worker.run(sample_incident)

    assert len(result.timeline_events) == 1
    assert result.timeline_events[0].source == "metrics_worker"
    assert "Error rate" in result.timeline_events[0].event


@pytest.mark.asyncio
async def test_metrics_worker_context_none(llm_settings, sample_incident):
    worker = MetricsWorker(fake_tool_clients(), llm_settings)
    result = await worker.run(sample_incident, context=None)
    assert "error rate" in result.summary.lower()


@pytest.mark.asyncio
async def test_metrics_worker_with_deploy_context(llm_settings, sample_incident):
    worker = MetricsWorker(fake_tool_clients(), llm_settings)
    deploy_at = datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc)
    result = await worker.run(sample_incident, context={"deploy_at": deploy_at})
    assert len(result.timeline_events) == 1
