"""Parse Alertmanager webhook payloads into incident open parameters."""

from typing import Any


def parse_alertmanager_payload(body: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Extract open-incident params from Alertmanager webhook JSON.
    Only returns entries for firing alerts with a resolvable deployment/service name.
    """
    alerts = body.get("alerts") or []
    results: list[dict[str, Any]] = []

    for alert in alerts:
        if str(alert.get("status", "")).lower() != "firing":
            continue

        labels = alert.get("labels") or {}
        annotations = alert.get("annotations") or {}

        service = _extract_service(labels)
        if not service:
            continue

        namespace = labels.get("namespace") or labels.get("kubernetes_namespace") or "default"
        alertname = labels.get("alertname") or "unknown"
        severity = labels.get("severity") or labels.get("priority") or "SEV2"

        trigger = f"alertmanager:{alertname}"
        summary = annotations.get("summary") or annotations.get("description") or alertname

        results.append(
            {
                "service": service,
                "namespace": namespace,
                "trigger": trigger,
                "severity": _normalize_severity(severity),
                "summary": summary,
                "alertname": alertname,
            }
        )

    return results


def _extract_service(labels: dict[str, Any]) -> str | None:
    for key in ("deployment", "service", "app", "app_kubernetes_io_name", "name"):
        value = labels.get(key)
        if value and isinstance(value, str):
            return value.strip()

    pod = labels.get("pod")
    if pod and isinstance(pod, str):
        # payment-api-7d4f8b-xyz → payment-api
        parts = pod.rsplit("-", 2)
        if len(parts) >= 1:
            return parts[0]

    return None


def _normalize_severity(raw: str) -> str:
    upper = raw.upper()
    if upper.startswith("SEV"):
        return upper
    mapping = {
        "critical": "SEV1",
        "high": "SEV1",
        "warning": "SEV2",
        "medium": "SEV2",
        "info": "SEV3",
        "low": "SEV3",
    }
    return mapping.get(raw.lower(), "SEV2")
