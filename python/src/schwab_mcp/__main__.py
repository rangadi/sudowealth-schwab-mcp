"""Entrypoint: run the plain-HTTP MCP listener and the HTTPS OAuth listener."""

from __future__ import annotations

import asyncio
import contextlib

import httpx
import uvicorn

from .auth.tokens import TokenManager, select_token_store
from .auth_server import build_auth_app
from .client import MARKET_DATA_BASE_URL, SchwabClient
from .config import Settings
from .server import build_mcp
from .tls import ensure_cert


async def _serve() -> None:
    settings = Settings()

    oauth_http = httpx.AsyncClient(timeout=30)
    market_http = httpx.AsyncClient(base_url=MARKET_DATA_BASE_URL, timeout=30)

    tokens = TokenManager(settings, select_token_store(settings), oauth_http)
    client = SchwabClient(market_http, tokens)

    mcp_app = build_mcp(client, tokens).streamable_http_app()
    auth_app = build_auth_app(settings, tokens)
    cert_path, key_path = ensure_cert(settings.config_dir, settings.callback_host)

    mcp_server = uvicorn.Server(
        uvicorn.Config(
            mcp_app,
            host=settings.mcp_host,
            port=settings.mcp_port,
            log_level=settings.log_level,
        )
    )
    auth_server = uvicorn.Server(
        uvicorn.Config(
            auth_app,
            host=settings.callback_host,
            port=settings.callback_port,
            log_level=settings.log_level,
            ssl_certfile=str(cert_path),
            ssl_keyfile=str(key_path),
        )
    )

    print(f"MCP:   http://{settings.mcp_host}:{settings.mcp_port}/mcp")
    print(f"Login: https://{settings.callback_host}:{settings.callback_port}/authorize")
    try:
        await asyncio.gather(mcp_server.serve(), auth_server.serve())
    finally:
        await oauth_http.aclose()
        await market_http.aclose()


def main() -> None:
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(_serve())


if __name__ == "__main__":
    main()
