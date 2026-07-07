from __future__ import annotations

import httpx
import pytest
import respx

from schwab_mcp.client import MARKET_DATA_BASE_URL, SchwabClient
from schwab_mcp.server import build_mcp


class StubTokens:
    async def get_access_token(self) -> str:
        return "tok"

    def describe_auth(self) -> dict:
        return {"authenticated": False}


EXPECTED_TOOLS = {
    "status",
    "getQuotes",
    "getQuoteBySymbolId",
    "getOptionChain",
    "getOptionExpirationChain",
    "getPriceHistory",
    "getMovers",
    "getMarketHours",
    "getMarketHoursByMarketId",
    "searchInstruments",
    "getInstrumentByCusip",
}


@pytest.fixture
async def mcp():
    async with httpx.AsyncClient(base_url=MARKET_DATA_BASE_URL) as h:
        tokens = StubTokens()
        yield build_mcp(SchwabClient(h, tokens), tokens)


async def test_all_tools_registered(mcp):
    names = {t.name for t in await mcp.list_tools()}
    assert names == EXPECTED_TOOLS


@respx.mock
async def test_getquotes_maps_to_request(mcp):
    route = respx.get(f"{MARKET_DATA_BASE_URL}/quotes").mock(
        return_value=httpx.Response(200, json={"AAPL": {"symbol": "AAPL"}})
    )
    await mcp.call_tool("getQuotes", {"symbols": ["AAPL", "MSFT"], "fields": "quote"})

    req = route.calls.last.request
    assert req.url.params["symbols"] == "AAPL,MSFT"
    assert req.url.params["fields"] == "quote"


@respx.mock
async def test_path_param_tool(mcp):
    route = respx.get(f"{MARKET_DATA_BASE_URL}/movers/$SPX").mock(
        return_value=httpx.Response(200, json={"screeners": []})
    )
    await mcp.call_tool("getMovers", {"symbol_id": "$SPX", "sort": "VOLUME"})
    assert route.called
    assert route.calls.last.request.url.params["sort"] == "VOLUME"
