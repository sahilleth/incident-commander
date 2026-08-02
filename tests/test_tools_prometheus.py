"""Unit tests for Prometheus HTTP client."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from incident_commander.config import Settings
from incident_commander.tools.prometheus import PrometheusMetricsClient


@pytest.fixture
def prom_client(tmp_path) -> PrometheusMetricsClient:
    return PrometheusMetricsClient(
        Settings(
            incident_db_path=tmp_path / "prom.db",
            prometheus_url="http://prom.test",
        )
    )


def _mock_http_client(response: MagicMock | None = None, get_error: Exception | None = None):
    client = MagicMock()
    if get_error is not None:
        client.get = AsyncMock(side_effect=get_error)
    else:
        client.get = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    return client


@pytest.mark.asyncio
async def test_instant_query_success(prom_client):
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "status": "success",
        "data": {"result": [{"value": [1234567890.0, "8.5"]}]},
    }
    mock_client = _mock_http_client(response)

    with patch("httpx.AsyncClient", return_value=mock_client):
        value = await prom_client._instant_query("up")

    assert value == 8.5


@pytest.mark.asyncio
async def test_instant_query_http_error_returns_none(prom_client):
    response = MagicMock()
    response.status_code = 503
    mock_client = _mock_http_client(response)

    with patch("httpx.AsyncClient", return_value=mock_client):
        value = await prom_client._instant_query("up")

    assert value is None


@pytest.mark.asyncio
async def test_instant_query_network_error_returns_none(prom_client):
    mock_client = _mock_http_client(get_error=httpx.ConnectError("down"))

    with patch("httpx.AsyncClient", return_value=mock_client):
        value = await prom_client._instant_query("up")

    assert value is None


@pytest.mark.asyncio
async def test_instant_query_malformed_json_returns_none(prom_client):
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"status": "success", "data": {"result": [{"value": ["ts"]}]}}
    mock_client = _mock_http_client(response)

    with patch("httpx.AsyncClient", return_value=mock_client):
        value = await prom_client._instant_query("up")

    assert value is None


@pytest.mark.asyncio
async def test_snapshot_builds_metric_snapshot(prom_client):
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "status": "success",
        "data": {"result": [{"value": [1.0, "5.0"]}]},
    }
    mock_client = _mock_http_client(response)

    with patch("httpx.AsyncClient", return_value=mock_client):
        snap = await prom_client.snapshot(
            "payment-api",
            datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc),
            "default",
        )

    assert snap is not None
    assert snap.error_rate_pct == 5.0
    assert snap.source == "prometheus"
