"""HTTPS OAuth listener: /authorize kicks off login, /callback finishes it.

Only the user's browser talks to this app, over a self-signed cert.
"""

from __future__ import annotations

import secrets

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse
from starlette.routing import Route

from .auth.oauth import OAuthError, build_authorize_url
from .auth.tokens import TokenManager
from .config import Settings


def build_auth_app(settings: Settings, tokens: TokenManager) -> Starlette:
    pending_states: set[str] = set()

    async def authorize(_: Request) -> RedirectResponse:
        state = secrets.token_urlsafe(24)
        pending_states.add(state)
        return RedirectResponse(build_authorize_url(settings, state))

    async def callback(request: Request) -> HTMLResponse:
        error = request.query_params.get("error")
        if error:
            return _page(f"Schwab returned an error: {error}", ok=False)

        state = request.query_params.get("state")
        if not state or state not in pending_states:
            return _page("Invalid or expired state — start again at /authorize.", ok=False)
        pending_states.discard(state)

        code = request.query_params.get("code")
        if not code:
            return _page("No authorization code in the callback.", ok=False)

        try:
            await tokens.complete_login(code)
        except OAuthError as exc:
            return _page(f"Token exchange failed: {exc}", ok=False)

        return _page("Logged in to Schwab. You can close this tab.", ok=True)

    return Starlette(
        routes=[
            Route("/authorize", authorize, methods=["GET"]),
            Route("/callback", callback, methods=["GET"]),
        ]
    )


def _page(message: str, *, ok: bool) -> HTMLResponse:
    color = "#0a0" if ok else "#c00"
    title = "Success" if ok else "Login problem"
    html = (
        f"<!doctype html><meta charset=utf-8>"
        f"<title>{title}</title>"
        f"<div style='font:16px system-ui;margin:4rem auto;max-width:32rem;color:{color}'>"
        f"<h2>{title}</h2><p>{message}</p></div>"
    )
    return HTMLResponse(html, status_code=200 if ok else 400)
