# -*- coding: utf-8 -*-
"""
Rules Scoring Engine v2 - Áp dụng learned rules vào scoring

Cải tiến:
- Career change rules: Áp dụng penalty bất kể exp score
- Entry level bonus cap: Giới hạn tổng bonus tối đa
- Structured rule format support
- Priority-based rule application
"""
import re
import logging
from typing import Dict, List, Any, Tuple, Optional

logger = logging.getLogger(__name__)

# Constants for bonus caps
MAX_EXPERIENCE_SCORE = 50
ENTRY_LEVEL_BONUS_CAP = 25  # Max bonus for entry level
CAREER_CHANGE_PENALTY_MIN = 0.3  # 30% penalty minimum for career change


def parse_rule(rule_data: Any) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    """
    Parse a rule from either string text or structured dict.

    Returns: (rule_type, params)
    """
    # If rule is a dict with structured format
    if isinstance(rule_data, dict):
        rule_type = rule_data.get("rule_type", rule_data.get("type", ""))
        action = rule_data.get("action", {})
        condition = rule_data.get("condition", {})

        params = {
            "rule_id": rule_data.get("rule_id", ""),
            "priority": rule_data.get("priority", 50),
            "confidence": rule_data.get("confidence", 0.5),
            "action": action,
            "condition": condition,
        }

        # Parse action
        if action.get("type") == "bonus":
            params["bonus_value"] = action.get("value", action.get("min_value", 0))
            params["bonus_max"] = action.get("max", ENTRY_LEVEL_BONUS_CAP)
        elif action.get("type") == "penalty":
            params["penalty_percent"] = action.get("percent", action.get("penalty_percent", 0.3))

        return rule_type, params

    # If rule is a string (legacy format)
    rule_text = str(rule_data)
    return parse_rule_from_text(rule_text)


