import json

import pytest

from app.feature.conversation.service import ConversationService


@pytest.mark.asyncio
async def test_start_interview_creates_conversation(client):
    payload = {"job_description": "JD", "cv_profile": "CV"}
    resp = await client.post("/api/v1/conversations", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["id"] >= 1
    assert data["session_id"]
    assert data["status"] == "active"
    assert data["job_description"] == "JD"
    assert data["cv_profile"] == "CV"


@pytest.mark.asyncio
async def test_get_next_question_creates_message(client, monkeypatch):
    async def fake_initial_question(self, conversation_id: int) -> str:  # noqa: ARG001
        return "Q1?"

    monkeypatch.setattr(ConversationService, "generate_initial_question", fake_initial_question)

    start = await client.post("/api/v1/conversations", json={"job_description": "JD", "cv_profile": "CV"})
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

    start = await client.post("/api/v1/conversations", json={"job_description": "JD", "cv_profile": "CV"})
    session_id = start.json()["session_id"]

    await client.get(f"/api/v1/conversations/{session_id}/next-question")

    resp = await client.post(f"/api/v1/conversations/{session_id}/answer", json={"answer": "My answer"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == session_id
    assert data["question"] == "Q2?"
    assert data["message_id"] >= 1


@pytest.mark.asyncio
async def test_end_interview_returns_evaluation(client, monkeypatch):
    async def fake_initial_question(self, conversation_id: int) -> str:  # noqa: ARG001
        return "Q1?"

    async def fake_evaluate(self, conversation_id: int) -> dict:
        return {"fit_score": 80, "recommendation": "PASS", "strengths": ["a"], "weaknesses": ["b"], "comments": "ok"}

    monkeypatch.setattr(ConversationService, "generate_initial_question", fake_initial_question)
    monkeypatch.setattr(ConversationService, "evaluate_answer", fake_evaluate)

    start = await client.post("/api/v1/conversations", json={"job_description": "JD", "cv_profile": "CV"})
    session_id = start.json()["session_id"]

    await client.get(f"/api/v1/conversations/{session_id}/next-question")

    resp = await client.post(f"/api/v1/conversations/{session_id}/end")
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == session_id
    assert data["score"] == 80
    assert data["result"]["recommendation"] == "PASS"
    assert data["total_messages"] >= 1

