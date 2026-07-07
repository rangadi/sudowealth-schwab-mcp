# Schwab MCP — Python Implementation Spec & Plan

> **Status:** Draft for review.
> **Scope of this document:** A ground-up Python rewrite of the Schwab MCP
> server, starting with a **bare localhost server, no Cloudflare**. Phase 1 is
> **market-data-only**. The design is driven by the Schwab OpenAPI specs in
> [`../openapi/`](../openapi/).

---

## 1. Goals & non-goals

### Goals

- A **single-user, local** MCP server you run on your own machine and connect to
  from Claude Desktop / MCP Inspector / any local MCP client.
- **Zero cloud dependency** — no Cloudflare Workers, Durable Objects, KV, or
  hosted OAuth provider. Everything runs and persists on `localhost`.
- **Market-data tools first** (the 10 read-only endpoints), so the first
  milestone is useful and safe on its own.
- **Modern, simple, elegant Python**: async, typed, small surface area, few
  dependencies, generated where generation is cheap and hand-written where
  clarity matters.
- Faithful to the Schwab API contract by **deriving types from the OpenAPI
  specs** rather than re-transcribing them by hand.

### Non-goals (for the first milestone)

- Multi-user hosting, invite codes, per-user tool scoping, allowlists.
  (These exist in the TypeScript/Cloudflare version because it is a shared,
  hosted server. A local single-user server does not need them.)
- Remote transports, TLS termination for inbound MCP traffic, cookie
  encryption, account-identifier scrubbing for third parties.
- Trading / account tools — deferred to Phase 2, behind an explicit opt-in.

---

## 2. What we're porting from (reference: the TS server)

The existing TypeScript server (`../src`) is a Cloudflare Worker that:

- Acts as an **OAuth server** to the MCP client *and* an **OAuth client** to
  Schwab, via `@cloudflare/workers-oauth-provider`.
- Uses the `@sudowealth/schwab-api` SDK for the Schwab client + token manager.
- Stores AES-256-GCM-encrypted tokens in KV.
- Exposes two tool families: **market** (10 tools) and **trader**
  (accounts / orders / transactions / preferences), market-only by default.
- Adds hosted-multi-user concerns: invite enrollment, tool scoping, account
  scrubbing, SSE + streamable-HTTP transports.

The Python port keeps the **tool surface** and the **Schwab OAuth + API
contract**, and drops everything that only exists to serve *other people* over
the internet. We are our own single OAuth client, talking straight to Schwab.

---

## 3. The Schwab API contract (from the OpenAPI specs)

### Market Data API — `https://api.schwabapi.com/marketdata/v1`

Phase-1 tools map 1:1 to these endpoints:

| Tool | Method & path | Notes |
|---|---|---|
| `getQuotes` | `GET /quotes` | `symbols`, `fields`, `indicative` |
| `getQuoteBySymbolId` | `GET /{symbol_id}/quotes` | single symbol |
| `getOptionChain` | `GET /chains` | full option chain w/ Greeks |
| `getOptionExpirationChain` | `GET /expirationchain` | expirations for a symbol |
| `getPriceHistory` | `GET /pricehistory` | candles by period/frequency |
| `getMovers` | `GET /movers/{symbol_id}` | index movers |
| `getMarketHours` | `GET /markets` | multiple markets |
| `getMarketHoursByMarketId` | `GET /markets/{market_id}` | single market |
| `searchInstruments` | `GET /instruments` | search by symbol + projection |
| `getInstrumentByCusip` | `GET /instruments/{cusip_id}` | lookup by CUSIP |

All are `GET`, all read-only. Auth is a bearer access token.

### Trader API — `https://api.schwabapi.com/trader/v1` (Phase 2)

`/accounts`, `/accounts/{n}`, `/accounts/accountNumbers`, orders
(`GET/POST/PUT/DELETE`), `/orders`, `previewOrder`, transactions,
`/userPreference`. Deferred.

### OAuth (from `trader-api-openapi-spec.json` → `securitySchemes.oauth`)

- **Flow:** authorization code.
- **Authorize:** `https://api.schwabapi.com/v1/oauth/authorize`
  (`response_type=code`, `client_id`, `redirect_uri`, `scope=readonly`).
