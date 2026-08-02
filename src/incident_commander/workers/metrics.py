"""Metrics and SLO analyst worker with ReAct loop."""

import asyncio

from typing import Any

from incident_commander.agents.react import DeterministicStep, ReActTool
from incident_commander.models.incident import Incident, TimelineEvent, WorkerResult
from incident_commander.workers.base import BaseWorker


class MetricsWorker(BaseWorker):
    name = "metrics_worker"

    async def run(
        self, incident: Incident, context: dict[str, Any] | None = None
    ) -> WorkerResult:
        snap = None
        since = self._since(incident)

        async def fetch_snapshot() -> str:
            nonlocal snap
            snap = await self.clients.metrics.snapshot(
                incident.service, since, incident.namespace
            )
            return "ok" if snap else "empty"

        async def retry_snapshot() -> str:
            await asyncio.sleep(2)
            nonlocal snap
            snap = await self.clients.metrics.snapshot(
                incident.service, since, incident.namespace
            )
            return "ok" if snap else "empty"

        steps = [
            DeterministicStep(
                thought="Query Prometheus for error rate and latency",
                action_name="metrics.snapshot",
                run=fetch_snapshot,
                stop_if=lambda s: s == "ok",
            ),
            DeterministicStep(
                thought="Retry metrics query after short delay",
                action_name="metrics.snapshot_retry",
                run=retry_snapshot,
            ),
        ]

        react_result = await self.react.run_deterministic(
            goal=f"Measure golden signals for {incident.service}",
            steps=steps,
        )

        if self.settings.llm_is_configured() and snap is None:
            llm_result = await self.react.run_llm(
                goal=f"Get service metrics for {incident.service}",
                tools=[
                    ReActTool(
                        name="prometheus_snapshot",
                        description="Instant query error rate, p99, RPS",
                        handler=lambda _: retry_snapshot(),
                        parameters={"type": "object", "properties": {}},
                    ),
                ],
                context={
                    "service": incident.service,
                    "namespace": incident.namespace,
                },
                max_iterations=2,
            )
            react_result.tools_called.extend(llm_result.tools_called)
            react_result.iterations += llm_result.iterations

        events: list[TimelineEvent] = []
        if snap is None:
            react_result.summary = (
                "No Prometheus metrics matched configured queries for this service."
            )
            return self._to_worker_result(react_result, events)

        spike = snap.error_rate_pct > snap.baseline_error_rate_pct * 2
        confidence = "high" if spike else "medium"
        note_suffix = f" [{snap.notes}]" if snap.notes else ""
        events.append(
            TimelineEvent(
                id=self._event_id(incident.incident_id, "metrics-0"),
                at=snap.at,
                source=self.name,
                event=(
                    f"Error rate {snap.error_rate_pct:.1f}% "
                    f"(baseline {snap.baseline_error_rate_pct:.1f}%), "
                    f"P99 {snap.p99_latency_ms:.0f}ms, "
                    f"RPS {snap.request_rate:.1f} "
                    f"(source: {snap.source}){note_suffix}"
                ),
                confidence=confidence,
                metadata={
                    "error_rate_pct": snap.error_rate_pct,
                    "p99_latency_ms": snap.p99_latency_ms,
                    "request_rate": snap.request_rate,
                },
            )
        )
        react_result.summary = (
            f"Error rate {snap.error_rate_pct:.1f}% vs baseline "
            f"{snap.baseline_error_rate_pct:.1f}%."
        )

        return self._to_worker_result(react_result, events)
