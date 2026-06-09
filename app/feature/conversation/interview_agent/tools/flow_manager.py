# -*- coding: utf-8 -*-
import logging
from typing import Dict

from langchain_core.tools import BaseTool

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

    def __init__(self, conversation_id: int, config: Dict = None):
        super().__init__()
        self._conversation_id = conversation_id
        self._config = config or DEFAULT_CONFIG.copy()
        self._current_phase_index = 0
        self._phases = [
            ("warmup", "Warm-up: Giới thiệu & trải nghiệm gần đây"),
            ("technical", "Technical: Kỹ năng cốt lõi"),
            ("behavioral", "Behavioral: teamwork & problem-solving"),
            ("culture", "Culture Fit: môi trường & giá trị"),
            ("closing", "Closing: câu hỏi của ứng viên"),
        ]

    def _run(self, action: str) -> str:
        if action == "check_completion":
            current_phase = self._phases[self._current_phase_index][0]
            return (
                f"Current phase: {current_phase} "
                f"(phase {self._current_phase_index + 1}/{len(self._phases)}). "
                f"Total question limit: {self._config['total_question_limit']}. "
                f"Có thể tiếp tục phỏng vấn."
            )

        if action == "decide_next_phase":
            if self._current_phase_index < len(self._phases) - 1:
                self._current_phase_index += 1
                phase_key, phase_desc = self._phases[self._current_phase_index]
                return f"Chuyển sang phase tiếp theo: {phase_desc}"
            return "Đã hoàn thành tất cả các phase. Có thể kết thúc phỏng vấn."

        if action == "get_phase":
            phase_key, phase_desc = self._phases[self._current_phase_index]
            return f"Hiện tại đang ở phase: {phase_desc}"

        return f"Action '{action}' không hợp lệ. Dùng: check_completion, decide_next_phase, get_phase"
