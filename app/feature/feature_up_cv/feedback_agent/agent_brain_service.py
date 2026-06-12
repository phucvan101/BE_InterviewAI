# -*- coding: utf-8 -*-
"""
Agent Brain Service - Dịch vụ phân tích feedback tự động

Tích hợp vào workflow feedback hiện tại:
1. Khi có feedback từ user → Agent Brain phân tích
2. Phát hiện patterns → Sinh rules
3. Lưu rules vào memory
4. Lần sau scoring → Rules được áp dụng
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass

from app.feature.feature_up_cv.feedback_agent.agent_brain import (
    AgentFeedbackAnalyzer,
    ScoreAnalysis,
    PatternInsight,
)
from app.feature.feature_up_cv.feedback_agent.memory_faiss import agent_memory

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    """Kết quả phân tích của Agent Brain"""
    case_id: str
    actual_score: float
    expected_range: tuple
    root_cause: str
    reasons: List[str]
    suggested_rules: List[Dict]
    patterns_detected: List[str]


class AgentBrainService:
    """
    Service layer cho Agent Brain - Xử lý feedback và sinh rules tự động
    """

    def __init__(self):
        self.analyzer = AgentFeedbackAnalyzer(memory=agent_memory)
        self._initialized = False

    def _ensure_initialized(self):
        """Đảm bảo analyzer được khởi tạo với memory"""
        if not self._initialized:
            self.analyzer.memory = agent_memory
            self._initialized = True

    def analyze_feedback(
        self,
        cv_data: Dict,
        jd_data: Dict,
        scoring_result: Dict,
        expected_range: tuple,
        case_id: Optional[str] = None,
    ) -> AnalysisResult:
        """
        Phân tích một feedback và sinh rules.

        Args:
            cv_data: Dữ liệu CV đã parse
            jd_data: Dữ liệu JD đã parse
            scoring_result: Kết quả scoring từ hybrid_scoring
            expected_range: (min, max) - khoảng điểm mong đợi
            case_id: ID của case (tùy chọn, dùng timestamp nếu không có)

        Returns:
            AnalysisResult với root cause và rules
        """
        self._ensure_initialized()

        if case_id is None:
            case_id = f"feedback_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Run analysis
        analysis = self.analyzer.analyze_case(
            case_id=case_id,
            cv_data=cv_data,
            jd_data=jd_data,
            scoring_result=scoring_result,
            expected_range=expected_range,
        )

        # Get patterns
        patterns = self.analyzer.detect_patterns()
        pattern_types = [p.pattern_type for p in patterns if p.confidence > 0.6]

        return AnalysisResult(
            case_id=case_id,
            actual_score=analysis.actual_score,
            expected_range=expected_range,
            root_cause=analysis.root_cause,
            reasons=analysis.reasons,
            suggested_rules=analysis.suggested_rules,
            patterns_detected=pattern_types,
        )

    def apply_learning(self) -> Dict[str, Any]:
        """
        Áp dụng các rules đã học vào memory.

        Returns:
            Dict với số lượng rules đã thêm
        """
        self._ensure_initialized()

        added_rule_ids = self.analyzer.apply_learning_to_memory()

        return {
            "success": True,
            "rules_added": len(added_rule_ids),
            "rule_ids": added_rule_ids,
        }

    def get_analysis_report(self) -> Dict[str, Any]:
        """
        Lấy báo cáo phân tích tổng hợp.

        Returns:
            Dict với patterns, suggested_rules, và summary
        """
        self._ensure_initialized()

        return self.analyzer.get_analysis_report()

    def get_memory_stats(self) -> Dict[str, Any]:
        """Lấy thống kê memory hiện tại"""
        return agent_memory.get_stats()

    def clear_analysis_history(self):
        """Xóa lịch sử phân tích (không xóa memory)"""
        self.analyzer.analysis_history.clear()
        self.analyzer.pattern_cache.clear()


# Global instance
agent_brain_service = AgentBrainService()
