"""Token model, persistence backends, and lazy-refresh manager."""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol, runtime_checkable

import httpx
from pydantic import BaseModel

from ..config import Settings
from . import oauth

# Schwab does not return the refresh-token lifetime; it is a fixed 7 days.
REFRESH_TOKEN_TTL = timedelta(days=7)
# Refresh the access token this long before it actually expires.
REFRESH_SKEW = timedelta(minutes=5)

Now = Callable[[], datetime]


def _utcnow() -> datetime:
    return datetime.now(UTC)


class NotAuthenticatedError(Exception):
    """No usable tokens — the user must (re)run the browser login."""


class TokenSet(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    scope: str = "readonly"
    expires_at: datetime
    refresh_expires_at: datetime

    @classmethod
    def from_response(cls, data: dict, *, now: Now = _utcnow) -> TokenSet:
        issued = now()
        return cls(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            token_type=data.get("token_type", "Bearer"),
            scope=data.get("scope", "readonly"),
            expires_at=issued + timedelta(seconds=int(data["expires_in"])),
            refresh_expires_at=issued + REFRESH_TOKEN_TTL,
        )

    def access_expired(self, *, now: Now = _utcnow) -> bool:
        return now() >= self.expires_at - REFRESH_SKEW

    def refresh_expired(self, *, now: Now = _utcnow) -> bool:
        return now() >= self.refresh_expires_at


@runtime_checkable
class TokenStore(Protocol):
    def load(self) -> TokenSet | None: ...
    def save(self, tokens: TokenSet) -> None: ...


class KeyringTokenStore:
    """Primary store: OS keyring (macOS Keychain)."""

    SERVICE = "schwab-mcp"
    USERNAME = "schwab-tokens"

    def load(self) -> TokenSet | None:
        import keyring

        raw = keyring.get_password(self.SERVICE, self.USERNAME)
        return TokenSet.model_validate_json(raw) if raw else None

    def save(self, tokens: TokenSet) -> None:
        import keyring

        keyring.set_password(self.SERVICE, self.USERNAME, tokens.model_dump_json())


class FileTokenStore:
    """Fallback store: a 0600 JSON file (headless / no keyring backend)."""

    def __init__(self, path: Path):
        self.path = path

    def load(self) -> TokenSet | None:
        if not self.path.exists():
            return None
        return TokenSet.model_validate_json(self.path.read_text())

    def save(self, tokens: TokenSet) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Write then chmod, creating with restrictive perms from the start.
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(tokens.model_dump_json())


def select_token_store(settings: Settings) -> TokenStore:
    """Keyring if a real backend is available, else the 0600 file."""
    try:
        import keyring
        from keyring.backends.fail import Keyring as FailKeyring

        if not isinstance(keyring.get_keyring(), FailKeyring):
            return KeyringTokenStore()
    except Exception:
        pass
    return FileTokenStore(settings.config_dir / "token.json")


class TokenManager:
    """Loads/persists tokens and hands out a valid access token, refreshing lazily."""

    def __init__(
        self,
        settings: Settings,
        store: TokenStore,
        http: httpx.AsyncClient,
        *,
        now: Now = _utcnow,
    ):
        self._settings = settings
        self._store = store
        self._http = http
        self._now = now
        self._cache: TokenSet | None = None

    def _current(self) -> TokenSet | None:
        if self._cache is None:
            self._cache = self._store.load()
        return self._cache

    def _persist(self, tokens: TokenSet) -> None:
        self._cache = tokens
        self._store.save(tokens)

    async def complete_login(self, code: str) -> TokenSet:
        data = await oauth.exchange_code(self._settings, code, self._http)
        tokens = TokenSet.from_response(data, now=self._now)
        self._persist(tokens)
        return tokens

    def describe_auth(self) -> dict:
        """Non-secret snapshot of login state, for the `status` tool."""
        tokens = self._current()
        if tokens is None:
            return {"authenticated": False, "reason": "no tokens stored"}
        if tokens.refresh_expired(now=self._now):
            return {"authenticated": False, "reason": "refresh token expired (>7 days)"}
        return {
            "authenticated": True,
            "scope": tokens.scope,
            "access_expires_at": tokens.expires_at.isoformat(),
            "refresh_expires_at": tokens.refresh_expires_at.isoformat(),
        }

    def _authorize_url(self) -> str:
        return self._settings.schwab_redirect_uri.rsplit("/", 1)[0] + "/authorize"

    async def get_access_token(self) -> str:
        tokens = self._current()
        if tokens is None:
            raise NotAuthenticatedError(
                f"Not logged in. Visit {self._authorize_url()} to authorize with Schwab."
            )
        if tokens.refresh_expired(now=self._now):
            raise NotAuthenticatedError(
                "Schwab login expired (refresh token older than 7 days). "
                f"Visit {self._authorize_url()} to log in again."
            )
        if tokens.access_expired(now=self._now):
            data = await oauth.refresh_tokens(self._settings, tokens.refresh_token, self._http)
            refreshed = TokenSet.from_response(data, now=self._now)
            # The refresh token is hard-capped at 7 days from the initial login,
            # regardless of how many times we refresh — keep the original anchor.
            tokens = refreshed.model_copy(update={"refresh_expires_at": tokens.refresh_expires_at})
            self._persist(tokens)
        return tokens.access_token
