from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.feature.auth.models.user import User
from app.feature.conversation.model.conversation import Conversation
from app.feature.admin.dashboard.schemas.dashboard import (
    AdminDashboardActivityPoint,
    AdminDashboardOverview,
    AdminDashboardStats,
    AdminDashboardSystemUtilization,
    AdminDashboardTopUser,
)


class AdminDashboardService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_overview(self, activity_range: str = "week") -> AdminDashboardOverview:
        if activity_range not in {"week", "month"}:
            activity_range = "week"

        stats = await self._get_stats()
        activity = await self._get_activity(activity_range)
        top_users = await self._get_top_users()

        return AdminDashboardOverview(
            stats=stats,
            interview_activity_range=activity_range,
            interview_activity=activity,
            top_interview_activity=top_users,
            system_utilization=self._get_system_utilization(stats),
        )

    async def _get_stats(self) -> AdminDashboardStats:
        now = datetime.now(timezone.utc)
        current_start = now - timedelta(days=30)
        previous_start = now - timedelta(days=60)

        result = await self.db.execute(
            select(
                func.count(Conversation.id).label("total"),
                func.sum(case((Conversation.status == "active", 1), else_=0)).label("active"),
                func.sum(case((Conversation.status == "completed", 1), else_=0)).label("completed"),
                func.avg(
                    case((Conversation.score.isnot(None), Conversation.score), else_=None)
                ).label("average_score"),
                func.sum(case((Conversation.created_at >= current_start, 1), else_=0)).label(
                    "current_period_total"
                ),
                func.sum(
                    case(
                        (
                            (Conversation.created_at >= previous_start)
                            & (Conversation.created_at < current_start),
                            1,
                        ),
                        else_=0,
                    )
                ).label("previous_period_total"),
            )
        )
        row = result.one()

        total = row.total or 0
        active = row.active or 0
        completed = row.completed or 0
        current_period_total = row.current_period_total or 0
        previous_period_total = row.previous_period_total or 0

        success_rate = round((completed / total) * 100, 2) if total else 0.0
        average_score = round(float(row.average_score), 2) if row.average_score is not None else None
        growth_percent = self._calculate_growth_percent(
            current=current_period_total,
            previous=previous_period_total,
        )

        return AdminDashboardStats(
            total_interviews=total,
            total_interviews_growth_percent=growth_percent,
            live_sessions=active,
            live_sessions_label="Live" if active else "Idle",
            success_rate=success_rate,
            success_rate_label="Stable" if success_rate >= 70 else "Needs attention",
            average_score=average_score,
        )

    async def _get_activity(self, activity_range: str) -> list[AdminDashboardActivityPoint]:
        if activity_range == "month":
            return await self._get_month_activity()
        return await self._get_week_activity()

    async def _get_week_activity(self) -> list[AdminDashboardActivityPoint]:
        today = datetime.now(timezone.utc).date()
        start_date = today - timedelta(days=today.weekday())
        labels = ["Th2", "Th3", "Th4", "Th5", "Th6", "Th7", "CN"]
        day_dates = [start_date + timedelta(days=offset) for offset in range(7)]

        start_dt = self._date_start(day_dates[0])
        end_dt = self._date_start(day_dates[-1] + timedelta(days=1))

        rows = await self._query_activity_by_day(start_dt=start_dt, end_dt=end_dt)
        row_map = {row.activity_date: row for row in rows}

        return [
            AdminDashboardActivityPoint(
                label=labels[index],
                date=day,
                total_interviews=row_map.get(day).total_interviews if day in row_map else 0,
                completed_interviews=(
                    row_map.get(day).completed_interviews if day in row_map else 0
                ),
            )
            for index, day in enumerate(day_dates)
        ]

    async def _get_month_activity(self) -> list[AdminDashboardActivityPoint]:
        today = datetime.now(timezone.utc).date()
        start_date = today - timedelta(days=29)
        day_dates = [start_date + timedelta(days=offset) for offset in range(30)]

        start_dt = self._date_start(day_dates[0])
        end_dt = self._date_start(day_dates[-1] + timedelta(days=1))

        rows = await self._query_activity_by_day(start_dt=start_dt, end_dt=end_dt)
        row_map = {row.activity_date: row for row in rows}

        return [
            AdminDashboardActivityPoint(
                label=day.strftime("%d/%m"),
                date=day,
                total_interviews=row_map.get(day).total_interviews if day in row_map else 0,
                completed_interviews=(
                    row_map.get(day).completed_interviews if day in row_map else 0
                ),
            )
            for day in day_dates
        ]

    async def _query_activity_by_day(self, start_dt: datetime, end_dt: datetime):
        activity_date = func.date(Conversation.created_at).label("activity_date")
        result = await self.db.execute(
            select(
                activity_date,
                func.count(Conversation.id).label("total_interviews"),
                func.sum(case((Conversation.status == "completed", 1), else_=0)).label(
                    "completed_interviews"
                ),
            )
            .where(Conversation.created_at >= start_dt, Conversation.created_at < end_dt)
            .group_by(activity_date)
        )
        return result.all()

    async def _get_top_users(self) -> list[AdminDashboardTopUser]:
        session_count = func.count(Conversation.id).label("session_count")
        result = await self.db.execute(
            select(User, session_count)
            .join(Conversation, Conversation.user_id == User.id)
            .where(User.is_deleted == False, User.is_superuser == False)
            .group_by(User.id)
            .order_by(session_count.desc(), User.username.asc())
            .limit(6)
        )

        return [
            AdminDashboardTopUser(
                user_id=user.id,
                full_name=user.full_name,
                username=user.username,
                email=user.email,
                avatar_url=user.avatar_url,
                session_count=session_count,
            )
            for user, session_count in result.all()
        ]

    @staticmethod
    def _get_system_utilization(stats: AdminDashboardStats) -> AdminDashboardSystemUtilization:
        if stats.live_sessions >= 10:
            return AdminDashboardSystemUtilization(
                level="high",
                message="System utilization is currently high.",
            )
        if stats.live_sessions > 0:
            return AdminDashboardSystemUtilization(
                level="normal",
                message="System utilization is currently normal.",
            )
        return AdminDashboardSystemUtilization(
            level="low",
            message="System utilization is currently low.",
        )

    @staticmethod
    def _calculate_growth_percent(current: int, previous: int) -> float:
        if previous == 0:
            return 100.0 if current > 0 else 0.0
        return round(((current - previous) / previous) * 100, 2)

    @staticmethod
    def _date_start(value: date) -> datetime:
        return datetime.combine(value, time.min, tzinfo=timezone.utc)
