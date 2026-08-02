"""Logs and error pattern worker with ReAct loop."""

from datetime import timedelta
from typing import Any

from incident_commander.agents.react import DeterministicStep, ReActTool
from incident_commander.models.incident import Incident, TimelineEvent, WorkerResult
from incident_commander.workers.base import BaseWorker


class LogsWorker(BaseWorker):
    name = "logs_worker"

    async def run(
        self, incident: Incident, context: dict[str, Any] | None = None
    ) -> WorkerResult:
        context = context or {}
        patterns: list = []
        since_incident = self._since(incident)
        since_expanded = self._since(
            incident, extra_minutes=self.settings.deploy_lookback_minutes
        )
        deploy_at = context.get("deploy_at")

        async def fetch_recent() -> int:
            nonlocal patterns
            patterns = await self.clients.logs.top_error_patterns(
                incident.service, since_incident, incident.namespace
            )
            return len(patterns)

        async def fetch_expanded() -> int:
            nonlocal patterns
            patterns = await self.clients.logs.top_error_patterns(
                incident.service, since_expanded, incident.namespace
            )
            return len(patterns)

        async def fetch_around_deploy() -> int:
            nonlocal patterns
            if deploy_at is None:
                return 0
            anchor = deploy_at
            if anchor.tzinfo is None:
                from datetime import timezone

                anchor = anchor.replace(tzinfo=timezone.utc)
            since = anchor - timedelta(minutes=2)
            patterns = await self.clients.logs.top_error_patterns(
                incident.service, since, incident.namespace
            )
            return len(patterns)

        steps: list[DeterministicStep] = []

        if deploy_at is not None:
            steps.append(
                DeterministicStep(
                    thought="Search error patterns in tight window around deploy timestamp",
                    action_name="logs.top_error_patterns_around_deploy",
                    run=fetch_around_deploy,
                    stop_if=lambda n: n > 0,
                )
            )

        steps.extend(
            [
                DeterministicStep(
                    thought="Search error patterns since incident opened",
                    action_name="logs.top_error_patterns",
                    run=fetch_recent,
                    stop_if=lambda n: n > 0,
                ),
                DeterministicStep(
                    thought="Expand log window and search again",
                    action_name="logs.top_error_patterns_expanded",
                    run=fetch_expanded,
                    stop_if=lambda n: n > 0,
                ),
            ]
        )

        react_result = await self.react.run_deterministic(
            goal=f"Find top error log patterns for {incident.service}",
            steps=steps,
        )

        if self.settings.llm_is_configured() and not patterns:
            llm_result = await self.react.run_llm(
                goal=f"Find error signatures in logs for {incident.service}",
                tools=[
                    ReActTool(
                        name="search_errors",
                        description="Search error/exception patterns in logs",
                        handler=lambda _: fetch_expanded(),
                        parameters={"type": "object", "properties": {}},
                    ),
                ],
                context={
                    "service": incident.service,
                    "namespace": incident.namespace,
                    "deploy_at": deploy_at.isoformat() if deploy_at else None,
                },
                max_iterations=3,
            )
            react_result.tools_called.extend(llm_result.tools_called)
            react_result.iterations += llm_result.iterations
            react_result.steps.extend(llm_result.steps)
            if llm_result.summary:
                react_result.summary = llm_result.summary

        events: list[TimelineEvent] = []
        for i, p in enumerate(patterns):
            events.append(
                TimelineEvent(
                    id=self._event_id(incident.incident_id, f"log-{i}"),
                    at=p.first_seen,
                    source=self.name,
                    event=f"{p.level.upper()}: {p.message} ({p.count} occurrences)",
                    confidence="high",
                    metadata={"count": p.count, "level": p.level},
                )
            )

        if not patterns:
            react_result.summary = "No error patterns in log window."

        return self._to_worker_result(react_result, events)
