import pytest

from app.feature.conversation.service import ConversationService


@pytest.mark.asyncio
async def test_evaluate_answer_parses_json(session, test_user, monkeypatch):
    service = ConversationService(session)
    conv = await service.create_conversation(
        user_id=test_user.id,
        job_position="Backend Engineer",
        job_description="JD",
        cv_profile="CV",
    )
    await service.add_message(conversation_id=conv.id, role="interviewer", content="Q1", question="Q1")
    await service.add_message(conversation_id=conv.id, role="candidate", content="A1", answer="A1")
    await session.commit()

    def fake_generate_content(*, prompt: str, step: str, config):  # noqa: ARG001
        return 'Some text before {"fit_score": 42, "recommendation": "MAYBE", "strengths": [], "weaknesses": [], "comments": "x"} some text after'

    monkeypatch.setattr("app.feature.conversation.service.generate_content", fake_generate_content)
    result = await service.evaluate_answer(conv.id)
    assert result["fit_score"] == 42
    assert result["recommendation"] == "MAYBE"