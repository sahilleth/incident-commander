"""Deploy / change correlator worker with ReAct loop."""

from typing import Any

from incident_commander.agents.react import DeterministicStep, ReActTool
from incident_commander.models.incident import Incident, TimelineEvent, WorkerResult
from incident_commander.workers.base import BaseWorker


class DeployCorrelatorWorker(BaseWorker):
    name = "deploy_correlator"

    async def run(
        self, incident: Incident, context: dict[str, Any] | None = None
    ) -> WorkerResult:
        deploys: list = []
        history_text = ""

        since_incident = self._since(incident)
        since_expanded = self._since(
            incident, extra_minutes=self.settings.deploy_lookback_minutes
        )

        async def fetch_recent() -> int:
            nonlocal deploys
            deploys = await self.clients.deploy.recent_deploys(
                incident.service, since_incident, incident.namespace
            )
            return len(deploys)

        async def fetch_expanded() -> int:
            nonlocal deploys
            deploys = await self.clients.deploy.recent_deploys(
                incident.service, since_expanded, incident.namespace
            )
            return len(deploys)

        async def fetch_history() -> str:
            nonlocal history_text
            history_text = await self.clients.deploy.rollout_history_text(
                incident.service, incident.namespace
            )
            return history_text[:200]

        deterministic_steps = [
            DeterministicStep(
                thought="Check replica sets created since incident opened",
                action_name="deploy.recent_deploys",
                run=fetch_recent,
                stop_if=lambda n: n > 0,
            ),
            DeterministicStep(
                thought="Expand deploy lookback window before incident",
                action_name="deploy.recent_deploys_expanded",
                run=fetch_expanded,
                stop_if=lambda n: n > 0,
            ),
            DeterministicStep(
                thought="Read kubectl rollout history for deployment",
                action_name="deploy.rollout_history",
                run=fetch_history,
            ),
        ]

        llm_tools = [
            ReActTool(
                name="recent_deploys_since_incident",
                description=(
                    "List replica set deploy events since the incident opened. "
                    "Start here — check recent ReplicaSets first."
                ),
                handler=lambda _: fetch_recent(),
                parameters={"type": "object", "properties": {}},
            ),
            ReActTool(
                name="recent_deploys_expanded",
                description=(
                    f"Expand the lookback window by {self.settings.deploy_lookback_minutes} "
                    "minutes before the incident opened. Use only if recent_deploys_since_incident "
                    "found nothing."
                ),
                handler=lambda _: fetch_expanded(),
                parameters={"type": "object", "properties": {}},
            ),
            ReActTool(
                name="rollout_history",
                description=(
                    "Fetch kubectl rollout history text as a last resort for revision context "
                    "when deploy events are missing or ambiguous."
                ),
                handler=lambda _: fetch_history(),
                parameters={"type": "object", "properties": {}},
            ),
        ]

        llm_context = {
            "service": incident.service,
            "namespace": incident.namespace,
            "incident_opened_at": since_incident.isoformat(),
            "deploy_lookback_minutes": self.settings.deploy_lookback_minutes,
        }

        if self.settings.llm_is_configured():
            react_result = await self.react.run_llm(
                goal=f"Find deploy changes for {incident.service}",
                tools=llm_tools,
                context=llm_context,
                max_iterations=3,
            )
            if not react_result.finished or react_result.error:
                fallback = await self.react.run_deterministic(
                    goal=f"Find recent deploys for {incident.service}",
                    steps=deterministic_steps,
                )
                react_result.tools_called.extend(fallback.tools_called)
                react_result.iterations += fallback.iterations
                react_result.steps.extend(fallback.steps)
                if fallback.summary:
                    react_result.summary = fallback.summary
                if fallback.finished and not react_result.error:
                    react_result.finished = True
                    react_result.error = None
        else:
            react_result = await self.react.run_deterministic(
                goal=f"Find recent deploys for {incident.service}",
                steps=deterministic_steps,
            )

        events: list[TimelineEvent] = []
        for i, d in enumerate(deploys):
            events.append(
                TimelineEvent(
                    id=self._event_id(incident.incident_id, f"deploy-{i}"),
                    at=d.at,
                    source=self.name,
                    event=f"{d.description} (revision {d.revision})",
                    confidence="high",
                    metadata={"revision": d.revision, "source": d.source},
                )
            )

        if history_text and not deploys:
            events.append(
                TimelineEvent(
                    id=self._event_id(incident.incident_id, "history-0"),
                    at=since_incident,
                    source=self.name,
                    event=f"Rollout history: {history_text[:400]}",
                    confidence="medium",
                    metadata={"type": "rollout_history"},
                )
            )

        if not events:
            react_result.summary = "No deploys detected in incident or lookback window."
        elif deploys:
            latest = deploys[-1]
            react_result.summary = (
                f"Found {len(deploys)} deploy(s). "
                f"Latest revision {latest.revision} at {latest.at.isoformat()}."
            )
        else:
            react_result.summary = (
                "No replica sets in lookback window; rollout history captured."
            )

        return self._to_worker_result(react_result, events)