- **Token:** `https://api.schwabapi.com/v1/oauth/token`.
- **Client auth:** HTTP Basic (`client_id:client_secret`) on the token call.
- **Lifetimes (Schwab behavior, not in the spec):** access token ≈ **30 min**,
  refresh token ≈ **7 days**. When the refresh token expires the user must log
  in again — same weekly re-auth the TS server documents.
- **Redirect URI constraint:** Schwab requires an **HTTPS** callback and it must
  **exactly match** what's registered in the Schwab developer portal. This is
  the one real friction point for a localhost app — see §6.

---

## 4. Technology choices

| Concern | Choice | Why |
|---|---|---|
| Language | **Python 3.12+** | modern typing (`type` aliases, `Literal`, generics) |
| Packaging / env | **`uv`** + `pyproject.toml` | fast, reproducible, standard lockfile |
| MCP server | **`mcp` SDK, `FastMCP`** | official SDK; decorator tools; auto JSON-Schema from type hints |
| MCP transport | **streamable HTTP on plain `http://127.0.0.1`** | loopback only; MCP client needs **no cert trust** |
| OAuth callback | **HTTPS on `https://127.0.0.1` (separate port)** | only Schwab's redirect requires TLS; only your browser hits it |
| TLS | **self-signed cert (IP SAN `127.0.0.1`), callback port only** | generated once into the config dir; browser clicks through once per login |
| HTTP client | **`httpx`** (async) | modern async client, connection pooling, timeouts |
| Models / validation | **Pydantic v2** | validation + serialization; pairs with FastMCP |
| Model generation | **`datamodel-code-generator`** | generate response models from the OpenAPI JSON |
| Settings | **`pydantic-settings`** + `.env` | typed config, mirrors the TS `envSchema` |
| Token storage | **OS keyring** (`keyring`), `0600`-file fallback | secrets stay out of plaintext; no bespoke crypto |
| ASGI server | **`uvicorn`** (two binds: HTTP + HTTPS) | serves the FastMCP app; TLS on the callback bind only |
| Logging | **`structlog`** (or stdlib `logging`) | structured logs to **stderr** |
| Lint / format | **`ruff`** | one tool for both |
| Tests | **`pytest`** + `respx` (httpx mocking) | mock Schwab without live creds |

**Dependency budget (runtime):** `mcp`, `httpx`, `pydantic`,
`pydantic-settings`, `keyring`. That's it for Phase 1. Everything else is dev-only.

### Why FastMCP + type hints instead of hand-rolled JSON schemas

FastMCP derives each tool's input schema from the function signature. A tool
like `getQuotes(symbols: list[str], fields: str | None = None, indicative:
bool | None = None)` produces a correct MCP tool schema automatically — no Zod
equivalent, no manual schema objects. We keep tool inputs hand-written (they're
small and we want good descriptions), and **generate response models** from the
OpenAPI spec where we want typed responses.

---

## 5. Architecture

```
python/
├── pyproject.toml            # deps, ruff, project metadata
├── .env.example              # SCHWAB_CLIENT_ID / SECRET / REDIRECT_URI
├── README.md                 # setup + "log in" + connect to Claude Desktop
├── spec.md                   # this file
└── src/schwab_mcp/
    ├── __init__.py
    ├── __main__.py           # `python -m schwab_mcp` → run both listeners
    ├── server.py             # HTTP listener: FastMCP streamable-HTTP at /mcp
    ├── auth_server.py        # HTTPS listener: /authorize + /callback (TLS)
    ├── config.py             # Settings (pydantic-settings)
    ├── tls.py                # ensure/generate the self-signed localhost cert (callback only)
    ├── auth/
    │   ├── oauth.py          # authorize URL, /callback handler, token exchange
    │   └── tokens.py         # TokenStore: load/save/refresh, expiry logic
    ├── client.py             # SchwabClient: httpx wrapper, auth injection, retry
    ├── tools/
    │   ├── market.py         # the 10 market-data tools
    │   └── trader.py         # Phase 2 (stub in Phase 1)
    └── models/
        ├── market.py         # generated response models (datamodel-codegen)
        └── trader.py         # generated (Phase 2)
```

### Runtime flow (Phase 1)

