"""
LangChain @tool wrappers for the Feedback Agent.

These wrap the manager classes (SynonymManager, PatternManager,
ThresholdOverrideManager, AgentKnowledgeMemory, RulesEngine) so the
LangChain agent can call them natively via tool-calling.

Usage in an agent::

    from app.feature.feature_up_cv.feedback_agent.langchain_tools import (
        build_tool_set,
    )
    tools = build_tool_set()
    # -> List[BaseTool] ready for create_agent(llm, tools)
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


# ── Synonym tools ───────────────────────────────────────────────
@tool
def yaml_add_synonyms(items: List[Dict[str, str]]) -> str:
    """
    Add new skill synonym pairs to the YAML knowledge base.

    Each item is a dict with keys ``base_skill`` and ``synonym``.
    Example: ``[{"base_skill": "express.js", "synonym": "nest.js"}]``.

    Returns a short status string suitable for LLM context.
    """
    from .synonym_manager import get_synonym_manager

    manager = get_synonym_manager()
    count, added = manager.add_synonyms(items)
    if count == 0:
        return f"No new synonyms added (all duplicates or invalid). Existing: {len(manager.load_synonyms())}"
    return f"Added {count} new synonym pair(s): {added}"


# ── Pattern tools ────────────────────────────────────────────────
@tool
def yaml_add_patterns(items: List[Dict[str, Any]]) -> str:
    """
    Add new skill patterns to ``skill_patterns.yaml``.

    Each item is a dict with ``type`` = ``compound_skill`` or
    ``context_phrase`` and the corresponding fields. See
    ``pattern_manager.PatternManager`` for full schema.
    """
    from .pattern_manager import get_pattern_manager
    from app.feature.feature_up_cv.scoring._scores._shared import (
        reload_skill_patterns,
    )

    manager = get_pattern_manager()
    count, added = manager.add_patterns(items)
    if count == 0:
        return "No new patterns added (all duplicates or invalid)."
    reload_skill_patterns()  # bust the cache so next scoring sees them
    return f"Added {count} new pattern(s): {added}"


# ── Threshold tools ──────────────────────────────────────────────
@tool
def yaml_set_threshold(category: str, perfect_match: float, relevant_match: float, note: str = "") -> str:
    """
    Override perfect/relevant-match thresholds for a category.

    ``category`` ∈ {default, technical_skill, tool, skill, soft_skill,
    culture, language, responsibility, experience}. Values are in
    [0.0, 1.0].
    """
    from .threshold_manager import get_threshold_manager

    manager = get_threshold_manager()
    ok, msg = manager.set_override(
        category=category,
        perfect_match=perfect_match,
        relevant_match=relevant_match,
        note=note,
    )
    return f"OK: {msg}" if ok else f"ERROR: {msg}"


# ── FAISS memory tools ───────────────────────────────────────────
@tool
def faiss_add_learned_rule(rule_text: str, threshold_adjustments: Optional[Dict[str, Dict[str, float]]] = None) -> str:
    """
    Persist a learned rule to FAISS memory for future semantic recall.

    ``rule_text`` should be a short, generalisable sentence. Optional
    ``threshold_adjustments`` mirrors the
    ``FeedbackEvaluation.threshold_adjustments`` payload.
    """
    from .memory_faiss import get_agent_memory

    context: Dict[str, Any] = {"source": "feedback_agent"}
    if threshold_adjustments:
        context["threshold_adjustments"] = threshold_adjustments
    memory = get_agent_memory()
    row_id = memory.add_learned_rule(rule_text=rule_text, context=context)
    if row_id is None:
        return "ERROR: failed to embed / store rule (no embedder or FAISS)."
    return f"Stored rule #{row_id}"


@tool
def faiss_search_similar_rules(query: str, k: int = 3) -> str:
    """Return the top-k learned rules semantically similar to ``query``."""
    from .memory_faiss import get_agent_memory

    memory = get_agent_memory()
    results = memory.search_similar_rules(query=query, k=k)
    if not results:
        return "No prior rules found."
    return json.dumps(
        [
            {"rule": r.get("rule", ""), "score": round(score, 3)}
            for r, score in results
        ],
        ensure_ascii=False,
    )


# ── Rules engine tools (Hướng 3: propose new rule type) ─────────
@tool
def rules_propose_new_rule_type(
    rule_type: str,
    description: str,
    condition: Dict[str, Any],
    action: Dict[str, Any],
    priority: int = 50,
    confidence: float = 0.5,
) -> str:
    """
    Persist a *structured* proposed rule type to FAISS (Hướng 3).

    Unlike ``faiss_add_learned_rule`` (text-only), this tool records a
    full rule schema so the rules engine can later apply it. The
    persistence format is JSON-compatible with
    ``_rules_engine.parse_rule``.
    """
    from .memory_faiss import get_agent_memory

    payload: Dict[str, Any] = {
        "rule_type": rule_type,
        "description": description,
        "condition": condition,
        "action": action,
        "priority": int(priority),
        "confidence": float(confidence),
    }
    text = (
        f"[PROPOSED RULE] type={rule_type}; description={description}; "
        f"action={action.get('type', 'unknown')}"
    )
    memory = get_agent_memory()
    row_id = memory.add_learned_rule(
        rule_text=text,
        context={"source": "feedback_agent", "structured_rule": payload},
    )
    if row_id is None:
        return "ERROR: failed to store structured rule."
    return f"Stored structured rule #{row_id} (type={rule_type}, priority={priority})"


# ── Company research tool (Hướng 7) ──────────────────────────────
@tool
def company_research_if_missing(company_name: str, jd_text: str) -> str:
    """
    Look up company info on the parser service.

    Returns a compact JSON blob with industry / tech stack / size, or
    a clear error message if the company name is missing.
    """
    from app.feature.feature_up_cv.parsers.parser_company import (
        llm_parser_company,
    )

    if not company_name or not company_name.strip():
        return json.dumps({"ok": False, "reason": "no_company_name"})
    blob = jd_text or f"Company: {company_name}"
    info = llm_parser_company(blob)
    if not info.get("success"):
        return json.dumps(
            {"ok": False, "company": company_name, "reason": info.get("error", "parser_failed")}
        )
    return json.dumps(
        {
            "ok": True,
            "company": info.get("company_name", company_name),
            "industry": info.get("industry", ""),
            "key_skills": info.get("key_skills", []),
            "company_size": info.get("company_size", ""),
        },
        ensure_ascii=False,
    )


# ── Implied fields tool (Hướng 5) ────────────────────────────────
@tool
def jd_infer_implied_fields(jd_struct_json: str) -> str:
    """
    Scan a JD struct (as a JSON string) and back-fill any missing
    ``seniority`` / ``years_of_experience`` values from implicit text
    signals. Returns the resulting JSON.
    """
    from .implied_fields import backfill_jd_struct

    try:
        jd_struct = json.loads(jd_struct_json) if jd_struct_json else {}
    except json.JSONDecodeError as e:
        return json.dumps({"ok": False, "error": f"invalid_json: {e}"})
    out = backfill_jd_struct(jd_struct, overwrite=False)
    return json.dumps(
        {
            "ok": True,
            "imputed": {
                "seniority": out.get("seniority"),
                "years_of_experience": out.get("years_of_experience"),
            },
        },
        ensure_ascii=False,
    )


# ── Bundle ───────────────────────────────────────────────────────
def build_tool_set() -> List[Any]:
    """Return the full tool list the agent exposes to the LLM."""
    return [
        yaml_add_synonyms,
        yaml_add_patterns,
        yaml_set_threshold,
        faiss_add_learned_rule,
        faiss_search_similar_rules,
        rules_propose_new_rule_type,
        company_research_if_missing,
        jd_infer_implied_fields,
    ]
