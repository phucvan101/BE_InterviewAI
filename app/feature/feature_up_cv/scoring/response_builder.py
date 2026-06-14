# -*- coding: utf-8 -*-
"""
Response Builder — tạo output giàu thông tin cho BE trả về FE.

Thiết kế:
- main_strengths: mảng {type, title, description} — Điểm mạnh nổi bật
- areas_for_improvement: mảng {type, title, description, priority} — Điểm cần cải thiện
- recommendation: {level, summary, summary_detail, action_items, interview_tips}
- experience_detail: {score, level, years, summary, highlights, gaps}
- education_detail: {score, level, major_relevant, certifications, summary}
- career_objectives_detail: {score, summary, alignment}
- company_fit_detail: {score, tech_match, domain_fit, culture_fit, engineering}
"""


import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Strength Type Tags ─────────────────────────────────────────────────────────────
STRENGTH_EXP_FULL = "experience_full"
STRENGTH_EXP_PARTIAL = "experience_partial"
STRENGTH_EXP_PROJECT = "experience_project"
STRENGTH_SKILL_STRONG = "skills_strong"
STRENGTH_SKILL_PARTIAL = "skills_partial"
STRENGTH_EDU_MATCH = "education_match"
STRENGTH_EDU_STUDENT = "education_student"
STRENGTH_CERT = "certifications"
STRENGTH_CAREER_CLEAR = "career_clear"
STRENGTH_COMPANY_FIT = "company_fit"
STRENGTH_SKILL_OVERLAP = "skill_overlap"

# ── Area Type Tags ─────────────────────────────────────────────────────────────
AREA_EXP_GAP = "experience_gap"
AREA_EXP_DOMAIN = "experience_domain"
AREA_EXP_SENIORITY = "experience_seniority"
AREA_SKILL_MISSING = "skills_missing"
AREA_SKILL_COVERAGE = "skills_coverage"
AREA_DOMAIN_MISMATCH = "domain_mismatch"
AREA_EDU_LEVEL = "education_level"
AREA_EDU_MAJOR = "education_major"
AREA_CAREER_VAGUE = "career_vague"
AREA_CAREER_OVERQUALIFIED = "career_overqualified"


@dataclass
class StrengthItem:
    type: str
    title: str
    description: str
    score_impact: Optional[float] = None  # điểm ảnh hưởng (nếu biết)
    icon: Optional[str] = None


@dataclass
class AreaItem:
    type: str
    title: str
    description: str
    priority: str = "medium"  # high / medium / low
    suggestions: List[str] = field(default_factory=list)


@dataclass
class RecommendationItem:
    level: str  # very_high / high / medium / low / very_low
    summary: str  # 1 câu tổng kết
    summary_detail: str  # vài câu giải thích
    action_items: List[str] = field(default_factory=list)
    interview_tips: List[str] = field(default_factory=list)
    score_range: str = ""  # e.g. "75-85"


