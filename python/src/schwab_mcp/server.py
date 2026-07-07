"""Builds the FastMCP application (plain-HTTP `/mcp` transport)."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .auth.tokens import TokenManager
from .client import SchwabClient
from .tools.market import register_market_tools

APP_NAME = "schwab-mcp"


def build_mcp(client: SchwabClient, tokens: TokenManager) -> FastMCP:
    mcp = FastMCP(APP_NAME, stateless_http=True)

    @mcp.tool(name="status", description="Report Schwab login/authentication state.")
    async def status() -> dict:
        return tokens.describe_auth()

    register_market_tools(mcp, client)
    return mcp
