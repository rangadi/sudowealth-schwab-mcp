"""Typed configuration loaded from the environment / .env."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


def default_config_dir() -> Path:
    """Where we keep the self-signed cert and the file-fallback token store."""
    return Path.home() / ".config" / "schwab-mcp"


class Settings(BaseSettings):
    """Runtime settings. Secrets come from the environment; tokens do not."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    schwab_client_id: SecretStr = Field(alias="SCHWAB_CLIENT_ID")
    schwab_client_secret: SecretStr = Field(alias="SCHWAB_CLIENT_SECRET")
    schwab_redirect_uri: str = Field(
        default="https://127.0.0.1:8182/callback", alias="SCHWAB_REDIRECT_URI"
    )

    # Plain-HTTP listener the MCP client connects to.
    mcp_host: str = Field(default="127.0.0.1", alias="MCP_HOST")
    mcp_port: int = Field(default=8000, alias="MCP_PORT")

    # HTTPS listener that only the browser hits during OAuth login.
    callback_host: str = Field(default="127.0.0.1", alias="CALLBACK_HOST")
    callback_port: int = Field(default=8182, alias="CALLBACK_PORT")

    log_level: str = Field(default="info", alias="LOG_LEVEL")
    config_dir: Path = Field(default_factory=default_config_dir, alias="CONFIG_DIR")

    trader_tools: bool = Field(default=False, alias="TRADER_TOOLS")

    @property
    def scope(self) -> str:
        return "readonly"