# ── Build Main Strengths ─────────────────────────────────────────────────────────────
def build_main_strengths(
    exp_score: float,
    skills_score: float,
    edu_score: float,
    career_obj_score: float,
    company_score: float,
    exp_features: dict,
    skills_breakdown: dict,
    criteria_match_results: list,
    cv_domain: str,
    jd_domain: str,
) -> List[StrengthItem]:
    """
    Xây dựng danh sách Điểm mạnh dựa trên kết quả chấm điểm chi tiết.
    """
    strengths: List[StrengthItem] = []

    # ── Experience ───────────────────────────────────────────────
    max_exp = 50.0
    exp_ratio = exp_score / max_exp
    exp_years = exp_features.get("all_exp_years", 0.0) if exp_features else 0.0
    years_req = exp_features.get("years_req", 0.0) if exp_features else 0.0

    if exp_score >= 40:
        years_text = f"{exp_years:.1f} năm" if exp_years > 0 else ""
        req_text = f"yêu cầu {years_req:.0f} năm" if years_req > 0 else ""
        strengths.append(StrengthItem(
            type=STRENGTH_EXP_FULL,
            title="Kinh nghiệm phong phú, đáp ứng yêu cầu",
            description=(
                f"Ứng viên có {years_text} kinh nghiệm, vượt mức yêu cầu. "
                f"Kinh nghiệm thực tế phù hợp với JD, thể hiện năng lực vượt trội."
            ) if years_text else "Kinh nghiệm đáp ứng tốt yêu cầu vị trí.",
            score_impact=exp_score,
            icon="experience",
        ))
    elif exp_score >= 30:
        strengths.append(StrengthItem(
            type=STRENGTH_EXP_PARTIAL,
            title="Có nền tảng kinh nghiệm tốt",
            description=(
                f"Ứng viên có {exp_years:.1f} năm kinh nghiệm thực tế "
                f"và đáp ứng được phần lớn yêu cầu về kinh nghiệm của vị trí."
            ) if exp_years > 0 else "Ứng viên có nền tảng kinh nghiệm đáp ứng yêu cầu.",
            score_impact=exp_score,
            icon="experience",
        ))
    elif exp_score >= 20 and exp_years > 0:
        strengths.append(StrengthItem(
            type=STRENGTH_EXP_PROJECT,
            title="Có kinh nghiệm dự án cá nhân/freelance",
            description=(
                f"Ứng viên có {exp_years:.1f} năm kinh nghiệm, phù hợp với vị trí "
                f"entry-level hoặc Fresher. Đây là điểm khởi đầu tốt."
            ),
            score_impact=exp_score,
            icon="experience",
        ))

    # ── Skills ─────────────────────────────────────────────────
    max_skills = 30.0
    skill_ratio = skills_score / max_skills
    critical_matched = skills_breakdown.get("critical_matched", 0)
    critical_total = skills_breakdown.get("critical_total", 0)
    perfect_score = skills_breakdown.get("perfect_score", 0.0)
    relevant_score = skills_breakdown.get("relevant_score", 0.0)
    criteria_count = skills_breakdown.get("criteria_count", 0)

    if skills_score >= 22:
        crit_text = f"{critical_matched}/{critical_total} kỹ năng bắt buộc" if critical_total > 0 else ""
        strengths.append(StrengthItem(
            type=STRENGTH_SKILL_STRONG,
            title="Kỹ năng kỹ thuật mạnh, đáp ứng tốt JD",
            description=(
                f"Ứng viên đáp ứng được {skill_ratio:.0%} yêu cầu kỹ năng "
                f"({perfect_score:.0f}đ perfect + {relevant_score:.0f}đ relevant). "
                f"{crit_text}."
            ) if criteria_count > 0 else "Kỹ năng kỹ thuật của ứng viên đáp ứng tốt yêu cầu.",
            score_impact=skills_score,
            icon="skills",
        ))
    elif skills_score >= 15:
        matched_count = sum(
            1 for r in criteria_match_results
            if r.get("match_status") in ("PERFECT_MATCH", "RELEVANT_MATCH")
        ) if criteria_match_results else 0

    # ── Education ──────────────────────────────────────────────
    if edu_score >= 8:
        strengths.append(StrengthItem(
            type=STRENGTH_EDU_MATCH,
            title="Trình độ học vấn phù hợp và đúng ngành",
            description="Ứng viên có bằng cấp đúng ngành, đáp ứng yêu cầu học vấn của vị trí.",
            score_impact=edu_score,
            icon="education",
        ))
    elif edu_score >= 6:
        strengths.append(StrengthItem(
            type=STRENGTH_EDU_MATCH,
            title="Trình độ học vấn cơ bản đáp ứng yêu cầu",
            description="Trình độ học vấn phù hợp với vị trí tuyển dụng.",
            score_impact=edu_score,
            icon="education",
        ))

    # Certifications bonus
    cert_count = exp_features.get("cert_count", 0) if exp_features else 0
    if cert_count >= 3:
        strengths.append(StrengthItem(
            type=STRENGTH_CERT,
            title=f"Sở hữu {cert_count} chứng chỉ chuyên môn",
            description=(
                f"Ứng viên có {cert_count} chứng chỉ liên quan đến lĩnh vực — "
                f"thể hiện tinh thần tự học và nâng cao năng lực chuyên môn."
            ),
            icon="certification",
        ))

    # ── Career Objectives ───────────────────────────────────────
    if career_obj_score >= 8:
        strengths.append(StrengthItem(
            type=STRENGTH_CAREER_CLEAR,
            title="Mục tiêu nghề nghiệp rõ ràng, phù hợp JD",
            description=(
                "Ứng viên có định hướng rõ ràng, mục tiêu nghề nghiệp "
                "hoàn toàn phù hợp với JD. Đây là dấu hiệu tích cực về sự cam kết."
            ),
            score_impact=career_obj_score,
            icon="career",
        ))
    elif career_obj_score >= 5:
        strengths.append(StrengthItem(
            type=STRENGTH_CAREER_CLEAR,
            title="Mục tiêu nghề nghiệp có liên quan đến JD",
            description="Mục tiêu nghề nghiệp của ứng viên có liên quan đến vị trí tuyển dụng.",
            score_impact=career_obj_score,
            icon="career",
        ))

    # ── Company Fit ─────────────────────────────────────────────
    if company_score >= 8:
        strengths.append(StrengthItem(
            type=STRENGTH_COMPANY_FIT,
            title="Phù hợp văn hóa và kỹ thuật công ty",
            description=(
                f"Ứng viên có điểm phù hợp công ty cao ({company_score:.0f}/10). "
                f"Kỹ năng, ngành nghề và văn hóa làm việc phù hợp với công ty."
            ),
            score_impact=company_score,
            icon="company",
        ))
    elif company_score >= 5:
        strengths.append(StrengthItem(
            type=STRENGTH_COMPANY_FIT,
            title="Có điểm phù hợp với công ty",
            description="Ứng viên có một số điểm phù hợp với công ty, có thể thích ứng tốt.",
            score_impact=company_score,
            icon="company",
        ))

    return strengths


