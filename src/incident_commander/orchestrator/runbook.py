"""Execute approved mitigation actions against live infrastructure."""

from incident_commander.models.incident import Incident, SuggestedAction
from incident_commander.tools.clients import K8sClient, ToolClients


class RunbookExecutor:
    def __init__(self, clients: ToolClients) -> None:
        self.clients = clients

    async def execute(self, incident: Incident, action: SuggestedAction) -> str:
        action_type = action.type.lower()

        if action_type == "rollback":
            return await self._rollback(incident, action)
        if action_type == "scale":
            return await self._scale(incident, action)
        if action_type == "investigate":
            return "Investigation recorded; no automated action executed"
        if action_type == "escalate":
            return "Escalation recorded; notify on-call manually"

        raise ValueError(f"Unknown action type: {action.type}")

    async def _rollback(self, incident: Incident, action: SuggestedAction) -> str:
        service = action.params.get("service", incident.service)
        namespace = action.params.get("namespace", incident.namespace)
        return await self.clients.k8s.rollout_undo(service, namespace)

    async def _scale(self, incident: Incident, action: SuggestedAction) -> str:
        service = action.params.get("service", incident.service)
        namespace = action.params.get("namespace", incident.namespace)
        replicas = action.params.get("replicas")
        if replicas is None:
            raise ValueError("scale action requires replicas in params")
        return await self.clients.k8s.scale_deployment(service, namespace, int(replicas))