1. **`python -m schwab_mcp`** starts two loopback listeners over the same app:
   - **HTTP** `http://127.0.0.1:8000/mcp` — the FastMCP streamable-HTTP
     endpoint the MCP client connects to (no TLS, no cert trust);
   - **HTTPS** `https://127.0.0.1:8182/` (self-signed) — serves
     `GET /authorize` (→ redirects the browser to Schwab) and `GET /callback`
     (Schwab redirects back with `?code=...`; server exchanges + stores tokens).
2. **Login** (one-time, and again ~weekly when the refresh token lapses): visit
   `https://127.0.0.1:8182/authorize` in a browser (or a `schwab-mcp login`
   helper that just opens that URL). If no valid tokens exist, market tools
   return a clear "log in at https://127.0.0.1:8182/authorize" error.
3. Each tool call → `SchwabClient` ensures a fresh access token (refreshing
   silently if within the refresh window) → issues the `httpx` request →
   returns parsed JSON to the MCP client.

### `SchwabClient` responsibilities

- Hold a single `httpx.AsyncClient` (base URL = market-data host).
- Before each request, ask `TokenStore` for a valid access token; refresh if the
  access token is within ~5 min of expiry (mirrors the TS `refreshThresholdMs`).
- Attach `Authorization: Bearer <token>`.
- Map HTTP errors to clean MCP tool errors (401 → "re-login"; 429 → surfaced;
  4xx/5xx → message + status). No account data in logs.

---

## 6. OAuth on localhost — the design detail that matters

**Decided:** HTTPS is used **only** where Schwab forces it — the redirect URI.
The MCP endpoint stays plain HTTP (see §5). Schwab mandates an **HTTPS redirect
URI** matching the portal registration; `https://127.0.0.1:8182/callback`
satisfies that with a **self-signed cert** that only your browser ever sees.

**Login flow (browser hits `https://127.0.0.1:8182/authorize`):**

1. Server generates a random `state` (CSRF) and, optionally, PKCE
   `code_verifier`/`code_challenge` if Schwab honors it (fall back to plain
   auth-code if not), then 302-redirects to Schwab's authorize URL
   (`scope=readonly`, `redirect_uri=https://127.0.0.1:8182/callback`).
2. User logs in at schwab.com, selects accounts, is redirected back to
   `/callback` with `?code=...&state=...`.
3. Server verifies `state`, exchanges `code` at the token endpoint (Basic auth
   with client id/secret), receives `access_token` + `refresh_token` +
   `expires_in`, and persists them via `TokenStore`. Renders a "you can close
   this tab" page.

The browser warns once about the self-signed cert on first `/authorize` visit —
clicking through is documented in the README, and `tls.py` writes the cert into
the config dir so it's stable across restarts. **The MCP client never touches
this cert** — it connects to the plain-HTTP `/mcp` port.

**Refresh:** `grant_type=refresh_token`; done lazily inside `SchwabClient`.
When the refresh token itself is expired (~7 days), tools return a friendly
"log in again at https://127.0.0.1:8182/authorize" error.

**Registered redirect URI:** register `https://127.0.0.1:8182/callback` in
the Schwab developer portal and set the same value in `.env` as
`SCHWAB_REDIRECT_URI`. Ports are configurable (defaults TBD — see Q6).

---

## 7. Token storage

**Decided: keyring-first, `0600`-file fallback.**

**Primary:** OS keyring via the `keyring` package (macOS Keychain on your
machine). One JSON blob (`access_token`, `refresh_token`, `expires_at`,
`refresh_expires_at`, `scope`) under a fixed service/username key. No custom
crypto to own, no plaintext on disk; the refresh token (the sensitive, ~7-day
credential) is encrypted at rest by the Keychain.

**Fallback:** `~/.config/schwab-mcp/token.json` with `0600` perms, used only
when no keyring backend is available (headless / SSH / CI). `TokenStore` is a
tiny load/save interface that picks the backend at runtime.

**Rejected — encrypted file:** AES-256-GCM would require storing the key on the
same machine (in `.env`, next to the ciphertext), so it adds crypto to maintain
without a real security gain in a single-user local threat model. The TS
`TOKEN_ENCRYPTION_KEY` earns its place only because tokens there live in shared
cloud KV.

---

## 8. Configuration

`.env` (loaded by `pydantic-settings`), mirroring the TS `envSchema` minus the
Cloudflare bits:

