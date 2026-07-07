from __future__ import annotations

import base64
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import respx

from schwab_mcp.auth import oauth


def test_build_authorize_url(settings):
    url = oauth.build_authorize_url(settings, state="xyz")
    parsed = urlparse(url)
    q = parse_qs(parsed.query)
    assert parsed.path.endswith("/oauth/authorize")
    assert q["response_type"] == ["code"]
    assert q["client_id"] == ["test-client-id"]
    assert q["redirect_uri"] == [settings.schwab_redirect_uri]
    assert q["scope"] == ["readonly"]
    assert q["state"] == ["xyz"]


@respx.mock
async def test_exchange_code_uses_basic_auth(settings, http):
    route = respx.post(oauth.TOKEN_URL).mock(
        return_value=httpx.Response(
            200, json={"access_token": "a", "refresh_token": "r", "expires_in": 1800}
        )
    )
    await oauth.exchange_code(settings, "the-code", http)

    req = route.calls.last.request
    expected = "Basic " + base64.b64encode(b"test-client-id:test-client-secret").decode()
    assert req.headers["authorization"] == expected
    assert b"grant_type=authorization_code" in req.content
    assert b"the-code" in req.content


@respx.mock
async def test_refresh_reuses_old_token_when_absent(settings, http):
    respx.post(oauth.TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "a", "expires_in": 1800})
    )
    data = await oauth.refresh_tokens(settings, "old-refresh", http)
    assert data["refresh_token"] == "old-refresh"


@respx.mock
async def test_token_error_raises(settings, http):
    respx.post(oauth.TOKEN_URL).mock(return_value=httpx.Response(400, text="bad"))
    with pytest.raises(oauth.OAuthError):
        await oauth.exchange_code(settings, "x", http)
