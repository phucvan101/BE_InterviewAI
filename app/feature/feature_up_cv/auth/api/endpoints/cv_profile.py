from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_active_user, get_current_authenticated_user
from app.feature.auth.models.user import User
from app.feature.feature_up_cv.auth.services.cv_profile_service import CVProfileService

router = APIRouter(prefix="/cv", tags=["CV Profile"])


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_cv(
    file_url: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    return await CVProfileService(db).create(current_user.id, file_url)


@router.get("/")
async def get_my_cvs(
    current_user: User = Depends(get_current_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    return await CVProfileService(db).get_by_user(current_user.id)


@router.delete("/{cv_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cv(
    cv_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    await CVProfileService(db).delete(cv_id)
