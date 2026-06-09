import pytest

from app.feature.feature_up_cv.auth.models.analysis_session import AnalysisSession
from app.feature.feature_up_cv.auth.models.cv_profile import CVProfile
from app.feature.feature_up_cv.auth.models.job_description import JobDescription
from app.feature.conversation.service import ConversationService


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


@pytest.mark.asyncio
async def test_generate_initial_question_uses_company_info(session, test_user, monkeypatch):
    service = ConversationService(session)

    cv = CVProfile(user_id=test_user.id, raw_file_url="cv.pdf", text_hashed="cv-hash")
    jd = JobDescription(user_id=test_user.id, raw_file_url="jd.pdf", text_hashed="jd-hash")
    session.add_all([cv, jd])
    await session.flush()

    analysis_session = AnalysisSession(
        user_id=test_user.id,
        id_cv=cv.id_cv,
        id_jd=jd.id_jd,
        cv_raw_text="CV raw text",
        jd_raw_text="JD raw text",
        company_info="Company info snapshot",
    )
    session.add(analysis_session)
    await session.flush()

    conv = await service.create_conversation(
        user_id=test_user.id,
        job_position="Backend Engineer",
        job_description="JD",
        cv_profile="CV",
        analysis_session_id=analysis_session.id_session,
    )
    await session.commit()

    captured = {}

    def fake_generate_content(*, prompt: str, step: str, config):  # noqa: ARG001
        captured["prompt"] = prompt
        return "Q1?"

    monkeypatch.setattr("app.feature.conversation.service.generate_content", fake_generate_content)

    question = await service.generate_initial_question(conv.id)

    assert question == "Q1?"
    assert "Company Research:" in captured["prompt"]
    assert "Company info snapshot" in captured["prompt"]
    assert "CV" in captured["prompt"]
    assert "JD" in captured["prompt"]
    assert "Câu hỏi phải chạm đủ 3 phần" in captured["prompt"]


@pytest.mark.asyncio
async def test_generate_initial_question_falls_back_to_company_question(session, test_user, monkeypatch):
    service = ConversationService(session)

    cv = CVProfile(user_id=test_user.id, raw_file_url="cv.pdf", text_hashed="cv-hash")
    jd = JobDescription(user_id=test_user.id, raw_file_url="jd.pdf", text_hashed="jd-hash")
    session.add_all([cv, jd])
    await session.flush()

    analysis_session = AnalysisSession(
        user_id=test_user.id,
        id_cv=cv.id_cv,
        id_jd=jd.id_jd,
        cv_raw_text="CV raw text",
        jd_raw_text="JD raw text",
        company_info="Company info snapshot",
    )
    session.add(analysis_session)
    await session.flush()

    conv = await service.create_conversation(
        user_id=test_user.id,
        job_position="Backend Engineer",
        job_description="JD",
        cv_profile="CV",
        analysis_session_id=analysis_session.id_session,
    )
    await session.commit()

    call_count = {"count": 0}

    def fake_generate_content(*, prompt: str, step: str, config):  # noqa: ARG001
        call_count["count"] += 1
        return "Hãy kể về kinh nghiệm của bạn với Python."

    monkeypatch.setattr("app.feature.conversation.service.generate_content", fake_generate_content)

    question = await service.generate_initial_question(conv.id)

    assert call_count["count"] == 2
    assert "tìm hiểu gì về" in question.lower()


@pytest.mark.asyncio
async def test_generate_third_question_prioritizes_company_info(session, test_user, monkeypatch):
    service = ConversationService(session)

    cv = CVProfile(user_id=test_user.id, raw_file_url="cv.pdf", text_hashed="cv-hash")
    jd = JobDescription(user_id=test_user.id, raw_file_url="jd.pdf", text_hashed="jd-hash")
    session.add_all([cv, jd])
    await session.flush()

    analysis_session = AnalysisSession(
        user_id=test_user.id,
        id_cv=cv.id_cv,
        id_jd=jd.id_jd,
        cv_raw_text="CV raw text",
        jd_raw_text="JD raw text",
        company_info="Company info snapshot",
    )
    session.add(analysis_session)
    await session.flush()

    conv = await service.create_conversation(
        user_id=test_user.id,
        job_position="Backend Engineer",
        job_description="JD",
        cv_profile="CV",
        analysis_session_id=analysis_session.id_session,
    )
    await session.flush()

    await service.add_message(conversation_id=conv.id, role="interviewer", content="Q1", question="Q1")
    await service.add_message(conversation_id=conv.id, role="candidate", content="A1", answer="A1")
    await service.add_message(conversation_id=conv.id, role="interviewer", content="Q2", question="Q2")
    await service.add_message(conversation_id=conv.id, role="candidate", content="A2", answer="A2")
    await session.commit()

    call_count = {"count": 0}

    def fake_generate_content(*, prompt: str, step: str, config):  # noqa: ARG001
        call_count["count"] += 1
        return "Hãy kể về kinh nghiệm của bạn với Python."

    monkeypatch.setattr("app.feature.conversation.service.generate_content", fake_generate_content)

    question = await service.generate_next_question(conv.id, previous_answer="A2")

    assert call_count["count"] == 2
    assert "tìm hiểu gì về" in question.lower()
