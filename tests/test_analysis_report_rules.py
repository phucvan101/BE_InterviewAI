from app.feature.conversation.model.conversation import ConversationMessage
from app.feature.conversation.schema import AnalysisReportPayload
from app.feature.conversation.service import ConversationService


def _payload(company_score: int = 50) -> AnalysisReportPayload:
    return AnalysisReportPayload.model_validate(
        {
            "overall_score": 70,
            "overall_grade": "B",
            "level": "Khá",
            "summary": "summary",
            "tags": [],
            "scores": {
                "technical": {"score": 80, "evidence": "tech"},
                "communication": {"score": 70, "evidence": "comm"},
                "confidence": {"score": 70, "evidence": "confidence"},
                "soft_skills": {"score": 60, "evidence": "soft"},
                "company_knowledge": {"score": company_score, "evidence": "AI gave partial credit"},
            },
            "ai_coach_insights": [],
            "strengths": [],
            "weaknesses": [],
            "knowledge_gaps": [],
            "study_plan": [],
        }
    )


def test_company_knowledge_score_is_kept_without_company_question():
    service = ConversationService(db=None)
    payload = _payload(company_score=50)
    messages = [
        ConversationMessage(role="interviewer", content="Bạn hãy mô tả kinh nghiệm Vue 3?", question="Bạn hãy mô tả kinh nghiệm Vue 3?"),
        ConversationMessage(role="candidate", content="Tôi đã dùng Vue 3 trong dự án.", answer="Tôi đã dùng Vue 3 trong dự án."),
    ]

    service._apply_analysis_report_business_rules(
        payload=payload,
        messages=messages,
        company_name="VeloTech",
    )

    assert payload.scores.company_knowledge.score == 50
    assert payload.scores.company_knowledge.evidence == "AI gave partial credit"
    assert payload.overall_score == 70
    assert payload.overall_grade == "B"


def test_company_knowledge_score_is_kept_with_company_question():
    service = ConversationService(db=None)
    payload = _payload(company_score=50)
    messages = [
        ConversationMessage(role="interviewer", content="Bạn biết gì về VeloTech và sản phẩm B2B SaaS của công ty?", question="Bạn biết gì về VeloTech và sản phẩm B2B SaaS của công ty?"),
    ]

    service._apply_analysis_report_business_rules(
        payload=payload,
        messages=messages,
        company_name="VeloTech",
    )

    assert payload.scores.company_knowledge.score == 50
    assert payload.overall_score == 70
