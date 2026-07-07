"""Manual paste-the-code login, for when the loopback callback can't be used.

Use this to test against an *already-approved* redirect URI (e.g. a hosted
callback) while a 127.0.0.1 change is still "Modification Pending" at Schwab.

Set SCHWAB_REDIRECT_URI to the approved URL, run this, log in, then paste the
URL Schwab redirects your browser to (the address bar) back into the prompt.
The redirect target never has to reach this machine — Schwab delivers the
authorization code in that URL, and we exchange it directly.
"""

from __future__ import annotations

import asyncio
import contextlib
import secrets
import webbrowser
from urllib.parse import parse_qs, urlparse

import httpx

from .auth.oauth import build_authorize_url
from .auth.tokens import TokenManager, select_token_store
from .config import Settings


def _extract_code(pasted: str) -> str:
    """Accept a full redirected URL, a bare 'code=...' query, or just the code."""
    pasted = pasted.strip()
    query = ""
    if pasted.startswith("http"):
        query = urlparse(pasted).query
    elif "code=" in pasted:
        query = pasted.split("?", 1)[-1]
    if query:
        codes = parse_qs(query).get("code")
        if codes:
            return codes[0]
    return pasted  # assume the user pasted the bare code


async def _exchange(settings: Settings, code: str) -> None:
    async with httpx.AsyncClient(timeout=30) as http:
        tokens = TokenManager(settings, select_token_store(settings), http)
        await tokens.complete_login(code)


def main() -> None:
    settings = Settings()
    url = build_authorize_url(settings, state=secrets.token_urlsafe(16))

    print("Using redirect_uri:", settings.schwab_redirect_uri)
    print("\n1. Open this URL and log in to Schwab:\n")
    print(url)
    with contextlib.suppress(Exception):
        webbrowser.open(url)

    print(
        "\n2. After logging in, your browser is redirected to the callback URL."
        "\n   Copy the FULL URL from the address bar (it contains ?code=...)."
    )
    pasted = input("\nPaste the redirected URL (or just the code): ")
    code = _extract_code(pasted)
    if not code:
        raise SystemExit("No authorization code found in what you pasted.")

    asyncio.run(_exchange(settings, code))
    print("\n✓ Success — tokens stored. Now run `uv run schwab-mcp`.")


if __name__ == "__main__":
    main()
