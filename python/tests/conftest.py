from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest

from schwab_mcp.config import Settings


class Clock:
    """A controllable clock for deterministic expiry tests."""

    def __init__(self, start: datetime):
        self.now = start

    def __call__(self) -> datetime:
        return self.now

    def advance(self, delta: timedelta) -> None:
        self.now += delta


@pytest.fixture
def clock() -> Clock:
    return Clock(datetime(2026, 1, 1, 12, 0, tzinfo=UTC))


@pytest.fixture
def settings(tmp_path, monkeypatch) -> Settings:
    monkeypatch.setenv("SCHWAB_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("SCHWAB_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("CONFIG_DIR", str(tmp_path))
    # Avoid picking up a real .env from the repo during tests.
    return Settings(_env_file=None)


@pytest.fixture
async def http() -> httpx.AsyncClient:
    async with httpx.AsyncClient(timeout=5) as c:
        yield c
