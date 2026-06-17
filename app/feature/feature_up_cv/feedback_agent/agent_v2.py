"""
Phase 5 — React-style agent using LangGraph prebuilt ``create_react_agent``.

The original ``agent.py`` module uses a one-shot LLM call plus a hand-
written JSON parser. ``FeedbackAgentV2`` instead drives an actual
ReAct loop:

    1. LLM is given system + user prompt + the tool set.
    2. LLM decides whether to call a tool (e.g. faiss_search_similar_rules)
       or to produce the final ``FeedbackEvaluation`` JSON.
    3. The agent loop terminates when the LLM emits a parseable
       ``FeedbackEvaluation`` (or after a max-step cap).

This module preserves backward-compat:

  * ``FeedbackAgent`` (the existing one-shot) keeps working.
  * ``FeedbackAgentV2`` is the new ReAct style. Service layer is
    expected to swap to V2 once the project moves off Phase 1/2
    code paths.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.graph.message import add_messages
from typing_extensions import Annotated, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage

from .langchain_adapter import get_gemini_chat_model
from .langchain_tools import build_tool_set
from .observability import trace_agent_call
from .prompts import (
    FeedbackEvaluation,
    SYSTEM_PROMPT_EVALUATOR,
    build_user_prompt,
)

logger = logging.getLogger(__name__)


# ── State ────────────────────────────────────────────────────────
class ReactState(TypedDict, total=False):
    messages: Annotated[List[BaseMessage], add_messages]
    evaluation: Optional[FeedbackEvaluation]
    error: Optional[str]
    steps: int


_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def _extract_json_block(text: str) -> Optional[str]:
    if not text:
        return None
    m = _FENCE_RE.search(text)
    if m:
        candidate = m.group(1).strip()
        if candidate.startswith("{"):
            return candidate
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            ch = text[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
        start = text.find("{", start + 1)
    return None


# ── V2: ReAct agent factory ──────────────────────────────────────
_MAX_STEPS = 6


def _build_v2_chat():
    """Return a Gemini chat model that the LangGraph agent will drive."""
    return get_gemini_chat_model(step="feedback_agent_v2_react")


def _node_call_llm(state: ReactState) -> ReactState:
    chat = _build_v2_chat()
    tools = build_tool_set()
    chat_with_tools = chat.bind_tools(tools)

    msgs: List[BaseMessage] = list(state.get("messages", []))
    try:
        resp = chat_with_tools.invoke(msgs)
    except Exception as e:
        logger.error("[ReactAgent] LLM call failed: %s", e)
        return {
            "messages": [AIMessage(content=f"LLM error: {e}")],
            "error": f"llm_failed: {e}",
        }
    return {"messages": [resp], "steps": int(state.get("steps", 0)) + 1}


def _node_should_continue(state: ReactState) -> str:
    if state.get("error"):
        return END
    if int(state.get("steps", 0)) >= _MAX_STEPS:
        logger.warning("[ReactAgent] max steps reached")
        return END
    last = state["messages"][-1] if state.get("messages") else None
    if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
        return "tools"
    return END


def _node_finalize(state: ReactState) -> ReactState:
    """
    Walk backwards through the messages and try to find a valid
    ``FeedbackEvaluation`` JSON blob. We accept the last AIMessage
    that contains parseable JSON.
    """
    ev: Optional[FeedbackEvaluation] = None
    for msg in reversed(state.get("messages", [])):
        if not isinstance(msg, AIMessage):
            continue
        text = msg.content if isinstance(msg.content, str) else str(msg.content)
        candidate = _extract_json_block(text) or text
        try:
            data = json.loads(candidate)
        except Exception:
            continue
        try:
            ev = FeedbackEvaluation.model_validate(data)
            break
        except Exception:
            continue
    if ev is None:
        # DEBUG: dump last AI message for visibility
        for m in reversed(state.get("messages", [])):
            if isinstance(m, AIMessage):
                logger.warning(
                    "[ReactAgent] no valid evaluation; last AI content: %r",
                    m.content[:500] if isinstance(m.content, str) else str(m.content)[:500],
                )
                break
        return {
            "evaluation": FeedbackEvaluation(
                is_valid_complaint=False,
                rationale=(
                    "Hệ thống AI không trả về JSON hợp lệ sau khi dùng tool. "
                    "Vui lòng thử lại."
                ),
            ),
            "error": "no_valid_evaluation",
        }
    return {"evaluation": ev}


def build_react_graph():
    tools = build_tool_set()
    g = StateGraph(ReactState)
    g.add_node("agent", _node_call_llm)
    g.add_node("tools", ToolNode(tools))
    g.add_node("finalize", _node_finalize)

    g.set_entry_point("agent")
    g.add_conditional_edges(
        "agent",
        _node_should_continue,
        {"tools": "tools", END: "finalize"},
    )
    g.add_edge("tools", "agent")
    g.add_edge("finalize", END)
    return g.compile()


_graph_singleton = None


def get_react_graph():
    global _graph_singleton
    if _graph_singleton is None:
        _graph_singleton = build_react_graph()
    return _graph_singleton


# ── V2 facade ────────────────────────────────────────────────────
class FeedbackAgentV2:
    """
    ReAct-style Feedback Agent (Phase 5).

    The caller can swap to this class by replacing the ``FeedbackAgent``
    import in ``score_feedback_service``. Until then, this class is
    available for direct unit testing.
    """

    def __init__(self, model: Optional[str] = None) -> None:
        self.model = model  # unused for now, kept for parity

    @trace_agent_call(name="feedback_agent.evaluate_v2")
    async def evaluate(
        self,
        cv_text: str,
        jd_text: str,
        feedback_text: str,
        current_scores: Optional[Dict[str, float]] = None,
    ) -> FeedbackEvaluation:
        graph = get_react_graph()
        user_prompt = build_user_prompt(
            cv_text=cv_text,
            jd_text=jd_text,
            feedback_text=feedback_text,
            current_scores=current_scores,
        )
        init: ReactState = {
            "messages": [
                SystemMessage(content=SYSTEM_PROMPT_EVALUATOR),
                HumanMessage(content=user_prompt),
            ],
            "steps": 0,
        }
        result = await graph.ainvoke(init)
        ev: FeedbackEvaluation = result.get("evaluation")  # type: ignore[assignment]
        if ev is None:
            return FeedbackEvaluation(
                is_valid_complaint=False,
                rationale="Hệ thống AI không phản hồi, vui lòng thử lại.",
            )
        return ev

    async def evaluate_with_trace(
        self,
        cv_text: str,
        jd_text: str,
        feedback_text: str,
        current_scores: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """Return both the evaluation and the full message trace (for tests / UI)."""
        graph = get_react_graph()
        user_prompt = build_user_prompt(
            cv_text=cv_text,
            jd_text=jd_text,
            feedback_text=feedback_text,
            current_scores=current_scores,
        )
        init: ReactState = {
            "messages": [
                SystemMessage(content=SYSTEM_PROMPT_EVALUATOR),
                HumanMessage(content=user_prompt),
            ],
            "steps": 0,
        }
        result = await graph.ainvoke(init)
        return {
            "evaluation": result.get("evaluation"),
            "messages": [
                {
                    "type": m.__class__.__name__,
                    "content": m.content if isinstance(m.content, str) else str(m.content),
                    "tool_calls": getattr(m, "tool_calls", None),
                }
                for m in result.get("messages", [])
                if m.__class__.__name__ in {"AIMessage", "ToolMessage"}
            ],
            "steps": result.get("steps", 0),
            "error": result.get("error"),
        }

    def apply_learning(
        self,
        evaluation: FeedbackEvaluation,
    ) -> Dict[str, Any]:
        """
        Execute the side effects declared in the evaluation.

        The V2 ReAct loop may have *also* called the relevant tools during
        the agent run, but in that case the YAML/FAISS state has already
        been mutated in-place. ``apply_learning`` is idempotent: re-running
        it on an evaluation whose tools already wrote the new entries will
        just de-duplicate and report zero new items.
        """
        from .pattern_manager import get_pattern_manager
        from .synonym_manager import get_synonym_manager
        from .threshold_manager import get_threshold_manager
        from app.feature.feature_up_cv.scoring._scores._shared import (
            reload_skill_patterns,
        )

        result: Dict[str, Any] = {
            "synonyms_added": [],
            "patterns_added": [],
            "thresholds_applied": [],
            "learned_rule_row_id": None,
            "learned_rule": evaluation.learned_rule,
            "proposed_overrides": evaluation.proposed_overrides,
        }

        # 1) Synonyms
        if evaluation.new_synonyms:
            try:
                manager = get_synonym_manager()
                count, added = manager.add_synonyms(evaluation.new_synonyms)
                result["synonyms_added"] = added
                logger.info(
                    "[FeedbackAgentV2] added %d new synonym pair(s) to YAML",
                    count,
                )
            except Exception as e:
                logger.error("[FeedbackAgentV2] failed to add synonyms: %s", e)
                result["synonyms_added_error"] = str(e)

        # 1b) Patterns
        if evaluation.new_patterns:
            try:
                pm = get_pattern_manager()
                count, added = pm.add_patterns(evaluation.new_patterns)
                result["patterns_added"] = added
                reload_skill_patterns()
            except Exception as e:
                logger.error("[FeedbackAgentV2] failed to add patterns: %s", e)
                result["patterns_added_error"] = str(e)

        # 1c) Thresholds
        if evaluation.threshold_adjustments:
            try:
                tm = get_threshold_manager()
                applied: List[Dict[str, Any]] = []
                for cat, payload in evaluation.threshold_adjustments.items():
                    if not isinstance(payload, dict):
                        continue
                    ok, msg = tm.set_override(
                        category=cat,
                        perfect_match=payload.get("perfect_match"),
                        relevant_match=payload.get("relevant_match"),
                        note=str(payload.get("note", "")),
                    )
                    if ok:
                        applied.append({"category": cat, **payload})
                result["thresholds_applied"] = applied
            except Exception as e:
                logger.error("[FeedbackAgentV2] failed to apply thresholds: %s", e)
                result["thresholds_applied_error"] = str(e)

        # 2) Learned rule → FAISS
        if evaluation.learned_rule and evaluation.learned_rule.strip():
            try:
                from .memory_faiss import get_agent_memory

                memory = get_agent_memory()
                rule_context: Dict[str, Any] = {"source": "feedback_agent_v2"}
                if evaluation.threshold_adjustments:
                    rule_context["threshold_adjustments"] = (
                        evaluation.threshold_adjustments
                    )
                row_id = memory.add_learned_rule(
                    rule_text=evaluation.learned_rule,
                    context=rule_context,
                )
                result["learned_rule_row_id"] = row_id
            except Exception as e:
                logger.error("[FeedbackAgentV2] failed to store learned_rule: %s", e)
                result["learned_rule_error"] = str(e)

        # 3) Pending rule (Phase 7)
        if evaluation.proposed_new_rule_type:
            try:
                from .pending_rules import get_pending_rule_store

                store = get_pending_rule_store()
                rid = store.enqueue(
                    rule_payload=evaluation.proposed_new_rule_type,
                    proposed_by="agent_v2",
                    rationale=evaluation.rationale or "",
                )
                result["pending_rule_id"] = rid
                result["pending_rule_status"] = "pending_review"
            except Exception as e:
                logger.error("[FeedbackAgentV2] failed to enqueue pending rule: %s", e)
                result["pending_rule_error"] = str(e)

        return result


# ── Module-level singleton ────────────────────────────────────────────────
_agent_v2: Optional[FeedbackAgentV2] = None


def get_feedback_agent() -> FeedbackAgentV2:
    """
    Singleton accessor — the service layer calls this name regardless
    of which agent version is active. As of Phase 6 the implementation
    is the ReAct-style ``FeedbackAgentV2``.
    """
    global _agent_v2
    if _agent_v2 is None:
        _agent_v2 = FeedbackAgentV2()
    return _agent_v2
