from app.feature.conversation.schema import AnalysisReportPayload
from app.feature.conversation.service.score_anomaly_detector import ScoreAnomalyDetector


def _payload(
    *,
    overall_score: int = 80,
    technical_score: int = 85,
    technical_evidence: str = "Ứng viên giải thích rõ cách thiết kế API FastAPI với service layer.",
) -> AnalysisReportPayload:
    return AnalysisReportPayload.model_validate(
        {
            "overall_score": overall_score,
            "overall_grade": "B+",
            "level": "Tốt",
            "summary": "summary",
            "tags": [],
            "scores": {
                "technical": {"score": technical_score, "evidence": technical_evidence},
                "communication": {"score": 80, "evidence": "Trình bày rõ ràng có cấu trúc và đúng trọng tâm."},
                "confidence": {"score": 80, "evidence": "Trả lời dứt khoát với ví dụ cụ thể từ dự án."},
                "soft_skills": {"score": 75, "evidence": "Có nhắc đến phối hợp nhóm và xử lý phản hồi."},
                "company_knowledge": {"score": 70, "evidence": "Có liên hệ một phần tới sản phẩm công ty."},
            },
            "ai_coach_insights": [],
            "strengths": [],
            "weaknesses": [],
            "knowledge_gaps": [],
            "study_plan": [],
        }
    )


def test_detects_overall_score_deviation():
    warnings = ScoreAnomalyDetector().validate(_payload(overall_score=99))

    assert any(item["type"] == "overall_score_deviation" for item in warnings)


def test_detects_high_score_with_short_evidence():
    warnings = ScoreAnomalyDetector().validate(
        _payload(technical_score=90, technical_evidence="Tốt.")
    )

    assert any(
        item["type"] == "high_score_short_evidence"
        and item["criterion"] == "technical"
        for item in warnings
    )


def test_detects_high_score_with_low_similarity():
    warnings = ScoreAnomalyDetector().validate(
        _payload(technical_score=90),
        evidence_similarities={"technical": 0.2},
    )

    assert any(
        item["type"] == "high_score_low_similarity"
        and item["criterion"] == "technical"
        and item["similarity"] == 0.2
        for item in warnings
    )


def test_does_not_warn_for_low_similarity_when_score_is_not_high():
    warnings = ScoreAnomalyDetector().validate(
        _payload(technical_score=79),
        evidence_similarities={"technical": 0.2},
    )

    assert not any(item["type"] == "high_score_low_similarity" for item in warnings)
