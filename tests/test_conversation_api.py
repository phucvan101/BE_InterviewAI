import json

import pytest

from app.feature.feature_up_cv.auth.models.analysis_session import AnalysisSession
from app.feature.feature_up_cv.auth.models.cv_profile import CVProfile
from app.feature.feature_up_cv.auth.models.job_description import JobDescription
from app.feature.conversation.schema import AnalysisReportPayload
from app.feature.conversation.router.endpoints.conversation import _next_retry_job_position
from app.feature.conversation.service import ConversationService


async def _complete_minimum_answers(client, session_id: str) -> None:
    for idx in range(3):
        resp = await client.post(
            f"/api/v1/conversations/{session_id}/answer",
            json={"answer": f"Answer {idx + 1}"},
        )
        assert resp.status_code == 200


def test_next_retry_job_position_adds_or_increments_suffix():
    assert _next_retry_job_position("Backend Engineer") == "Backend Engineer - lần 2"
    assert _next_retry_job_position("Backend Engineer - lần 2") == "Backend Engineer - lần 3"
    assert _next_retry_job_position("Backend Engineer  -  lần 9") == "Backend Engineer - lần 10"


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

    async def fake_next_question(self, conversation_id: int, previous_answer: str | None = None) -> str:  # noqa: ARG001
        return "Next question?"

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
    monkeypatch.setattr(ConversationService, "generate_next_question", fake_next_question)
    monkeypatch.setattr(ConversationService, "generate_analysis_report_payload", fake_report_payload)

    start = await client.post(
        "/api/v1/conversations",
        json={"job_position": "Backend Engineer", "job_description": "JD", "cv_profile": "CV"},
    )
    session_id = start.json()["session_id"]

    await client.get(f"/api/v1/conversations/{session_id}/next-question")
    await _complete_minimum_answers(client, session_id)

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
async def test_create_analysis_report_rejects_without_candidate_answers(client, monkeypatch):
    async def fake_initial_question(self, conversation_id: int) -> str:  # noqa: ARG001
        return "Q1?"

    monkeypatch.setattr(ConversationService, "generate_initial_question", fake_initial_question)

    start = await client.post(
        "/api/v1/conversations",
        json={"job_position": "Backend Engineer", "job_description": "JD", "cv_profile": "CV"},
    )
    session_id = start.json()["session_id"]

    await client.get(f"/api/v1/conversations/{session_id}/next-question")

    resp = await client.post(f"/api/v1/conversations/{session_id}/analysis-report")

    assert resp.status_code == 400
    assert "Cần trả lời ít nhất 3 câu hỏi" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_create_analysis_report_rejects_with_only_one_candidate_answer(client, monkeypatch):
    async def fake_initial_question(self, conversation_id: int) -> str:  # noqa: ARG001
        return "Q1?"

    async def fake_next_question(self, conversation_id: int, previous_answer: str | None = None) -> str:  # noqa: ARG001
        return "Q2?"

    monkeypatch.setattr(ConversationService, "generate_initial_question", fake_initial_question)
    monkeypatch.setattr(ConversationService, "generate_next_question", fake_next_question)

    start = await client.post(
        "/api/v1/conversations",
        json={"job_position": "Backend Engineer", "job_description": "JD", "cv_profile": "CV"},
    )
    session_id = start.json()["session_id"]

    await client.get(f"/api/v1/conversations/{session_id}/next-question")
    await client.post(f"/api/v1/conversations/{session_id}/answer", json={"answer": "Only one answer"})

    resp = await client.post(f"/api/v1/conversations/{session_id}/analysis-report")

    assert resp.status_code == 400
    assert "Cần trả lời ít nhất 3 câu hỏi" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_list_analysis_reports_returns_paginated_reports(client, monkeypatch):
    async def fake_next_question(self, conversation_id: int, previous_answer: str | None = None) -> str:  # noqa: ARG001
        return "Next question?"

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

    monkeypatch.setattr(ConversationService, "generate_next_question", fake_next_question)
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

    await _complete_minimum_answers(client, session_id)
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


