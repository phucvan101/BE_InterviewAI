"""
Prompts and Pydantic schemas for the Feedback Agent.

The agent takes a user's natural-language complaint about a CV-JD match
score and decides whether the complaint has merit. If yes, it proposes
concrete remediation actions:

  - new_synonyms        : skill groups the existing synonym dict missed
  - learned_rule        : a generalisation written for the rules engine
  - proposed_overrides  : exact section-by-section score corrections

The schema below is what the LLM is asked to produce. The keys for
``proposed_overrides`` are tightly constrained to the 5 sections the
hybrid scoring engine understands, with explicit max caps.
"""
from typing import Any, ClassVar, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ── Pydantic output schema (what the LLM must produce) ─────────────────────
class FeedbackEvaluation(BaseModel):
    is_valid_complaint: bool = Field(
        description=(
            "True nếu khiếu nại của ứng viên có cơ sở thực tế trong CV và "
            "hợp lý, False nếu không."
        )
    )
    rationale: str = Field(
        description=(
            "Lý do chi tiết chấp nhận hoặc bác bỏ khiếu nại, giải thích "
            "lịch sự, chuyên nghiệp để gửi lại cho ứng viên."
        )
    )
    learned_rule: Optional[str] = Field(
        None,
        description=(
            "Quy tắc/bài học logic tổng quát rút ra từ phản hồi (ví dụ: "
            "'Next.js có thể tính tương đương Express.js', 'Kinh nghiệm "
            "e-commerce tương đương retail'). Để trống nếu không hợp lệ."
        ),
    )
    new_synonyms: Optional[List[Dict[str, str]]] = Field(
        None,
        description=(
            "Danh sách các cặp từ đồng nghĩa mới được phát hiện. Mỗi item "
            "là một dict có key base_skill và synonym (ví dụ: "
            "[{'base_skill': 'express.js', 'synonym': 'nest.js'}]). "
            "Để trống nếu không có."
        ),
    )
    proposed_overrides: Optional[Dict[str, float]] = Field(
        None,
        description=(
            "Đề xuất điểm ghi đè TUYỆT ĐỐI mới cho các phần bị chấm sai (nếu "
            "khiếu nại hợp lý). Chỉ được dùng các key: 'experience_score' (max "
            "50), 'skills_score' (max 30), 'education_score' (max 10), "
            "'career_objectives_score' (max 10), 'company_fit_score' (max "
            "10). Chỉ đề xuất tăng điểm ở phần bị chấm sai dựa trên "
            "bằng chứng thực tế. Dùng field này KHI agent biết chính xác điểm "
            "tuyệt đối cần đạt."
        ),
    )
    proposed_adjustments: Optional[Dict[str, float]] = Field(
        None,
        description=(
            "Đề xuất điều chỉnh DẠNG DELTA (cộng/trừ) cho từng section. Ví "
            "dụ {'skills_score': 5.0, 'experience_score': 3.0} nghĩa là CỘNG "
            "5đ vào skills hiện tại, 3đ vào experience hiện tại. Ưu tiên "
            "dùng field này thay vì proposed_overrides khi không chắc "
            "chắn điểm tuyệt đối — delta an toàn hơn và tự cộng dồn với "
            "các lần phản hồi sau. Mỗi giá trị sẽ bị CLAMP về khoảng "
            "[-10, +10] để tránh LLM đề xuất cộng quá đà. Nếu cả "
            "proposed_overrides và proposed_adjustments đều có, "
            "proposed_adjustments được ưu tiên."
        ),
    )
    proposed_new_rule_type: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "Phase 7: đề xuất một RULE TYPE MỚI hoàn toàn (Hướng 3 + "
            "human-in-the-loop). Format: "
            "{rule_type, description, condition, action, priority, confidence}. "
            "Rule này sẽ KHÔNG tự động apply mà được đưa vào hàng chờ "
            "pending_rules để operator review trước khi active."
        ),
    )
    new_patterns: Optional[List[Dict[str, Any]]] = Field(
        None,
        description=(
            "Danh sách pattern mới phát hiện. Mỗi item là dict có key 'type' "
            "='compound_skill' | 'context_phrase' kèm các field tương ứng "
            "(xem pattern_manager). Để trống nếu không có."
        ),
    )
    threshold_adjustments: Optional[Dict[str, Dict[str, Any]]] = Field(
        None,
        description=(
            "Đề xuất điều chỉnh perfect_match / relevant_match threshold "
            "cho từng category. Ví dụ: "
            "{'technical_skill': {'perfect_match': 0.75, 'relevant_match': 0.50, "
            "'note': 'Vietnamese natural language'}}. "
            "Category hợp lệ: default, technical_skill, tool, skill, "
            "soft_skill, culture, language, responsibility, experience. "
            "Mỗi inner dict có thể chứa 'perfect_match' (float), "
            "'relevant_match' (float) và 'note' (str). "
            "Để trống nếu threshold hiện tại đã phù hợp."
        ),
    )

    # ── Constraints ───────────────────────────────────────────────────────
    ALLOWED_SECTIONS: ClassVar[Dict[str, float]] = {
        "experience_score": 50.0,
        "skills_score": 30.0,
        "education_score": 10.0,
        "career_objectives_score": 10.0,
        "company_fit_score": 10.0,
    }

    @field_validator("proposed_overrides")
    @classmethod
    def _clamp_overrides(cls, v: Optional[Dict[str, float]]) -> Optional[Dict[str, float]]:
        if v is None:
            return v
        clean: Dict[str, float] = {}
        for key, value in v.items():
            if key not in cls.ALLOWED_SECTIONS:
                # Silently drop unknown keys so the LLM can experiment
                # without breaking the parser.
                continue
            try:
                num = float(value)
            except (TypeError, ValueError):
                continue
            cap = cls.ALLOWED_SECTIONS[key]
            clean[key] = max(0.0, min(num, cap))
        return clean or None

    @field_validator("proposed_adjustments")
    @classmethod
    def _clamp_adjustments(cls, v: Optional[Dict[str, float]]) -> Optional[Dict[str, float]]:
        """Clamp each delta into a sane [-10, +10] range."""
        if v is None:
            return v
        clean: Dict[str, float] = {}
        for key, value in v.items():
            if key not in cls.ALLOWED_SECTIONS:
                continue
            try:
                num = float(value)
            except (TypeError, ValueError):
                continue
            clean[key] = max(-10.0, min(num, 10.0))
        return clean or None


