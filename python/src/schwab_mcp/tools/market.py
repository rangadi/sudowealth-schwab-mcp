"""The 10 read-only Schwab Market Data tools.

Parameter names mirror the Schwab query parameters verbatim so the mapping to
the API is obvious. Enums come straight from the OpenAPI spec.
"""

from __future__ import annotations

from typing import Literal

from mcp.server.fastmcp import FastMCP

from ..client import SchwabClient

ContractType = Literal["CALL", "PUT", "ALL"]
Strategy = Literal[
    "SINGLE",
    "ANALYTICAL",
    "COVERED",
    "VERTICAL",
    "CALENDAR",
    "STRANGLE",
    "STRADDLE",
    "BUTTERFLY",
    "CONDOR",
    "DIAGONAL",
    "COLLAR",
    "ROLL",
]
ExpMonth = Literal[
    "JAN",
    "FEB",
    "MAR",
    "APR",
    "MAY",
    "JUN",
    "JUL",
    "AUG",
    "SEP",
    "OCT",
    "NOV",
    "DEC",
    "ALL",
]
Entitlement = Literal["PN", "NP", "PP"]
PeriodType = Literal["day", "month", "year", "ytd"]
FrequencyType = Literal["minute", "daily", "weekly", "monthly"]
MoverIndex = Literal[
    "$DJI",
    "$COMPX",
    "$SPX",
    "NYSE",
    "NASDAQ",
    "OTCBB",
    "INDEX_ALL",
    "EQUITY_ALL",
    "OPTION_ALL",
    "OPTION_PUT",
    "OPTION_CALL",
]
MoverSort = Literal["VOLUME", "TRADES", "PERCENT_CHANGE_UP", "PERCENT_CHANGE_DOWN"]
MoverFrequency = Literal[0, 1, 5, 10, 30, 60]
MarketId = Literal["equity", "option", "bond", "future", "forex"]
Projection = Literal[
    "symbol-search", "symbol-regex", "desc-search", "desc-regex", "search", "fundamental"
]


def register_market_tools(mcp: FastMCP, client: SchwabClient) -> None:
    @mcp.tool(name="getQuotes", description="Get quotes for a list of symbols.")
    async def get_quotes(
        symbols: list[str],
        fields: str | None = None,
        indicative: bool | None = None,
    ):
        return await client.get(
            "/quotes",
            {"symbols": symbols, "fields": fields, "indicative": indicative},
        )

    @mcp.tool(name="getQuoteBySymbolId", description="Get the quote for a single symbol.")
    async def get_quote_by_symbol_id(symbol_id: str, fields: str | None = None):
        return await client.get(f"/{symbol_id}/quotes", {"fields": fields})

    @mcp.tool(
        name="getOptionChain",
        description="Get the option chain (with Greeks) for an optionable symbol.",
    )
    async def get_option_chain(
        symbol: str,
        contractType: ContractType | None = None,
        strikeCount: int | None = None,
        includeUnderlyingQuote: bool | None = None,
        strategy: Strategy | None = None,
        interval: float | None = None,
        strike: float | None = None,
        range: str | None = None,
        fromDate: str | None = None,
        toDate: str | None = None,
        expMonth: ExpMonth | None = None,
        entitlement: Entitlement | None = None,
    ):
        return await client.get(
            "/chains",
            {
                "symbol": symbol,
                "contractType": contractType,
                "strikeCount": strikeCount,
                "includeUnderlyingQuote": includeUnderlyingQuote,
                "strategy": strategy,
                "interval": interval,
                "strike": strike,
                "range": range,
                "fromDate": fromDate,
                "toDate": toDate,
                "expMonth": expMonth,
                "entitlement": entitlement,
            },
        )

    @mcp.tool(
        name="getOptionExpirationChain",
        description="Get the option expiration chain for an optionable symbol.",
    )
    async def get_option_expiration_chain(symbol: str):
        return await client.get("/expirationchain", {"symbol": symbol})

    @mcp.tool(
        name="getPriceHistory",
        description="Get price-history candles for a symbol and date range.",
    )
    async def get_price_history(
        symbol: str,
        periodType: PeriodType | None = None,
        period: int | None = None,
        frequencyType: FrequencyType | None = None,
        frequency: int | None = None,
        startDate: int | None = None,
        endDate: int | None = None,
        needExtendedHoursData: bool | None = None,
        needPreviousClose: bool | None = None,
    ):
        return await client.get(
            "/pricehistory",
            {
                "symbol": symbol,
                "periodType": periodType,
                "period": period,
                "frequencyType": frequencyType,
                "frequency": frequency,
                "startDate": startDate,
                "endDate": endDate,
                "needExtendedHoursData": needExtendedHoursData,
                "needPreviousClose": needPreviousClose,
            },
        )

    @mcp.tool(name="getMovers", description="Get the movers for an index.")
    async def get_movers(
        symbol_id: MoverIndex,
        sort: MoverSort | None = None,
        frequency: MoverFrequency | None = None,
    ):
        return await client.get(f"/movers/{symbol_id}", {"sort": sort, "frequency": frequency})

    @mcp.tool(name="getMarketHours", description="Get market hours for one or more markets.")
    async def get_market_hours(markets: list[MarketId], date: str | None = None):
        return await client.get("/markets", {"markets": markets, "date": date})

    @mcp.tool(
        name="getMarketHoursByMarketId",
        description="Get market hours for a specific market.",
    )
    async def get_market_hours_by_market_id(market_id: MarketId, date: str | None = None):
        return await client.get(f"/markets/{market_id}", {"date": date})

    @mcp.tool(
        name="searchInstruments",
        description="Search instruments by symbol and projection type.",
    )
    async def search_instruments(symbol: str, projection: Projection):
        return await client.get("/instruments", {"symbol": symbol, "projection": projection})

    @mcp.tool(name="getInstrumentByCusip", description="Get an instrument by its CUSIP.")
    async def get_instrument_by_cusip(cusip_id: str):
        return await client.get(f"/instruments/{cusip_id}")
