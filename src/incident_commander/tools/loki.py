"""Loki log query client."""

from collections import Counter
from datetime import datetime, timezone

import httpx

from incident_commander.config import Settings
from incident_commander.tools.clients import LogPattern, LogsClient


class LokiLogsClient(LogsClient):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.base_url = settings.loki_url.rstrip("/")

    async def top_error_patterns(
        self, service: str, since: datetime, namespace: str, limit: int = 5
    ) -> list[LogPattern]:
        if since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)

        # Common label patterns; adjust via query if your Loki labels differ
        queries = [
            f'{{namespace="{namespace}", app="{service}"}} |~ "(?i)error|exception|fatal"',
            f'{{namespace="{namespace}", app_kubernetes_io_name="{service}"}} |~ "(?i)error|exception|fatal"',
            f'{{namespace="{namespace}", pod=~"{service}.*"}} |~ "(?i)error|exception|fatal"',
        ]

        for query in queries:
            patterns = await self._query_patterns(query, since, limit)
            if patterns:
                return patterns
        return []

    async def _query_patterns(
        self, query: str, since: datetime, limit: int
    ) -> list[LogPattern]:
        start_ns = int(since.timestamp() * 1e9)
        end_ns = int(datetime.now(timezone.utc).timestamp() * 1e9)
        params = {
            "query": query,
            "start": start_ns,
            "end": end_ns,
            "limit": 500,
            "direction": "backward",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{self.base_url}/loki/api/v1/query_range",
                params=params,
            )
            if resp.status_code != 200:
                return []
            data = resp.json()

        lines: list[str] = []
        for stream in data.get("data", {}).get("result", []):
            for _ts, line in stream.get("values", []):
                text = line.strip()
                if text:
                    lines.append(text)

        if not lines:
            return []

        normalized = [_normalize_log_line(line) for line in lines]
        counts = Counter(normalized)
        patterns: list[LogPattern] = []
        for message, count in counts.most_common(limit):
            patterns.append(
                LogPattern(
                    first_seen=since,
                    message=message[:500],
                    count=count,
                    level="error",
                )
            )
        return patterns


def _normalize_log_line(line: str) -> str:
    # Strip timestamps / log levels for clustering
    parts = line.split("]", 2)
    if len(parts) >= 3:
        return parts[-1].strip()
    return line[:500]
