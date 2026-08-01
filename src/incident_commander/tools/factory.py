"""Factory for live tool clients."""

from incident_commander.config import Settings
from incident_commander.tools.clients import ToolClients
from incident_commander.tools.kubectl import Kubectl
from incident_commander.tools.kubectl_logs import KubectlLogsClient
from incident_commander.tools.kubernetes import KubernetesClient, KubernetesDeployClient
from incident_commander.tools.loki import LokiLogsClient
from incident_commander.tools.prometheus import PrometheusMetricsClient


def build_tool_clients(settings: Settings) -> ToolClients:
    kubectl = Kubectl(settings)
    k8s = KubernetesClient(kubectl)
    deploy = KubernetesDeployClient(kubectl)

    if settings.log_backend == "loki":
        logs = LokiLogsClient(settings)
    else:
        logs = KubectlLogsClient(kubectl, k8s)

    metrics = PrometheusMetricsClient(settings)

    return ToolClients(deploy=deploy, logs=logs, k8s=k8s, metrics=metrics)
