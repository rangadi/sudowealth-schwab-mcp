# Schwab MCP (Python)

A local [Model Context Protocol](https://modelcontextprotocol.io) server that
gives an AI assistant read-only access to **Charles Schwab market data** — real
-time quotes, option chains, price history, movers, market hours, and
instrument search.

Single-user, runs entirely on your machine. No cloud, no Cloudflare. This is
Phase 1 (**market data only**); account/trading tools are deferred to Phase 2.

> Unofficial and community-built. Not affiliated with or endorsed by Charles
> Schwab. Use at your own risk.

See [`spec.md`](spec.md) for the full design.

## Prerequisites

- [`uv`](https://docs.astral.sh/uv/) (`brew install uv`)
- A **Schwab developer app** at <https://developer.schwab.com> — you need its
  **App Key** (client id) and **Secret**, and it must be **"Ready For Use"**
  (newly created or just-edited apps sit in "Approved - Pending" /
  "Modification Pending" and won't authorize until they clear).

## Setup

```bash
cd python
uv sync --extra dev          # install into a local .venv
cp .env.example .env         # then edit .env with your credentials
```

Fill in `.env`:

```
SCHWAB_CLIENT_ID=your-app-key
SCHWAB_CLIENT_SECRET=your-app-secret
SCHWAB_REDIRECT_URI=https://127.0.0.1:8182/callback
```

`SCHWAB_REDIRECT_URI` must **exactly** match the callback URL registered on your
Schwab app (Schwab treats `127.0.0.1` and `localhost` as different).

## Log in to Schwab

Access tokens last ~30 min (auto-refreshed); the refresh token lasts ~7 days,
after which you log in again. Two ways to log in:

### Normal (loopback callback)

Requires your Schwab app's callback to be `https://127.0.0.1:8182/callback`.

```bash
uv run schwab-mcp
```

Open <https://127.0.0.1:8182/authorize>, click through the one-time
self-signed-cert warning (only your browser ever sees this cert), log in at
Schwab, and pick your accounts. You'll land on "Logged in to Schwab."

### Manual (paste-the-code)

Use this when your loopback callback isn't usable yet (e.g. the `127.0.0.1`
change is still "Modification Pending") but you have another **approved**
redirect URI. Set `SCHWAB_REDIRECT_URI` to that approved URL, then:

```bash
uv run schwab-mcp-login
```

Log in via the URL it opens; when the browser lands on the callback, copy the
**full address-bar URL** and paste it into the prompt. The redirect target
never has to reach your machine — Schwab delivers the code in that URL and the
tool exchanges it directly. (Move quickly: Schwab auth codes expire in under a
minute.)

## Run the server

```bash
uv run schwab-mcp
```

- **MCP endpoint (plain HTTP):** `http://127.0.0.1:8000/mcp`
- **OAuth endpoints (HTTPS):** `https://127.0.0.1:8182/authorize` + `/callback`

## Connect a client

The server must be running and logged in first.

**Claude Code** (native HTTP):

```bash
claude mcp add --transport http schwab http://127.0.0.1:8000/mcp
```

**Claude Desktop** (bridged with `mcp-remote`, since Desktop connectors expect
public HTTPS + OAuth) — add to
`~/Library/Application Support/Claude/claude_desktop_config.json` and restart:

```json
{
  "mcpServers": {
    "schwab": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "http://127.0.0.1:8000/mcp", "--allow-http"]
    }
  }
}
```

**MCP Inspector**:

```bash
npx @modelcontextprotocol/inspector
```

Transport `Streamable HTTP`, URL `http://127.0.0.1:8000/mcp`, Connect.

## Tools

`status` plus the 10 market-data tools: `getQuotes`, `getQuoteBySymbolId`,
`getOptionChain`, `getOptionExpirationChain`, `getPriceHistory`, `getMovers`,
`getMarketHours`, `getMarketHoursByMarketId`, `searchInstruments`,
`getInstrumentByCusip`.

Try: _"Get quotes for AAPL and MSFT"_, _"Show the TSLA option chain"_, _"What
are today's $SPX movers?"_, _"Are the markets open?"_

## Configuration

| Var | Default | Notes |
|---|---|---|
| `SCHWAB_CLIENT_ID` | — | Schwab App Key (required) |
| `SCHWAB_CLIENT_SECRET` | — | Schwab Secret (required) |
| `SCHWAB_REDIRECT_URI` | `https://127.0.0.1:8182/callback` | must match Schwab registration |
| `MCP_HOST` / `MCP_PORT` | `127.0.0.1` / `8000` | plain-HTTP MCP listener |
| `CALLBACK_HOST` / `CALLBACK_PORT` | `127.0.0.1` / `8182` | HTTPS OAuth listener |
| `LOG_LEVEL` | `info` | `debug` for verbose OAuth logging |
| `CONFIG_DIR` | `~/.config/schwab-mcp` | cert + file-fallback token store |

Tokens are stored in the OS keyring (macOS Keychain) when available, else a
`0600` file in `CONFIG_DIR`. They are never written to `.env`.

## Development

```bash
uv run pytest          # tests (Schwab is mocked; no live creds needed)
uv run ruff check .    # lint
uv run ruff format .   # format
```