```
SCHWAB_CLIENT_ID=...
SCHWAB_CLIENT_SECRET=...
SCHWAB_REDIRECT_URI=https://127.0.0.1:8182/callback   # must match Schwab portal
MCP_PORT=8000           # plain-HTTP /mcp listener
CALLBACK_PORT=8182       # HTTPS /authorize + /callback listener
LOG_LEVEL=info                # trace|debug|info|warn|error
# TRADER_TOOLS=false          # Phase 2 opt-in switch
```

Secrets are read from the environment/`.env`; **tokens** are never in `.env` —
they live in the keyring after `login`.

---

## 9. Response models — generate, don't hand-write

**Decided (Phase 1): responses stay raw JSON.** Full generated Pydantic response
models were evaluated and deliberately *not* applied — Schwab's market-data
payloads are large and full of optional/variant fields, so strict validation
would risk rejecting valid live data for no wire benefit (the MCP client
consumes JSON directly). If token cost becomes an issue, the value-add is
*targeted trimming* of verbose tools (quotes, option chains), which is a
hand-shaped product decision, not mechanical codegen.

The codegen path remains available if needed: run `datamodel-code-generator`
against `../openapi/market-data-openapi-spec.json` to emit Pydantic v2 models
into `models/market.py`.

**Tool inputs stay hand-written** with rich descriptions and `Literal` enums
(e.g. `periodType`, `frequencyType`, movers `sort`) taken from the spec's enums,
so the model-facing schema is high quality.

---

## 10. Milestones / plan

**Phase 1 is complete** and verified end-to-end against live Schwab (OAuth login,
token persistence + refresh, all 10 market tools via MCP Inspector).

**M0 — Skeleton** ✅ — plain-HTTP FastMCP server at `/mcp` with a `status` tool.

**M1 — OAuth login** ✅ — `config.py`, `tls.py` (self-signed cert), token store
(keyring + `0600` file fallback), HTTPS `/authorize` + `/callback`, token
exchange + lazy refresh. Plus `schwab-mcp-login` manual paste-the-code flow.

**M2 — Market data client + tools** ✅ — `SchwabClient` (httpx + lazy refresh),
all 10 market tools with typed inputs, wired in `server.py`.

**M3 — Polish** ✅ — responses left as raw JSON (see §9), error mapping,
`/authorize`+`/callback` logging via `LOG_LEVEL`, and `README.md`.

**M4 — Tests & CI** ✅ — 27 `pytest`/`respx` tests (client, tools, token refresh,
OAuth, TLS, manual login); `python-ci` GitHub Action (ruff + format + pytest).

**M5 — Phase 2 (later, opt-in)**
Trader tools behind `TRADER_TOOLS=true`, `scope=readonly` vs full, optional
account-number display mapping. Deferred until Phase 1 is solid.

---

## 11. Decisions (resolved)

1. **Transport** — two loopback listeners over one FastMCP app: plain **HTTP**
   `http://127.0.0.1:8000/mcp` for the MCP client (no cert trust), **HTTPS**
   `https://127.0.0.1:8182/` for the OAuth `/authorize` + `/callback` routes. No
   stdio.
2. **Phase-1 scope** — **market-data-only** (the 10 read-only tools). Trader
   tools deferred to Phase 2 behind `TRADER_TOOLS`.
3. **OAuth callback** — loopback HTTPS + self-signed cert, hit only by the
   browser during login. Registered redirect URI: `https://127.0.0.1:8182/callback`.
4. **Token storage** — keyring-first, `0600`-file fallback (see §7).
5. **Drop `@sudowealth/schwab-api`** — TS-only; the Python server talks to Schwab
   directly via `httpx` from the OpenAPI contract.
6. **Ports** — `8000` (MCP, HTTP) and `8182` (callback, HTTPS), both configurable.

**Redirect-URI host:** **`127.0.0.1`** (not `localhost`) — matches your existing
Schwab registration, follows RFC 8252's loopback-IP recommendation, and aligns
with the `schwab-py` ecosystem convention (source of the `8182` port). The
self-signed cert carries an IP SAN for `127.0.0.1`.

<details><summary>original open-question text (superseded)</summary>

**Ports & registered redirect URI:** the HTTPS callback port must match the
redirect URI registered in your Schwab developer app. What redirect URI is your
app registered with today (host, port, path)? And any preference for the
plain-HTTP `/mcp` port?

</details>