# ── System prompt ─────────────────────────────────────────────────────────
SYSTEM_PROMPT_EVALUATOR = """
Bạn là một AI Agent chuyên phân tích khiếu nại của ứng viên về điểm số CV so với Job Description (JD).
Nhiệm vụ chính: Xác định xem phản hồi của ứng viên CÓ CƠ SỞ hay không dựa trên nội dung có sẵn trong CV (không tự bịa thêm thông tin).

⚠️ BẮT BUỘC TRẢ VỀ JSON HỢP LỆ THEO ĐÚNG SCHEMA SAU (không thêm field khác, không bỏ field):
{
  "is_valid_complaint": true | false,
  "rationale": "Lý do chi tiết bằng tiếng Việt (50-200 từ)",
  "learned_rule": "Quy tắc tổng quát rút ra (string) hoặc null nếu không có",
  "new_synonyms": [{"base_skill": "x", "synonym": "y"}] hoặc null,
  "proposed_overrides": {"experience_score": <0-50>, "skills_score": <0-30>, "education_score": <0-10>, "career_objectives_score": <0-10>, "company_fit_score": <0-10>} hoặc null,
  "proposed_adjustments": {"experience_score": <-10..10>, "skills_score": <-10..10>, ...} hoặc null,
  "proposed_new_rule_type": null,
  "new_patterns": [{"type": "compound_skill"|"context_phrase", ...}] hoặc null,
  "threshold_adjustments": {"technical_skill": {"perfect_match": 0.0-1.0, "relevant_match": 0.0-1.0, "note": "..."}} hoặc null
}

KEY 'is_valid_complaint' BẮT BUỘC PHẢI CÓ VÀ LÀ boolean (true/false). KHÔNG dùng key khác như 'analysis' hay 'decision'.

Quy trình phân tích:
1. Đọc kĩ đoạn [RAW_CV_TEXT] và [JD_TEXT].
2. Đọc phản hồi của ứng viên trong [USER_FEEDBACK] và so sánh với điểm số hiện tại (nếu có).
3. Nếu khiếu nại có cơ sở:
   - Đúc kết bài học tổng quát để hệ thống ghi nhớ (learned_rule).
   - Trích xuất cặp từ đồng nghĩa nếu phát hiện hệ thống chưa nhận diện được (new_synonyms).
   - Đề xuất tăng điểm thích đáng ở phần bị chấm thiếu sót thông qua (proposed_overrides) hoặc (proposed_adjustments) nếu dùng delta.
   - Phase 3: Nếu kỹ năng cần NHIỀU token cùng lúc mới match (vd React+TypeScript),
     dùng new_patterns với type=compound_skill.
   - Phase 3: Nếu CV mô tả bằng cụm từ tự nhiên (vd "tích hợp cổng thanh toán"),
     dùng new_patterns với type=context_phrase.
   - Phase 3: Nếu threshold perfect/relevant hiện tại sai cho 1 category cụ thể,
     dùng threshold_adjustments (chỉ áp dụng kèm learned_rule tương ứng).
4. Sau khi phân tích, BẮT BUỘC kết thúc bằng khối JSON đúng schema trên (bọc trong ```json ... ``` nếu muốn).

Hãy phân tích và trả về JSON hợp lệ theo schema yêu cầu.
"""


# ── User-prompt template ───────────────────────────────────────────────────
USER_PROMPT_TEMPLATE = """
[RAW_CV_TEXT]
{cv_text}
[/RAW_CV_TEXT]

[JD_TEXT]
{jd_text}
[/JD_TEXT]

[CURRENT_SCORES]
{current_scores}
[/CURRENT_SCORES]

[USER_FEEDBACK]
{feedback_text}
[/USER_FEEDBACK]

Hãy phân tích và trả về JSON hợp lệ theo schema yêu cầu.

Gợi ý áp dụng:
- Nếu khiếu nại về kỹ năng BỊ MISS dù CV có liên quan → dùng new_patterns với
  compound_skill (cần nhiều token cùng lúc) hoặc context_phrase (ánh xạ cụm từ).
- Nếu khiếu nại "threshold quá cao" / "cùng sim mà JD khác match" → dùng
  threshold_adjustments với category phù hợp (technical_skill / soft_skill / ...).
"""


def build_user_prompt(
    cv_text: str,
    jd_text: str,
    feedback_text: str,
    current_scores: Optional[Dict[str, float]] = None,
) -> str:
    """Build the full user-prompt sent to the LLM."""
    if current_scores is None:
        current_scores = {}
    return USER_PROMPT_TEMPLATE.format(
        cv_text=cv_text or "(trống)",
        jd_text=jd_text or "(trống)",
        current_scores=current_scores or "(không có điểm hiện tại)",
        feedback_text=feedback_text or "(trống)",
    )
