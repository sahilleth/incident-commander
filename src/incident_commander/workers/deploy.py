"""Deploy / change correlator worker with ReAct loop."""

from incident_commander.agents.react import DeterministicStep, ReActTool
from incident_commander.models.incident import TimelineEvent, WorkerResult
from incident_commander.workers.base import BaseWorker


class DeployCorrelatorWorker(BaseWorker):
    name = "deploy_correlator"

    async def run(self, incident) -> WorkerResult:
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

        steps = [
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

        react_result = await self.react.run_deterministic(
            goal=f"Find recent deploys for {incident.service}",
            steps=steps,
        )

        if self.settings.llm_is_configured() and not deploys:
            llm_result = await self.react.run_llm(
                goal=f"Find deploy changes for {incident.service}",
                tools=[
                    ReActTool(
                        name="recent_deploys",
                        description="List replica set deploy events since timestamp",
                        handler=lambda _: fetch_expanded(),
                        parameters={"type": "object", "properties": {}},
                    ),
                    ReActTool(
                        name="rollout_history",
                        description="kubectl rollout history text",
                        handler=lambda _: fetch_history(),
                        parameters={"type": "object", "properties": {}},
                    ),
                ],
                context={
                    "service": incident.service,
                    "namespace": incident.namespace,
                },
                max_iterations=3,
            )
            react_result.tools_called.extend(llm_result.tools_called)
            react_result.iterations += llm_result.iterations
            if llm_result.summary:
                react_result.summary = llm_result.summary

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