# ── Build Areas for Improvement ───────────────────────────────────────────────────
def build_areas_for_improvement(
    exp_score: float,
    skills_score: float,
    edu_score: float,
    career_obj_score: float,
    exp_features: dict,
    skills_breakdown: dict,
    missing_requirements: list,
    criteria_match_results: list,
    cv_domain: str,
    jd_domain: str,
    domain_penalty: float,
    seniority_gap: int,
    years_req: float,
    all_exp_years: float,
    is_entry_level: bool,
    cv_is_student: bool,
) -> List[AreaItem]:
    """
    Xây dựng danh sách Điểm cần cải thiện với ưu tiên và gợi ý.
    """
    areas: List[AreaItem] = []

    max_exp = 50.0
    max_skills = 30.0
    max_edu = 10.0

    # ── Experience Gap ─────────────────────────────────────────
    exp_ratio = exp_score / max_exp
    if exp_ratio < 0.5 and all_exp_years > 0:
        gap = years_req - all_exp_years if years_req > 0 else 1.0
        if gap > 0.5:
            suggestions = [
                "Tích lũy thêm kinh nghiệm thực tế qua các dự án hoặc công việc part-time",
                "Tham gia các khóa học thực hành để bổ sung kinh nghiệm",
                "Xây dựng portfolio từ các project cá nhân để thể hiện năng lực",
            ]
            areas.append(AreaItem(
                type=AREA_EXP_GAP,
                title="Thiếu kinh nghiệm so với yêu cầu",
                description=(
                    f"Ứng viên có {all_exp_years:.1f} năm kinh nghiệm, "
                    f"thiếu khoảng {gap:.1f} năm so với yêu cầu ({years_req:.0f} năm). "
                    f"Đây là khoảng cách đáng kể cần được bù đắp."
                ),
                priority="high",
                suggestions=suggestions,
            ))
        elif gap > 0:
            areas.append(AreaItem(
                type=AREA_EXP_GAP,
                title="Kinh nghiệm gần đạt yêu cầu",
                description=(
                    f"Thiếu khoảng {gap:.1f} năm kinh nghiệm. "
                    f"Ứng viên cần thêm thời gian để đáp ứng đầy đủ."
                ),
                priority="medium",
                suggestions=[
                    "Tích lũy thêm kinh nghiệm qua dự án thực tế",
                    "Thể hiện kỹ năng tương đương qua các dự án cá nhân",
                ],
            ))

    if all_exp_years == 0 and exp_ratio < 0.3:
        areas.append(AreaItem(
            type=AREA_EXP_GAP,
            title="Chưa có kinh nghiệm làm việc thực tế",
            description=(
                "Ứng viên chưa có kinh nghiệm làm việc chính thức. "
                "Cần đánh giá qua dự án cá nhân, thực tập hoặc các bằng chứng khác."
            ),
            priority="high",
            suggestions=[
                "Ứng viên có thể phù hợp với vị trí Intern/Fresher",
                "Xem xét khả năng qua các dự án và kỹ năng đã học",
            ],
        ))

    # ── Seniority Gap ─────────────────────────────────────────
    if seniority_gap > 0 and not is_entry_level:
        gap_labels = {1: "1 cấp", 2: "2 cấp", 3: "3+ cấp"}
        gap_label = gap_labels.get(seniority_gap, f"{seniority_gap} cấp")
        areas.append(AreaItem(
            type=AREA_EXP_SENIORITY,
            title=f"Chênh lệch cấp độ senior: thiếu {gap_label}",
            description=(
                f"CV thể hiện cấp độ thấp hơn yêu cầu của JD. "
                f"Ứng viên có thể cần thêm thời gian để phát triển lên senior level."
            ),
            priority="high" if seniority_gap >= 2 else "medium",
            suggestions=[
                "Xem xét đào tạo nội bộ để nâng cấp kỹ năng",
                "Giao việc phù hợp với mức hiện tại, tăng dần độ khó",
                "Đánh giá khả năng phát triển của ứng viên trong phỏng vấn",
            ],
        ))

    # ── Domain Mismatch ───────────────────────────────────────
    if domain_penalty >= 0.5:
        domain_label_map = {
            "tech_ai": "AI/Machine Learning",
            "tech_software": "Software Engineering",
            "tech_data": "Data Engineering",
            "tech_devops": "DevOps",
            "tech_security": "Security",
            "sales": "Sales",
            "marketing": "Marketing",
            "finance": "Finance",
            "hr": "Human Resources",
            "operations": "Operations",
            "unknown": "Không xác định",
        }
        cv_label = domain_label_map.get(cv_domain, cv_domain)
        jd_label = domain_label_map.get(jd_domain, jd_domain)
        areas.append(AreaItem(
            type=AREA_DOMAIN_MISMATCH,
            title=f"Lĩnh vực không khớp: {cv_label} ≠ {jd_label}",
            description=(
                f"CV thuộc lĩnh vực '{cv_label}' trong khi JD yêu cầu '{jd_label}'. "
                f"Đây là sự lệch hướng đáng kể, cần đánh giá kỹ trong phỏng vấn."
            ),
            priority="high",
            suggestions=[
                "Xác định kỹ năng chuyển đổi được giữa 2 lĩnh vực",
                "Đánh giá khả năng học hỏi nhanh và thích ứng",
                "Cân nhắc nếu ứng viên có potential vượt bậc",
            ],
        ))

    # ── Skills Missing ─────────────────────────────────────────
    critical_missing = [
        r for r in missing_requirements
        if r.get("importance") == "CRITICAL"
    ]
    important_missing = [
        r for r in missing_requirements
        if r.get("importance") == "IMPORTANT"
    ]

    if critical_missing:
        skill_names = [r["requirement"][:60] for r in critical_missing[:5]]
        areas.append(AreaItem(
            type=AREA_SKILL_MISSING,
            title=f"Thiếu {len(critical_missing)} kỹ năng bắt buộc",
            description=(
                "Ứng viên không có trong CV các kỹ năng bắt buộc: "
                f"{'; '.join(skill_names)}. "
                "Đây là yêu cầu không thể thiếu của vị trí."
            ),
            priority="high",
            suggestions=[
                f"Bạn nên bổ sung: {skill_names[0]}" if skill_names else "",
                "Hãy chuẩn bị sẵn sàng để thảo luận về những gì bạn đã tự học được",
                "Khi được hỏi, hãy thể hiện khả năng tự học nhanh",
            ],
        ))

    if important_missing:
        skill_names = [r["requirement"][:60] for r in important_missing[:5]]
        areas.append(AreaItem(
            type=AREA_SKILL_COVERAGE,
            title=f"Thiếu {len(important_missing)} kỹ năng quan trọng",
            description=(
                "Các kỹ năng quan trọng còn thiếu: "
                f"{'; '.join(skill_names)}. "
                "Việc bổ sung sẽ tăng đáng kể khả năng đáp ứng JD."
            ),
            priority="medium",
            suggestions=[
                "Bạn nên chủ động đề cập những gì bạn đã tự tìm hiểu về lĩnh vực này",
                "Chuẩn bị sẵn sàng để thảo luận về kiến thức liên quan dù chưa có kinh nghiệm chính thức",
            ],
        ))

    # ── Education ──────────────────────────────────────────────
    edu_ratio = edu_score / max_edu
    if edu_ratio < 0.6:
        if not cv_is_student:
            areas.append(AreaItem(
                type=AREA_EDU_LEVEL,
                title="Trình độ học vấn thấp hơn yêu cầu",
                description=(
                    "Trình độ học vấn của ứng viên chưa đáp ứng tốt yêu cầu của JD. "
                    "Cần xem xét nếu có bằng chứng kinh nghiệm bù đắp."
                ),
                priority="medium",
                suggestions=[
                    "Hãy chuẩn bị giải thích rõ ràng về lộ trình học tập và kinh nghiệm tự học của bạn",
                    "Đề cập đến các khóa học online, chứng chỉ hoặc dự án cá nhân để bổ sung",
                ],
            ))

    # ── Career ────────────────────────────────────────────────
    if career_obj_score < 4:
        areas.append(AreaItem(
            type=AREA_CAREER_VAGUE,
            title="Mục tiêu nghề nghiệp chưa rõ ràng hoặc không phù hợp",
            description=(
                "CV không có mục tiêu nghề nghiệp rõ ràng hoặc mục tiêu "
                "không phù hợp với JD. Điều này có thể ảnh hưởng đến cam kết lâu dài."
            ),
            priority="medium",
            suggestions=[
                "Hãy nghiên cứu kỹ JD để hiểu rõ định hướng công ty và nhấn mạnh sự phù hợp",
                "Chuẩn bị câu trả lời về mục tiêu nghề nghiệp ngắn và dài hạn của bạn",
            ],
        ))

    return areas


