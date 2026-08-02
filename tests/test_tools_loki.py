"""Unit tests for Loki HTTP client."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from incident_commander.config import Settings
from incident_commander.tools.loki import LokiLogsClient


@pytest.fixture
def loki_client(tmp_path) -> LokiLogsClient:
    return LokiLogsClient(
        Settings(
            incident_db_path=tmp_path / "loki.db",
            loki_url="http://loki.test",
        )
    )


def _mock_http_client(response: MagicMock):
    client = MagicMock()
    client.get = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    return client


@pytest.mark.asyncio
async def test_top_error_patterns_success(loki_client):
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "data": {
            "result": [
                {
                    "values": [
                        ["1", "ERROR NullPointerException in handler"],
                        ["2", "ERROR NullPointerException in handler"],
                    ]
                }
            ]
        }
    }
    mock_client = _mock_http_client(response)

    with patch("httpx.AsyncClient", return_value=mock_client):
        patterns = await loki_client.top_error_patterns(
            "payment-api",
            datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc),
            "default",
            limit=3,
        )

    assert len(patterns) == 1
    assert patterns[0].count == 2
    assert "NullPointerException" in patterns[0].message


@pytest.mark.asyncio
async def test_top_error_patterns_http_error_returns_empty(loki_client):
    response = MagicMock()
    response.status_code = 500
    mock_client = _mock_http_client(response)

    with patch("httpx.AsyncClient", return_value=mock_client):
        patterns = await loki_client.top_error_patterns(
            "payment-api",
            datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc),
            "default",
        )

    assert patterns == []


@pytest.mark.asyncio
async def test_query_patterns_malformed_json_raises(loki_client):
    response = MagicMock()
    response.status_code = 200
    response.json.side_effect = ValueError("invalid json")
    mock_client = _mock_http_client(response)

    with patch("httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(ValueError, match="invalid json"):
            await loki_client._query_patterns(
                '{app="payment-api"}',
                datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc),
                limit=5,
            )
