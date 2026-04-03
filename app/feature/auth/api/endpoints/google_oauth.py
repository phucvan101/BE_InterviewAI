from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings

from app.core.database import get_db
from app.feature.auth.schemas.user import (
    GoogleAuthUrlResponse,
    GoogleCodeRequest,
    GoogleIdTokenRequest,
    TokenResponse,
)
from app.feature.auth.services.google_oauth_service import GoogleOAuthService
from app.feature.auth.services.user_service import UserService

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.get(
    "/google/login",
    summary="Redirect to Google OAuth consent screen",
)
async def google_login(
    state: str | None = Query(None),
) -> RedirectResponse:
    url = GoogleOAuthService.build_auth_url(state=state)
    return RedirectResponse(url=url, status_code=status.HTTP_302_FOUND)


@router.get(
    "/google/url",
    response_model=GoogleAuthUrlResponse,
    summary="Get Google OAuth consent URL",
)
async def google_auth_url(
    state: str | None = Query(None),
) -> GoogleAuthUrlResponse:
    url = GoogleOAuthService.build_auth_url(state=state)
    return GoogleAuthUrlResponse(url=url)


@router.get(
    "/google/callback",
    response_model=TokenResponse,
    summary="Google OAuth callback (exchange code for tokens)",
)
async def google_callback(
    code: str = Query(..., min_length=5),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    token_response = await UserService(db).login_with_google_code(code)

    frontend_url = settings.FRONTEND_URL.rstrip("/") + "/auth/callback"
    redirect_url = (
        f"{frontend_url}"
        f"?access_token={token_response.access_token}"
        f"&refresh_token={token_response.refresh_token}"
    )
    
    response = RedirectResponse(url=redirect_url, status_code=302)
    response.headers["Cross-Origin-Opener-Policy"] = "unsafe-none"
    return response


@router.post(
    "/google/id-token",
    response_model=TokenResponse,
    summary="Login with Google ID token",
)
async def google_id_token_login(
    data: GoogleIdTokenRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    return await UserService(db).login_with_google_id_token(data.id_token)


@router.post(
    "/google/code",
    response_model=TokenResponse,
    summary="Exchange Google authorization code for tokens",
)
async def google_code_login(
    data: GoogleCodeRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    return await UserService(db).login_with_google_code(data.code)
