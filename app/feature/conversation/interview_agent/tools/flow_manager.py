# -*- coding: utf-8 -*-
import logging
from typing import Dict, Optional, TYPE_CHECKING

from langchain_core.tools import BaseTool

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "min_questions_per_topic": 1,
    "max_questions_per_topic": 3,
    "total_question_limit": 15,
}


class FlowManagerTool(BaseTool):
    name: str = "flow_manager"
    description: str = (
        "Quản lý luồng phỏng vấn. "
        "Actions: check_completion (kiểm tra completion), "
        "decide_next_phase (chuyển phase), get_phase (lấy current phase)"
    )

    def __init__(self, conversation_id: int, config: Dict = None, db: "AsyncSession" = None):
        super().__init__()
        self._conversation_id = conversation_id
        self._config = config or DEFAULT_CONFIG.copy()
        self._db = db
        self._state = None

    async def _get_state(self):
        """Lấy state từ database."""
        if self._state is None and self._db:
            from app.feature.conversation.auth.services.interview_state_service import InterviewStateService
            service = InterviewStateService(self._db)
            self._state = await service.get_or_create(self._conversation_id)
        return self._state

    async def _run_async(self, action: str) -> str:
        """Async version of run with DB support."""
        state = await self._get_state()

        if action == "check_completion":
            current_phase = state.get_current_phase() if state else {"key": "warmup", "name": "Warm-up"}
            return (
                f"Current phase: {current_phase.get('name', 'Unknown')} "
                f"Total question limit: {self._config['total_question_limit']}. "
                f"Có thể tiếp tục phỏng vấn."
            )

        if action == "decide_next_phase":
            if state:
                advanced = state.advance_phase()
                if advanced:
                    next_phase = state.get_current_phase()
                    return f"Chuyển sang phase tiếp theo: {next_phase.get('name', 'Unknown')}"
            return "Đã hoàn thành tất cả các phase. Có thể kết thúc phỏng vấn."

        if action == "get_phase":
            if state:
                current_phase = state.get_current_phase()
                return f"Hiện tại đang ở phase: {current_phase.get('name', 'Unknown')}"
            return "Hiện tại đang ở phase: Warm-up"

        return f"Action '{action}' không hợp lệ. Dùng: check_completion, decide_next_phase, get_phase"

    def _run(self, action: str) -> str:
        """Sync wrapper - runs in sync context but returns placeholder for async."""
        return f"FlowManager[conv={self._conversation_id}] action={action} (async mode)"