def parse_rule_from_text(rule_text: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    """
    Parse a learned rule text and return rule_type and parameters.

    Các rule types:
    - FRESH_GRAD_PROJECT_BONUS: +15-25 điểm experience cho fresh grad có projects
    - DOMAIN_EXPERIENCE_PENALTY: -40-60% điểm experience khi domain khác nhau
    - SEVERE_DOMAIN_MISMATCH: Giới hạn experience score và áp dụng domain penalty
    - ENTRY_LEVEL_INTERNSHIP: Tính internship như experience
    - CAREER_CHANGE_PENALTY: Penalty cho career change bất kể exp score
    """
    rule_text_lower = rule_text.lower()

    # FRESH_GRAD_PROJECT_BONUS
    if "fresh_grad" in rule_text_lower or "project_bonus" in rule_text_lower:
        return "FRESH_GRAD_PROJECT_BONUS", {
            "bonus_base": 15,
            "bonus_range": (15, 25),
            "per_project_bonus": (5, 8)
        }

    # CAREER_CHANGE_PENALTY - Cải tiến: áp dụng bất kể exp score
    if "career_change" in rule_text_lower:
        match = re.search(r'(\d+)-(\d+)%', rule_text)
        if match:
            min_penalty = int(match.group(1)) / 100
            max_penalty = int(match.group(2)) / 100
        else:
            min_penalty, max_penalty = 0.55, 0.65  # Default: 55-65%
        return "CAREER_CHANGE_PENALTY", {
            "penalty_range": (min_penalty, max_penalty),
            "apply_always": True  # Áp dụng bất kể exp score
        }

    # DOMAIN_EXPERIENCE_PENALTY
    if "domain_experience_penalty" in rule_text_lower or "domain penalty" in rule_text_lower:
        match = re.search(r'(\d+)-(\d+)%', rule_text)
        if match:
            min_penalty = int(match.group(1)) / 100
            max_penalty = int(match.group(2)) / 100
        else:
            min_penalty, max_penalty = 0.4, 0.6
        return "DOMAIN_EXPERIENCE_PENALTY", {
            "penalty_range": (min_penalty, max_penalty)
        }

    # SEVERE_DOMAIN_MISMATCH
    if "severe_domain_mismatch" in rule_text_lower or ("sales" in rule_text_lower and "tech_backend" in rule_text_lower):
        return "SEVERE_DOMAIN_MISMATCH", {
            "max_experience_score": 15,
            "domain_penalty": -0.5
        }

    # ENTRY_LEVEL_INTERNSHIP - Cải tiến: có bonus cap
    if "entry_level_internship" in rule_text_lower or "internship" in rule_text_lower:
        return "ENTRY_LEVEL_INTERNSHIP", {
            "internship_years_equiv": (0.5, 1.0),
            "per_project_bonus": 5,
            "bonus_cap": ENTRY_LEVEL_BONUS_CAP  # Max bonus cap
        }

    return None, None


def apply_learned_rules(
    cv_data: dict,
    jd_data: dict,
    learned_knowledge: dict,
    exp_score: float,
    skills_score: float,
    domain_penalty: float,
    domain_penalty_reason: str,
    total_work_years: float,
    project_years: float,
) -> Tuple[float, float, float, str, str]:
    """
    Apply learned rules to adjust scores.

    Returns: (adjusted_exp_score, adjusted_skills_score, adjusted_domain_penalty,
              new_domain_penalty_reason, rules_applied)
    """
    if not learned_knowledge or "rules" not in learned_knowledge:
        return exp_score, skills_score, domain_penalty, domain_penalty_reason, ""

    rules_data = learned_knowledge["rules"]
    if not rules_data:
        return exp_score, skills_score, domain_penalty, domain_penalty_reason, ""

    rules_text = []
    adjusted_exp = exp_score
    adjusted_skill = skills_score
    adjusted_domain_penalty = domain_penalty
    new_domain_reason = domain_penalty_reason

    # Track total bonus for entry level cap
    total_bonus_applied = 0.0

    for rule_data in rules_data:
        rule_type, params = parse_rule(rule_data)

        if rule_type is None:
            continue

        # FRESH_GRAD_PROJECT_BONUS
        if rule_type == "FRESH_GRAD_PROJECT_BONUS":
            result = _apply_fresh_grad_bonus(cv_data, jd_data, adjusted_exp, params)
            if result:
                bonus, message = result
                # Apply bonus cap
                if total_bonus_applied + bonus > ENTRY_LEVEL_BONUS_CAP:
                    bonus = max(0, ENTRY_LEVEL_BONUS_CAP - total_bonus_applied)
                    message += f" (bị giới hạn bởi cap {ENTRY_LEVEL_BONUS_CAP})"
                adjusted_exp = min(adjusted_exp + bonus, MAX_EXPERIENCE_SCORE)
                total_bonus_applied += bonus
                rules_text.append(message)

        # CAREER_CHANGE_PENALTY - Cải tiến: áp dụng bất kể exp score
        elif rule_type == "CAREER_CHANGE_PENALTY":
            result = _apply_career_change_penalty(cv_data, jd_data, adjusted_exp, params)
            if result:
                penalty_amount, message = result
                adjusted_exp = max(adjusted_exp - penalty_amount, 0)
                rules_text.append(message)

        # DOMAIN_EXPERIENCE_PENALTY
        elif rule_type == "DOMAIN_EXPERIENCE_PENALTY":
            result = _apply_domain_penalty(cv_data, jd_data, adjusted_exp, params)
            if result:
                penalty_amount, message = result
                adjusted_exp = max(adjusted_exp - penalty_amount, 0)
                rules_text.append(message)

        # SEVERE_DOMAIN_MISMATCH
        elif rule_type == "SEVERE_DOMAIN_MISMATCH":
            result = _apply_severe_domain_mismatch(cv_data, adjusted_exp, adjusted_domain_penalty, jd_data, params)
            if result:
                new_exp, new_penalty, message = result
                adjusted_exp = new_exp
                adjusted_domain_penalty = new_penalty
                new_domain_reason = message
                rules_text.append(message)

        # ENTRY_LEVEL_INTERNSHIP - Cải tiến: có bonus cap
        elif rule_type == "ENTRY_LEVEL_INTERNSHIP":
            result = _apply_entry_level_bonus(cv_data, jd_data, adjusted_exp, total_bonus_applied, params)
            if result:
                bonus, message, new_total_bonus = result
                adjusted_exp = min(adjusted_exp + bonus, MAX_EXPERIENCE_SCORE)
                total_bonus_applied = new_total_bonus
                rules_text.append(message)

    rules_applied = " | ".join(r for r in rules_text if isinstance(r, str))
    return adjusted_exp, adjusted_skill, adjusted_domain_penalty, new_domain_reason, rules_applied


def _apply_fresh_grad_bonus(cv_data: dict, jd_data: dict, current_exp: float, params: dict) -> Optional[Tuple[float, str]]:
    """Apply fresh grad project bonus"""
    is_student = cv_data.get("is_student", False)
    projects = cv_data.get("projects", [])
    jd_skills = [s.get("requirement", "").lower() if isinstance(s, dict) else str(s).lower()
                for s in jd_data.get("skills_required", [])]

    if not (is_student and projects):
        return None

    # Count relevant projects
    relevant_projects = 0
    for proj in projects:
        proj_techs = [t.lower() for t in proj.get("technologies", [])]
        proj_desc = proj.get("description", "").lower()

        for jd_skill in jd_skills:
            if any(jd_skill in tech or jd_skill in proj_desc for tech in proj_techs):
                relevant_projects += 1
                break

    if relevant_projects == 0:
        return None

    min_bonus = params.get("bonus_base", 15)
    per_project = params.get("per_project_bonus", (5, 8))

    # Calculate bonus: base + per project
    base_bonus = min_bonus
    project_bonus = relevant_projects * ((per_project[0] + per_project[1]) / 2)
    total_bonus = min(base_bonus + project_bonus, params.get("bonus_range", (15, 25))[1])

    message = f"FRESH_GRAD_PROJECT_BONUS: +{total_bonus:.1f} điểm experience cho {relevant_projects} projects liên quan"
    return total_bonus, message


def _apply_career_change_penalty(cv_data: dict, jd_data: dict, current_exp: float, params: dict) -> Optional[Tuple[float, str]]:
    """
    Apply career change penalty.
    Cải tiến: Áp dụng penalty bất kể exp score nếu domain khác nhau rõ ràng.
    """
    cv_domain = cv_data.get("domain", "unknown")
    jd_domain = jd_data.get("domain", jd_data.get("structured", {}).get("domain", "unknown"))

    # Career change = domain khác nhau rõ ràng (tech vs non-tech)
    non_tech_domains = ["marketing", "sales", "finance", "hr", "operations"]
    tech_domains = ["tech_ai", "tech_backend", "tech_frontend", "tech_data", "tech_devops"]

    is_career_change = False

    # Case 1: Non-tech CV apply for tech JD
    if cv_domain in non_tech_domains and jd_domain in tech_domains:
        is_career_change = True
    # Case 2: Tech CV apply for non-tech JD
    elif cv_domain in tech_domains and jd_domain in non_tech_domains:
        is_career_change = True

    if not is_career_change:
        return None

    # Apply penalty
    penalty_range = params.get("penalty_range", (0.55, 0.65))
    penalty_percent = (penalty_range[0] + penalty_range[1]) / 2  # Mid-range
    penalty_amount = current_exp * penalty_percent

    message = f"CAREER_CHANGE_PENALTY: -{penalty_percent*100:.0f}% ({penalty_amount:.1f} điểm) vì career change: {cv_domain} → {jd_domain}"
    return penalty_amount, message


def _apply_domain_penalty(cv_data: dict, jd_data: dict, current_exp: float, params: dict) -> Optional[Tuple[float, str]]:
    """Apply domain experience penalty for domain mismatch"""
    cv_domain = cv_data.get("domain", "unknown")
    jd_domain = jd_data.get("domain", jd_data.get("structured", {}).get("domain", "unknown"))

    if cv_domain == jd_domain or cv_domain == "unknown" or jd_domain == "unknown":
        return None

    # Only apply if both are tech domains (same category)
    tech_domains = ["tech_ai", "tech_backend", "tech_frontend", "tech_data", "tech_devops"]
    if cv_domain in tech_domains and jd_domain in tech_domains:
        penalty_range = params.get("penalty_range", (0.4, 0.6))
        penalty = (penalty_range[0] + penalty_range[1]) / 2
        penalty_amount = current_exp * penalty
        message = f"DOMAIN_EXPERIENCE_PENALTY: -{penalty*100:.0f}% ({penalty_amount:.1f} điểm) vì domain CV={cv_domain} khác JD={jd_domain}"
        return penalty_amount, message

    return None


def _apply_severe_domain_mismatch(
    cv_data: dict,
    current_exp: float,
    current_domain_penalty: float,
    jd_data: dict,
    params: dict
) -> Optional[Tuple[float, float, str]]:
    """Apply severe domain mismatch penalty"""
    cv_domain = cv_data.get("domain", "unknown")
    max_exp_score = params.get("max_experience_score", 15)

    if cv_domain != "sales" and "sales" not in cv_domain.lower():
        return None

    # Check if CV has tech skills that match JD
    jd_skills = [s.get("requirement", "").lower() if isinstance(s, dict) else str(s).lower()
                for s in jd_data.get("skills_required", [])]
    cv_skills = [s.lower() for s in cv_data.get("skills", [])]

    tech_matches = sum(1 for jd_skill in jd_skills
                     if any(jd_skill in cv_skill or cv_skill in jd_skill for cv_skill in cv_skills))

    if tech_matches > 0:
        return None  # Has some tech skills, don't apply severe penalty

    # Apply severe penalty
    new_exp = min(current_exp, max_exp_score)
    extra_penalty = params.get("domain_penalty", -0.5)
    new_domain_penalty = min(current_domain_penalty + extra_penalty, -1.0)
    message = f"Domain mismatch nghiêm trọng: CV là {cv_domain}, JD là tech_backend"

    return new_exp, new_domain_penalty, message


def _apply_entry_level_bonus(
    cv_data: dict,
    jd_data: dict,
    current_exp: float,
    total_bonus_applied: float,
    params: dict
) -> Optional[Tuple[float, str, float]]:
    """
    Apply entry level internship bonus.
    Cải tiến: Có bonus cap để tránh bonus quá nhiều.
    """
    is_student = cv_data.get("is_student", False)
    work_exp = cv_data.get("work_experience", [])
    projects = cv_data.get("projects", [])

    if not (is_student and (work_exp or projects)):
        return None

    bonus_cap = params.get("bonus_cap", ENTRY_LEVEL_BONUS_CAP)
    total_bonus = total_bonus_applied
    messages = []

    # Bonus for internships
    internship_count = 0
    for exp in work_exp:
        title = exp.get("title", "").lower()
        company = exp.get("company", "").lower()
        if "intern" in title or "thực tập" in title or "internship" in company:
            internship_count += 1

    if internship_count > 0:
        years_range = params.get("internship_years_equiv", (0.5, 1.0))
        years_equiv = (years_range[0] + years_range[1]) / 2 * internship_count
        internship_bonus = years_equiv * 10
        total_bonus += internship_bonus
        messages.append(f"{internship_bonus:.1f}đ internship")

    # Bonus for relevant projects (capped)
    if projects:
        jd_skills = [s.get("requirement", "").lower() if isinstance(s, dict) else str(s).lower()
                    for s in jd_data.get("skills_required", [])]

        for proj in projects:
            proj_techs = [t.lower() for t in proj.get("technologies", [])]
            proj_desc = proj.get("description", "").lower()

            for jd_skill in jd_skills:
                if any(jd_skill in tech or jd_skill in proj_desc for tech in proj_techs):
                    project_bonus = params.get("per_project_bonus", 5)
                    total_bonus += project_bonus
                    messages.append(f"{project_bonus}đ proj")
                    break

    if total_bonus == total_bonus_applied:
        return None

    # Apply cap
    capped_bonus = total_bonus - total_bonus_applied
    if total_bonus > bonus_cap:
        capped_bonus = max(0, bonus_cap - total_bonus_applied)

    if capped_bonus <= 0:
        return None

    message = f"ENTRY_LEVEL_INTERNSHIP: +{capped_bonus:.1f} điểm ({', '.join(messages)})"
    return capped_bonus, message, total_bonus
