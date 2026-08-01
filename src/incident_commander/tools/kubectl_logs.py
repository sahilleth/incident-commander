"""kubectl-based log aggregation when Loki is not used."""

import re
from collections import Counter
from datetime import datetime, timezone

from incident_commander.tools.clients import LogPattern, LogsClient
from incident_commander.tools.kubectl import Kubectl, KubectlError
from incident_commander.tools.kubernetes import KubernetesClient


ERROR_RE = re.compile(r"(error|exception|fatal|panic|failed)", re.IGNORECASE)


class KubectlLogsClient(LogsClient):
    def __init__(self, kubectl: Kubectl, k8s: KubernetesClient) -> None:
        self.kubectl = kubectl
        self.k8s = k8s

    async def top_error_patterns(
        self, service: str, since: datetime, namespace: str, limit: int = 5
    ) -> list[LogPattern]:
        if since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)

        pods = await self.k8s.pods_for_service(service, namespace)
        if not pods:
            return []

        since_str = since.strftime("%Y-%m-%dT%H:%M:%SZ")
        lines: list[str] = []

        for pod in pods[:5]:
            try:
                out = await self.kubectl.run(
                    [
                        "logs",
                        pod.name,
                        "-n",
                        namespace,
                        "--since-time",
                        since_str,
                        "--tail",
                        "300",
                        "--all-containers",
                        "--prefix",
                    ]
                )
                for line in out.splitlines():
                    if ERROR_RE.search(line):
                        lines.append(line.strip())
            except KubectlError:
                continue

        if not lines:
            return []

        normalized = [_strip_prefix(line) for line in lines]
        counts = Counter(normalized)
        return [
            LogPattern(
                first_seen=since,
                message=msg[:500],
                count=count,
                level="error",
            )
            for msg, count in counts.most_common(limit)
        ]


def _strip_prefix(line: str) -> str:
    if "] " in line:
        return line.split("] ", 1)[-1][:500]
    return line[:500]
