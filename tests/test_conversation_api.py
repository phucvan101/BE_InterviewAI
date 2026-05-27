import json

import pytest

from app.feature.conversation.schema import AnalysisReportPayload
from app.feature.conversation.service import ConversationService


@pytest.mark.asyncio
async def test_start_interview_creates_conversation(client):
    payload = {"job_position": "Backend Engineer", "company_name": "Acme", "job_description": "JD", "cv_profile": "CV"}
    resp = await client.post("/api/v1/conversations", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["id"] >= 1
    assert data["session_id"]
    assert data["status"] == "active"
    assert data["job_position"] == "Backend Engineer"
    assert data["company_name"] == "Acme"
    assert data["job_description"] == "JD"
    assert data["cv_profile"] == "CV"


@pytest.mark.asyncio
async def test_start_interview_extracts_metadata_from_job_description(client):
    payload = {
        "job_description": (
            "[VELOTECH] TUYỂN DỤNG FRONTEND DEVELOPER (VUEJS/NUXT.JS)\n"
            "Vị trí: Lập trình viên Frontend (VueJS)\n"
            "Cấp bậc: Khá / Trên Junior"
        ),
        "cv_profile": "NGUYỄN PHÚC\nFRONTEND DEVELOPER (VUEJS)",
    }

    resp = await client.post("/api/v1/conversations/", json=payload)

    assert resp.status_code == 201
    data = resp.json()
    assert data["job_position"] == "Lập trình viên Frontend (VueJS)"
    assert data["company_name"] == "VELOTECH"


@pytest.mark.asyncio
async def test_get_next_question_creates_message(client, monkeypatch):
    async def fake_initial_question(self, conversation_id: int) -> str:  # noqa: ARG001
        return "Q1?"

    monkeypatch.setattr(ConversationService, "generate_initial_question", fake_initial_question)

    start = await client.post(
        "/api/v1/conversations",
        json={"job_position": "Backend Engineer", "job_description": "JD", "cv_profile": "CV"},
    )
    session_id = start.json()["session_id"]

    resp = await client.get(f"/api/v1/conversations/{session_id}/next-question")
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == session_id
    assert data["question"] == "Q1?"
    assert data["message_id"] >= 1


@pytest.mark.asyncio
async def test_send_answer_saves_candidate_and_returns_next_question(client, monkeypatch):
    async def fake_initial_question(self, conversation_id: int) -> str:  # noqa: ARG001
        return "Q1?"

    async def fake_next_question(self, conversation_id: int, previous_answer: str | None = None) -> str:
        assert previous_answer == "My answer"
        return "Q2?"

    monkeypatch.setattr(ConversationService, "generate_initial_question", fake_initial_question)
    monkeypatch.setattr(ConversationService, "generate_next_question", fake_next_question)

    start = await client.post(
        "/api/v1/conversations",
        json={"job_position": "Backend Engineer", "job_description": "JD", "cv_profile": "CV"},
    )
    session_id = start.json()["session_id"]

    await client.get(f"/api/v1/conversations/{session_id}/next-question")

    resp = await client.post(f"/api/v1/conversations/{session_id}/answer", json={"answer": "My answer"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == session_id
    assert data["question"] == "Q2?"
    assert data["message_id"] >= 1


@pytest.mark.asyncio
async def test_create_analysis_report_completes_interview_and_returns_evaluation(client, monkeypatch):
    async def fake_initial_question(self, conversation_id: int) -> str:  # noqa: ARG001
        return "Q1?"

    async def fake_report_payload(self, conversation_id: int):  # noqa: ARG001
        payload = AnalysisReportPayload.model_validate(
            {
                "overall_score": 80,
                "overall_grade": "B+",
                "level": "Tốt",
                "summary": "Ứng viên có nền tảng tốt.",
                "tags": ["Kỹ thuật tốt"],
                "scores": {
                    "technical": {"score": 85, "evidence": "Trả lời đúng trọng tâm."},
                    "communication": {"score": 78, "evidence": "Diễn đạt rõ."},
                    "confidence": {"score": 80, "evidence": "Câu trả lời dứt khoát."},
                    "soft_skills": {"score": 70, "evidence": "Có nhắc tới teamwork."},
                    "company_knowledge": {"score": 60, "evidence": "Có liên hệ một phần tới JD."},
                },
                "ai_coach_insights": [
                    {"type": "positive", "title": "Kỹ thuật tốt", "description": "Có ví dụ thực tế."}
                ],
                "strengths": ["a"],
                "weaknesses": ["b"],
                "knowledge_gaps": [
                    {
                        "title": "Kiến thức công ty",
                        "impact": "medium",
                        "evidence": "Chưa nêu rõ sản phẩm.",
                        "recommendation": "Ôn lại sản phẩm chính.",
                    }
                ],
                "study_plan": [
                    {
                        "priority": 1,
                        "topic": "STAR",
                        "reason": "Tăng cấu trúc câu trả lời.",
                        "actions": ["Chuẩn bị 3 ví dụ theo STAR"],
                    }
                ],
            }
        )
        return payload, '{"overall_score":80}'

    monkeypatch.setattr(ConversationService, "generate_initial_question", fake_initial_question)
    monkeypatch.setattr(ConversationService, "generate_analysis_report_payload", fake_report_payload)

    start = await client.post(
        "/api/v1/conversations",
        json={"job_position": "Backend Engineer", "job_description": "JD", "cv_profile": "CV"},
    )
    session_id = start.json()["session_id"]

    await client.get(f"/api/v1/conversations/{session_id}/next-question")

    resp = await client.post(f"/api/v1/conversations/{session_id}/analysis-report")
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == session_id
    assert data["status"] == "completed"
    assert data["overall_score"] == 80
    assert data["overall_grade"] == "B+"
    assert data["scores"]["technical"]["score"] == 85
    assert data["study_plan"][0]["topic"] == "STAR"
    assert data["total_messages"] >= 1
    assert data["started_at"] is not None
    assert data["ended_at"] is not None
    assert data["interview_duration_seconds"] >= 0


@pytest.mark.asyncio
async def test_list_analysis_reports_returns_paginated_reports(client, monkeypatch):
    async def fake_report_payload(self, conversation_id: int):  # noqa: ARG001
        payload = AnalysisReportPayload.model_validate(
            {
                "overall_score": 82,
                "overall_grade": "B+",
                "level": "Tốt",
                "summary": "Ứng viên phù hợp với vị trí backend.",
                "tags": ["Backend"],
                "scores": {
                    "technical": {"score": 88, "evidence": "Nắm vững API."},
                    "communication": {"score": 80, "evidence": "Trả lời rõ."},
                    "confidence": {"score": 82, "evidence": "Tự tin."},
                    "soft_skills": {"score": 76, "evidence": "Có tinh thần hợp tác."},
                    "company_knowledge": {"score": 70, "evidence": "Có tìm hiểu công ty."},
                },
                "ai_coach_insights": [],
                "strengths": ["API design"],
                "weaknesses": [],
                "knowledge_gaps": [],
                "study_plan": [],
            }
        )
        return payload, '{"overall_score":82}'

    monkeypatch.setattr(ConversationService, "generate_analysis_report_payload", fake_report_payload)

    start = await client.post(
        "/api/v1/conversations",
        json={
            "job_position": "Backend Engineer",
            "company_name": "Acme",
            "job_description": "JD",
            "cv_profile": "CV",
        },
    )
    session_id = start.json()["session_id"]

    await client.post(f"/api/v1/conversations/{session_id}/analysis-report")

    resp = await client.get("/api/v1/conversations/analysis-reports?page=1&page_size=10")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["page"] == 1
    assert data["page_size"] == 10
    assert len(data["items"]) == 1
    assert data["items"][0]["session_id"] == session_id
    assert data["items"][0]["job_position"] == "Backend Engineer"
    assert data["items"][0]["company_name"] == "Acme"
    assert data["items"][0]["overall_score"] == 82
    assert data["items"][0]["started_at"] is not None
    assert data["items"][0]["ended_at"] is not None
    assert data["items"][0]["interview_duration_seconds"] >= 0
