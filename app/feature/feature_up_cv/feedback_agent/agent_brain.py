# -*- coding: utf-8 -*-
"""
Agent Feedback Analyzer - Tự động phân tích và sinh rules từ feedback

Khả năng:
1. Self-reflection: Phân tích kết quả scoring vs expected
2. Root cause analysis: Tìm nguyên nhân gốc rễ
3. Rule generation: Tạo rules từ phân tích
4. Pattern detection: Phát hiện patterns từ nhiều cases
5. System improvement: Đề xuất cải tiến hệ thống (thay hard-coded values)
"""

import json
import re
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from dataclasses import dataclass, field
from collections import defaultdict

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────────
# KNOWLEDGE BASE: Các hard-coded values phổ biến trong scoring
# ────────────────────────────────────────────────────────────────
@dataclass
class HardCodedValue:
    """Thông tin về một giá trị hard-coded trong code"""
    name: str
    current_value: Any
    file_path: str
    line_number: int
    context: str  # Code context xung quanh


@dataclass
class ImprovementSuggestion:
    """Đề xuất cải tiến hệ thống"""
    category: str  # "threshold", "penalty", "bonus", "formula"
    issue: str
    current_value: Any
    suggested_value: Any
    evidence: List[Dict]  # Các cases ủng hộ đề xuất
    confidence: float
    impact: str  # "high", "medium", "low"
    suggested_code_change: str
    priority: int


@dataclass
class ScoreAnalysis:
    """Kết quả phân tích một case"""
    case_id: str
    actual_score: float
    expected_range: Tuple[float, float]
    is_too_high: bool
    is_too_low: bool
    score_diff: float  # diff từ center của expected range
    detailed_scores: Dict[str, float]
    reasons: List[str] = field(default_factory=list)
    root_cause: str = ""
    suggested_rules: List[Dict] = field(default_factory=list)
    v2_analysis: Dict = field(default_factory=dict)  # v2 module outputs


@dataclass
class PatternInsight:
    """Pattern phát hiện được từ nhiều cases"""
    pattern_type: str  # "fresh_grad", "career_change", "domain_mismatch"
    affected_cases: List[str]
    common_symptom: str
    root_cause: str
    suggested_action: str
    confidence: float = 0.5


# ────────────────────────────────────────────────────────────────
# CONFIG: Agent Feedback Configuration
# ────────────────────────────────────────────────────────────────
AGENT_FEEDBACK_CONFIG = {
    # Thresholds for pattern detection
    "min_cases_for_pattern": 2,
    "min_confidence_for_rule": 0.70,
    "max_rule_age_days": 90,
    
    # Score deviation thresholds
    "significant_deviation": 10.0,  # Độ lệch đáng kể
    "minor_deviation": 5.0,  # Độ lệch nhỏ
    
    # Overqualified thresholds
    "overqualified_ratio_threshold": 2.0,  # 2x experience
    
    # Career change domains
    "non_tech_domains": ["marketing", "sales", "finance", "hr", "operations", 
                          "healthcare", "education", "design", "management"],
    "tech_domains": ["tech_ai", "tech_backend", "tech_frontend", "tech_data", 
                     "tech_devops", "tech_security", "tech_mobile", "tech_qa"],
    
    # Seniority keywords
    "junior_keywords": ["intern", "fresher", "junior", "entry", "trainee"],
    "senior_keywords": ["senior", "lead", "principal", "staff", "architect", 
                        "manager", "director"],
    
    # Skills context patterns
    "weak_context_keywords": ["khóa học", "course", "training", "online", 
                              "certification", "học viên", "student", "bootcamp",
                              "tự học", "self-taught"],
    "strong_context_keywords": ["production", "deployed", "implemented", "developed", 
                                "built", "maintained", "led", "architected", 
                                "optimized", "scaled", "developed", "managed"],
}


