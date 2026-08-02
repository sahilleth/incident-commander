"""Tests for K8sWorker."""

from datetime import datetime, timezone

import pytest

from incident_commander.config import Settings
from incident_commander.models.incident import Incident, IncidentStatus
from incident_commander.workers.k8s import K8sWorker
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
        incident_id="INC-TEST-K8S",
        status=IncidentStatus.INVESTIGATING,
        opened_at=datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc),
        trigger="test",
        service="payment-api",
        namespace="default",
    )


@pytest.mark.asyncio
async def test_k8s_worker_deterministic_timeline(llm_settings, sample_incident):
    worker = K8sWorker(fake_tool_clients(), llm_settings)
    result = await worker.run(sample_incident)

    assert any(e.source == "k8s_worker" for e in result.timeline_events)
    assert any("CrashLoopBackOff" in e.event for e in result.timeline_events)


@pytest.mark.asyncio
async def test_k8s_worker_context_none(llm_settings, sample_incident):
    worker = K8sWorker(fake_tool_clients(), llm_settings)
    result = await worker.run(sample_incident, context=None)
    assert "pods unhealthy" in result.summary.lower() or "warning" in result.summary.lower()


@pytest.mark.asyncio
async def test_k8s_worker_ignores_deploy_context(llm_settings, sample_incident):
    worker = K8sWorker(fake_tool_clients(), llm_settings)
    deploy_at = datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc)
    result = await worker.run(sample_incident, context={"deploy_at": deploy_at})
    assert len(result.timeline_events) >= 1
