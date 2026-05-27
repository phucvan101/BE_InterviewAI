"""
Test script for Conversation API flow
Sử dụng chế độ async để test toàn bộ quy trình phỏng vấn
"""

import asyncio
import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.feature.auth.models.user import User
from app.feature.conversation.service import ConversationService
from app.feature.conversation.model.conversation import ConversationStatus

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Sample data
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

SAMPLE_ANSWERS = [
    "Tôi có hơn 3 năm kinh nghiệm với Python, chủ yếu là backend development. Tôi đã làm việc với FastAPI và Django để xây dựng REST APIs.",
    "Tôi luôn áp dụng các best practices như proper error handling, input validation, logging, và testing. Tôi viết unit tests và integration tests.",
    "Tôi đã work với AWS trong 2 năm, sử dụng EC2, RDS, S3, Lambda cho các dự án. Tôi cũng có kinh nghiệm với Docker và CI/CD pipelines.",
    "Tôi có kinh nghiệm thiết kế cơ sở dữ liệu relational và viết các query tối ưu. Tôi cũng sử dụng ORM như SQLAlchemy.",
]


async def setup_test_user(db: AsyncSession) -> User:
    """Tạo user test nếu chưa tồn tại"""
    from sqlalchemy import select
    
    result = await db.execute(
        select(User).where(User.email == "test@example.com")
    )
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        logger.info(f"Test user already exists: {existing_user.email}")
        return existing_user
    
    # Tạo user mới
    test_user = User(
        email="test@example.com",
        username="testuser",
        full_name="Test User",
        hashed_password=hash_password("test123456"),
        auth_provider="password",
        is_active=True,
        is_verified=True,
    )
    db.add(test_user)
    await db.flush()
    logger.info(f"Created test user: {test_user.email} (id={test_user.id})")
    return test_user


async def test_conversation_flow():
    """Test complete conversation flow"""
    db: AsyncSession = AsyncSessionLocal()
    service = ConversationService(db)
    
    try:
        # ──────────────────────────────────────────────────────────────
        # Step 1: Setup
        # ──────────────────────────────────────────────────────────────
        logger.info("=" * 70)
        logger.info("TEST: Complete Conversation Flow")
        logger.info("=" * 70)
        
        user = await setup_test_user(db)
        await db.commit()
        
        # ──────────────────────────────────────────────────────────────
        # Step 2: Create conversation
        # ──────────────────────────────────────────────────────────────
        logger.info("\n[STEP 1] Creating conversation...")
        conversation = await service.create_conversation(
            user_id=user.id,
            job_description=SAMPLE_JOB_DESCRIPTION,
            cv_profile=SAMPLE_CV_PROFILE,
        )
        await db.commit()
        
        logger.info(f"✓ Conversation created:")
        logger.info(f"  - Session ID: {conversation.session_id}")
        logger.info(f"  - Conversation ID: {conversation.id}")
        logger.info(f"  - Status: {conversation.status}")
        logger.info(f"  - Created at: {conversation.created_at}")
        
        # ──────────────────────────────────────────────────────────────
        # Step 3: Get first question
        # ──────────────────────────────────────────────────────────────
        logger.info("\n[STEP 2] Generating first question...")
        question_1 = await service.generate_initial_question(conversation.id)
        logger.info(f"✓ First question generated:")
        logger.info(f"  {question_1[:100]}...")
        
        msg_1 = await service.add_message(
            conversation_id=conversation.id,
            role="interviewer",
            content=question_1,
            question=question_1,
        )
        await db.commit()
        logger.info(f"✓ Message saved (id={msg_1.id})")
        
        # ──────────────────────────────────────────────────────────────
        # Step 4: Send answers and get next questions (simulate Q&A)
        # ──────────────────────────────────────────────────────────────
        for i, answer in enumerate(SAMPLE_ANSWERS, 1):
            logger.info(f"\n[STEP {i+2}] Round {i} - Candidate answers...")
            
            # Save answer
            await service.add_message(
                conversation_id=conversation.id,
                role="candidate",
                content=answer,
                answer=answer,
            )
            logger.info(f"✓ Answer saved: {answer[:60]}...")
            
            # Generate next question
            if i < len(SAMPLE_ANSWERS):
                logger.info(f"Generating next question...")
                next_question = await service.generate_next_question(
                    conversation.id,
                    previous_answer=answer,
                )
                logger.info(f"✓ Next question generated:")
                logger.info(f"  {next_question[:100]}...")
                
                msg = await service.add_message(
                    conversation_id=conversation.id,
                    role="interviewer",
                    content=next_question,
                    question=next_question,
                )
                await db.commit()
                logger.info(f"✓ Message saved (id={msg.id})")
        
        # ──────────────────────────────────────────────────────────────
        # Step 5: End interview and evaluate
        # ──────────────────────────────────────────────────────────────
        logger.info(f"\n[STEP {len(SAMPLE_ANSWERS)+2}] Evaluating interview...")
        evaluation = await service.evaluate_answer(conversation.id)
        
        logger.info(f"✓ Evaluation complete:")
        logger.info(f"  - Fit Score: {evaluation.get('fit_score')}/100")
        logger.info(f"  - Recommendation: {evaluation.get('recommendation')}")
        logger.info(f"  - Strengths: {', '.join(evaluation.get('strengths', [])[:2])}")
        logger.info(f"  - Weaknesses: {', '.join(evaluation.get('weaknesses', [])[:2])}")
        
        # End conversation
        await service.end_conversation(
            conversation.id,
            result=evaluation,
            score=evaluation.get('fit_score'),
        )
        await db.commit()
        
        # ──────────────────────────────────────────────────────────────
        # Step 6: Verify results
        # ──────────────────────────────────────────────────────────────
        logger.info(f"\n[STEP {len(SAMPLE_ANSWERS)+3}] Verifying results...")
        
        # Reload conversation
        final_conversation = await service.get_conversation_by_session_id(
            conversation.session_id
        )
        messages = await service.get_conversation_messages(conversation.id)
        
        logger.info(f"✓ Final state:")
        logger.info(f"  - Conversation Status: {final_conversation.status}")
        logger.info(f"  - Final Score: {final_conversation.score}")
        logger.info(f"  - Total Messages: {len(messages)}")
        logger.info(f"    * Interviewer: {len([m for m in messages if m.role == 'interviewer'])}")
        logger.info(f"    * Candidate: {len([m for m in messages if m.role == 'candidate'])}")
        
        # ──────────────────────────────────────────────────────────────
        # Summary
        # ──────────────────────────────────────────────────────────────
        logger.info("\n" + "=" * 70)
        logger.info("✅ TEST PASSED - Complete conversation flow works!")
        logger.info("=" * 70)
        logger.info(f"Session ID: {conversation.session_id}")
        logger.info(f"Total Q&A rounds: {len(SAMPLE_ANSWERS)}")
        logger.info(f"Final Score: {final_conversation.score}")
        logger.info(f"Recommendation: {evaluation.get('recommendation')}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ TEST FAILED: {str(e)}", exc_info=True)
        await db.rollback()
        return False
    finally:
        await db.close()


if __name__ == "__main__":
    logger.info("Starting test...")
    success = asyncio.run(test_conversation_flow())
    exit(0 if success else 1)
