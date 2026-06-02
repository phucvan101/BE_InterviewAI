from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db as prod_get_db
from app.core.dependencies import get_current_active_user as prod_get_current_active_user
from app.feature.admin.dashboard.api.router import api_router as dashboard_router
from app.feature.auth.models.user import User
from app.feature.conversation.model.conversation import Conversation


async def _create_user(session: AsyncSession, username: str, email: str, *, is_superuser: bool = False) -> User:
    user = User(
        email=email,
        username=username,
        full_name=username.title(),
        hashed_password="not-used-in-tests",
        auth_provider="password",
        is_active=True,
        is_deleted=False,
        is_superuser=is_superuser,
        is_verified=True,
    )
    session.add(user)
    await session.flush()
    return user


async def _create_conversation(
    session: AsyncSession,
    user: User,
    *,
    status: str,
    score: float | None,
    created_at: datetime,
) -> Conversation:
    conversation = Conversation(
        user_id=user.id,
        job_position="Backend Engineer",
        company_name="Acme",
        job_description="JD",
        cv_profile="CV",
        status=status,
        score=score,
        created_at=created_at,
        updated_at=created_at,
        started_at=created_at,
    )
    session.add(conversation)
    await session.flush()
    return conversation


@pytest.mark.asyncio
async def test_admin_dashboard_overview_returns_design_metrics(session: AsyncSession):
    admin = await _create_user(session, "admin", "admin@example.com", is_superuser=True)
    alice = await _create_user(session, "alice", "alice@example.com")
    bob = await _create_user(session, "bob", "bob@example.com")

    now = datetime.now(timezone.utc)
    await _create_conversation(session, alice, status="completed", score=90, created_at=now)
    await _create_conversation(session, alice, status="completed", score=80, created_at=now - timedelta(days=1))
    await _create_conversation(session, bob, status="active", score=None, created_at=now - timedelta(days=2))
    await _create_conversation(session, bob, status="completed", score=70, created_at=now - timedelta(days=40))
    await session.commit()

    app = FastAPI()
    app.include_router(dashboard_router, prefix=settings.API_PREFIX)

    async def override_get_db():
        yield session

    async def override_get_current_active_user() -> User:
        return admin

    app.dependency_overrides[prod_get_db] = override_get_db
    app.dependency_overrides[prod_get_current_active_user] = override_get_current_active_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/admin/dashboard/overview?activity_range=week")

    assert resp.status_code == 200
    data = resp.json()

    assert data["stats"]["total_interviews"] == 4
    assert data["stats"]["live_sessions"] == 1
    assert data["stats"]["live_sessions_label"] == "Live"
    assert data["stats"]["success_rate"] == 75.0
    assert data["stats"]["success_rate_label"] == "Stable"
    assert data["stats"]["average_score"] == 80.0
    assert data["stats"]["average_score_denominator"] == 100

    assert data["interview_activity_range"] == "week"
    assert len(data["interview_activity"]) == 8
    assert {point["label"] for point in data["interview_activity"]} == {
        "Th2",
        "Th3",
        "Th4",
        "Th5",
        "Th6",
        "Th7",
        "CN",
    }

    assert data["top_interview_activity"][0]["username"] == "alice"
    assert data["top_interview_activity"][0]["session_count"] == 2
    assert data["top_interview_activity"][1]["username"] == "bob"
    assert data["top_interview_activity"][1]["session_count"] == 2
    assert data["system_utilization"]["level"] == "normal"
