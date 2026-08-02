"""API authentication dependencies."""

import secrets

from fastapi import HTTPException, Request


def _bearer_token(request: Request) -> str | None:
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        return None
    return auth[7:].strip()


async def require_auth(request: Request) -> None:
    """Bearer token auth when `INCIDENT_COMMANDER_API_TOKEN` is configured."""
    settings = request.app.state.settings
    expected = settings.api_auth_token
    if not expected:
        return

    token = _bearer_token(request)
    if token is None:
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid Authorization header. Use: Bearer <token>",
        )
    if not secrets.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="Invalid API token")


async def require_webhook_auth(request: Request) -> None:
    """Header token auth for Alertmanager webhook when configured."""
    settings = request.app.state.settings
    expected = settings.alertmanager_webhook_token
    if not expected:
        return

    header_name = settings.alertmanager_webhook_header
    value = request.headers.get(header_name)
    if value is None:
        raise HTTPException(
            status_code=401,
            detail=f"Missing webhook auth header: {header_name}",
        )
    if not secrets.compare_digest(value, expected):
        raise HTTPException(status_code=401, detail="Invalid webhook token")
