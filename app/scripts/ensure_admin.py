import asyncio

from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine
from app.core.security import hash_password
from app.feature.auth.models.user import User


async def ensure_admin() -> User:
    async with AsyncSessionLocal() as db:
        email_result = await db.execute(
            select(User).where(User.email == settings.DEFAULT_ADMIN_EMAIL)
        )
        user_by_email = email_result.scalar_one_or_none()

        username_result = await db.execute(
            select(User).where(User.username == settings.DEFAULT_ADMIN_USERNAME)
        )
        user_by_username = username_result.scalar_one_or_none()
        print('here!!1')

        if (
            user_by_email is not None
            and user_by_username is not None
            and user_by_email.id != user_by_username.id
        ):
            raise RuntimeError(
                "DEFAULT_ADMIN_EMAIL and DEFAULT_ADMIN_USERNAME belong to different users"
            )

        user = user_by_email or user_by_username
        hashed_password = hash_password(settings.DEFAULT_ADMIN_PASSWORD)

        if user is None:
            user = User(
                email=settings.DEFAULT_ADMIN_EMAIL,
                username=settings.DEFAULT_ADMIN_USERNAME,
                full_name=settings.DEFAULT_ADMIN_FULL_NAME,
                hashed_password=hashed_password,
                auth_provider="password",
                is_active=True,
                is_deleted=False,
                is_superuser=True,
                is_verified=True,
            )
            db.add(user)
            action = "created"
        else:
            user.email = settings.DEFAULT_ADMIN_EMAIL
            user.username = settings.DEFAULT_ADMIN_USERNAME
            user.full_name = user.full_name or settings.DEFAULT_ADMIN_FULL_NAME
            user.hashed_password = hashed_password
            user.auth_provider = "password"
            user.is_active = True
            user.is_deleted = False
            user.is_superuser = True
            user.is_verified = True
            action = "updated"

        await db.commit()
        await db.refresh(user)
        print(
            f"{action}: id={user.id}, email={user.email}, "
            f"username={user.username}, is_superuser={user.is_superuser}"
        )
        return user 


async def main() -> None:
    try:
        await ensure_admin()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
