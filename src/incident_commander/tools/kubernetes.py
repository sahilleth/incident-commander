"""Live Kubernetes and deploy clients via kubectl."""

from datetime import datetime, timezone

from incident_commander.tools.clients import DeployClient, DeployEvent, K8sClient, PodStatus
from incident_commander.tools.kubectl import Kubectl, KubectlError


def _parse_k8s_time(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _normalize_since(since: datetime) -> datetime:
    if since.tzinfo is None:
        return since.replace(tzinfo=timezone.utc)
    return since


class KubernetesDeployClient(DeployClient):
    def __init__(self, kubectl: Kubectl) -> None:
        self.kubectl = kubectl

    async def _deployment_selector(self, service: str, namespace: str) -> str | None:
        try:
            dep = await self.kubectl.get_json("deployment", service, namespace)
        except KubectlError:
            return None
        labels = dep.get("spec", {}).get("selector", {}).get("matchLabels", {})
        if not labels:
            return None
        return ",".join(f"{k}={v}" for k, v in labels.items())

    async def recent_deploys(
        self, service: str, since: datetime, namespace: str
    ) -> list[DeployEvent]:
        since = _normalize_since(since)
        selector = await self._deployment_selector(service, namespace)
        if not selector:
            return []

        rs_data = await self.kubectl.list_json("replicaset", namespace, selector)
        events: list[DeployEvent] = []

        for item in rs_data.get("items", []):
            meta = item.get("metadata", {})
            created = meta.get("creationTimestamp")
            if not created:
                continue
            at = _parse_k8s_time(created)
            if at < since:
                continue
            revision = meta.get("annotations", {}).get(
                "deployment.kubernetes.io/revision", "unknown"
            )
            rs_name = meta.get("name", "unknown")
            events.append(
                DeployEvent(
                    at=at,
                    service=service,
                    revision=str(revision),
                    description=f"ReplicaSet {rs_name} created for deployment {service}",
                    source="kubernetes",
                )
            )

        return sorted(events, key=lambda e: e.at)

    async def rollout_history_text(self, service: str, namespace: str) -> str:
        try:
            out = await self.kubectl.run(
                ["rollout", "history", f"deployment/{service}", "-n", namespace]
            )
            return out.strip()[:2000]
        except KubectlError as exc:
            return f"rollout history unavailable: {exc}"


def _parse_pods(items: list, namespace: str) -> list[PodStatus]:
    pods: list[PodStatus] = []
    for item in items:
        meta = item.get("metadata", {})
        status = item.get("status", {})
        phase = status.get("phase", "Unknown")
        name = meta.get("name", "")
        revision = meta.get("annotations", {}).get(
            "deployment.kubernetes.io/revision"
        )
        ready = True
        restarts = 0
        reason = None
        for cs in status.get("containerStatuses", []):
            restarts = max(restarts, cs.get("restartCount", 0))
            if not cs.get("ready", False):
                ready = False
            state = cs.get("state", {})
            waiting = state.get("waiting", {})
            if waiting.get("reason"):
                reason = waiting["reason"]
            terminated = state.get("terminated", {})
            if terminated.get("reason"):
                reason = terminated["reason"]
        pods.append(
            PodStatus(
                name=name,
                namespace=namespace,
                phase=phase,
                ready=ready,
                restarts=restarts,
                reason=reason,
                revision=revision,
            )
        )
    return pods


class KubernetesClient(K8sClient):
    def __init__(self, kubectl: Kubectl) -> None:
        self.kubectl = kubectl
        self._deploy = KubernetesDeployClient(kubectl)

    async def _pod_selector(self, service: str, namespace: str) -> str | None:
        return await self._deploy._deployment_selector(service, namespace)

    async def pods_by_label(
        self, label_selector: str, namespace: str
    ) -> list[PodStatus]:
        pod_data = await self.kubectl.list_json("pods", namespace, label_selector)
        return _parse_pods(pod_data.get("items", []), namespace)

    async def pods_for_service(self, service: str, namespace: str) -> list[PodStatus]:
        selector = await self._pod_selector(service, namespace)
        if not selector:
            return []
        return await self.pods_by_label(selector, namespace)

    async def recent_warning_events(
        self, namespace: str, since: datetime
    ) -> list[str]:
        since = _normalize_since(since)
        try:
            out = await self.kubectl.run(
                [
                    "get",
                    "events",
                    "-n",
                    namespace,
                    "--field-selector",
                    "type=Warning",
                    "-o",
                    "json",
                ]
            )
        except KubectlError:
            return []

        import json

        data = json.loads(out)
        messages: list[str] = []
        for item in data.get("items", []):
            meta = item.get("metadata", {})
            last = meta.get("lastTimestamp") or meta.get("eventTime")
            if not last:
                continue
            at = _parse_k8s_time(last)
            if at < since:
                continue
            reason = item.get("reason", "")
            message = item.get("message", "")
            involved = item.get("involvedObject", {})
            obj = f"{involved.get('kind', '')}/{involved.get('name', '')}"
            messages.append(f"{obj} {reason}: {message}".strip())

        return messages[:20]

    async def rollout_undo(self, service: str, namespace: str) -> str:
        out = await self.kubectl.run(
            ["rollout", "undo", f"deployment/{service}", "-n", namespace]
        )
        return out.strip() or f"rollout undo deployment/{service} succeeded"
