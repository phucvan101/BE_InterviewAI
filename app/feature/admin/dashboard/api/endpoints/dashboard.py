from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.feature.admin.dashboard.schemas.dashboard import AdminDashboardOverview
from app.feature.admin.dashboard.services.dashboard_service import AdminDashboardService
from app.feature.auth.models.user import User

router = APIRouter(prefix="/admin/dashboard", tags=["Admin Dashboard"])


@router.get(
    "/overview",
    response_model=AdminDashboardOverview,
    summary="[Admin] Dashboard overview metrics",
)
async def get_dashboard_overview(
    activity_range: str = Query(
        "week",
        pattern="^(week|month)$",
        description="Khoảng dữ liệu cho biểu đồ Interview Activity",
    ),
    _: User = Depends(require_permission("sessions.read")),
    db: AsyncSession = Depends(get_db),
) -> AdminDashboardOverview:
    return await AdminDashboardService(db).get_overview(activity_range=activity_range)