@pytest.mark.asyncio
async def test_analysis_report_returns_original_cv_preview(client, session, test_user, tmp_path, monkeypatch):
    async def fake_next_question(self, conversation_id: int, previous_answer: str | None = None) -> str:  # noqa: ARG001
        return "Next question?"

    async def fake_report_payload(self, conversation_id: int):  # noqa: ARG001
        payload = AnalysisReportPayload.model_validate(
            {
                "overall_score": 82,
                "overall_grade": "B+",
                "level": "Tốt",
                "summary": "Ứng viên phù hợp.",
                "tags": [],
                "scores": {
                    "technical": {"score": 88, "evidence": "Nắm vững API."},
                    "communication": {"score": 80, "evidence": "Trả lời rõ."},
                    "confidence": {"score": 82, "evidence": "Tự tin."},
                    "soft_skills": {"score": 76, "evidence": "Có tinh thần hợp tác."},
                    "company_knowledge": {"score": 70, "evidence": "Có tìm hiểu công ty."},
                },
                "ai_coach_insights": [],
                "strengths": [],
                "weaknesses": [],
                "knowledge_gaps": [],
                "study_plan": [],
            }
        )
        return payload, '{"overall_score":82}'

    monkeypatch.setattr(ConversationService, "generate_next_question", fake_next_question)
    monkeypatch.setattr(ConversationService, "generate_analysis_report_payload", fake_report_payload)

    cv_path = tmp_path / "candidate.pdf"
    cv_content = b"%PDF-1.4\n% test cv\n"
    cv_path.write_bytes(cv_content)

    cv = CVProfile(user_id=test_user.id, raw_file_url=str(cv_path), text_hashed="cv-hash")
    jd = JobDescription(user_id=test_user.id, raw_file_url=str(tmp_path / "jd.pdf"), text_hashed="jd-hash")
    session.add_all([cv, jd])
    await session.flush()

    analysis_session = AnalysisSession(
        user_id=test_user.id,
        id_cv=cv.id_cv,
        id_jd=jd.id_jd,
        cv_raw_text="CV raw text",
        jd_raw_text="JD raw text",
    )
    session.add(analysis_session)
    await session.commit()
    await session.refresh(analysis_session)

    start = await client.post(
        "/api/v1/conversations",
        json={"analysis_session_id": analysis_session.id_session, "job_position": "Backend Engineer"},
    )
    assert start.status_code == 201
    start_data = start.json()
    assert start_data["analysis_session_id"] == analysis_session.id_session
    assert start_data["session_id"] != str(analysis_session.id_session)
    session_id = start_data["session_id"]

    await _complete_minimum_answers(client, session_id)
    report = await client.post(f"/api/v1/conversations/{session_id}/analysis-report")
    assert report.status_code == 200
    data = report.json()
    assert data["analysis_session_id"] == analysis_session.id_session
    assert data["cv_preview"] == {
        "id_cv": cv.id_cv,
        "file_name": "candidate.pdf",
        "content_type": "application/pdf",
        "preview_url": f"/api/v1/conversations/{session_id}/cv-preview",
    }

    preview = await client.get(data["cv_preview"]["preview_url"])
    assert preview.status_code == 200
    assert preview.headers["content-type"] == "application/pdf"
    assert preview.content == cv_content


@pytest.mark.asyncio
async def test_retry_interview_creates_new_conversation_without_reupload(client, session, test_user, tmp_path, monkeypatch):
    async def fake_next_question(self, conversation_id: int, previous_answer: str | None = None) -> str:  # noqa: ARG001
        return "Next question?"

    async def fake_report_payload(self, conversation_id: int):  # noqa: ARG001
        payload = AnalysisReportPayload.model_validate(
            {
                "overall_score": 55,
                "overall_grade": "C",
                "level": "Cần cải thiện",
                "summary": "Ứng viên muốn thử phỏng vấn lại.",
                "tags": [],
                "scores": {
                    "technical": {"score": 55, "evidence": "Cần trả lời sâu hơn."},
                    "communication": {"score": 60, "evidence": "Diễn đạt chấp nhận được."},
                    "confidence": {"score": 50, "evidence": "Còn lưỡng lự."},
                    "soft_skills": {"score": 55, "evidence": "Có nêu ví dụ ngắn."},
                    "company_knowledge": {"score": 55, "evidence": "Có nhắc tới JD."},
                },
                "ai_coach_insights": [],
                "strengths": [],
                "weaknesses": ["Thiếu ví dụ cụ thể"],
                "knowledge_gaps": [],
                "study_plan": [],
            }
        )
        return payload, '{"overall_score":55}'

    monkeypatch.setattr(ConversationService, "generate_next_question", fake_next_question)
    monkeypatch.setattr(ConversationService, "generate_analysis_report_payload", fake_report_payload)

    cv = CVProfile(user_id=test_user.id, raw_file_url=str(tmp_path / "candidate.pdf"), text_hashed="cv-retry")
    jd = JobDescription(user_id=test_user.id, raw_file_url=str(tmp_path / "jd.pdf"), text_hashed="jd-retry")
    session.add_all([cv, jd])
    await session.flush()

    analysis_session = AnalysisSession(
        user_id=test_user.id,
        id_cv=cv.id_cv,
        id_jd=jd.id_jd,
        cv_raw_text="CV raw text for retry",
        jd_raw_text="JD raw text for retry",
    )
    session.add(analysis_session)
    await session.commit()
    await session.refresh(analysis_session)

    start = await client.post(
        "/api/v1/conversations",
        json={"analysis_session_id": analysis_session.id_session, "job_position": "Backend Engineer"},
    )
    assert start.status_code == 201
    original = start.json()

    await _complete_minimum_answers(client, original["session_id"])
    report = await client.post(f"/api/v1/conversations/{original['session_id']}/analysis-report")
    assert report.status_code == 200

    retry = await client.post(f"/api/v1/conversations/{original['session_id']}/retry")
    assert retry.status_code == 201
    data = retry.json()
    assert data["id"] != original["id"]
    assert data["session_id"] != original["session_id"]
    assert data["analysis_session_id"] == analysis_session.id_session
    assert data["status"] == "active"
    assert data["job_position"] == "Backend Engineer - lần 2"
    assert data["job_description"] == "JD raw text for retry"
    assert data["cv_profile"] == "CV raw text for retry"
    assert data["messages"] == []