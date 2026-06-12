from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_active_user, get_db
from app.feature.auth.models.user import User
from app.feature.email.schema import SendEmailRequest, SendEmailResponse
from app.feature.email.service import EmailApplicationService

router = APIRouter(
    prefix="/email",
    tags=["Email"],
)


@router.post("/send-job-application", response_model=SendEmailResponse)
async def send_job_application(
    request: SendEmailRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SendEmailResponse:
    """
    Gửi email xin việc với CV.

    - **session_id**: ID của analysis session

    Response:
    - **success**: True nếu gửi thành công
    - **message**: Thông báo chi tiết về kết quả
    """
    try:
        service = EmailApplicationService(db)
        success, message = await service.send_job_application(
            request.session_id,
            user_id=current_user.id,
        )

        return SendEmailResponse(success=success, message=message)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")