# ── Build Recommendation ─────────────────────────────────────────────────────────────
def build_recommendation(
    overall: float,
    exp_score: float,
    skills_score: float,
    edu_score: float,
    career_obj_score: float,
    company_score: float,
    domain_penalty: float,
    critical_missing: list,
    areas: List[AreaItem],
) -> RecommendationItem:
    """
    Xây dựng khuyến nghị dành cho ỨNG VIÊN.
    Ngôn ngữ hướng tới việc giúp ứng viên hiểu điểm mạnh/yếu và chuẩn bị phỏng vấn.
    """
    max_exp, max_skills = 50.0, 30.0

    # ── Xác định level ─────────────────────────────────────────────────────────────
    if overall >= 80 and domain_penalty < 0.3:
        level = "very_high"
        score_range = "80-100"
        action_items = [
            "Bạn là ứng viên rất mạnh — hãy tự tin trong phỏng vấn",
            "Chuẩn bị kỹ các dự án đã làm để demo năng lực thực tế",
            "Nghiên cứu kỹ về công ty để thể hiện sự quan tâm nghiêm túc",
        ]
        interview_tips = [
            "Tập trung giải thích rõ ràng quá trình làm việc và kết quả đạt được",
            "Chuẩn bị câu hỏi về team, văn hóa công ty và định hướng phát triển",
            "Sẵn sàng thảo luận về các thách thức kỹ thuật đã vượt qua",
        ]

    elif overall >= 65 and domain_penalty < 0.5:
        level = "high"
        score_range = "65-79"
        action_items = [
            "Chuẩn bị kỹ các kỹ năng đáp ứng được để thể hiện sâu hơn",
            "Nghiên cứu trước những kỹ năng còn thiếu — biết điểm yếu giúp tự tin hơn",
            "Thực hành trả lời câu hỏi về những thiếu sót một cách xây dựng",
        ]
        interview_tips = [
            "Đọc kỹ JD để nhấn mạnh những gì bạn đáp ứng được",
            "Chuẩn bị ví dụ cụ thể từ các dự án cá nhân hoặc học tập",
            "Khi được hỏi về kỹ năng thiếu, hãy thể hiện khả năng tự học và định hướng phát triển",
        ]

    elif overall >= 45:
        level = "medium"
        score_range = "45-64"
        action_items = [
            "Tập trung phát triển những kỹ năng còn thiếu trước khi phỏng vấn",
            "Chuẩn bị thuyết trình về những gì bạn đã làm được — kể cả dự án cá nhân",
            "Nghiên cứu kỹ JD để hiểu rõ kỳ vọng và điều chỉnh tâm thế phù hợp",
        ]
        interview_tips = [
            "Thể hiện thái độ ham học hỏi và quyết tâm phát triển",
            "Chuẩn bị câu chuyện về quá trình tự học hoặc các khóa học đã tham gia",
            "Đánh giá xem văn hóa công ty có phù hợp với bạn không — phỏng vấn là 2 chiều",
        ]

    elif overall >= 25:
        level = "low"
        score_range = "25-44"
        action_items = [
            "Đây có thể chưa phải vị trí phù hợp nhất — cân nhắc tìm kiếm các yêu cầu khác",
            "Nếu vẫn muốn ứng tuyển, hãy tập trung vào tiềm năng phát triển và thái độ",
            "Xem xét để build thêm portfolio trước khi ứng tuyển lại",
        ]
        interview_tips = [
            "Chuẩn bị kỹ về động lực và mục tiêu nghề nghiệp ngắn hạn",
            "Thể hiện sự khiêm nhường và khả năng học hỏi nhanh",
            "Đánh giá thực sự xem bạn có muốn theo đuổi vị trí này không",
        ]

    else:
        level = "very_low"
        score_range = "0-24"
        action_items = [
            "Vị trí này có vẻ chưa phù hợp với profile hiện tại của bạn",
            "Hãy tập trung vào việc xây dựng kỹ năng cốt lõi trước",
            "Thử tìm các vị trí intern/junior phù hợp hơn để tích lũy kinh nghiệm",
        ]
        interview_tips = []

    # ── Summary chi tiết ──────────────────────────────────────────────────────────
    exp_ratio = exp_score / max_exp
    skill_ratio = skills_score / max_skills

    exp_assessment = (
        "Kinh nghiệm: " +
        ("xuất sắc" if exp_ratio >= 0.8 else
         "tốt" if exp_ratio >= 0.6 else
         "trung bình" if exp_ratio >= 0.4 else
         "cần cải thiện")
    )
    skill_assessment = (
        "Kỹ năng: " +
        ("xuất sắc" if skill_ratio >= 0.7 else
         "tốt" if skill_ratio >= 0.5 else
         "trung bình" if skill_ratio >= 0.3 else
         "cần cải thiện")
    )

    summary_detail = (
        f"Tổng điểm của bạn: {overall}/100 ({exp_assessment}, {skill_assessment}). "
    )

    if domain_penalty >= 0.5:
        summary_detail += (
            "Lĩnh vực CV và JD có sự khác biệt — hãy sẵn sàng giải thích điều này trong phỏng vấn. "
        )
    if critical_missing:
        summary_detail += (
            f"Bạn đang thiếu {len(critical_missing)} kỹ năng bắt buộc mà nhà tuyển dụng yêu cầu. "
        )

    summary_detail += _build_fit_summary(overall, exp_score, skills_score, edu_score, career_obj_score)

    return RecommendationItem(
        level=level,
        summary=_build_fit_summary_short(overall),
        summary_detail=summary_detail.strip(),
        action_items=action_items,
        interview_tips=interview_tips,
        score_range=score_range,
    )


