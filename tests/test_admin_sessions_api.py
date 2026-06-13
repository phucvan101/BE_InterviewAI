from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db as prod_get_db
from app.core.dependencies import get_current_active_user as prod_get_current_active_user
from app.feature.admin.sessions.api.router import api_router as admin_sessions_router
from app.feature.auth.models.user import User
from app.feature.conversation.model.conversation import Conversation


@pytest.mark.asyncio
async def test_admin_sessions_candidate_includes_avatar_url(session: AsyncSession) -> None:
    admin = User(
        email="admin-sessions@example.com",
        username="adminsessions",
        full_name="Admin Sessions",
        hashed_password="not-used-in-tests",
        auth_provider="password",
        is_active=True,
        is_deleted=False,
        is_superuser=True,
        is_verified=True,
    )
    candidate = User(
        email="candidate@example.com",
        username="candidate",
        full_name="Candidate User",
        hashed_password="not-used-in-tests",
        auth_provider="google",
        avatar_url="https://example.com/candidate.png",
        is_active=True,
        is_deleted=False,
        is_superuser=False,
        is_verified=True,
    )
    session.add_all([admin, candidate])
    await session.flush()

    now = datetime.now(timezone.utc)
    session.add(
        Conversation(
            user_id=candidate.id,
            job_position="Backend Engineer",
            company_name="Acme",
            job_description="JD",
            cv_profile="CV",
            status="completed",
            score=85,
            created_at=now,
            updated_at=now,
            started_at=now,
        )
    )
    await session.commit()

    app = FastAPI()
    app.include_router(admin_sessions_router, prefix=settings.API_PREFIX)

    async def override_get_db():
        yield session

    async def override_get_current_active_user() -> User:
        return admin

    app.dependency_overrides[prod_get_db] = override_get_db
    app.dependency_overrides[prod_get_current_active_user] = override_get_current_active_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/admin/sessions/")

    assert resp.status_code == 200
    data = resp.json()
    assert data["items"][0]["candidate"]["avatar_url"] == "https://example.com/candidate.png"
