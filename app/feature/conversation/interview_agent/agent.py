# -*- coding: utf-8 -*-
import json
import logging
import re
from typing import TYPE_CHECKING, Optional

from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.messages import HumanMessage, AIMessage
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from app.feature.conversation.interview_agent.llm import GeminiLangChainLLM
from app.feature.conversation.interview_agent.memory import get_memory
from app.feature.conversation.interview_agent.tools import (
    ContextRetrieverTool,
    QuestionTrackerTool,
    FlowManagerTool,
)

logger = logging.getLogger(__name__)


class InterviewQuestionOutput(BaseModel):
    question: str = Field(description="Câu hỏi phỏng vấn")
    topic: str = Field(description="Chủ đề của câu hỏi")
    follow_up: Optional[str] = Field(None, description="Gợi ý follow-up")


class InterviewEvaluationOutput(BaseModel):
    fit_score: float = Field(description="Điểm phù hợp (0-100)")
    strengths: list[str] = Field(description="Điểm mạnh")
    weaknesses: list[str] = Field(description="Điểm yếu")
    recommendation: str = Field(description="PASS|FAIL|MAYBE")
    comments: str = Field(description="Nhận xét tổng quan")


class InterviewAgent:
    def __init__(self):
        self._question_llm = GeminiLangChainLLM(temperature=0.7)
        self._eval_llm = GeminiLangChainLLM(temperature=0.0)
        self._question_parser = PydanticOutputParser(pydantic_object=InterviewQuestionOutput)
        self._eval_parser = PydanticOutputParser(pydantic_object=InterviewEvaluationOutput)

        self._question_prompt = PromptTemplate.from_template(
            "{system_prompt}\n\n"
            "[JOB_DESCRIPTION]\n{jd_text}\n\n"
            "[CV_PROFILE]\n{cv_text}\n\n"
            "[CONVERSATION_HISTORY]\n{chat_history}\n\n"
            "{format_instructions}\n\n"
            "Đặt câu hỏi tiếp theo dựa trên thông tin trên."
        )

        self._eval_prompt = PromptTemplate.from_template(
            "{system_prompt}\n\n"
            "[JOB_DESCRIPTION]\n{jd_text}\n\n"
            "[CV_PROFILE]\n{cv_text}\n\n"
            "[CONVERSATION_HISTORY]\n{chat_history}\n\n"
            "{format_instructions}"
        )

    def _get_tools(self, jd_text: str, cv_text: str, conversation_id: int, db: "AsyncSession" = None):
        return {
            "context": ContextRetrieverTool(jd_text=jd_text, cv_text=cv_text),
            "tracker": QuestionTrackerTool(conversation_id=conversation_id, jd_text=jd_text, db=db),
            "flow": FlowManagerTool(conversation_id=conversation_id, db=db),
        }

    async def generate_question(
        self,
        job_description: str,
        cv_profile: str,
        conversation_id: int,
        db: "AsyncSession",
        analysis_result: Optional[dict] = None,
        previous_answer: Optional[str] = None,
    ) -> str:
        memory = await get_memory(conversation_id, db=db)

        if previous_answer:
            last_human = next(
                (m for m in reversed(memory.get_history_messages()) if isinstance(m, HumanMessage)),
                None,
            )
            if last_human:
                memory.save_context(last_human.content, previous_answer)

        chat_history = memory.get_history()

        tools = self._get_tools(job_description, cv_profile, conversation_id, db=db)
        flow_status = await tools["flow"]._run_async("get_phase")
        tracker_status = await tools["tracker"]._run_async("get_topics")

        analysis_context = ""
        if analysis_result:
            missing_skills = analysis_result.get("missing_skills", [])
            main_strengths = analysis_result.get("main_strengths", [])
            overall_score = analysis_result.get("overall_score", 0)

            missing_skills_text = ""
            if missing_skills:
                skill_names = [s.get("skill", s) if isinstance(s, dict) else str(s) for s in missing_skills[:10]]
                missing_skills_text = ", ".join(skill_names)

            strengths_text = ""
            if main_strengths:
                strength_names = [s.get("title", s) if isinstance(s, dict) else str(s) for s in main_strengths[:5]]
                strengths_text = ", ".join(strength_names)

            if missing_skills_text or strengths_text:
                analysis_context = f"""
[PHÂN TÍCH CV TRƯỚC PHỎNG VẤN]
- Điểm phù hợp CV-JD: {overall_score}/100
- Điểm mạnh của ứng viên: {strengths_text or "Chưa có thông tin"}
- Kỹ năng còn thiếu cần kiểm tra: {missing_skills_text or "Chưa có thông tin"}
"""
        context_hint = ""
        if job_description[:200]:
            context_hint = f"\n\n[CONTEXT HINT]\nJD đang tuyển: {job_description[:200]}..."

        system_prompt = f"""Bạn là người phỏng vấn AI chuyên nghiệp. Đặt câu hỏi phỏng vấn tiếp theo.

NGUYÊN TẮC:
1. Mỗi câu hỏi phải ngắn gọn (1-2 câu), rõ ràng, mở để ứng viên thể hiện kinh nghiệm
2. Không đưa ra đáp án hoặc gợi ý trong câu hỏi
3. Điều chỉnh theo profile của ứng viên
4. Theo dõi các topic đã hỏi
5. Ưu tiên hỏi về các kỹ năng còn thiếu được xác định từ phân tích CV

{flow_status}

{tracker_status}
{analysis_context}
{context_hint}
"""

        try:
            prompt = self._question_prompt.format(
                system_prompt=system_prompt,
                jd_text=job_description[:2000],
                cv_text=cv_profile[:2000],
                chat_history=chat_history or "(Chưa có lịch sử - đây là câu hỏi đầu tiên)",
                format_instructions=self._question_parser.get_format_instructions(),
            )

            raw = await self._question_llm.ainvoke(prompt)
            parsed = self._question_parser.parse(raw)

            await tools["tracker"]._run_async("mark_asked", topic=parsed.topic, question=parsed.question)
            await tools["flow"]._run_async("decide_next_phase")

            question_text = parsed.question
            if parsed.follow_up:
                question_text += f"\n\n{parsed.follow_up}"

            logger.info(f"[InterviewAgent] Generated question: topic={parsed.topic}, conv={conversation_id}")
            return question_text

        except Exception as e:
            logger.warning(f"[InterviewAgent] Parse failed, using fallback: {e}")
            return self._fallback_question(job_description, cv_profile, chat_history, previous_answer)

    def _fallback_question(
        self,
        jd_text: str,
        cv_text: str,
        chat_history: str,
        previous_answer: Optional[str],
    ) -> str:
        from app.feature.feature_up_cv.core.gemini_client import generate_content

        extra = f"Câu trả lời trước: {previous_answer}" if previous_answer else ""
        prompt = (
            "Bạn là người phỏng vấn AI. Đặt câu hỏi phỏng vấn tiếp theo (chỉ 1 câu hỏi, ngắn gọn).\n\n"
            f"JD: {jd_text[:1500]}\nCV: {cv_text[:1500]}\n\nLịch sử:\n{chat_history or '(chưa có)'}\n\n"
            f"{extra}\n\nChỉ trả lời câu hỏi, không thêm giải thích."
        )
        return generate_content(prompt=prompt, step="interview_fallback").strip()

    async def evaluate_interview(
        self,
        job_description: str,
        cv_profile: str,
        conversation_id: int,
        db: "AsyncSession",
        analysis_result: Optional[dict] = None,
    ) -> dict:
        memory = await get_memory(conversation_id, db=db)
        chat_history = memory.get_history()

        cv_analysis_context = ""
        if analysis_result:
            overall_score = analysis_result.get("overall_score", 0)
            missing_skills = analysis_result.get("missing_skills", [])
            main_strengths = analysis_result.get("main_strengths", [])

            missing_text = ", ".join([
                s.get("skill", s) if isinstance(s, dict) else str(s)
                for s in missing_skills[:10]
            ]) if missing_skills else "Không có"

            strengths_text = ", ".join([
                s.get("title", s) if isinstance(s, dict) else str(s)
                for s in main_strengths[:5]
            ]) if main_strengths else "Không có"

            cv_analysis_context = f"""
[PHÂN TÍCH CV TRƯỚC PHỎNG VẤN]
- Điểm CV-JD trước interview: {overall_score}/100
- Kỹ năng còn thiếu: {missing_text}
- Điểm mạnh: {strengths_text}
"""

        system_prompt = f"""Bạn là chuyên gia HR đánh giá phỏng vấn. Dựa trên toàn bộ cuộc trò chuyện, hãy đánh giá tổng thể ứng viên.
{cv_analysis_context}
LƯU Ý: So sánh hiệu suất phỏng vấn với kết quả phân tích CV ban đầu để đưa ra đánh giá chính xác hơn."""

        try:
            prompt = self._eval_prompt.format(
                system_prompt=system_prompt,
                jd_text=job_description[:3000],
                cv_text=cv_profile[:3000],
                chat_history=chat_history or "(Không có lịch sử)",
                format_instructions=self._eval_parser.get_format_instructions(),
            )

            raw = await self._eval_llm.ainvoke(prompt)
            parsed = self._eval_parser.parse(raw)

            result = {
                "fit_score": parsed.fit_score,
                "strengths": parsed.strengths,
                "weaknesses": parsed.weaknesses,
                "recommendation": parsed.recommendation,
                "comments": parsed.comments,
            }
        except Exception as e:
            logger.warning(f"[InterviewAgent] Evaluation parse failed: {e}")

            try:
                raw = await self._eval_llm.ainvoke(prompt)
                json_match = re.search(r"\{.*\}", raw, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                else:
                    raise ValueError("No JSON found")
            except Exception:
                result = {
                    "fit_score": 50,
                    "strengths": [],
                    "weaknesses": [f"Lỗi đánh giá: {str(e)}"],
                    "recommendation": "MAYBE",
                    "comments": "Đánh giá thất bại - cần review thủ công",
                }

        logger.info(f"[InterviewAgent] Evaluation complete: score={result['fit_score']}, conv={conversation_id}")
        return result


interview_agent = InterviewAgent()
