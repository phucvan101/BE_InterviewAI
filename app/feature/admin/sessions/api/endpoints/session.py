from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.feature.audit.schemas import PaginatedAuditLogs
from app.feature.audit.services import AuditLogService
from app.feature.auth.models.user import User
from app.feature.admin.sessions.schemas.session import (
    AdminPaginatedSessions,
    AdminSessionDetail,
    AdminSessionRow,
    AdminSessionStatusUpdate,
)
from app.feature.admin.sessions.services.session_service import AdminSessionService

router = APIRouter(prefix="/admin/sessions", tags=["Admin Sessions"])


@router.get(
    "/",
    response_model=AdminPaginatedSessions,
    summary="[Admin] List interview sessions",
)
async def list_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: Optional[int] = Query(None, description="Lọc theo user ID"),
    username: Optional[str] = Query(None, description="Lọc theo tên người dùng"),
    job_position: Optional[str] = Query(None, description="Lọc theo vị trí công việc"),
    company_name: Optional[str] = Query(None, description="Lọc theo tên công ty"),
    status: Optional[str] = Query(
        None,
        pattern="^(active|completed|paused)$",
        description="Lọc theo trạng thái: active | completed | paused",
    ),
    created_at: Optional[datetime] = Query(None, description="Lọc theo thời gian tạo"),
    _: User = Depends(require_permission("sessions.read")),
    db: AsyncSession = Depends(get_db),
) -> AdminPaginatedSessions:
    return await AdminSessionService(db).get_all(
        page=page,
        page_size=page_size,
        user_id=user_id,
        username=username,
        job_position=job_position,
        status=status,
        company_name=company_name,
        created_at=created_at,
    )


@router.get(
    "/{session_id}",
    response_model=AdminSessionDetail,
    summary="[Admin] Get session detail",
)
async def get_session(
    session_id: int,
    _: User = Depends(require_permission("sessions.read")),
    db: AsyncSession = Depends(get_db),
) -> AdminSessionDetail:
    conversation = await AdminSessionService(db)._get_or_404(session_id)
    messages = conversation.messages or []
    report = conversation.analysis_report

    from app.feature.admin.sessions.schemas.session import (
        AdminAnalysisReportRow,
        AdminMessageRow,
    )

    return AdminSessionDetail(
        id=conversation.id,
        session_id=conversation.session_id,
        user_id=conversation.user_id,
        job_position=conversation.job_position,
        company_name=conversation.company_name,
        job_description=conversation.job_description,
        cv_profile=conversation.cv_profile,
        status=conversation.status,
        score=conversation.score,
        result=conversation.result,
        started_at=conversation.started_at,
        ended_at=conversation.ended_at,
        interview_duration_seconds=conversation.interview_duration_seconds,
        message_count=len(messages),
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        messages=[
            AdminMessageRow(
                id=m.id,
                role=m.role,
                content=m.content,
                question=m.question,
                answer=m.answer,
                created_at=m.created_at,
            )
            for m in sorted(messages, key=lambda m: m.created_at)
        ],
        analysis_report=(
            AdminAnalysisReportRow(
                id=report.id,
                status=report.status,
                overall_score=report.overall_score,
                overall_grade=report.overall_grade,
                level=report.level,
                summary=report.summary,
                tags=report.tags,
                scores=report.scores,
                strengths=report.strengths,
                weaknesses=report.weaknesses,
                created_at=report.created_at,
                updated_at=report.updated_at,
            )
            if report
            else None
        ),
    )


@router.patch(
    "/{session_id}/status",
    response_model=AdminSessionRow,
    summary="[Admin] Update session status",
)
async def update_session_status(
    session_id: int,
    data: AdminSessionStatusUpdate,
    current_user: User = Depends(require_permission("sessions.update")),
    db: AsyncSession = Depends(get_db),
) -> AdminSessionRow:
    service = AdminSessionService(db)
    conversation = await service.update_status(session_id, data, actor=current_user)

    # Compute message count after update
    from sqlalchemy import func, select
    from app.feature.conversation.model.conversation import ConversationMessage

    mc_result = await db.execute(
        select(func.count(ConversationMessage.id)).where(
            ConversationMessage.conversation_id == conversation.id
        )
    )
    message_count = mc_result.scalar_one()

    return AdminSessionRow(
        id=conversation.id,
        session_id=conversation.session_id,
        user_id=conversation.user_id,
        job_position=conversation.job_position,
        company_name=conversation.company_name,
        status=conversation.status,
        score=conversation.score,
        started_at=conversation.started_at,
        ended_at=conversation.ended_at,
        interview_duration_seconds=conversation.interview_duration_seconds,
        message_count=message_count,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


@router.delete(
    "/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="[Admin] Delete session (hard delete, cascade messages & report)",
)
async def delete_session(
    session_id: int,
    current_user: User = Depends(require_permission("sessions.delete")),
    db: AsyncSession = Depends(get_db),
) -> None:
    await AdminSessionService(db).delete(session_id, actor=current_user)


@router.get(
    "/{session_id}/audit-logs",
    response_model=PaginatedAuditLogs,
    summary="[Admin] Get session audit logs",
)
async def get_session_audit_logs(
    session_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: User = Depends(require_permission("sessions.read")),
    db: AsyncSession = Depends(get_db),
) -> PaginatedAuditLogs:
    await AdminSessionService(db)._get_or_404(session_id)
    return await AuditLogService(db).list_by_entity(
        entity_type="session",
        entity_id=session_id,
        page=page,
        page_size=page_size,
    )