class AgentFeedbackAnalyzer:
    """
    Agent Brain - Phân tích feedback và sinh rules tự động
    """

    def __init__(self, memory=None):
        self.memory = memory
        self.analysis_history: List[ScoreAnalysis] = []
        self.pattern_cache: List[PatternInsight] = []
        self.config = AGENT_FEEDBACK_CONFIG

    def analyze_case(
        self,
        case_id: str,
        cv_data: Dict,
        jd_data: Dict,
        scoring_result: Dict,
        expected_range: Tuple[float, float],
        v2_analysis: Dict = None
    ) -> ScoreAnalysis:
        """
        Phân tích một case và tìm root cause.
        """
        actual_score = scoring_result.get("overall_score", 0)
        detailed_scores = scoring_result.get("detailed_scores", {})

        min_expected, max_expected = expected_range
        center_expected = (min_expected + max_expected) / 2

        is_too_high = actual_score > max_expected
        is_too_low = actual_score < min_expected
        score_diff = actual_score - center_expected

        analysis = ScoreAnalysis(
            case_id=case_id,
            actual_score=actual_score,
            expected_range=expected_range,
            is_too_high=is_too_high,
            is_too_low=is_too_low,
            score_diff=score_diff,
            detailed_scores=detailed_scores,
            v2_analysis=v2_analysis or {}
        )

        # Phân tích chi tiết từng component
        self._analyze_experience_score(analysis, cv_data, jd_data, detailed_scores)
        self._analyze_skills_score(analysis, cv_data, jd_data, detailed_scores)
        self._analyze_domain_fit(analysis, cv_data, jd_data, detailed_scores)
        self._analyze_career_objective(analysis, cv_data, jd_data, detailed_scores)
        self._analyze_v2_modules(analysis, cv_data, jd_data, v2_analysis)

        # Tìm root cause chính
        analysis.root_cause = self._determine_root_cause(analysis)

        # Sinh rules từ phân tích
        analysis.suggested_rules = self._generate_rules_from_analysis(analysis, cv_data, jd_data)

        self.analysis_history.append(analysis)
        return analysis

    def _analyze_v2_modules(
        self,
        analysis: ScoreAnalysis,
        cv_data: Dict,
        jd_data: Dict,
        v2_analysis: Dict
    ):
        """Phân tích kết quả từ các v2 modules"""
        if not v2_analysis:
            return

        reasons = []

        # Check overqualified detection
        if v2_analysis.get("v2_overqualified"):
            reasons.append(f"Overqualified detected: {v2_analysis.get('overqualified_severity', 'unknown')}")

        # Check career change detection
        if v2_analysis.get("v2_career_change"):
            reasons.append(f"Career change: {v2_analysis.get('v2_career_change_severity', 'unknown')}")

        # Check experience quality
        exp_quality_mult = v2_analysis.get("v2_exp_quality_mult", 1.0)
        if exp_quality_mult < 0.8:
            reasons.append(f"Experience quality low: {exp_quality_mult:.0%}")

        # Check skills context
        skills_context_mult = v2_analysis.get("v2_skills_context_mult", 1.0)
        if skills_context_mult < 0.9:
            reasons.append(f"Skills context issue: {skills_context_mult:.0%}")

        analysis.reasons.extend(reasons)


# ────────────────────────────────────────────────────────────────
# KNOWLEDGE BASE: Các hard-coded values phổ biến trong scoring
# ────────────────────────────────────────────────────────────────
@dataclass
class HardCodedValue:
    """Thông tin về một giá trị hard-coded trong code"""
    name: str
    current_value: Any
    file_path: str
    line_number: int
    context: str  # Code context xung quanh


@dataclass
class ImprovementSuggestion:
    """Đề xuất cải tiến hệ thống"""
    category: str  # "threshold", "penalty", "bonus", "formula"
    issue: str
    current_value: Any
    suggested_value: Any
    evidence: List[Dict]  # Các cases ủng hộ đề xuất
    confidence: float
    impact: str  # "high", "medium", "low"
    suggested_code_change: str
    priority: int


@dataclass
class ScoreAnalysis:
    """Kết quả phân tích một case"""
    case_id: str
    actual_score: float
    expected_range: Tuple[float, float]
    is_too_high: bool
    is_too_low: bool
    score_diff: float  # diff từ center của expected range
    detailed_scores: Dict[str, float]
    reasons: List[str] = field(default_factory=list)
    root_cause: str = ""
    suggested_rules: List[Dict] = field(default_factory=list)
    v2_analysis: Dict = field(default_factory=dict)  # v2 module outputs


@dataclass
class PatternInsight:
    """Pattern phát hiện được từ nhiều cases"""
    pattern_type: str  # "fresh_grad", "career_change", "domain_mismatch"
    affected_cases: List[str]
    common_symptom: str
    root_cause: str
    suggested_action: str
    confidence: float = 0.5


