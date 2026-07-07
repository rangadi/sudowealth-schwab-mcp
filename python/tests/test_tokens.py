from __future__ import annotations

import stat
from datetime import timedelta

import httpx
import pytest
import respx

from schwab_mcp.auth import oauth
from schwab_mcp.auth.tokens import (
    FileTokenStore,
    NotAuthenticatedError,
    TokenManager,
    TokenSet,
)


def _resp(access="a1", refresh="r1", expires_in=1800):
    return {"access_token": access, "refresh_token": refresh, "expires_in": expires_in}


def test_from_response_sets_expiries(clock):
    t = TokenSet.from_response(_resp(), now=clock)
    assert t.expires_at == clock.now + timedelta(seconds=1800)
    assert t.refresh_expires_at == clock.now + timedelta(days=7)


def test_access_expired_respects_skew(clock):
    t = TokenSet.from_response(_resp(expires_in=1800), now=clock)
    assert not t.access_expired(now=clock)
    clock.advance(timedelta(minutes=26))  # 30m - 5m skew => expired at 25m
    assert t.access_expired(now=clock)


def test_file_store_roundtrip_and_perms(tmp_path, clock):
    store = FileTokenStore(tmp_path / "sub" / "token.json")
    tokens = TokenSet.from_response(_resp(), now=clock)
    store.save(tokens)
    assert store.load() == tokens
    mode = stat.S_IMODE((tmp_path / "sub" / "token.json").stat().st_mode)
    assert mode == 0o600


@respx.mock
async def test_manager_refreshes_and_anchors_refresh_window(settings, http, clock, tmp_path):
    store = FileTokenStore(tmp_path / "token.json")
    initial = TokenSet.from_response(_resp(access="old", refresh="r1"), now=clock)
    store.save(initial)

    route = respx.post(oauth.TOKEN_URL).mock(
        return_value=httpx.Response(200, json=_resp(access="new", refresh="r2"))
    )
    mgr = TokenManager(settings, store, http, now=clock)

    clock.advance(timedelta(minutes=26))  # force access-token refresh
    token = await mgr.get_access_token()

    assert token == "new"
    assert route.called
    saved = store.load()
    # refresh window stays anchored to the original login, not now()+7d
    assert saved.refresh_expires_at == initial.refresh_expires_at


async def test_manager_no_tokens_raises(settings, http, clock, tmp_path):
    store = FileTokenStore(tmp_path / "token.json")
    mgr = TokenManager(settings, store, http, now=clock)
    with pytest.raises(NotAuthenticatedError):
        await mgr.get_access_token()


async def test_manager_refresh_expired_raises(settings, http, clock, tmp_path):
    store = FileTokenStore(tmp_path / "token.json")
    store.save(TokenSet.from_response(_resp(), now=clock))
    mgr = TokenManager(settings, store, http, now=clock)
    clock.advance(timedelta(days=8))
    with pytest.raises(NotAuthenticatedError):
        await mgr.get_access_token()


def test_describe_auth(settings, http, clock, tmp_path):
    store = FileTokenStore(tmp_path / "token.json")
    mgr = TokenManager(settings, store, http, now=clock)
    assert mgr.describe_auth() == {"authenticated": False, "reason": "no tokens stored"}
    store.save(TokenSet.from_response(_resp(), now=clock))
    mgr._cache = None  # force reload
    assert mgr.describe_auth()["authenticated"] is True
