from datetime import datetime
import logging
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm import joinedload



from app.feature.audit.services import AuditLogService, diff_dicts
from app.feature.auth.models.user import User
from app.feature.conversation.model.conversation import (
    Conversation,
    ConversationAnalysisReport,
    ConversationMessage,
)
from app.feature.admin.sessions.schemas.session import (
    AdminPaginatedSessions,
    AdminSessionRow,
    AdminSessionStats,
    AdminSessionStatusUpdate,
    AdminUserResponse
)

logger = logging.getLogger(__name__)


class AdminSessionService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.audit_service = AuditLogService(db)

    # ──────────────────────────────────────────────────────────
    # Queries
    # ──────────────────────────────────────────────────────────

    async def get_by_id(self, session_id: int) -> Conversation | None:
        result = await self.db.execute(
            select(Conversation)
            .options(
                selectinload(Conversation.messages),
                selectinload(Conversation.analysis_report),
            )
            .where(Conversation.id == session_id)
        )
        return result.scalar_one_or_none()

    async def get_by_session_uuid(self, session_uuid: str) -> Conversation | None:
        result = await self.db.execute(
            select(Conversation)
            .options(
                selectinload(Conversation.messages),
                selectinload(Conversation.analysis_report),
            )
            .where(Conversation.session_id == session_uuid)
        )
        return result.scalar_one_or_none()

    async def get_all(
        self,
        page: int = 1,
        page_size: int = 20,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        job_position: Optional[str] = None,
        status: Optional[str] = None,
        company_name: Optional[str] = None,
        created_at: Optional[datetime] = None,
    ) -> AdminPaginatedSessions:
        logger.debug(
            "get_all params: page=%s, page_size=%s, user_id=%s, job_position=%r, status=%r, company_name=%r, created_at=%r",
            page, page_size, user_id, job_position, status, company_name, created_at,
        )

        offset = (page - 1) * page_size

        # Sub-query: count messages per conversation
        msg_count_subq = (
            select(
                ConversationMessage.conversation_id,
                func.count(ConversationMessage.id).label("message_count"),
            )
            .group_by(ConversationMessage.conversation_id)
            .subquery()
        )

        # stmt = select(Conversation)
        stmt = select(Conversation).join(User, Conversation.user_id == User.id).options(joinedload(Conversation.user))
        filters = []

        if user_id is not None:
            filters.append(Conversation.user_id == user_id)
        if username:
            filters.append(User.username.ilike(f"%{username}%"))
        if job_position:
            filters.append(Conversation.job_position.ilike(f"%{job_position}%"))
        if status:
            filters.append(Conversation.status == status)
        if company_name:
            filters.append(Conversation.company_name.ilike(f"%{company_name}%"))

        if created_at:
            filters.append(Conversation.created_at == created_at)

        if filters:
            stmt = stmt.where(*filters)
        

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar_one()

        # Fetch paginated rows
        rows_result = await self.db.execute(
            stmt.order_by(Conversation.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        conversations = list(rows_result.scalars().all())

        # Enrich with message count
        if conversations:
            conv_ids = [c.id for c in conversations]
            mc_result = await self.db.execute(
                select(
                    ConversationMessage.conversation_id,
                    func.count(ConversationMessage.id).label("cnt"),
                )
                .where(ConversationMessage.conversation_id.in_(conv_ids))
                .group_by(ConversationMessage.conversation_id)
            )
            mc_map: dict[int, int] = {row.conversation_id: row.cnt for row in mc_result}
        else:
            mc_map = {}

        # Build response items manually to inject message_count
        from app.feature.admin.sessions.schemas.session import (AdminSessionRow, AdminUserResponse)

        items = [
            AdminSessionRow(
                id=c.id,
                session_id=c.session_id,
                user_id=c.user_id,
                job_position=c.job_position,
                company_name=c.company_name,
                status=c.status,
                score=c.score,
                started_at=c.started_at,
                ended_at=c.ended_at,
                interview_duration_seconds=c.interview_duration_seconds,
                message_count=mc_map.get(c.id, 0),
                created_at=c.created_at,
                updated_at=c.updated_at,
                candidate=AdminUserResponse(
                    id=c.user.id,
                    email=c.user.email,
                    username=c.user.username,
                ) if c.user else None,
            )
            for c in conversations
        ]

        return AdminPaginatedSessions(
            total=total,
            page=page,
            page_size=page_size,
            stats=await self._get_stats(filters),
            items=items,
        )

    # ──────────────────────────────────────────────────────────
    # Mutations
    # ──────────────────────────────────────────────────────────

    async def update_status(
        self,
        session_db_id: int,
        data: AdminSessionStatusUpdate,
        actor: User | None = None,
    ) -> Conversation:
        conversation = await self._get_or_404(session_db_id)
        before_state = self._serialize_conversation(conversation)

        conversation.status = data.status  # type: ignore[assignment]

        await self.db.flush()
        await self.db.refresh(conversation)
        after_state = self._serialize_conversation(conversation)

        old_data, new_data = diff_dicts(before_state, after_state)
        if new_data:
            await self.audit_service.log_change(
                actor=actor,
                entity_type="session",
                entity_id=conversation.id,
                action="update_status",
                old_data=old_data,
                new_data=new_data,
            )

        return conversation

    async def delete(self, session_db_id: int, actor: User | None = None) -> None:
        """Hard-delete conversation and its children (cascade)."""
        conversation = await self._get_or_404(session_db_id)
        before_state = self._serialize_conversation(conversation)

        await self.db.delete(conversation)
        await self.db.flush()

        await self.audit_service.log_change(
            actor=actor,
            entity_type="session",
            entity_id=session_db_id,
            action="delete",
            old_data=before_state,
        )

    # ────────────────────────────────────────────────────────
    # Helpers
    # ────────────────────────────────────────────────────────

    async def _get_stats(self, filters: list) -> AdminSessionStats:
        """Tính thống kê tổng hợp trong một lần query GROUP BY."""
        from sqlalchemy import case

        base_stmt = select(Conversation)
        if filters:
            base_stmt = base_stmt.where(*filters)
        base_subq = base_stmt.subquery()

        stats_result = await self.db.execute(
            select(
                func.count().label("total"),
                func.sum(
                    case((base_subq.c.status == "active", 1), else_=0)
                ).label("active"),
                func.sum(
                    case((base_subq.c.status == "completed", 1), else_=0)
                ).label("completed"),
                func.sum(
                    case((base_subq.c.status == "paused", 1), else_=0)
                ).label("paused"),
                func.avg(
                    case((base_subq.c.score.isnot(None), base_subq.c.score), else_=None)
                ).label("avg_score"),
            ).select_from(base_subq)
        )
        row = stats_result.one()

        avg = float(round(row.avg_score, 2)) if row.avg_score is not None else None
        return AdminSessionStats(
            total_sessions=row.total or 0,
            active_sessions=row.active or 0,
            completed_sessions=row.completed or 0,
            paused_sessions=row.paused or 0,
            average_score=avg,
        )

    async def _get_or_404(self, session_db_id: int) -> Conversation:
        result = await self.db.execute(
            select(Conversation)
            .options(
                selectinload(Conversation.messages),
                selectinload(Conversation.analysis_report),
            )
            .where(Conversation.id == session_db_id)
        )
        conversation = result.scalar_one_or_none()
        if conversation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found",
            )
        return conversation

    @staticmethod
    def _serialize_conversation(c: Conversation) -> dict:
        return {
            "id": c.id,
            "session_id": c.session_id,
            "user_id": c.user_id,
            "job_position": c.job_position,
            "company_name": c.company_name,
            "status": c.status,
            "score": c.score,
            "started_at": c.started_at,
            "ended_at": c.ended_at,
            "interview_duration_seconds": c.interview_duration_seconds,
            "created_at": c.created_at,
            "updated_at": c.updated_at,
        }