def _build_fit_summary(
    overall: float,
    exp_score: float,
    skills_score: float,
    edu_score: float,
    career_obj_score: float,
) -> str:
    """Tạo tóm tắt mức độ phù hợp — ngôn ngữ dành cho ứng viên."""
    parts = []
    if overall >= 75:
        parts.append("Bạn là ứng viên rất phù hợp cho vị trí này.")
    elif overall >= 55:
        parts.append("Bạn đáp ứng được phần lớn yêu cầu, có cơ hội cao nếu thể hiện tốt.")
    elif overall >= 35:
        parts.append("Bạn đáp ứng được một phần yêu cầu, cần chuẩn bị kỹ để bù đắp điểm thiếu.")
    else:
        parts.append("Bạn còn thiếu nhiều yêu cầu quan trọng — hãy cân nhắc và phát triển thêm.")

    if exp_score < 25:
        parts.append("Điểm yếu cần lưu ý: kinh nghiệm thực tế.")
    elif skills_score < 15:
        parts.append("Điểm yếu cần lưu ý: kỹ năng kỹ thuật.")

    return " ".join(parts)


def _build_fit_summary_short(overall: float) -> str:
    """Tạo câu tóm tắt 1 dòng — ngôn ngữ dành cho ứng viên."""
    if overall >= 80:
        return "Bạn rất phù hợp — hãy tự tin ứng tuyển!"
    elif overall >= 65:
        return "Bạn đáp ứng tốt yêu cầu — cơ hội cao!"
    elif overall >= 50:
        return "Bạn đáp ứng được phần lớn yêu cầu."
    elif overall >= 35:
        return "Bạn đáp ứng một phần — cần chuẩn bị thêm."
    elif overall >= 20:
        return "Bạn còn thiếu nhiều yêu cầu quan trọng."
    else:
        return "Vị trí này chưa phù hợp với profile hiện tại của bạn."


