from __future__ import annotations

import time
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, status

from app.core.config import settings


class GoogleOAuthService:
    @staticmethod
    def _ensure_configured() -> None:
        if not settings.GOOGLE_CLIENT_ID:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Google OAuth is not configured: GOOGLE_CLIENT_ID is missing",
            )
        if not settings.GOOGLE_CLIENT_SECRET:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Google OAuth is not configured: GOOGLE_CLIENT_SECRET is missing",
            )
        if not settings.GOOGLE_REDIRECT_URI:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Google OAuth is not configured: GOOGLE_REDIRECT_URI is missing",
            )

    @staticmethod
    def build_auth_url(state: str | None = None) -> str:
        GoogleOAuthService._ensure_configured()
        params: dict[str, Any] = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "response_type": "code",
            "scope": " ".join(settings.GOOGLE_SCOPES),
            "access_type": "offline",
            "prompt": "consent",
        }
        if state:
            params["state"] = state
        return f"{settings.GOOGLE_AUTH_URI}?{urlencode(params)}"

    @staticmethod
    async def exchange_code_for_tokens(code: str) -> dict[str, Any]:
        GoogleOAuthService._ensure_configured()
        data = {
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(settings.GOOGLE_TOKEN_URI, data=data)
        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Google token exchange failed: {response.text}",
            )
        return response.json()

    @staticmethod
    async def verify_id_token(id_token: str) -> dict[str, Any]:
        GoogleOAuthService._ensure_configured()
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                settings.GOOGLE_TOKENINFO_URI,
                params={"id_token": id_token},
            )
        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Google id_token",
            )

        data = response.json()

        if data.get("aud") != settings.GOOGLE_CLIENT_ID:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Google id_token audience mismatch",
            )

        if data.get("iss") not in settings.GOOGLE_ALLOWED_ISSUERS:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Google id_token issuer mismatch",
            )

        exp_raw = data.get("exp")
        try:
            exp = int(exp_raw)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Google id_token has invalid expiration",
            )
        if exp <= int(time.time()):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Google id_token is expired",
            )

        return data
