import pytest
from fastapi import HTTPException

from app.core.dependencies import get_current_active_user, get_current_authenticated_user
from app.feature.auth.models.user import User


def _user(*, is_active: bool = True, is_deleted: bool = False) -> User:
    return User(
        id=1,
        email="locked@example.com",
        username="lockeduser",
        hashed_password="not-used",
        is_active=is_active,
        is_deleted=is_deleted,
    )


@pytest.mark.asyncio
async def test_authenticated_user_allows_locked_account() -> None:
    user = _user(is_active=False)

    assert await get_current_authenticated_user(user) is user


@pytest.mark.asyncio
async def test_active_user_rejects_locked_account() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await get_current_active_user(_user(is_active=False))

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Inactive user"


@pytest.mark.asyncio
async def test_authenticated_user_rejects_deleted_account() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await get_current_authenticated_user(_user(is_deleted=True))

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Deleted user"
