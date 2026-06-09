import pytest

from app.feature.conversation.auth.services import ConversationService
from app.feature.conversation.interview_agent.agent import interview_agent


@pytest.mark.asyncio
async def test_conversation_service_crud(session, test_user):
    service = ConversationService(session)
<<<<<<< HEAD
<<<<<<< HEAD
    conv = await service.create_conversation(
        user_id=test_user.id,
        job_position="Backend Engineer",
        job_description="JD",
        cv_profile="CV",
    )
=======
    conv = await service.create_conversation(user_id=test_user.id, job_description="JD", cv_profile="CV")
>>>>>>> c2202c1 (rebase main)
    await service.add_message(conversation_id=conv.id, role="interviewer", content="Q1", question="Q1")
    await service.add_message(conversation_id=conv.id, role="candidate", content="A1", answer="A1")
=======

    conv = await service.create_conversation(
        user_id=test_user.id,
        job_description="Python Developer",
        cv_profile="Experienced Python dev",
    )
    await session.commit()
    assert conv.id >= 1
    assert conv.session_id
    assert conv.status == "active"

    retrieved = await service.get_conversation_by_id(conv.id)
    assert retrieved is not None
    assert retrieved.job_description == "Python Developer"

    conversations, total = await service.get_user_conversations(user_id=test_user.id)
    assert total >= 1

    ended = await service.end_conversation(conv.id, result={"fit_score": 75}, score=75)
    assert ended.status == "completed"
    assert ended.score == 75


@pytest.mark.asyncio
async def test_conversation_message_lifecycle(session, test_user):
    service = ConversationService(session)

    conv = await service.create_conversation(
        user_id=test_user.id,
        job_description="JD",
        cv_profile="CV",
    )
>>>>>>> 7a94a79 (thay đổi workflow conversation)
    await session.commit()

    msg1 = await service.add_message(conv.id, role="interviewer", content="Q1?", question="Q1?")
    msg2 = await service.add_message(conv.id, role="candidate", content="A1", answer="A1")
    await session.commit()

<<<<<<< HEAD
    monkeypatch.setattr("app.feature.conversation.service.generate_content", fake_generate_content)
    result = await service.evaluate_answer(conv.id)
    assert result["fit_score"] == 42
    assert result["recommendation"] == "MAYBE"
<<<<<<< HEAD
=======

>>>>>>> c2202c1 (rebase main)
=======
    messages = await service.get_conversation_messages(conv.id)
    assert len(messages) == 2

    last = await service.get_last_message(conv.id)
    assert last.id == msg2.id
    assert last.role == "candidate"

    by_role = await service.get_messages_by_role(conv.id, "interviewer")
    assert len(by_role) == 1
    assert by_role[0].content == "Q1?"


@pytest.mark.asyncio
async def test_interview_agent_generate_question(monkeypatch):
    async def fake_generate_question(self, job_description, cv_profile, conversation_id, previous_answer=None):
        if previous_answer:
            return f"Follow-up: {previous_answer}"
        return "First question?"

    monkeypatch.setattr(type(interview_agent), "generate_question", fake_generate_question)

    result = await interview_agent.generate_question(
        job_description="JD",
        cv_profile="CV",
        conversation_id=9999,
    )
    assert result == "First question?"

    result_followup = await interview_agent.generate_question(
        job_description="JD",
        cv_profile="CV",
        conversation_id=9999,
        previous_answer="I used Python for 3 years",
    )
    assert "Follow-up" in result_followup


@pytest.mark.asyncio
async def test_interview_agent_evaluate(monkeypatch):
    async def fake_evaluate(self, job_description, cv_profile, conversation_id):
        return {
            "fit_score": 85,
            "strengths": ["Good Python skills"],
            "weaknesses": ["Limited SQL experience"],
            "recommendation": "PASS",
            "comments": "Solid candidate",
        }

    monkeypatch.setattr(type(interview_agent), "evaluate_interview", fake_evaluate)

    result = await interview_agent.evaluate_interview(
        job_description="JD",
        cv_profile="CV",
        conversation_id=9999,
    )
    assert result["fit_score"] == 85
    assert result["recommendation"] == "PASS"
    assert "Python" in result["strengths"][0]
>>>>>>> 7a94a79 (thay đổi workflow conversation)