# ── Build Experience Detail ─────────────────────────────────────────────────────────────
def build_experience_detail(
    exp_score: float,
    exp_rationale: str,
    exp_features: dict,
    cv_level: int,
    req_level: int,
    seniority_gap: int,
    is_entry_level: bool,
    cv_data: dict = None,
) -> dict:
    """Xây dựng chi tiết kinh nghiệm cho response."""
    max_exp = 50.0
    ratio = exp_score / max_exp

    level_map = {
        0: "Intern/Fresher",
        1: "Junior",
        2: "Mid-level",
        3: "Senior",
        4: "Lead/Principal",
    }
    seniority_map = {
        0: "Intern/Fresher (0 năm)",
        1: "Junior (1-2 năm)",
        2: "Mid-level (2-5 năm)",
        3: "Senior (5+ năm)",
        4: "Lead/Principal (7+ năm)",
    }

    years_req = exp_features.get("years_req", 0.0) if exp_features else 0.0
    all_exp_years = exp_features.get("all_exp_years", 0.0) if exp_features else 0.0
    project_years = exp_features.get("project_years", 0.0) if exp_features else 0.0
    work_years = all_exp_years - project_years if all_exp_years > 0 else 0.0

    gap_text = ""
    if years_req > 0 and all_exp_years > 0:
        gap = years_req - all_exp_years
        if gap > 0:
            gap_text = f"Thiếu {gap:.1f} năm so với yêu cầu"
        elif gap < -1:
            gap_text = f"Thừa {abs(gap):.1f} năm (overqualified)"

    level_text = level_map.get(cv_level, "Không xác định")
    req_text = seniority_map.get(req_level, "Không xác định")

    # Generate clean summary based on score level only
    if ratio >= 0.8:
        summary_text = "Kinh nghiệm và cấp độ đạt yêu cầu."
    elif ratio >= 0.6:
        summary_text = "Kinh nghiệm đáp ứng tốt yêu cầu."
    elif ratio >= 0.4:
        summary_text = "Kinh nghiệm cơ bản đáp ứng yêu cầu."
    else:
        summary_text = "Kinh nghiệm chưa đáp ứng đủ yêu cầu."

    # Calculate project_relevance_avg from exp_features
    project_relevance_scores = exp_features.get("project_relevance_scores", []) if exp_features else []
    if project_relevance_scores:
        project_relevance_avg = round(sum(project_relevance_scores) / len(project_relevance_scores) * 100, 0)
    else:
        project_relevance_avg = 0.0

    # Extract achievements/highlights from work experience
    highlights = []
    if cv_data and isinstance(cv_data, dict):
        work_exp = cv_data.get("work_experience", [])
        if isinstance(work_exp, list):
            for exp in work_exp:
                if isinstance(exp, dict):
                    hl = exp.get("highlights", [])
                    if isinstance(hl, list):
                        for h in hl:
                            if h and len(h.strip()) > 10:
                                highlights.append(h.strip())
                    elif isinstance(hl, str) and len(hl.strip()) > 10:
                        highlights.append(hl.strip())

    return {
        "score": round(exp_score, 1),
        "score_level": (
            "xuất sắc" if ratio >= 0.8 else
            "tốt" if ratio >= 0.6 else
            "trung bình" if ratio >= 0.4 else
            "yếu"
        ),
        "summary": summary_text,
        "cv_level": level_text,
        "jd_required_level": req_text,
        "cv_level_code": cv_level,
        "jd_required_level_code": req_level,
        "seniority_gap": seniority_gap,
        "is_entry_level": is_entry_level,
        "years_of_experience": round(max(work_years, 0.0), 1),
        "years_detail": {
            "total_years": round(all_exp_years, 1),
            "work_years": round(max(work_years, 0.0), 1),
            "project_years": round(project_years, 1),
            "required_years": round(years_req, 1),
            "gap_text": gap_text,
        },
        "project_relevance_avg": project_relevance_avg,
        "highlights": highlights[:5],  # Limit to top 5 highlights
        "projects": [
            {
                "name": p.get("name", "Project"),
                "relevance": round(p.get("relevance_score", 0.0) * 100, 0),
                "description": p.get("description", ""),
            }
            for p in (exp_features.get("projects", []) if exp_features else [])
        ] if exp_features and exp_features.get("projects") else [],
    }


