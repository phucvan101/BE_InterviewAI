import json
import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import delete as sa_delete


from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.feature.conversation.model.conversation import (
    Conversation,
    ConversationAnalysisReport,
    ConversationMessage,
    ConversationStatus,
    MessageRole,
)
from app.feature.conversation.schema import AnalysisReportPayload
from app.feature.conversation.service.score_anomaly_detector import ScoreAnomalyDetector
from app.feature.feature_up_cv.gemini_client import generate_content, GeminiConfig

from app.core.ml_models import get_hallucination_guard


logger = logging.getLogger(__name__)
MIN_CANDIDATE_ANSWERS_FOR_ANALYSIS_REPORT = 3


def _ensure_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _calculate_duration_seconds(started_at: datetime, ended_at: datetime) -> int:
    started_at = _ensure_aware_utc(started_at)
    ended_at = _ensure_aware_utc(ended_at)
    return max(0, int((ended_at - started_at).total_seconds()))


class ConversationService:
    """Service quản lý conversations và messages"""
    
    def __init__(self, db: AsyncSession):
        self.db = db

    # ──────────────────────────────────────────────────────────────
    # Conversation CRUD
    # ──────────────────────────────────────────────────────────────

    async def create_conversation(
        self,
        user_id: int,
        job_position: str,
        job_description: str,
        cv_profile: str,
        company_name: str | None = None,
        analysis_session_id: int | None = None,
        session_id: str | None = None,
        force_new: bool = False,
    ) -> Conversation:
        """Tạo conversation mới"""
        if analysis_session_id and not force_new:
            existing = await self.get_conversation_by_analysis_session_id(
                user_id=user_id,
                analysis_session_id=analysis_session_id,
            )
            if existing:
                return existing

        # Idempotent: nếu session_id đã có conversation thì trả về luôn
        if session_id and not force_new:
            existing = await self.get_conversation_by_session_id(session_id)
            if existing:
                return existing

        conversation_kwargs = {
            "user_id": user_id,
            "job_position": job_position,
            "company_name": company_name,
            "job_description": job_description,
            "cv_profile": cv_profile,
            "analysis_session_id": analysis_session_id,
            "status": ConversationStatus.ACTIVE,
        }
        if session_id:
            conversation_kwargs["session_id"] = session_id

        conversation = Conversation(**conversation_kwargs)
        self.db.add(conversation)
        await self.db.flush()  # Get the ID without committing
        await self.db.refresh(conversation)
        logger.info(f"Created conversation: session_id={conversation.session_id}, user_id={user_id}")
        return conversation

    async def get_conversation_by_id(self, conversation_id: int) -> Optional[Conversation]:
        """Lấy conversation theo ID"""
        result = await self.db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        return result.scalar_one_or_none()

    async def get_conversation_by_session_id(self, session_id: str) -> Optional[Conversation]:
        """Lấy conversation theo session ID"""
        result = await self.db.execute(
            select(Conversation).where(Conversation.session_id == session_id)
        )
        return result.scalar_one_or_none()

    async def get_conversation_by_analysis_session_id(
        self,
        user_id: int,
        analysis_session_id: int,
    ) -> Optional[Conversation]:
        """Lấy conversation đã tạo từ một analysis session của user."""
        result = await self.db.execute(
            select(Conversation).where(
                Conversation.user_id == user_id,
                Conversation.analysis_session_id == analysis_session_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_user_conversations(
    self,
    user_id: int,
    page: int = 1,
    page_size: int = 10,
    status: Optional[str] = None,
    job_position: Optional[str] = None,
    ) -> tuple[list[Conversation], int]:
        """Lấy tất cả conversations của user (có phân trang)"""
        offset = (page - 1) * page_size

        base_where = [Conversation.user_id == user_id]

        if status:
            base_where.append(Conversation.status == status)

        if job_position:
            base_where.append(Conversation.job_position.ilike(f"%{job_position}%"))

        # Count total
        result = await self.db.execute(
            select(func.count(Conversation.id)).where(*base_where)
        )
        total = result.scalar() or 0

        # Get paginated results
        result = await self.db.execute(
            select(Conversation)
            .where(*base_where)
            .order_by(desc(Conversation.created_at))
            .offset(offset)
            .limit(page_size)
        )
        conversations = result.scalars().all()

        return conversations, total

    async def end_conversation(
        self,
        conversation_id: int,
        result: Optional[dict] = None,
        score: Optional[float] = None,
    ) -> Conversation:
        """Kết thúc conversation"""
        conversation = await self.get_conversation_by_id(conversation_id)
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")

        conversation.status = ConversationStatus.COMPLETED
        if result:
            conversation.result = json.dumps(result, ensure_ascii=False)
        if score is not None:
            conversation.score = score
        ended_at = datetime.now(timezone.utc)
        conversation.ended_at = ended_at
        conversation.interview_duration_seconds = _calculate_duration_seconds(
            conversation.started_at,
            ended_at,
        )

        await self.db.flush()
        await self.db.refresh(conversation)
        logger.info(f"Ended conversation: id={conversation_id}, score={score}")
        return conversation

    async def get_analysis_report_by_conversation_id(
        self,
        conversation_id: int,
    ) -> Optional[ConversationAnalysisReport]:
        """Lấy báo cáo phân tích theo conversation ID"""
        result = await self.db.execute(
            select(ConversationAnalysisReport).where(
                ConversationAnalysisReport.conversation_id == conversation_id
            )
        )
        return result.scalar_one_or_none()

    async def get_user_analysis_reports(
        self,
        user_id: int,
        page: int = 1,
        page_size: int = 10,
        status: Optional[str] = None,
    ) -> tuple[list[tuple[ConversationAnalysisReport, Conversation, int]], int]:
        """Lấy danh sách báo cáo phân tích của user (có phân trang)"""
        offset = (page - 1) * page_size

        count_stmt = (
            select(func.count(ConversationAnalysisReport.id))
            .join(Conversation, ConversationAnalysisReport.conversation_id == Conversation.id)
            .where(Conversation.user_id == user_id)
        )
        if status:
            count_stmt = count_stmt.where(ConversationAnalysisReport.status == status)

        result = await self.db.execute(count_stmt)
        total = result.scalar() or 0

        message_count = func.count(ConversationMessage.id).label("message_count")
        stmt = (
            select(ConversationAnalysisReport, Conversation, message_count)
            .join(Conversation, ConversationAnalysisReport.conversation_id == Conversation.id)
            .outerjoin(
                ConversationMessage,
                ConversationMessage.conversation_id == Conversation.id,
            )
            .where(Conversation.user_id == user_id)
            .group_by(ConversationAnalysisReport.id, Conversation.id)
            .order_by(desc(ConversationAnalysisReport.created_at))
            .offset(offset)
            .limit(page_size)
        )
        if status:
            stmt = stmt.where(ConversationAnalysisReport.status == status)

        result = await self.db.execute(stmt)
        return [(report, conversation, message_count) for report, conversation, message_count in result.all()], total

    async def create_analysis_report(self, conversation_id: int) -> ConversationAnalysisReport:
        """Tạo báo cáo phân tích nâng cao cho cuộc phỏng vấn"""
        existing = await self.get_analysis_report_by_conversation_id(conversation_id)
        if existing:
            return existing

        conversation = await self.get_conversation_by_id(conversation_id)
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")

        valid_answer_count = await self.count_valid_candidate_answers(conversation_id)
        if valid_answer_count < MIN_CANDIDATE_ANSWERS_FOR_ANALYSIS_REPORT:
            raise ValueError(
                "Not enough candidate answers to create analysis report: "
                f"{valid_answer_count}/{MIN_CANDIDATE_ANSWERS_FOR_ANALYSIS_REPORT}"
            )

        payload, raw_ai_response = await self.generate_analysis_report_payload(conversation_id)
        
        # Hallucination check
        
        # Lấy lại messages để dùng cho HallucinationGuard
        messages = await self.get_conversation_messages(conversation_id)

        guard = get_hallucination_guard()
        evidence_similarities = guard.calculate_evidence_similarities(payload, messages)
        hallucination_warnings = guard.validate_evidence(
            payload,
            messages,
            evidence_similarities=evidence_similarities,
        )
        if hallucination_warnings:
            logger.warning(
                f"[HallucinationGuard] conversation_id={conversation_id} "
                f"warnings={hallucination_warnings}"
            )

        score_warnings = ScoreAnomalyDetector().validate(
            payload,
            evidence_similarities=evidence_similarities,
        )
        if score_warnings:
            logger.warning(
                f"[ScoreAnomalyDetector] conversation_id={conversation_id} "
                f"warnings={score_warnings}"
            )

        report = ConversationAnalysisReport(
            conversation_id=conversation_id,
            status="completed",
            overall_score=payload.overall_score,
            overall_grade=payload.overall_grade,
            level=payload.level,
            summary=payload.summary,
            tags=payload.tags,
            scores=payload.scores.model_dump(),
            ai_coach_insights=[item.model_dump() for item in payload.ai_coach_insights],
            strengths=payload.strengths,
            weaknesses=payload.weaknesses,
            knowledge_gaps=[item.model_dump() for item in payload.knowledge_gaps],
            study_plan=[item.model_dump() for item in payload.study_plan],
            raw_ai_response=raw_ai_response,
        )
        self.db.add(report)

        conversation.status = ConversationStatus.COMPLETED
        conversation.score = payload.overall_score
        result_payload = payload.model_dump()
        result_payload["company_score"] = payload.scores.company_knowledge.score
        conversation.result = json.dumps(result_payload, ensure_ascii=False)
        ended_at = datetime.now(timezone.utc)
        conversation.ended_at = ended_at
        conversation.interview_duration_seconds = _calculate_duration_seconds(
            conversation.started_at,
            ended_at,
        )

        await self.db.flush()
        await self.db.refresh(report)
        await self.db.refresh(conversation)
        logger.info(
            f"Created analysis report: conversation_id={conversation_id}, "
            f"score={payload.overall_score}, grade={payload.overall_grade}"
        )
        return report


    async def delete_conversation(self, conversation_id: int, user_id: int) -> bool:
        """Xóa conversation cùng toàn bộ dữ liệu liên quan"""
        conversation = await self.get_conversation_by_id(conversation_id)
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")

        if conversation.user_id != user_id:
            raise PermissionError(
                f"User {user_id} does not have permission to delete conversation {conversation_id}"
            )

        # 1. Xóa analysis report (nếu có)
        await self.db.execute(
            sa_delete(ConversationAnalysisReport).where(
                ConversationAnalysisReport.conversation_id == conversation_id
            )
        )

        # 2. Xóa toàn bộ messages
        await self.db.execute(
            sa_delete(ConversationMessage).where(
                ConversationMessage.conversation_id == conversation_id
            )
        )

        # 3. Xóa conversation
        await self.db.delete(conversation)
        await self.db.flush()

        logger.info(
            f"Deleted conversation and related data: id={conversation_id}, user_id={user_id}"
        )
        return True
    # ──────────────────────────────────────────────────────────────
    # Message Management
    # ──────────────────────────────────────────────────────────────

    async def add_message(
        self,
        conversation_id: int,
        role: str,
        content: str,
        question: Optional[str] = None,
        answer: Optional[str] = None,
    ) -> ConversationMessage:
        """Thêm message vào conversation"""
        message = ConversationMessage(
            conversation_id=conversation_id,
            role=role,
            content=content,
            question=question,
            answer=answer,
        )
        self.db.add(message)
        await self.db.flush()
        await self.db.refresh(message)
        logger.info(f"Added message: id={message.id}, role={role}, conversation_id={conversation_id}")
        return message

    def _get_company_research_text(self, conversation: Conversation) -> Optional[str]:
        analysis_session = conversation.analysis_session
        if not analysis_session:
            return None
        return analysis_session.company_info or analysis_session.ci_raw_text

    def _build_company_research_section(self, conversation: Conversation) -> str:
        company_research_text = self._get_company_research_text(conversation)
        if not company_research_text:
            return ""
        return f"""
Company Research:
{company_research_text}
"""

    def _question_mentions_company_context(self, question: str, conversation: Conversation) -> bool:
        company_research_text = self._get_company_research_text(conversation)
        if not company_research_text:
            return False

        terms = [
            "công ty",
            "cong ty",
            "company",
            "sản phẩm",
            "san pham",
            "product",
            "domain",
            "văn hóa",
            "van hoa",
            "culture",
            "bối cảnh",
            "boi canh",
            "business",
            "khách hàng",
            "khach hang",
            "thị trường",
            "thi truong",
        ]
        if conversation.company_name:
            terms.append(conversation.company_name.lower())
        question_text = question.lower()
        return any(term in question_text for term in terms)

    def _build_company_question_prompt(
        self,
        *,
        conversation: Conversation,
        company_research_section: str,
        history: str | None = None,
        previous_answer: str | None = None,
        initial: bool = False,
        balanced_focus: str | None = None,
    ) -> str:
        if initial:
            return f"""
Bạn là một người phỏng vấn AI chuyên nghiệp.
Mục tiêu bắt buộc: câu hỏi phải cân bằng giữa CV, JD, và nếu có Company Research thì cả công ty nữa.
Không được để câu hỏi chỉ xoay quanh một mảng duy nhất.

Job Description:
{conversation.job_description}

CV Profile:
{conversation.cv_profile}
{company_research_section}
{balanced_focus or ""}

Hãy tạo đúng 1 câu hỏi mở đầu, trong đó liên hệ trực tiếp CV của ứng viên với JD.
Nếu có Company Research, ưu tiên hỏi theo hướng:
- Công ty đang làm về gì
- Công ty kinh doanh trong lĩnh vực nào
- Công ty đang bán sản phẩm, dịch vụ hoặc giải pháp gì
- Khách hàng mục tiêu là ai
- Văn hóa, giá trị hoặc bối cảnh kinh doanh của công ty là gì

Nếu tự nhiên hơn, có thể gộp các ý trên vào cùng một câu hỏi, nhưng câu hỏi phải nghe như câu hỏi phỏng vấn thật.

Chỉ trả lời câu hỏi, không thêm bất kỳ lời giải thích nào khác.
"""

        return f"""
Bạn là một người phỏng vấn AI chuyên nghiệp.
Mục tiêu bắt buộc: câu hỏi tiếp theo phải luân phiên bao phủ CV, JD, và nếu có Company Research thì cả công ty nữa.
Không được bỏ qua bất kỳ mảng nào đã chưa được khai thác đủ.

Job Description:
{conversation.job_description}

CV Profile:
{conversation.cv_profile}
{company_research_section}
Lịch sử cuộc trò chuyện:
{history or ""}

Phần trả lời trước đó của ứng viên:
{previous_answer or "N/A"}

{balanced_focus or ""}

Hãy tạo đúng 1 câu hỏi tiếp theo, sao cho câu hỏi có thể chạm vào cả CV hoặc JD, và nếu có Company Research thì thêm góc nhìn về công ty.
Ưu tiên các hướng hỏi về:
- Công ty đang làm gì / giải quyết vấn đề gì
- Công ty kinh doanh lĩnh vực nào
- Công ty đang bán sản phẩm, dịch vụ hoặc giải pháp gì
- Khách hàng mục tiêu hoặc thị trường của công ty
- Văn hóa, giá trị, cách vận hành hoặc bối cảnh kinh doanh của công ty

Nếu phù hợp, hãy biến các ý trên thành một câu hỏi tự nhiên thay vì liệt kê nhiều ý rời rạc.
Chỉ trả lời câu hỏi, không thêm bất kỳ lời giải thích nào khác.
"""

    def _fallback_company_question(self, conversation: Conversation) -> str:
        company_name = conversation.company_name or "công ty"
        return (
            f"Bạn đã tìm hiểu gì về {company_name}, đặc biệt là công ty đang làm gì, kinh doanh lĩnh vực nào, "
            "đang bán sản phẩm hoặc dịch vụ gì, và điều gì trong văn hóa hoặc mô hình kinh doanh của công ty "
            "khiến bạn thấy phù hợp với vị trí này?"
        )

    def _build_balanced_interview_focus(self, conversation: Conversation, *, has_history: bool) -> str:
        has_company = bool(self._get_company_research_text(conversation))
        if not has_history:
            if has_company:
                return (
                    "Câu hỏi phải chạm đủ 3 phần: kinh nghiệm trong CV, yêu cầu trong JD, "
                    "và một ý về Company Research."
                )
            return "Câu hỏi phải chạm đủ 2 phần: kinh nghiệm trong CV và yêu cầu trong JD."

        if has_company:
            return (
                "Nếu lịch sử chưa có phần công ty thì hỏi về Company Research. "
                "Nếu đã có rồi thì hãy cân bằng giữa CV và JD ở câu này."
            )

        return "Hãy cân bằng giữa CV và JD trong câu hỏi này."

    def _build_turn_based_focus(self, conversation: Conversation, question_number: int) -> str:
        has_company = bool(self._get_company_research_text(conversation))
        if question_number <= 1:
            if has_company:
                return (
                    "Câu hỏi số 1 phải chạm CV, JD, và có thể mở nhẹ vào Company Research, "
                    "nhưng vẫn giữ trọng tâm đánh giá kinh nghiệm ứng viên."
                )
            return "Câu hỏi số 1 phải chạm vào CV và JD."

        if question_number == 2:
            if has_company:
                return (
                    "Câu hỏi số 2 nên đi sâu hơn vào CV hoặc JD; có thể nhắc nhẹ Company Research nếu tự nhiên, "
                    "đặc biệt là công ty đang làm gì, kinh doanh gì hoặc bán gì."
                )
            return "Câu hỏi số 2 nên đi sâu hơn vào CV hoặc JD."

        if has_company:
            return (
                "Câu hỏi số 3 nên ưu tiên hỏi trực tiếp về Company Research: công ty đang làm gì, "
                "kinh doanh lĩnh vực nào, đang bán sản phẩm/dịch vụ gì, khách hàng là ai, hoặc văn hóa "
                "và bối cảnh kinh doanh, nhưng vẫn liên hệ với CV hoặc JD."
            )

        return "Câu hỏi tiếp theo nên tiếp tục khai thác CV và JD."

    def _generate_question_with_company_guardrail(
        self,
        *,
        conversation: Conversation,
        prompt: str,
        initial: bool,
        company_research_section: str,
        question_number: int,
        history: str | None = None,
        previous_answer: str | None = None,
        balanced_focus: str | None = None,
    ) -> str:
        question = generate_content(
            prompt=prompt,
            step="generate_initial_question" if initial else "generate_next_question",
            config=GeminiConfig(model="models/gemini-2.5-flash", temperature=0.7),
        ).strip()

        if not company_research_section or question_number < 3:
            return question

        if self._question_mentions_company_context(question, conversation):
            return question

        stronger_prompt = self._build_company_question_prompt(
            conversation=conversation,
            company_research_section=company_research_section,
            history=history,
            previous_answer=previous_answer,
            initial=initial,
            balanced_focus=balanced_focus,
        )
        retried_question = generate_content(
            prompt=stronger_prompt,
            step="generate_initial_question_company_guardrail" if initial else "generate_next_question_company_guardrail",
            config=GeminiConfig(model="models/gemini-2.5-flash", temperature=0.4),
        ).strip()

        if self._question_mentions_company_context(retried_question, conversation):
            return retried_question

        logger.warning(
            "Company research exists but generated question did not mention company context; using fallback question."
        )
        return self._fallback_company_question(conversation)

    async def get_conversation_messages(
        self,
        conversation_id: int,
        limit: Optional[int] = None,
    ) -> list[ConversationMessage]:
        """Lấy tất cả messages của conversation"""
        stmt = select(ConversationMessage).where(
            ConversationMessage.conversation_id == conversation_id
        ).order_by(ConversationMessage.created_at)

        if limit:
            stmt = stmt.limit(limit)

        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_last_message(self, conversation_id: int) -> Optional[ConversationMessage]:
        """Lấy message cuối cùng của conversation"""
        result = await self.db.execute(
            select(ConversationMessage).where(
                ConversationMessage.conversation_id == conversation_id
            ).order_by(desc(ConversationMessage.created_at)).limit(1)
        )
        return result.scalar_one_or_none()

    async def get_messages_by_role(
        self,
        conversation_id: int,
        role: str,
    ) -> list[ConversationMessage]:
        """Lấy tất cả messages của role cụ thể trong conversation"""
        result = await self.db.execute(
            select(ConversationMessage).where(
                and_(
                    ConversationMessage.conversation_id == conversation_id,
                    ConversationMessage.role == role,
                )
            ).order_by(ConversationMessage.created_at)
        )
        return result.scalars().all()

    async def count_valid_candidate_answers(self, conversation_id: int) -> int:
        """Đếm số câu trả lời ứng viên có nội dung thực sự."""
        messages = await self.get_messages_by_role(
            conversation_id=conversation_id,
            role=MessageRole.CANDIDATE.value,
        )
        return sum(1 for message in messages if (message.answer or message.content or "").strip())

    # ──────────────────────────────────────────────────────────────
    # AI Interview Logic
    # ──────────────────────────────────────────────────────────────

    async def generate_initial_question(self, conversation_id: int) -> str:
        """Tạo câu hỏi đầu tiên dựa trên JD, CV và optionally Company Research"""
        conversation = await self.get_conversation_by_id(conversation_id)
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")

        company_research_section = self._build_company_research_section(conversation)
        balanced_focus = self._build_turn_based_focus(conversation, question_number=1)
        prompt = f"""
Bạn là một người phỏng vấn AI chuyên nghiệp. Dựa trên Job Description, CV của ứng viên{', và Company Research' if company_research_section else ''}, hãy tạo một câu hỏi phỏng vấn đầu tiên.

Job Description:
{conversation.job_description}

CV Profile:
{conversation.cv_profile}
{company_research_section}
{balanced_focus}
Câu hỏi phải đánh giá kỹ năng và kinh nghiệm theo CV/JD.
Nếu có Company Research, ưu tiên lồng ghép ít nhất một ý về công ty: công ty đang làm gì, kinh doanh lĩnh vực nào, đang bán sản phẩm/dịch vụ gì, khách hàng mục tiêu là ai, hoặc văn hóa/bối cảnh kinh doanh.
Câu hỏi phải đồng thời bám vào CV và JD, không được chỉ hỏi công ty.
Câu hỏi nên:
- Cụ thể và có liên quan đến công việc
- Để lại chỗ cho ứng viên thể hiện kinh nghiệm của họ
- Nếu có Company Research, có yếu tố kiểm tra hiểu biết về công ty
- Có thể được trả lời trong khoảng 1-3 phút

Chỉ trả lời câu hỏi, không thêm bất kỳ lời giải thích nào khác.
"""
        try:
            question = self._generate_question_with_company_guardrail(
                conversation=conversation,
                prompt=prompt,
                initial=True,
                company_research_section=company_research_section,
                question_number=1,
                balanced_focus=balanced_focus,
            )
            return question
        except Exception as e:
            logger.error(f"Error generating initial question: {str(e)}")
            raise

    async def generate_next_question(
        self,
        conversation_id: int,
        previous_answer: Optional[str] = None,
    ) -> str:
        """Tạo câu hỏi tiếp theo dựa trên câu trả lời trước và optionally Company Research"""
        conversation = await self.get_conversation_by_id(conversation_id)
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")

        # Lấy lịch sử cuộc trò chuyện
        messages = await self.get_conversation_messages(conversation_id)
        
        # Build conversation history
        history = "\n".join([f"{msg.role.upper()}: {msg.content}" for msg in messages[-10:]])  # Last 10 messages

        company_research_section = self._build_company_research_section(conversation)
        interviewer_count = sum(1 for msg in messages if msg.role == MessageRole.INTERVIEWER.value)
        next_question_number = interviewer_count + 1
        balanced_focus = self._build_turn_based_focus(conversation, question_number=next_question_number)

        prompt = f"""
Bạn là một người phỏng vấn AI chuyên nghiệp. Dựa trên Job Description, CV{', Company Research' if company_research_section else ''}, và lịch sử cuộc trò chuyện, hãy tạo câu hỏi phỏng vấn tiếp theo.

Job Description:
{conversation.job_description}

CV Profile:
{conversation.cv_profile}
{company_research_section}
Lịch sử cuộc trò chuyện:
{history}

Dựa trên câu trả lời trước đó của ứng viên, hãy tạo một câu hỏi tiếp theo để:
- Đi sâu vào các chi tiết của câu trả lời trước
- Hoặc đánh giá một kỹ năng khác từ job description
- Hoặc kiểm tra hiểu biết của ứng viên về công ty đang làm gì, kinh doanh gì, đang bán gì, sản phẩm / dịch vụ / domain / văn hóa nếu có Company Research
- Hoặc kiểm tra tính nhất quán của ứng viên

Nếu có Company Research, ưu tiên ít nhất một câu hỏi trong phiên phỏng vấn có liên quan trực tiếp đến công ty hoặc bối cảnh kinh doanh, đặc biệt là công ty làm gì và bán gì.
{balanced_focus}

Câu hỏi nên tự nhiên, chuyên nghiệp, và có thể được trả lời trong khoảng 1-3 phút.

Chỉ trả lời câu hỏi, không thêm bất kỳ lời giải thích nào khác.
"""
        try:
            question = self._generate_question_with_company_guardrail(
                conversation=conversation,
                prompt=prompt,
                initial=False,
                company_research_section=company_research_section,
                question_number=next_question_number,
                history=history,
                previous_answer=previous_answer,
                balanced_focus=balanced_focus,
            )
            return question
        except Exception as e:
            logger.error(f"Error generating next question: {str(e)}")
            raise

    async def evaluate_answer(self, conversation_id: int) -> dict:
        """Đánh giá câu trả lời và tạo kết quả"""
        conversation = await self.get_conversation_by_id(conversation_id)
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")

        # Lấy tất cả messages
        messages = await self.get_conversation_messages(conversation_id)

        # Build evaluation prompt
        messages_text = "\n".join([f"{msg.role.upper()}: {msg.content}" for msg in messages])

        company_research_section = self._build_company_research_section(conversation)

        prompt = f"""
Bạn là một người phỏng vấn AI chuyên nghiệp. Hãy đánh giá cuộc phỏng vấn dựa trên Job Description, CV{', Company Research' if company_research_section else ''}, và lịch sử cuộc trò chuyện.

Job Description:
{conversation.job_description}

CV Profile:
{conversation.cv_profile}
{company_research_section}
Lịch sử cuộc trò chuyện:
{messages_text}

Nếu có Company Research, hãy đánh giá thêm mức độ ứng viên thể hiện hiểu biết về công ty, sản phẩm, domain, văn hóa hoặc bối cảnh kinh doanh.

Vui lòng đánh giá:
1. Điểm mạnh của ứng viên
2. Điểm yếu của ứng viên
3. Mức độ phù hợp với công việc (0-100)
4. Đề xuất quyết định cuối cùng (PASS/FAIL/MAYBE)

Trả lời dưới định dạng JSON:
{{
    "strengths": ["..."],
    "weaknesses": ["..."],
    "fit_score": <0-100>,
    "recommendation": "PASS|FAIL|MAYBE",
    "comments": "..."
}}
"""
        try:
            result_text = generate_content(
                prompt=prompt,
                step="evaluate_answer",
                config=GeminiConfig(model="models/gemini-2.5-flash", temperature=0.0),
            )
            
            # Parse JSON result
            import re
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return result
            else:
                return {"error": "Could not parse evaluation result"}
        except Exception as e:
            logger.error(f"Error evaluating answer: {str(e)}")
            raise

    async def generate_analysis_report_payload(self, conversation_id: int) -> tuple[AnalysisReportPayload, str]:
        """Gọi AI tạo payload báo cáo phân tích và validate bằng Pydantic"""
        conversation = await self.get_conversation_by_id(conversation_id)
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")

        messages = await self.get_conversation_messages(conversation_id)
        messages_text = "\n".join(
            f"{idx}. {msg.role.upper()}: {msg.content}"
            for idx, msg in enumerate(messages, start=1)
        )

        prompt = self._build_analysis_report_prompt(
            conversation=conversation,
            messages_text=messages_text,
        )

        result_text = generate_content(
            prompt=prompt,
            step="generate_analysis_report",
        )
        payload_dict = self._extract_json_object(result_text)
        payload = AnalysisReportPayload.model_validate(payload_dict)
        self._apply_analysis_report_business_rules(
            payload=payload,
            messages=messages,
            company_name=conversation.company_name,
        )
        return payload, result_text

    def _apply_analysis_report_business_rules(
        self,
        *,
        payload: AnalysisReportPayload,
        messages: list[ConversationMessage],
        company_name: str | None,
    ) -> None:
        return

    def _calculate_overall_score(self, payload: AnalysisReportPayload) -> int:
        scores = [
            payload.scores.technical.score,
            payload.scores.communication.score,
            payload.scores.confidence.score,
            payload.scores.soft_skills.score,
            payload.scores.company_knowledge.score,
        ]
        return round(sum(scores) / len(scores))

    def _grade_from_score(self, score: int) -> str:
        if score >= 90:
            return "A"
        if score >= 80:
            return "B+"
        if score >= 70:
            return "B"
        if score >= 60:
            return "C+"
        if score >= 50:
            return "C"
        return "D"

    def _level_from_score(self, score: int) -> str:
        if score >= 80:
            return "Tốt"
        if score >= 65:
            return "Khá"
        if score >= 50:
            return "Cần cải thiện"
        return "Yếu"

    def _build_analysis_report_prompt(
        self,
        *,
        conversation: Conversation,
        messages_text: str,
    ) -> str:
        company_research_section = self._build_company_research_section(conversation)
        
        return f"""
Bạn là AI Interview Evaluator cho hệ thống InterviewAI.

Hãy phân tích kết quả phỏng vấn dựa DUY NHẤT trên dữ liệu được cung cấp:
- Job description
- CV profile
- Company Research (nếu có)
- Lịch sử câu hỏi và câu trả lời

Không bịa thêm dữ kiện. Nếu thiếu dữ liệu để đánh giá tiêu chí nào, vẫn cho điểm nhưng phải ghi rõ trong evidence.
Riêng company_knowledge: hãy chấm theo mức độ ứng viên hiểu công ty/sản phẩm/domain/văn hóa/bối cảnh kinh doanh dựa trên dữ liệu phỏng vấn và Company Research nếu có.

Quy ước điểm:
- Tất cả score là số nguyên từ 0 đến 100.
- technical: độ đúng, độ sâu và tính thực tế của kiến thức/kỹ năng chuyên môn so với JD.
- communication: cách trình bày, độ rõ ràng, có cấu trúc, đúng trọng tâm.
- confidence: độ tự tin thể hiện qua câu chữ, gồm trả lời dứt khoát, có ví dụ cụ thể, ít né tránh, ít ngôn ngữ mơ hồ. Không đánh giá giọng nói/khuôn mặt.
- soft_skills: tư duy hợp tác, xử lý xung đột, ownership, chủ động, problem-solving.
- company_knowledge: mức độ hiểu công ty, sản phẩm, domain, yêu cầu vị trí và sự phù hợp văn hóa.

Quy ước overall_grade:
- 90-100: A
- 80-89: B+
- 70-79: B
- 60-69: C+
- 50-59: C
- 0-49: D

Yêu cầu output:
- Chỉ trả về JSON hợp lệ.
- Không trả markdown.
- Không thêm text ngoài JSON.
- Dùng đúng key và kiểu dữ liệu trong schema bên dưới.
- impact chỉ được là "low", "medium" hoặc "high".
- ai_coach_insights.type chỉ được là "positive", "warning" hoặc "improvement".

Schema JSON bắt buộc:
{{
  "overall_score": 78,
  "overall_grade": "B+",
  "level": "Tốt",
  "summary": "Tóm tắt đánh giá ngắn gọn bằng tiếng Việt.",
  "tags": ["Kỹ thuật tốt", "Cần cải thiện kiến thức công ty"],
  "scores": {{
    "technical": {{"score": 0, "evidence": "Bằng chứng cụ thể từ câu trả lời."}},
    "communication": {{"score": 0, "evidence": "Bằng chứng cụ thể từ câu trả lời."}},
    "confidence": {{"score": 0, "evidence": "Bằng chứng cụ thể từ câu trả lời dạng text."}},
    "soft_skills": {{"score": 0, "evidence": "Bằng chứng cụ thể từ câu trả lời."}},
    "company_knowledge": {{"score": 0, "evidence": "Bằng chứng cụ thể từ câu trả lời."}}
  }},
  "ai_coach_insights": [
    {{"type": "positive", "title": "Tiêu đề ngắn", "description": "Mô tả ngắn."}}
  ],
  "strengths": ["Điểm mạnh cụ thể"],
  "weaknesses": ["Điểm yếu cụ thể"],
  "knowledge_gaps": [
    {{
      "title": "Tên lỗ hổng",
      "impact": "high",
      "evidence": "Bằng chứng từ câu trả lời.",
      "recommendation": "Khuyến nghị ôn tập cụ thể."
    }}
  ],
  "study_plan": [
    {{
      "priority": 1,
      "topic": "Chủ đề cần ôn",
      "reason": "Lý do nên ôn chủ đề này.",
      "actions": ["Hành động cụ thể 1", "Hành động cụ thể 2"]
    }}
  ]
}}

Thông tin phiên phỏng vấn:
Vị trí: {conversation.job_position}
Công ty: {conversation.company_name or "Không rõ"}

Job Description:
{conversation.job_description}

CV Profile:
{conversation.cv_profile}
{company_research_section}
Lịch sử phỏng vấn:
{messages_text or "Chưa có câu hỏi/câu trả lời nào."}
"""

    def _extract_json_object(self, text: str) -> dict:
        """Trích JSON object từ output AI"""
        if not text:
            raise ValueError("AI returned empty analysis report")

        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        import re

        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if not json_match:
            raise ValueError("Could not parse analysis report JSON")

        parsed = json.loads(json_match.group())
        if not isinstance(parsed, dict):
            raise ValueError("Analysis report JSON must be an object")
        return parsed
