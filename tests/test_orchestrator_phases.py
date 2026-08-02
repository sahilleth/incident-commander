"""Orchestrator phase ordering tests."""

from datetime import datetime, timezone

import pytest

from incident_commander.config import Settings
from incident_commander.models.incident import Incident, IncidentStatus
from incident_commander.orchestrator.commander import IncidentCommander
from incident_commander.state.store import IncidentStore
from tests.fakes import fake_tool_clients


@pytest.mark.asyncio
async def test_deploy_finishes_before_phase2_workers_start(tmp_path):
    settings = Settings(
        incident_db_path=tmp_path / "phases.db",
        groq_api_key="",
        groq_api_key_fallback="",
        verify_max_attempts=1,
        verify_interval_seconds=0,
    )
    store = IncidentStore(settings.incident_db_path)
    await store.init()
    cmd = IncidentCommander(settings, store)
    cmd.clients = fake_tool_clients()

    incident = Incident(
        incident_id="INC-PHASES",
        status=IncidentStatus.INVESTIGATING,
        opened_at=datetime.now(timezone.utc),
        trigger="test",
        service="payment-api",
        namespace="default",
    )
    await store.save(incident)

    await cmd.investigate(incident.incident_id)
    loaded = await store.get(incident.incident_id)
    assert loaded is not None

    by_worker = {run.worker: run for run in loaded.worker_runs}
    deploy_finished = by_worker["deploy_correlator"].finished_at
    logs_started = by_worker["logs_worker"].started_at
    k8s_started = by_worker["k8s_worker"].started_at
    metrics_started = by_worker["metrics_worker"].started_at

    assert deploy_finished is not None
    assert logs_started is not None
    assert deploy_finished <= logs_started
    assert deploy_finished <= k8s_started
    assert deploy_finished <= metrics_started

    # Phase 2 workers overlap (started before the slowest among them finished)
    phase2 = [
        by_worker["logs_worker"],
        by_worker["k8s_worker"],
        by_worker["metrics_worker"],
    ]
    earliest_start = min(r.started_at for r in phase2 if r.started_at)
    latest_finish = max(r.finished_at for r in phase2 if r.finished_at)
    assert earliest_start <= latest_finish