# ── Build Education Detail ─────────────────────────────────────────────────────────────
def build_education_detail(edu_score: float, edu_rationale: str, cv_data: dict) -> dict:
    """Xây dựng chi tiết học vấn cho response."""
    max_edu = 10.0
    ratio = edu_score / max_edu

    certs = cv_data.get("certifications", [])
    cert_count = len(certs) if certs else 0
    cv_is_student = cv_data.get("is_student", False)
    edu_list = cv_data.get("education", [])
    cv_degree = 0
    if edu_list:
        degree_map_local = {
            "phd": 5, "tiến sĩ": 5, "doctor": 5,
            "thạc sĩ": 4, "master": 4,
            "cử nhân": 3, "bachelor": 3,
            "cao đẳng": 2, "college": 2,
            "trung cấp": 1,
        }
        for edu in edu_list:
            text = f"{edu.get('degree', '')} {edu.get('major', '')}".lower()
            for kw, val in degree_map_local.items():
                if kw in text:
                    cv_degree = max(cv_degree, val)

    degree_label_map = {
        5: "Sau đại học (Thạc sĩ/Tiến sĩ)",
        4: "Thạc sĩ",
        3: "Cử nhân/Đại học",
        2: "Cao đẳng",
        1: "Trung cấp",
        0: "Chưa xác định",
    }

    return {
        "score": round(edu_score, 1),
        "score_level": (
            "xuất sắc" if ratio >= 0.8 else
            "tốt" if ratio >= 0.6 else
            "trung bình" if ratio >= 0.4 else
            "yếu"
        ),
        "summary": edu_rationale,
        "degree_level": degree_label_map.get(cv_degree, "Chưa xác định"),
        "degree_code": cv_degree,
        "is_student": cv_is_student,
        "certifications": {
            "count": cert_count,
            "names": [c.get("name") or str(c) if isinstance(c, dict) else str(c) for c in certs[:5]],
        },
        "education_entries": [
            {
                "school": e.get("school", ""),
                "degree": e.get("degree", ""),
                "major": e.get("major", ""),
                "year": e.get("year", ""),
            }
            for e in edu_list[:3]
        ],
    }


