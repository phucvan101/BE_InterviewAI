from datetime import datetime, timezone

from app.feature.admin.users.schemas.user import AdminPaginatedUsers, AdminUserRow
from app.feature.auth.models.user import User


def test_admin_paginated_users_items_include_avatar_url() -> None:
    user = User(
        id=1,
        email="candidate@example.com",
        username="candidate",
        full_name="Candidate User",
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
    row = AdminUserRow.model_validate(user)
    row.interview_count = 3

    data = AdminPaginatedUsers(total=1, page=1, page_size=20, items=[row]).model_dump()

    assert data["items"][0]["avatar_url"] == "https://example.com/avatar.png"
