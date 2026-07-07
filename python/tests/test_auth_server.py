from __future__ import annotations

import httpx
import pytest
import respx
from starlette.testclient import TestClient

from schwab_mcp.auth import oauth
from schwab_mcp.auth.tokens import FileTokenStore, TokenManager
from schwab_mcp.auth_server import build_auth_app


@pytest.fixture
def app(settings, tmp_path, clock):
    store = FileTokenStore(tmp_path / "token.json")
    http = httpx.AsyncClient()
    tokens = TokenManager(settings, store, http, now=clock)
    return build_auth_app(settings, tokens), store


def test_authorize_redirects_to_schwab(app):
    auth_app, _ = app
    client = TestClient(auth_app)
    resp = client.get("/authorize", follow_redirects=False)
    assert resp.status_code in (302, 307)
    assert resp.headers["location"].startswith(oauth.AUTHORIZE_URL)


def test_callback_rejects_unknown_state(app):
    auth_app, _ = app
    client = TestClient(auth_app)
    resp = client.get("/callback?code=abc&state=never-issued")
    assert resp.status_code == 400


@respx.mock
def test_callback_completes_login(app):
    auth_app, store = app
    respx.post(oauth.TOKEN_URL).mock(
        return_value=httpx.Response(
            200, json={"access_token": "a", "refresh_token": "r", "expires_in": 1800}
        )
    )
    client = TestClient(auth_app)
    # Grab a valid state from the authorize redirect.
    loc = client.get("/authorize", follow_redirects=False).headers["location"]
    state = httpx.URL(loc).params["state"]

    resp = client.get(f"/callback?code=the-code&state={state}")
    assert resp.status_code == 200
    assert store.load().access_token == "a"