# ── Build Career Detail ─────────────────────────────────────────────────────────────
def build_career_detail(career_score: float, career_rationale: str) -> dict:
    """Xây dựng chi tiết mục tiêu nghề nghiệp cho response."""
    max_career = 10.0
    ratio = career_score / max_career

    return {
        "score": round(career_score, 1),
        "score_level": (
            "xuất sắc" if ratio >= 0.8 else
            "tốt" if ratio >= 0.5 else
            "trung bình" if ratio >= 0.3 else
            "yếu"
        ),
        "summary": career_rationale,
        "alignment": (
            "phù hợp cao" if ratio >= 0.7 else
            "phù hợp" if ratio >= 0.4 else
            "chưa phù hợp"
        ),
    }


# ── Build Company Fit Detail ─────────────────────────────────────────────────────────────
def build_company_fit_detail(company_score: float, company_rationale: str) -> dict:
    """Xây dựng chi tiết phù hợp công ty cho response."""
    max_company = 10.0
    ratio = company_score / max_company

    return {
        "score": round(company_score, 1),
        "score_level": (
            "xuất sắc" if ratio >= 0.8 else
            "tốt" if ratio >= 0.6 else
            "trung bình" if ratio >= 0.4 else
            "yếu"
        ),
        "summary": company_rationale,
        "fit_level": (
            "rất phù hợp" if ratio >= 0.7 else
            "phù hợp" if ratio >= 0.4 else
            "chưa phù hợp"
        ),
    }


# ── Top-Level Summary ─────────────────────────────────────────────────────────────
def build_summary_text(
    overall: float,
    exp_score: float,
    skills_score: float,
    edu_score: float,
    career_obj_score: float,
    company_score: float,
    domain_penalty: float,
) -> str:
    """Tạo đoạn tóm tắt ngắn gọn cho FE hiển thị."""
    parts = []

    if overall >= 75:
        parts.append("Ứng viên rất phù hợp với vị trí.")
    elif overall >= 55:
        parts.append("Ứng viên khá phù hợp, đáp ứng phần lớn yêu cầu.")
    elif overall >= 35:
        parts.append("Ứng viên đáp ứng một phần yêu cầu.")
    else:
        parts.append("Ứng viên chưa đáp ứng đủ yêu cầu chính.")

    if domain_penalty >= 0.5:
        parts.append("Lưu ý: lĩnh vực CV và JD có sự lệch nhau đáng kể.")

    return " ".join(parts)


# ── Score Badge ─────────────────────────────────────────────────────────────
def get_score_badge(score: float, max_score: float) -> str:
    """Trả về nhãn badge cho điểm."""
    ratio = score / max_score
    if ratio >= 0.8:
        return "excellent"
    elif ratio >= 0.6:
        return "good"
    elif ratio >= 0.4:
        return "average"
    elif ratio >= 0.2:
        return "poor"
    else:
        return "very_poor"
