# Project Review

## Summary

The project has a broad feature set, but several issues should be addressed before production deployment. The current implementation is better suited to a trusted local environment than an internet-facing deployment.

## High Priority Findings

### 1. No authentication or authorization

All API routes are publicly accessible when deployed, including state-changing and sensitive endpoints:

- `/api/gemini/config`
- `/api/advanced/telegram/config`
- `/api/upstox/paper/reset`
- `/api/upstox/paper/order`
- `/api/portfolio`
- `/api/watchlist`
- `/api/features/notes`
- Alert and broker endpoints

Anyone who can reach the server can modify portfolio data, reset paper trading capital, configure Telegram, or overwrite the Gemini API key.

Relevant files:

- [main.py](main.py:1)
- [api/gemini.py](api/gemini.py:38)
- [api/upstox_trading.py](api/upstox_trading.py:90)

### 2. Clean Docker installation may be broken

`main.py` imports `inngest`, and `core/upstox/client.py` imports `httpx`, but neither package appears in `requirements.txt`.

A fresh deployment may fail during import before the server starts.

Relevant files:

- [requirements.txt](requirements.txt)
- [main.py](main.py:10)
- [core/upstox/client.py](core/upstox/client.py:3)

### 3. Secrets are stored in plaintext

Gemini and Telegram credentials are written directly to JSON files:

- [api/gemini.py](api/gemini.py:32)
- [api/advanced.py](api/advanced.py:54)

The files are gitignored, but they remain exposed to anyone with filesystem access and are managed through unauthenticated endpoints.

### 4. Paper trading state is globally shared

`paper_desk` is a module-level singleton and stores all positions in one JSON file:

[api/upstox_trading.py](api/upstox_trading.py:15)

All users therefore share the same portfolio. Concurrent requests can also overwrite each other because reads and writes are not locked or atomic.

## Medium Priority Findings

### 5. Input validation is incomplete

Portfolio requests accept zero or negative quantities and prices:

[api/portfolio.py](api/portfolio.py:13)

This can create invalid holdings and may cause division-by-zero errors when calculating returns.

### 6. Frontend and backend paper-trading fields do not match

The backend returns fields such as:

- `id`
- `current_price`
- `unrealized_pnl`

The frontend expects:

- `position_id`
- `last_price`
- `mtm`

Relevant files:

- [api/upstox_trading.py](api/upstox_trading.py:82)
- [static/js/app.js](static/js/app.js:5829)

The paper portfolio UI may render incorrect values or fail when calling `.toFixed()` on missing fields.

### 7. Potential XSS through `innerHTML`

Many server-controlled values are inserted into HTML without escaping. For example, stock names and symbols are interpolated into HTML and inline JavaScript:

[static/js/app.js](static/js/app.js:2019)

News, AI responses, notes, and external market data should be escaped or rendered with DOM APIs.

### 8. WebSocket resource exhaustion

Each `/ws/live-prices` client starts its own polling loop and can request arbitrary symbols:

[main.py](main.py:109)

There is no connection limit, authentication, symbol limit, or rate limiting. A public deployment could generate excessive upstream API traffic.

### 9. Internal exception details are returned to clients

Several endpoints return `str(e)` directly, for example:

[api/upstox_trading.py](api/upstox_trading.py:103)

This can expose filesystem paths, provider responses, credential-related errors, or implementation details.

### 10. Market time handling depends on server timezone

`datetime.now()` is used for Indian market hours:

[main.py](main.py:221)

The deployment environment may use UTC, causing market status and intraday logic to be wrong. Time handling should use timezone-aware IST timestamps consistently.

## Recommended Fix Order

1. Add authentication and authorization.
2. Add missing dependencies to `requirements.txt`.
3. Move credentials to environment variables or a secret manager.
4. Fix paper-trading response field mismatches.
5. Add validation for quantities, prices, symbols, and strategy parameters.
6. Add file locking or move mutable state to a transactional database.
7. Escape dynamic frontend content and remove unsafe inline HTML construction.
8. Add WebSocket connection limits, symbol limits, and rate limiting.
9. Replace raw exception responses with generic errors and server-side logging.
10. Use timezone-aware IST handling throughout the application.

## Review Scope

No files other than this report were modified. Tests were not run during the review.