class AgentFeedbackAnalyzer:
    """
    Agent Brain - Phân tích feedback và sinh rules tự động
    """

    def __init__(self, memory=None):
        self.memory = memory
        self.analysis_history: List[ScoreAnalysis] = []
        self.pattern_cache: List[PatternInsight] = []
        self.config = AGENT_FEEDBACK_CONFIG

    def analyze_case(
        self,
        case_id: str,
        cv_data: Dict,
        jd_data: Dict,
        scoring_result: Dict,
        expected_range: Tuple[float, float]
    ) -> ScoreAnalysis:
        """
        Phân tích một case và tìm root cause.
        """
        actual_score = scoring_result.get("overall_score", 0)
        detailed_scores = scoring_result.get("detailed_scores", {})

        min_expected, max_expected = expected_range
        center_expected = (min_expected + max_expected) / 2

        is_too_high = actual_score > max_expected
        is_too_low = actual_score < min_expected
        score_diff = actual_score - center_expected

        analysis = ScoreAnalysis(
            case_id=case_id,
            actual_score=actual_score,
            expected_range=expected_range,
            is_too_high=is_too_high,
            is_too_low=is_too_low,
            score_diff=score_diff,
            detailed_scores=detailed_scores
        )

        # Phân tích chi tiết từng component
        self._analyze_experience_score(analysis, cv_data, jd_data, detailed_scores)
        self._analyze_skills_score(analysis, cv_data, jd_data, detailed_scores)
        self._analyze_domain_fit(analysis, cv_data, jd_data, detailed_scores)
        self._analyze_career_objective(analysis, cv_data, jd_data, detailed_scores)

        # Tìm root cause chính
        analysis.root_cause = self._determine_root_cause(analysis)

        # Sinh rules từ phân tích
        analysis.suggested_rules = self._generate_rules_from_analysis(analysis, cv_data, jd_data)

        self.analysis_history.append(analysis)
        return analysis

    def _analyze_experience_score(
        self,
        analysis: ScoreAnalysis,
        cv_data: Dict,
        jd_data: Dict,
        detailed_scores: Dict
    ):
        """Phân tích experience score"""
        exp_score = detailed_scores.get("experience_score", 0)
        max_exp = 50
        exp_ratio = exp_score / max_exp

        cv_exp = cv_data.get("work_experience", [])
        jd_years = jd_data.get("experience_years", 0)

        reasons = []

        # Tính years từ work experience
        total_years = 0
        for exp in cv_exp:
            start = exp.get("start", "")
            end = exp.get("end", "") or "present"
            try:
                start_year = int(start) if start else 0
                end_year = int(end) if end else 2024
                total_years += max(0, end_year - start_year)
            except:
                pass

        # Fresh grad check
        is_student = cv_data.get("is_student", False)
        if is_student and analysis.is_too_low:
            if exp_score < 25:
                reasons.append("Fresh grad có projects nhưng không được bonus đủ")

        # Experience gap check
        if total_years < jd_years and analysis.is_too_low:
            reasons.append(f"Experience ({total_years} năm) thấp hơn yêu cầu ({jd_years} năm)")

        if total_years > jd_years + 3 and analysis.is_too_high:
            reasons.append(f"Experience ({total_years} năm) cao hơn nhiều so với yêu cầu ({jd_years} năm)")

        # Career change check
        cv_domain = cv_data.get("domain", "unknown")
        jd_domain = jd_data.get("domain", jd_data.get("structured", {}).get("domain", "unknown"))
        non_tech = ["marketing", "sales", "finance", "hr", "operations"]
        tech = ["tech_ai", "tech_backend", "tech_frontend", "tech_data", "tech_devops"]

        if cv_domain in non_tech and jd_domain in tech:
            if analysis.is_too_high:
                reasons.append("Career change: CV từ non-tech sang tech nhưng không bị penalty đúng mức")
            else:
                reasons.append("Career change: Domain mismatch nhưng penalty chưa đủ")

        if cv_domain in tech and jd_domain in non_tech:
            reasons.append("Career change ngược: từ tech sang non-tech")

        # Sales check
        if "sales" in cv_domain.lower():
            if exp_ratio > 0.3 and analysis.is_too_high:
                reasons.append("Sales profile apply tech job: exp score quá cao")

        analysis.reasons.extend(reasons)

    def _analyze_skills_score(
        self,
        analysis: ScoreAnalysis,
        cv_data: Dict,
        jd_data: Dict,
        detailed_scores: Dict
    ):
        """Phân tích skills score"""
        skills_score = detailed_scores.get("skills_total_score", 0)
        max_skills = 30
        skills_ratio = skills_score / max_skills

        cv_skills = set(s.lower() for s in cv_data.get("skills", []))
        jd_skills_raw = jd_data.get("skills_required", [])
        jd_skills = set()

        for s in jd_skills_raw:
            if isinstance(s, dict):
                jd_skills.add(s.get("requirement", "").lower())
            else:
                jd_skills.add(str(s).lower())

        # Match analysis
        matched = cv_skills.intersection(jd_skills)
        missing = jd_skills - cv_skills

        if len(missing) > 5 and analysis.is_too_high:
            analysis.reasons.append(f"Thiếu {len(missing)} skills quan trọng nhưng score vẫn cao: {list(missing)[:3]}")

        if len(matched) >= 5 and analysis.is_too_low:
            analysis.reasons.append(f"Có {len(matched)} skills match nhưng score thấp")

    def _analyze_domain_fit(
        self,
        analysis: ScoreAnalysis,
        cv_data: Dict,
        jd_data: Dict,
        detailed_scores: Dict
    ):
        """Phân tích domain fit"""
        cv_domain = cv_data.get("domain", "unknown")
        jd_domain = jd_data.get("domain", jd_data.get("structured", {}).get("domain", "unknown"))
        domain_penalty = detailed_scores.get("domain_penalty", 0)

        if cv_domain != jd_domain and cv_domain != "unknown":
            if domain_penalty == 0 and analysis.is_too_high:
                analysis.reasons.append(f"Domain mismatch ({cv_domain} vs {jd_domain}) nhưng không có penalty")

            if domain_penalty < -0.3:
                analysis.reasons.append(f"Domain penalty quá nặng: {domain_penalty}")

    def _analyze_career_objective(
        self,
        analysis: ScoreAnalysis,
        cv_data: Dict,
        jd_data: Dict,
        detailed_scores: Dict
    ):
        """Phân tích career objective"""
        cv_obj = cv_data.get("career_objectives", cv_data.get("objective", "")).lower()
        jd_title = jd_data.get("job_title", "").lower()
        obj_score = detailed_scores.get("career_objectives_score", 0)

        # Overqualified check
        keywords_high = ["principal", "staff", "director", "vp", "lead architect"]
        keywords_junior = ["junior", "fresher", "intern", "entry"]

        if any(k in cv_obj for k in keywords_high):
            if analysis.is_too_low:
                analysis.reasons.append("CV apply cho senior/principal position")

        if any(k in jd_title for k in keywords_junior):
            if analysis.is_too_high:
                analysis.reasons.append("JD yêu cầu junior nhưng score quá cao")

    def _determine_root_cause(self, analysis: ScoreAnalysis) -> str:
        """Xác định root cause chính"""
        if not analysis.reasons:
            return "Không xác định được root cause"

        # Lấy reason quan trọng nhất
        priority_keywords = {
            "career change": "Career change không được xử lý đúng",
            "domain mismatch": "Domain mismatch không được penalty đúng mức",
            "experience": "Experience scoring không chính xác",
            "skills": "Skills matching không đúng",
            "fresh grad": "Fresh grad không được bonus đúng mức",
            "overqualified": "Overqualified candidate bị penalty không đúng",
            "sales": "Sales profile apply tech job",
            "penalty": "Penalty không chính xác",
            "bonus": "Bonus không đúng mức"
        }

        for reason in analysis.reasons:
            reason_lower = reason.lower()
            for keyword, cause in priority_keywords.items():
                if keyword in reason_lower:
                    return cause

        return analysis.reasons[0] if analysis.reasons else "Không xác định được"

    def _generate_rules_from_analysis(
        self,
        analysis: ScoreAnalysis,
        cv_data: Dict,
        jd_data: Dict
    ) -> List[Dict]:
        """Sinh rules từ phân tích với improved logic"""
        rules = []

        # Determine rule type based on reasons
        reasons_text = " ".join(analysis.reasons).lower()
        cv_domain = cv_data.get("domain", "unknown")
        jd_struct = jd_data.get("structured", jd_data)
        jd_domain = jd_struct.get("domain", jd_data.get("domain", "unknown"))
        is_student = cv_data.get("is_student", False)
        
        config = self.config
        non_tech = config["non_tech_domains"]
        tech = config["tech_domains"]

        # ── RULE TYPE 1: Fresh Grad with Projects ──────────────────────────────
        if is_student and analysis.is_too_low:
            if analysis.detailed_scores.get("experience_score", 0) < 30:
                rules.append({
                    "rule_type": "FRESH_GRAD_PROJECT_BONUS",
                    "condition": {
                        "cv.is_student": True,
                        "cv.projects.exists": True,
                        "analysis.is_too_low": True
                    },
                    "action": {
                        "type": "bonus",
                        "target": "experience_score",
                        "value": 20,
                        "reason": "Fresh grad có relevant projects"
                    },
                    "priority": 75,
                    "confidence": 0.8,
                    "ttl_days": 90,
                    "source_case": analysis.case_id,
                    "analysis": f"Score thấp ({analysis.actual_score}) cho fresh grad có projects"
                })

        # ── RULE TYPE 2: Career Change Detection ───────────────────────────────
        if cv_domain in non_tech and jd_domain in tech:
            # NON-TECH -> TECH career change
            rules.append({
                "rule_type": "CAREER_CHANGE_PENALTY_V2",
                "condition": {
                    "cv.domain": {"in": non_tech},
                    "jd.domain": {"in": tech},
                    "cv.work_years": {">=": 3}
                },
                "action": {
                    "type": "composite_penalty",
                    "components": [
                        {"target": "experience_score", "adjustment": 0.55},
                        {"target": "domain_penalty", "adjustment": 0.70}
                    ],
                    "cap": {
                        "experience_score": {"max": 25},
                        "overall_score": {"max": 45}
                    },
                    "reason": f"Career change từ {cv_domain} sang tech"
                },
                "priority": 88,
                "confidence": 0.85,
                "ttl_days": 90,
                "source_case": analysis.case_id,
                "analysis": f"Score cao ({analysis.actual_score}) cho career changer"
            })

        # ── RULE TYPE 3: Severe Domain Mismatch (Sales -> Tech) ───────────────
        if "sales" in cv_domain.lower() and jd_domain in tech:
            rules.append({
                "rule_type": "SEVERE_DOMAIN_MISMATCH",
                "condition": {
                    "cv.domain.contains": "sales",
                    "jd.domain": {"in": tech}
                },
                "action": {
                    "type": "cap",
                    "target": "experience_score",
                    "max_value": 15,
                    "domain_penalty": -0.5,
                    "reason": "Sales profile apply tech job"
                },
                "priority": 92,
                "confidence": 0.9,
                "ttl_days": 90,
                "source_case": analysis.case_id,
                "analysis": "Sales domain không phù hợp cho tech job"
            })

        # ── RULE TYPE 4: Overqualified Detection ───────────────────────────────
        work_exp = cv_data.get("work_experience", [])
        total_years = 0
        for exp in work_exp:
            start = exp.get("start", "")
            end = exp.get("end", "") or "present"
            try:
                start_year = int(start) if start else 0
                end_year = int(end) if end else 2024
                total_years += max(0, end_year - start_year)
            except:
                pass
        
        seniority = jd_struct.get("seniority", "").lower()
        is_junior_level = any(kw in seniority for kw in config["junior_keywords"])
        
        if total_years >= 5 and is_junior_level:
            rules.append({
                "rule_type": "OVERQUALIFIED_CANDIDATE",
                "condition": {
                    "cv.work_years": {">=": 5},
                    "jd.seniority": {"contains": config["junior_keywords"]}
                },
                "action": {
                    "type": "cap",
                    "target": "overall_score",
                    "max_value": 70,
                    "reason": "Overqualified candidate cho entry-level position"
                },
                "priority": 85,
                "confidence": 0.82,
                "ttl_days": 90,
                "source_case": analysis.case_id,
                "analysis": f"Overqualified: {total_years} năm cho JD yêu cầu junior"
            })

        # ── RULE TYPE 5: Skills Context Validation ─────────────────────────────
        projects = cv_data.get("projects", [])
        if is_student and len(projects) >= 1:
            # Student with projects should get bonus
            rules.append({
                "rule_type": "STUDENT_PROJECT_BONUS",
                "condition": {
                    "cv.is_student": True,
                    "cv.projects.count": {">=": 1}
                },
                "action": {
                    "type": "bonus",
                    "target": "experience_score",
                    "value": 15,
                    "reason": "Sinh viên có projects được tính là kinh nghiệm"
                },
                "priority": 72,
                "confidence": 0.78,
                "ttl_days": 90,
                "source_case": analysis.case_id,
                "analysis": "Student projects nên được tính là experience"
            })

        # ── RULE TYPE 6: Transferable Skills Bonus ────────────────────────────
        # For tech cross-field (e.g., QA -> Backend, Mobile -> Backend)
        if cv_domain in ["tech_qa", "tech_mobile", "tech_devops"] and jd_domain == "tech_backend":
            rules.append({
                "rule_type": "TRANSFERABLE_SKILLS_BONUS",
                "condition": {
                    "cv.domain": {"in": ["tech_qa", "tech_mobile", "tech_devops"]},
                    "jd.domain": "tech_backend"
                },
                "action": {
                    "type": "reduce_penalty",
                    "target": "domain_penalty",
                    "factor": 0.5,
                    "reason": "Tech cross-field có transferable skills"
                },
                "priority": 65,
                "confidence": 0.72,
                "ttl_days": 90,
                "source_case": analysis.case_id,
                "analysis": f"{cv_domain} có transferable skills sang {jd_domain}"
            })

        # ── RULE TYPE 7: Senior Match Bonus ───────────────────────────────────
        if total_years >= 5 and jd_domain in tech and cv_domain == jd_domain:
            # Senior candidate with exact domain match
            rules.append({
                "rule_type": "SENIOR_EXACT_MATCH_BONUS",
                "condition": {
                    "cv.work_years": {">=": 5},
                    "cv.domain": "jd.domain",
                    "cv.domain": {"in": tech}
                },
                "action": {
                    "type": "bonus",
                    "target": "experience_score",
                    "value": 10,
                    "reason": "Senior candidate đúng domain"
                },
                "priority": 70,
                "confidence": 0.80,
                "ttl_days": 90,
                "source_case": analysis.case_id,
                "analysis": f"Senior {total_years} năm đúng domain ({cv_domain})"
            })

        return rules

    def detect_patterns(self) -> List[PatternInsight]:
        """
        Phát hiện patterns từ nhiều cases đã phân tích.
        Enhanced v2: Better pattern detection with v2 module analysis.
        """
        patterns = []
        config = self.config
        min_cases = config["min_cases_for_pattern"]

        # Group by overqualified detection
        overqualified_cases = [
            a for a in self.analysis_history
            if a.v2_analysis.get("v2_overqualified", False)
        ]

        if len(overqualified_cases) >= min_cases:
            avg_deviation = sum(a.score_diff for a in overqualified_cases) / len(overqualified_cases)
            symptom = "Candidates overqualified được phát hiện nhưng score vẫn cao hơn expected"

            patterns.append(PatternInsight(
                pattern_type="overqualified_detection",
                affected_cases=[a.case_id for a in overqualified_cases],
                common_symptom=symptom,
                root_cause="Overqualified detection chưa được apply đúng vào score",
                suggested_action="Tăng penalty cho overqualified candidates, giảm OVERQUALIFIED_SCORE_CAP",
                confidence=0.82
            ))

        # Group by career change detection
        career_change_cases = [
            a for a in self.analysis_history
            if a.v2_analysis.get("v2_career_change", False)
        ]

        if len(career_change_cases) >= min_cases:
            avg_deviation = sum(a.score_diff for a in career_change_cases) / len(career_change_cases)
            avg_score = sum(a.actual_score for a in career_change_cases) / len(career_change_cases)

            patterns.append(PatternInsight(
                pattern_type="career_change_handling",
                affected_cases=[a.case_id for a in career_change_cases],
                common_symptom=f"Career changers được phát hiện nhưng score vẫn cao (avg: {avg_score:.0f})",
                root_cause="Career change penalty chưa đủ mạnh hoặc chưa được combine đúng",
                suggested_action="Tăng CAREER_CHANGE_SEVERE_PENALTY, apply composite penalty",
                confidence=0.78
            ))

        # Group by skills context issues
        skills_context_cases = [
            a for a in self.analysis_history
            if a.v2_analysis.get("v2_skills_context_mult", 1.0) < 0.9
        ]

        if len(skills_context_cases) >= min_cases:
            avg_context_mult = sum(a.v2_analysis.get("v2_skills_context_mult", 1.0) for a in skills_context_cases) / len(skills_context_cases)

            patterns.append(PatternInsight(
                pattern_type="skills_context_validation",
                affected_cases=[a.case_id for a in skills_context_cases],
                common_symptom=f"Skills context validation gây penalty không đúng mức (avg mult: {avg_context_mult:.0%})",
                root_cause="Skills context multiplier quá khắc nghiệt",
                suggested_action="Giảm penalty từ 0.85 xuống 0.95 cho work_ratio >= 0.3",
                confidence=0.85
            ))

        # Group by experience quality issues
        exp_quality_cases = [
            a for a in self.analysis_history
            if a.v2_analysis.get("v2_exp_quality_mult", 1.0) < 0.8
        ]

        if len(exp_quality_cases) >= min_cases:
            avg_mult = sum(a.v2_analysis.get("v2_exp_quality_mult", 1.0) for a in exp_quality_cases) / len(exp_quality_cases)

            patterns.append(PatternInsight(
                pattern_type="experience_quality",
                affected_cases=[a.case_id for a in exp_quality_cases],
                common_symptom=f"Experience quality multiplier thấp (avg: {avg_mult:.0%})",
                root_cause="Experience quality phạt quá nặng cho một số cases",
                suggested_action="Điều chỉnh exp quality multiplier cho phù hợp",
                confidence=0.70
            ))

        # Group by domain mismatch
        domain_mismatch_cases = [
            a for a in self.analysis_history
            if a.is_too_high and any("domain" in r.lower() for r in a.reasons)
        ]

        if len(domain_mismatch_cases) >= min_cases:
            patterns.append(PatternInsight(
                pattern_type="domain_mismatch",
                affected_cases=[a.case_id for a in domain_mismatch_cases],
                common_symptom="Domain mismatch nhưng score cao bất thường",
                root_cause="Domain penalty không đủ mạnh hoặc không được apply",
                suggested_action="Tăng penalty cho domain mismatch, đặc biệt với non-tech -> tech",
                confidence=0.80
            ))

        self.pattern_cache = patterns
        return patterns

    def get_analysis_report(self) -> Dict:
        """Tạo báo cáo phân tích tổng hợp"""
        if not self.analysis_history:
            return {"status": "no_data", "message": "Chưa có dữ liệu phân tích"}

        total = len(self.analysis_history)
        too_high = sum(1 for a in self.analysis_history if a.is_too_high)
        too_low = sum(1 for a in self.analysis_history if a.is_too_low)

        patterns = self.detect_patterns()

        # Collect all suggested rules
        all_rules = []
        for a in self.analysis_history:
            all_rules.extend(a.suggested_rules)

        return {
            "summary": {
                "total_cases": total,
                "too_high": too_high,
                "too_low": too_low,
                "accuracy_rate": (total - too_high - too_low) / total * 100
            },
            "patterns": [
                {
                    "type": p.pattern_type,
                    "affected_cases": p.affected_cases,
                    "root_cause": p.root_cause,
                    "suggested_action": p.suggested_action,
                    "confidence": p.confidence
                }
                for p in patterns
            ],
            "suggested_rules": all_rules,
            "cases": [
                {
                    "case_id": a.case_id,
                    "actual_score": a.actual_score,
                    "expected": a.expected_range,
                    "reasons": a.reasons,
                    "root_cause": a.root_cause,
                    "rules": a.suggested_rules
                }
                for a in self.analysis_history
            ]
        }

    def apply_learning_to_memory(self) -> List[str]:
        """
        Áp dụng các rules đã học vào memory.
        Returns: List of rule IDs added.
        """
        if not self.memory:
            logger.warning("[AgentBrain] No memory configured")
            return []

        added_rules = []
        report = self.get_analysis_report()

        for rule in report.get("suggested_rules", []):
            # Convert rule to text for FAISS
            rule_text = self._rule_to_text(rule)

            result = self.memory.add_learned_rule(
                rule_text=rule_text,
                context=f"Learned from case: {rule.get('source_case', 'unknown')}",
                rule_type=rule.get("rule_type"),
                condition=rule.get("condition"),
                action=rule.get("action"),
                priority=rule.get("priority", 50),
                confidence=rule.get("confidence", 0.5),
                ttl_days=rule.get("ttl_days", 30),
                source_case=rule.get("source_case"),
            )

            if result.get("success"):
                added_rules.append(result.get("rule_id"))

        logger.info(f"[AgentBrain] Applied {len(added_rules)} rules to memory")
        return added_rules

    def _rule_to_text(self, rule: Dict) -> str:
        """Convert structured rule to text for FAISS storage"""
        rule_type = rule.get("rule_type", "GENERIC_RULE")
        condition = rule.get("condition", {})
        action = rule.get("action", {})
        reason = action.get("reason", "")

        condition_str = ", ".join(f"{k}={v}" for k, v in condition.items())
        action_type = action.get("type", "unknown")
        target = action.get("target", "")

        return f"{rule_type} | Condition: {condition_str} | Action: {action_type} {target} | Reason: {reason}"

    def generate_system_improvements(self) -> List[ImprovementSuggestion]:
        """
        Generate system improvement suggestions based on patterns detected.
        This is the key method that translates feedback into actionable code changes.
        """
        suggestions = []
        patterns = self.detect_patterns()

        for pattern in patterns:
            # Generate improvement suggestions based on pattern type
            if pattern.pattern_type == "overqualified_detection":
                suggestions.append(ImprovementSuggestion(
                    category="threshold",
                    issue="Overqualified candidates not properly penalized",
                    current_value=70.0,
                    suggested_value=65.0,
                    evidence=self._get_pattern_evidence(pattern),
                    confidence=pattern.confidence,
                    impact="high",
                    suggested_code_change="""
# In _shared.py, ScoringConfig:
OVERQUALIFIED_SCORE_CAP = 65.0  # Reduced from 70.0
OVERQUALIFIED_ABSOLUTE_CAP = 60.0  # Reduced from 65.0
""",
                    priority=90
                ))

            elif pattern.pattern_type == "career_change_handling":
                suggestions.append(ImprovementSuggestion(
                    category="penalty",
                    issue="Career change penalty not applied strongly enough",
                    current_value=0.70,
                    suggested_value=0.85,
                    evidence=self._get_pattern_evidence(pattern),
                    confidence=pattern.confidence,
                    impact="high",
                    suggested_code_change="""
# In _shared.py, ScoringConfig:
CAREER_CHANGE_SEVERE_PENALTY = 0.85  # Increased from 0.70
""",
                    priority=88
                ))

            elif pattern.pattern_type == "skills_context_validation":
                suggestions.append(ImprovementSuggestion(
                    category="penalty",
                    issue="Skills context multiplier too strict",
                    current_value=0.85,
                    suggested_value=0.95,
                    evidence=self._get_pattern_evidence(pattern),
                    confidence=pattern.confidence,
                    impact="high",
                    suggested_code_change="""
# In validate_skills_context():
if work_ratio >= 0.3:  # Changed from 0.4
    context_multiplier = 0.95  # Changed from 0.85
""",
                    priority=85
                ))

            elif pattern.pattern_type == "experience_quality":
                suggestions.append(ImprovementSuggestion(
                    category="multiplier",
                    issue="Experience quality multiplier too harsh",
                    current_value=0.4,
                    suggested_value=0.5,
                    evidence=self._get_pattern_evidence(pattern),
                    confidence=pattern.confidence,
                    impact="medium",
                    suggested_code_change="""
# In analyze_experience_quality():
if tech_ratio >= 0.5:
    quality_multiplier = 0.7  # Changed from 0.6
else:
    quality_multiplier = 0.5  # Changed from 0.4
""",
                    priority=75
                ))

        return suggestions

    def _get_pattern_evidence(self, pattern: PatternInsight) -> List[Dict]:
        """Get evidence cases for a pattern"""
        evidence = []
        for case in self.analysis_history:
            if case.case_id in pattern.affected_cases:
                evidence.append({
                    "case_id": case.case_id,
                    "actual_score": case.actual_score,
                    "expected": case.expected_range,
                    "deviation": case.score_diff
                })
        return evidence

    def generate_feedback_report(self) -> Dict:
        """
        Generate comprehensive feedback report for system improvement.
        This is the main output that should be used for fixing the system.
        """
        patterns = self.detect_patterns()
        suggestions = self.generate_system_improvements()
        report = self.get_analysis_report()

        return {
            "timestamp": datetime.now().isoformat(),
            "summary": report["summary"],
            "patterns": [
                {
                    "type": p.pattern_type,
                    "affected_cases": p.affected_cases,
                    "root_cause": p.root_cause,
                    "suggested_action": p.suggested_action,
                    "confidence": p.confidence
                }
                for p in patterns
            ],
            "system_improvements": [
                {
                    "category": s.category,
                    "issue": s.issue,
                    "current_value": s.current_value,
                    "suggested_value": s.suggested_value,
                    "confidence": s.confidence,
                    "impact": s.impact,
                    "suggested_code_change": s.suggested_code_change,
                    "evidence": [
                        {"case_id": e["case_id"], "deviation": e["deviation"]}
                        for e in s.evidence
                    ]
                }
                for s in suggestions
            ],
            "suggested_rules": report.get("suggested_rules", []),
            "cases": report.get("cases", [])
        }


# Global instance
agent_brain = AgentFeedbackAnalyzer()
