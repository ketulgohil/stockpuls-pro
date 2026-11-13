"""Authentication module for StockPulse Pro.

Provides API key-based authentication for state-changing and sensitive API endpoints.

Authentication is configured via the ``APP_API_KEY`` environment variable (set in
``.env``) or the one-time ``POST /api/auth/setup`` endpoint, which persists the
key to ``data/auth_config.json``.  The environment variable takes precedence.
If no key is configured, a random key is generated and logged -- clients must
provide it via the ``X-API-Key`` header or the ``Authorization: Bearer <key>``
header on protected endpoints.

Endpoints
---------
POST /api/auth/setup    One-time setup of the API key (no auth required).
GET  /api/auth/status   Check whether authentication is configured.
POST /api/auth/change   Change the API key (requires current auth).
"""

from __future__ import annotations

import json
import os
import secrets
from pathlib import Path
from typing import Optional

from fastapi import Depends, HTTPException, Header

# ---------------------------------------------------------------------------
# Persisted configuration (data/auth_config.json, gitignored)
# ---------------------------------------------------------------------------

CONFIG_FILE = Path(__file__).resolve().parent.parent / "data" / "auth_config.json"


def load_auth_config() -> dict:
    """Load the persisted auth configuration, or ``{}`` if absent/unreadable."""
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_auth_config(data: dict) -> None:
    """Atomically persist the auth configuration."""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(str(CONFIG_FILE) + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    os.replace(tmp, CONFIG_FILE)


# ---------------------------------------------------------------------------
# In-memory API key (env var first, then persisted config, else generated)
# ---------------------------------------------------------------------------

_API_KEY: Optional[str] = None


def get_api_key() -> str:
    """Return the configured API key, generating one on first access if needed."""
    global _API_KEY
    if _API_KEY is None:
        _API_KEY = os.environ.get("APP_API_KEY") or load_auth_config().get("api_key")
        if not _API_KEY:
            _API_KEY = secrets.token_urlsafe(32)
            print(f"⚠️  No APP_API_KEY set. Generated default API key: {_API_KEY}")
            print("   Set APP_API_KEY in .env to use a fixed key.")
    return _API_KEY


# ---------------------------------------------------------------------------
# FastAPI security schemes (header-based, no error if missing)
# ---------------------------------------------------------------------------

API_KEY_HEADER_NAME = "X-API-Key"


async def _extract_key(
    x_api_key: Optional[str] = Header(None, alias=API_KEY_HEADER_NAME),
    authorization: Optional[str] = Header(None),
) -> Optional[str]:
    """Extract the API key from X-API-Key header or Authorization: Bearer header."""
    if x_api_key:
        return x_api_key
    if authorization and authorization.startswith("Bearer "):
        return authorization[len("Bearer "):]
    return None


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

async def verify_api_key(key: Optional[str] = Depends(_extract_key)) -> bool:
    """Require a valid API key.  Raises 401 if missing or incorrect."""
    expected = get_api_key()
    if key and key == expected:
        return True
    raise HTTPException(
        status_code=401,
        detail=(
            "Authentication required. Provide the API key via the X-API-Key "
            "header or Authorization: Bearer <key> header."
        ),
        headers={"WWW-Authenticate": 'ApiKey realm="StockPulse Pro"'},
    )


async def optional_auth(key: Optional[str] = Depends(_extract_key)) -> bool:
    """Optional authentication: returns True only if a valid key is provided."""
    expected = get_api_key()
    return bool(key and key == expected)
