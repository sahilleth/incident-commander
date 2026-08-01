"""Prometheus metrics client."""

from datetime import datetime, timezone

import httpx

from incident_commander.config import Settings
from incident_commander.tools.clients import MetricSnapshot, MetricsClient


def _substitute_prom_query(template: str, service: str, namespace: str) -> str:
    return template.replace("{service}", service).replace("{namespace}", namespace)


class PrometheusMetricsClient(MetricsClient):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.base_url = settings.prometheus_url.rstrip("/")

    async def snapshot(
        self, service: str, since: datetime, namespace: str = "default"
    ) -> MetricSnapshot | None:
        error_q = _substitute_prom_query(
            self.settings.prom_error_rate_query, service, namespace
        )
        p99_q = _substitute_prom_query(
            self.settings.prom_p99_latency_query, service, namespace
        )
        rps_q = _substitute_prom_query(
            self.settings.prom_request_rate_query, service, namespace
        )

        error_rate = await self._instant_query(error_q)
        p99 = await self._instant_query(p99_q)
        rps = await self._instant_query(rps_q)

        if error_rate is None and p99 is None and rps is None:
            return None

        return MetricSnapshot(
            at=datetime.now(timezone.utc),
            error_rate_pct=error_rate or 0.0,
            p99_latency_ms=p99 or 0.0,
            request_rate=rps or 0.0,
            baseline_error_rate_pct=1.0,
            source="prometheus",
            notes="kube-state-metrics restart rate (override PROM_*_QUERY for app metrics)",
        )

    async def _instant_query(self, query: str) -> float | None:
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(
                    f"{self.base_url}/api/v1/query",
                    params={"query": query},
                )
            except httpx.HTTPError:
                return None
            if resp.status_code != 200:
                return None
            data = resp.json()
            if data.get("status") != "success":
                return None
            results = data.get("data", {}).get("result", [])
            if not results:
                return None
            value = results[0].get("value", [])
            if len(value) < 2:
                return None
            try:
                return float(value[1])
            except (TypeError, ValueError):
                return None
