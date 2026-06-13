from datetime import datetime, timezone

from app.feature.auth.models.user import User
from app.feature.auth.schemas.user import AuthUserResponse


def test_auth_user_response_includes_avatar_url() -> None:
    user = User(
        id=1,
        email="avatar@example.com",
        username="avataruser",
        full_name="Avatar User",
        hashed_password="not-used",
        avatar_url="https://example.com/avatar.png",
        auth_provider="google",
        is_active=True,
        is_deleted=False,
        is_superuser=False,
        is_verified=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    data = AuthUserResponse.model_validate(user).model_dump()

    assert data["avatar_url"] == "https://example.com/avatar.png"
