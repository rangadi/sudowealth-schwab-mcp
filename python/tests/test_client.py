from __future__ import annotations

import httpx
import pytest
import respx

from schwab_mcp.auth.tokens import NotAuthenticatedError
from schwab_mcp.client import MARKET_DATA_BASE_URL, SchwabClient, SchwabError, _clean_params


class StubTokens:
    async def get_access_token(self) -> str:
        return "tok-123"


def make_client(http):
    return SchwabClient(http, StubTokens())


def test_clean_params_joins_lists_and_drops_none():
    out = _clean_params({"symbols": ["AAPL", "MSFT"], "fields": None, "indicative": True})
    assert out == {"symbols": "AAPL,MSFT", "indicative": True}


@respx.mock
async def test_get_sends_bearer_and_params(http):
    route = respx.get(f"{MARKET_DATA_BASE_URL}/quotes").mock(
        return_value=httpx.Response(200, json={"AAPL": {}})
    )
    async with httpx.AsyncClient(base_url=MARKET_DATA_BASE_URL) as h:
        result = await make_client(h).get("/quotes", {"symbols": ["AAPL"]})

    assert result == {"AAPL": {}}
    req = route.calls.last.request
    assert req.headers["authorization"] == "Bearer tok-123"
    assert req.url.params["symbols"] == "AAPL"


@respx.mock
async def test_401_maps_to_not_authenticated():
    respx.get(f"{MARKET_DATA_BASE_URL}/quotes").mock(return_value=httpx.Response(401))
    async with httpx.AsyncClient(base_url=MARKET_DATA_BASE_URL) as h:
        with pytest.raises(NotAuthenticatedError):
            await make_client(h).get("/quotes")


@respx.mock
async def test_429_and_500_map_to_schwab_error():
    async with httpx.AsyncClient(base_url=MARKET_DATA_BASE_URL) as h:
        respx.get(f"{MARKET_DATA_BASE_URL}/quotes").mock(return_value=httpx.Response(429))
        with pytest.raises(SchwabError, match="Rate limited"):
            await make_client(h).get("/quotes")
        respx.get(f"{MARKET_DATA_BASE_URL}/x").mock(return_value=httpx.Response(500, text="boom"))
        with pytest.raises(SchwabError, match="500"):
            await make_client(h).get("/x")
