"""Thin authenticated httpx wrapper over the Schwab Market Data API."""

from __future__ import annotations

from typing import Any

import httpx

from .auth.tokens import NotAuthenticatedError, TokenManager

MARKET_DATA_BASE_URL = "https://api.schwabapi.com/marketdata/v1"


class SchwabError(Exception):
    """A Schwab API request failed."""


class SchwabClient:
    def __init__(self, http: httpx.AsyncClient, tokens: TokenManager):
        self._http = http
        self._tokens = tokens

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """GET a Market Data endpoint and return the parsed JSON body."""
        token = await self._tokens.get_access_token()
        resp = await self._http.get(
            path,
            params=_clean_params(params),
            headers={"Authorization": f"Bearer {token}"},
        )
        _raise_for_status(resp)
        return resp.json()


def _clean_params(params: dict[str, Any] | None) -> dict[str, Any]:
    """Drop unset params and join list values into Schwab's comma format."""
    if not params:
        return {}
    cleaned: dict[str, Any] = {}
    for key, value in params.items():
        if value is None:
            continue
        cleaned[key] = ",".join(map(str, value)) if isinstance(value, list) else value
    return cleaned


def _raise_for_status(resp: httpx.Response) -> None:
    if resp.status_code < 400:
        return
    if resp.status_code == 401:
        raise NotAuthenticatedError(
            "Schwab rejected the access token (401). Re-authorize at /authorize."
        )
    if resp.status_code == 429:
        raise SchwabError("Rate limited by Schwab (429). Try again shortly.")
    raise SchwabError(f"Schwab API error {resp.status_code}: {resp.text[:500]}")
