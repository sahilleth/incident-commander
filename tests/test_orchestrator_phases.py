"""Orchestrator phase ordering tests."""

import asyncio
import time
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from incident_commander.config import Settings
from incident_commander.models.incident import Incident, IncidentStatus
from incident_commander.orchestrator.commander import IncidentCommander
from incident_commander.state.store import IncidentStore
from incident_commander.workers.k8s import K8sWorker
from incident_commander.workers.logs import LogsWorker
from incident_commander.workers.metrics import MetricsWorker
from tests.fakes import fake_tool_clients

PHASE2_SLEEP_SECONDS = 0.05
PHASE2_CONCURRENT_MAX_SECONDS = 0.12

_ORIGINAL_PHASE2_RUN = {
    LogsWorker: LogsWorker.run,
    K8sWorker: K8sWorker.run,
    MetricsWorker: MetricsWorker.run,
}


def _intervals_overlap(start_a, end_a, start_b, end_b) -> bool:
    return start_a < end_b and start_b < end_a


def _patch_phase2_workers_slow():
    for cls, original in _ORIGINAL_PHASE2_RUN.items():

        async def slow_run(self, incident, context=None, _orig=original):
            await asyncio.sleep(PHASE2_SLEEP_SECONDS)
            return await _orig(self, incident, context)

        cls.run = slow_run  # type: ignore[method-assign]


def _restore_phase2_workers():
    for cls, original in _ORIGINAL_PHASE2_RUN.items():
        cls.run = original  # type: ignore[method-assign]


@pytest.fixture(autouse=True)
def reset_worker_run_methods():
    yield
    _restore_phase2_workers()


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

    phase2_gather_seconds: list[float] = []
    real_gather = asyncio.gather

    async def track_gather(*coroutines, return_exceptions=False):
        if len(coroutines) == 3:
            start = time.perf_counter()
            result = await real_gather(*coroutines, return_exceptions=return_exceptions)
            phase2_gather_seconds.append(time.perf_counter() - start)
            return result
        return await real_gather(*coroutines, return_exceptions=return_exceptions)

    _patch_phase2_workers_slow()

    with patch(
        "incident_commander.orchestrator.commander.asyncio.gather",
        side_effect=track_gather,
    ):
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

    phase2 = [
        by_worker["logs_worker"],
        by_worker["k8s_worker"],
        by_worker["metrics_worker"],
    ]

    # Genuine interval overlap: at least one pair must have intersecting windows.
    overlaps = False
    for i in range(len(phase2)):
        for j in range(i + 1, len(phase2)):
            a, b = phase2[i], phase2[j]
            if a.started_at and a.finished_at and b.started_at and b.finished_at:
                if _intervals_overlap(a.started_at, a.finished_at, b.started_at, b.finished_at):
                    overlaps = True
    assert overlaps, "phase-2 workers did not overlap in time (likely ran sequentially)"

    assert phase2_gather_seconds, "expected to observe phase-2 asyncio.gather"
    assert phase2_gather_seconds[0] < PHASE2_CONCURRENT_MAX_SECONDS
