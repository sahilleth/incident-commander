"""Kubernetes infrastructure worker with ReAct loop."""

from incident_commander.agents.react import DeterministicStep, ReActTool
from incident_commander.models.incident import TimelineEvent
from incident_commander.workers.base import BaseWorker


class K8sWorker(BaseWorker):
    name = "k8s_worker"

    async def run(self, incident) -> WorkerResult:
        pods: list = []
        warnings: list = []
        since = self._since(incident)

        async def fetch_pods_deployment() -> int:
            nonlocal pods
            pods = await self.clients.k8s.pods_for_service(
                incident.service, incident.namespace
            )
            return len(pods)

        async def fetch_pods_app_label() -> int:
            nonlocal pods
            pods = await self.clients.k8s.pods_by_label(
                f"app={incident.service}", incident.namespace
            )
            return len(pods)

        async def fetch_warnings() -> int:
            nonlocal warnings
            warnings = await self.clients.k8s.recent_warning_events(
                incident.namespace, since
            )
            return len(warnings)

        steps = [
            DeterministicStep(
                thought="List pods for deployment selector",
                action_name="k8s.pods_for_service",
                run=fetch_pods_deployment,
                stop_if=lambda n: n > 0,
            ),
            DeterministicStep(
                thought="Fallback: list pods with app=<service> label",
                action_name="k8s.pods_by_label",
                run=fetch_pods_app_label,
            ),
            DeterministicStep(
                thought="Collect recent warning events in namespace",
                action_name="k8s.recent_warning_events",
                run=fetch_warnings,
            ),
        ]

        react_result = await self.react.run_deterministic(
            goal=f"Assess pod health for {incident.service}",
            steps=steps,
        )

        if self.settings.resolved_llm_api_key() and not pods:
            llm_result = await self.react.run_llm(
                goal=f"Find unhealthy pods for {incident.service}",
                tools=[
                    ReActTool(
                        name="pods_by_label",
                        description="List pods by label selector app=<service>",
                        handler=lambda _: fetch_pods_app_label(),
                        parameters={"type": "object", "properties": {}},
                    ),
                    ReActTool(
                        name="warning_events",
                        description="Recent K8s warning events",
                        handler=lambda _: fetch_warnings(),
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

        events: list[TimelineEvent] = []
        unhealthy = [p for p in pods if not p.ready or p.restarts > 0]

        for i, pod in enumerate(unhealthy):
            detail = pod.reason or pod.phase
            events.append(
                TimelineEvent(
                    id=self._event_id(incident.incident_id, f"pod-{i}"),
                    at=since,
                    source=self.name,
                    event=(
                        f"Pod {pod.namespace}/{pod.name}: {detail}, "
                        f"restarts={pod.restarts}, rev={pod.revision}"
                    ),
                    confidence="high",
                    metadata={
                        "pod": pod.name,
                        "restarts": pod.restarts,
                        "revision": pod.revision,
                    },
                )
            )

        for i, warn in enumerate(warnings[:5]):
            events.append(
                TimelineEvent(
                    id=self._event_id(incident.incident_id, f"event-{i}"),
                    at=since,
                    source=self.name,
                    event=f"K8s warning: {warn}",
                    confidence="medium",
                    metadata={"type": "warning_event"},
                )
            )

        react_result.summary = (
            f"{len(unhealthy)}/{len(pods)} pods unhealthy. "
            f"{len(warnings)} warning events."
        )

        return self._to_worker_result(react_result, events)
