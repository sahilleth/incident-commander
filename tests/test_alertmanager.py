"""Alertmanager webhook parsing tests."""

from incident_commander.api.alertmanager import parse_alertmanager_payload


def test_parse_firing_alert_with_deployment_label() -> None:
    body = {
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": "HighErrorRate",
                    "deployment": "payment-api",
                    "namespace": "production",
                    "severity": "critical",
                },
                "annotations": {"summary": "Error rate above 5%"},
            },
            {"status": "resolved", "labels": {"deployment": "other"}},
        ],
    }
    parsed = parse_alertmanager_payload(body)
    assert len(parsed) == 1
    assert parsed[0]["service"] == "payment-api"
    assert parsed[0]["namespace"] == "production"
    assert parsed[0]["trigger"] == "alertmanager:HighErrorRate"
    assert parsed[0]["severity"] == "SEV1"


def test_parse_pod_label_fallback() -> None:
    body = {
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": "PodCrashLooping",
                    "pod": "payment-api-abc123-xyz",
                    "namespace": "default",
                },
            },
        ],
    }
    parsed = parse_alertmanager_payload(body)
    assert parsed[0]["service"] == "payment-api"
