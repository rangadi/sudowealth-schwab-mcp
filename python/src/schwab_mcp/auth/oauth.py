"""Schwab OAuth 2.0 authorization-code helpers (pure request/response logic)."""

from __future__ import annotations

import base64
from urllib.parse import urlencode

import httpx

from ..config import Settings

AUTHORIZE_URL = "https://api.schwabapi.com/v1/oauth/authorize"
TOKEN_URL = "https://api.schwabapi.com/v1/oauth/token"


class OAuthError(Exception):
    """Schwab rejected a token request."""


def build_authorize_url(settings: Settings, state: str) -> str:
    params = {
        "response_type": "code",
        "client_id": settings.schwab_client_id.get_secret_value(),
        "redirect_uri": settings.schwab_redirect_uri,
        "scope": settings.scope,
        "state": state,
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


def _basic_auth(settings: Settings) -> str:
    raw = (
        f"{settings.schwab_client_id.get_secret_value()}:"
        f"{settings.schwab_client_secret.get_secret_value()}"
    )
    return "Basic " + base64.b64encode(raw.encode()).decode()


async def _post_token(settings: Settings, form: dict, http: httpx.AsyncClient) -> dict:
    resp = await http.post(
        TOKEN_URL,
        data=form,
        headers={
            "Authorization": _basic_auth(settings),
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    if resp.status_code >= 400:
        raise OAuthError(f"Schwab token endpoint returned {resp.status_code}: {resp.text}")
    return resp.json()


async def exchange_code(settings: Settings, code: str, http: httpx.AsyncClient) -> dict:
    """Trade an authorization code for the initial access/refresh tokens."""
    return await _post_token(
        settings,
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.schwab_redirect_uri,
        },
        http,
    )


async def refresh_tokens(settings: Settings, refresh_token: str, http: httpx.AsyncClient) -> dict:
    """Exchange a refresh token for a fresh access token."""
    data = await _post_token(
        settings,
        {"grant_type": "refresh_token", "refresh_token": refresh_token},
        http,
    )
    # Schwab reuses the same refresh token; keep the old one if none is returned.
    data.setdefault("refresh_token", refresh_token)
    return data
