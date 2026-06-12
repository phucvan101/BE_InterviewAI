import os
import sys
from pathlib import Path
from typing import AsyncIterator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Some environments export DEBUG as a non-boolean (e.g., "release"), which breaks Settings parsing.
os.environ["DEBUG"] = "false"

from app.core.config import settings
from app.core.database import Base
from app.core.database import get_db as prod_get_db
from app.core.dependencies import get_current_active_user as prod_get_current_active_user
from app.core.dependencies import get_current_authenticated_user as prod_get_current_authenticated_user
from app.feature.auth.models.user import User
from app.feature.conversation.router import api_router as conversation_router

# Ensure models are imported and registered on Base.metadata
import app.feature.conversation.model  # noqa: F401,E402
import app.feature.admin.roles.models  # noqa: F401,E402
import app.feature.feature_up_cv.auth.models  # noqa: F401,E402


@pytest_asyncio.fixture(scope="session")
async def engine(tmp_path_factory):
    # Use a dedicated schema inside Postgres (e.g. Docker) to avoid touching real data,
    # and to avoid needing extra deps like aiosqlite.
    import uuid

    schema = f"test_{uuid.uuid4().hex}"
    engine = create_async_engine(
        settings.DATABASE_URL,
        connect_args={"server_settings": {"search_path": schema}},
        pool_pre_ping=True,
    )

    try:
        async with engine.begin() as conn:
            await conn.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
            await conn.execute(sa.text(f'SET search_path TO "{schema}"'))
            await conn.run_sync(Base.metadata.create_all)
    except Exception as e:  # pragma: no cover
        await engine.dispose()
        pytest.skip(f"Postgres not available for tests: {e}")
    try:
        yield engine
    finally:
        async with engine.begin() as conn:
            await conn.execute(sa.text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await engine.dispose()


@pytest_asyncio.fixture()
async def session(engine) -> AsyncIterator[AsyncSession]:
    SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with SessionLocal() as session:
        yield session


@pytest_asyncio.fixture()
async def test_user(session: AsyncSession) -> User:
    user = User(
        email="test@example.com",
        username="testuser",
        full_name="Test User",
        hashed_password="not-used-in-tests",
        auth_provider="password",
        is_active=True,
        is_deleted=False,
        is_superuser=False,
        is_verified=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest_asyncio.fixture()
async def app(session: AsyncSession, test_user: User) -> FastAPI:
    app = FastAPI()
    app.include_router(conversation_router, prefix=settings.API_PREFIX)

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

    async def override_get_current_active_user() -> User:
        return test_user

    async def override_get_current_authenticated_user() -> User:
        return test_user

    app.dependency_overrides[prod_get_db] = override_get_db
    app.dependency_overrides[prod_get_current_active_user] = override_get_current_active_user
    app.dependency_overrides[prod_get_current_authenticated_user] = override_get_current_authenticated_user
    return app


@pytest_asyncio.fixture()
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
