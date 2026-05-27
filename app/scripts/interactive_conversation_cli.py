"""
Interactive terminal script to test the Conversation flow.

Run:
  PYTHONPATH=. .venv/bin/python app/scripts/interactive_conversation_cli.py

Options:
  --email test@example.com
  --username testuser
  --no-ai              # don't call Gemini; use local placeholder questions
"""
SAMPLE_CV_PROFILE = """
Name: Nguyen Van A
Email: nguyenvana@example.com
Phone: +84 123 456 789

Experience:
- Backend Developer at TechCorp (2021-2024, 3 years)
  * Built APIs using FastAPI
  * PostgreSQL database design
  * AWS deployment and DevOps
  
- Junior Developer at StartupXYZ (2019-2021, 2 years)
  * Django development
  * REST API development
  * MySQL database

Skills:
- Languages: Python, JavaScript, SQL
- Frameworks: FastAPI, Django, Flask
- Databases: PostgreSQL, MySQL, MongoDB
- Cloud: AWS, Google Cloud
- Tools: Docker, Git, CI/CD
"""
import argparse
import asyncio
import json
import sys
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.feature.auth.models.user import User
from app.feature.conversation.model.conversation import ConversationStatus
from app.feature.conversation.service import ConversationService


SAMPLE_JOB_DESCRIPTION = """
Senior Python Backend Engineer

Requirements:
- 5+ years experience with Python
- FastAPI or Django experience
- PostgreSQL and async programming
- AWS/Cloud services
- RESTful API design
- System design and scalability

Responsibilities:
- Design and build scalable backend services
- Mentor junior developers
- Code review and architecture decisions
""".strip()

SAMPLE_CV_PROFILE = """
Name: Nguyen Van A
Email: nguyenvana@example.com
Phone: +84 123 456 789

Experience:
- Backend Developer at TechCorp (2021-2024, 3 years)
  * Built APIs using FastAPI
  * PostgreSQL database design
  * AWS deployment and DevOps

- Junior Developer at StartupXYZ (2019-2021, 2 years)
  * Django development
  * REST API development
  * MySQL database

Skills:
- Languages: Python, JavaScript, SQL
- Frameworks: FastAPI, Django, Flask
- Databases: PostgreSQL, MySQL, MongoDB
- Cloud: AWS, Google Cloud
- Tools: Docker, Git, CI/CD
""".strip()


async def _ainput(prompt: str) -> str:
    return await asyncio.to_thread(input, prompt)


async def get_or_create_user(
    db: AsyncSession,
    *,
    email: str,
    username: str,
    password: str,
    full_name: str,
) -> User:
    result = await db.execute(select(User).where(User.email == email))
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    user = User(
        email=email,
        username=username,
        full_name=full_name,
        hashed_password=hash_password(password),
        auth_provider="password",
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


def local_question(round_idx: int) -> str:
    questions = [
        "Bạn hãy giới thiệu ngắn gọn về kinh nghiệm backend của bạn (1-2 phút).",
        "Bạn đã từng tối ưu performance PostgreSQL/SQL như thế nào? Nêu ví dụ cụ thể.",
        "Trong FastAPI, bạn xử lý async I/O và background tasks ra sao?",
        "Bạn thiết kế authentication/authorization (JWT/RBAC) như thế nào?",
    ]
    return questions[min(round_idx, len(questions) - 1)]


async def run_interactive(
    *,
    email: str,
    username: str,
    password: str,
    full_name: str,
    no_ai: bool,
    max_rounds: int,
    use_sample: bool,
) -> int:
    db: AsyncSession = AsyncSessionLocal()
    service = ConversationService(db)
    try:
        user = await get_or_create_user(
            db,
            email=email,
            username=username,
            password=password,
            full_name=full_name,
        )
        await db.commit()

        print("\n=== START INTERVIEW ===")
        if use_sample:
            job_description = SAMPLE_JOB_DESCRIPTION
            cv_profile = SAMPLE_CV_PROFILE
            print("(using SAMPLE_JOB_DESCRIPTION + SAMPLE_CV_PROFILE)")
        else:
            job_description = await _ainput("Paste Job Description (single line):\n> ")
            cv_profile = await _ainput("Paste CV profile (single line):\n> ")

        conversation = await service.create_conversation(
            user_id=user.id,
            job_position="Sample Interview" if use_sample else "N/A",
            job_description=job_description.strip() or "N/A",
            cv_profile=cv_profile.strip() or "N/A",
        )
        await db.commit()
        print(f"\nSession ID: {conversation.session_id}")
        print("Type your answer. Commands: /end to finish, /quit to exit without scoring.\n")

        last_answer: Optional[str] = None
        for round_idx in range(max_rounds):
            if no_ai:
                question = local_question(round_idx)
            else:
                if last_answer is None:
                    question = await service.generate_initial_question(conversation.id)
                else:
                    question = await service.generate_next_question(conversation.id, previous_answer=last_answer)

            msg_q = await service.add_message(
                conversation_id=conversation.id,
                role="interviewer",
                content=question,
                question=question,
            )
            await db.commit()

            print(f"\n[AI] {question}")
            answer = (await _ainput("[YOU] ")).strip()
            if answer.lower() in {"/quit", "/exit"}:
                print("Exit without evaluation.")
                return 0
            if answer.lower() == "/end":
                break
            if not answer:
                print("(empty answer ignored; use /end to finish)")
                continue

            await service.add_message(
                conversation_id=conversation.id,
                role="candidate",
                content=answer,
                answer=answer,
            )
            await db.commit()
            last_answer = answer

        print("\n=== EVALUATION ===")
        if no_ai:
            evaluation = {
                "fit_score": None,
                "recommendation": "N/A",
                "strengths": [],
                "weaknesses": [],
                "comments": "no-ai mode: evaluation skipped",
            }
            score = None
            recommendation = "N/A"
        else:
            report = await service.create_analysis_report(conversation.id)
            evaluation = {
                "overall_score": report.overall_score,
                "overall_grade": report.overall_grade,
                "summary": report.summary,
                "scores": report.scores,
                "knowledge_gaps": report.knowledge_gaps,
                "study_plan": report.study_plan,
            }
            score = report.overall_score
            recommendation = report.overall_grade

        if no_ai:
            await service.end_conversation(conversation.id, result=evaluation, score=score)
        await db.commit()

        print(f"Status: {ConversationStatus.COMPLETED}")
        print(f"Score: {score}")
        print(f"Grade: {recommendation}")
        print("Report JSON:")
        print(json.dumps(evaluation, ensure_ascii=False, indent=2))
        return 0
    finally:
        await db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Interactive Conversation CLI test")
    parser.add_argument("--email", default="test@example.com")
    parser.add_argument("--username", default="testuser")
    parser.add_argument("--password", default="test123456")
    parser.add_argument("--full-name", default="Test User")
    parser.add_argument("--max-rounds", type=int, default=6)
    parser.add_argument("--no-ai", action="store_true", help="Do not call Gemini; use local questions")
    parser.add_argument("--no-sample", action="store_true", help="Do not use sample JD/CV; prompt for input")
    args = parser.parse_args()

    try:
        return asyncio.run(
            run_interactive(
                email=args.email,
                username=args.username,
                password=args.password,
                full_name=args.full_name,
                no_ai=args.no_ai,
                max_rounds=args.max_rounds,
                use_sample=not args.no_sample,
            )
        )
    except KeyboardInterrupt:
        print("\nInterrupted.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
