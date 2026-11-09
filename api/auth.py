"""Authentication API endpoints.

One-time setup, status check, and key rotation for the API-key based
authentication system.  ``/setup`` does not require prior authentication
so an operator can configure the key on first deployment.
"""

from __future__ import annotations

import json
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from core.auth import get_api_key, verify_api_key

router = APIRouter(prefix="/api/auth", tags=["auth"])

CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "auth_config.json")


class SetupRequest(BaseModel):
    api_key: str


class SetupResponse(BaseModel):
    message: str
    status: str


class StatusResponse(BaseModel):
    configured: bool
    setup_required: bool


def _load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (ValueError, OSError):
            return {}
    return {}


def _save_config(data: dict) -> None:
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    tmp = CONFIG_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    os.replace(tmp, CONFIG_FILE)


@router.post("/setup", response_model=SetupResponse)
def setup_auth(request: SetupRequest):
    """Set the API key for authentication (one-time setup, no prior auth required).

    If an API key has already been configured (via ``APP_API_KEY`` env var or a
    previous setup call), this endpoint returns 403 -- use ``POST /api/auth/change``
    with a valid current key instead.
    """
    config = _load_config()
    env_key = os.environ.get("APP_API_KEY")

    if env_key:
        raise HTTPException(
            status_code=403,
            detail="API key is set via APP_API_KEY environment variable. Change it in .env and restart.",
        )
    if config.get("api_key") and not config.get("setup_complete", False):
        # Already configured
        raise HTTPException(
            status_code=403,
            detail="Authentication already configured. Use POST /api/auth/change with a valid current key.",
        )

    _save_config({"api_key": request.api_key, "setup_complete": True})

    # Update in-memory key so it takes effect without restart
    import core.auth as _auth_module  # noqa: WPS433
    _auth_module._API_KEY = request.api_key

    return {"message": "Authentication configured successfully", "status": "configured"}


@router.get("/status", response_model=StatusResponse)
def auth_status():
    """Check whether authentication is configured."""
    config = _load_config()
    env_key = os.environ.get("APP_API_KEY")
    configured = bool(env_key or config.get("api_key"))
    return {
        "configured": configured,
        "setup_required": not configured,
    }


@router.post("/change", response_model=SetupResponse)
def change_api_key(request: SetupRequest, authenticated: bool = Depends(verify_api_key)):
    """Change the API key (requires current authentication)."""
    _save_config({"api_key": request.api_key, "setup_complete": True})
    import core.auth as _auth_module  # noqa: WPS433
    _auth_module._API_KEY = request.api_key
    return {"message": "API key changed successfully", "status": "changed"}
