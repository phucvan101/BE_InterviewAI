"""
LangChain adapter for Gemini.

Wraps the existing ``gemini_client.generate_content`` so the rest of
the project can keep its retry / quota / key-rotation logic, while the
LangChain layer treats Gemini as a ``BaseChatModel``-shaped object that
can be plugged into chains, agents, and LangGraph.

This avoids requiring ``langchain-google-genai`` (which isn't installed)
and keeps the surface small: ``invoke()`` and ``ainvoke()`` are
enough for ``create_agent`` / ``with_structured_output``.

Tool-calling strategy (since Gemini is reached via plain text):
  * ``bind_tools(tools)`` returns a thin wrapper that injects a
    *tool list* into the system prompt and parses the LLM's reply
    for ``TOOL_CALL: name{json_args}`` markers to populate
    ``AIMessage.tool_calls``.
  * This is intentionally simple and works with the free Gemini
    endpoint — no function-calling API needed.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Type, TypeVar

from pydantic import BaseModel

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable, RunnableLambda

logger = logging.getLogger(__name__)

_T = TypeVar("_T", bound=BaseModel)

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)

# Match an LLM-emitted tool call of the form:
#   TOOL_CALL: tool_name{ "arg": "value" }
# or:
#   ```json
#   {"name": "tool_name", "arguments": {...}}
#   ```
_TOOL_CALL_RE = re.compile(
    r"TOOL_CALL\s*:\s*([a-zA-Z_][\w\.]*)\s*(\{.*?\})",
    re.DOTALL,
)
_TOOL_CALL_JSON_RE = re.compile(
    r"\{\s*\"name\"\s*:\s*\"([a-zA-Z_][\w\.]*)\"\s*,\s*\"arguments\"\s*:\s*(\{.*?\})\s*\}",
    re.DOTALL,
)


def _extract_json_block(text: str) -> Optional[str]:
    """Best-effort JSON object extraction from an LLM response."""
    if not text:
        return None
    m = _FENCE_RE.search(text)
    if m:
        candidate = m.group(1).strip()
        if candidate.startswith("{"):
            return candidate
        if candidate.startswith("["):
            return candidate
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
        start = text.find("{", start + 1)
    return None


def _messages_to_prompt(messages: List[BaseMessage]) -> str:
    """Flatten a list of LangChain messages into a single prompt string."""
    chunks: List[str] = []
    for m in messages:
        if isinstance(m, SystemMessage):
            chunks.append(f"[SYSTEM]\n{m.content}\n[/SYSTEM]")
        elif isinstance(m, HumanMessage):
            chunks.append(f"[USER]\n{m.content}\n[/USER]")
        elif isinstance(m, AIMessage):
            chunks.append(f"[ASSISTANT]\n{m.content}\n[/ASSISTANT]")
        else:
            chunks.append(str(m.content))
    return "\n\n".join(chunks)


def _format_tools_for_prompt(tools: List[Any]) -> str:
    """Render a tool list as a system prompt block the LLM can read."""
    lines: List[str] = ["[TOOLS_AVAILABLE]"]
    for t in tools:
        name = getattr(t, "name", None) or getattr(t, "__name__", "tool")
        desc = (getattr(t, "description", "") or "").strip()
        # Try to extract the args_schema to show expected args
        args_schema = getattr(t, "args_schema", None)
        if args_schema is not None and hasattr(args_schema, "schema"):
            try:
                schema = args_schema.schema()
                fields = schema.get("properties", {})
                if fields:
                    args_str = ", ".join(
                        f"{k}: {v.get('type', 'any')}" for k, v in fields.items()
                    )
                else:
                    args_str = "(no args)"
            except Exception:
                args_str = "(schema unknown)"
        else:
            # Fall back to parsing docstring
            args_str = ""
        lines.append(f"- {name}({args_str})")
        if desc:
            # truncate long descriptions
            if len(desc) > 400:
                desc = desc[:400] + "..."
            lines.append(f"    {desc}")
    lines.append("")
    lines.append("[TOOL_CALL_FORMAT]")
    lines.append(
        "To call a tool, emit EXACTLY one line of the form:\n"
        "  TOOL_CALL: tool_name{ \"arg1\": value, \"arg2\": value }\n"
        "After tool results are returned, you may either call another "
        "tool or emit the final JSON result."
    )
    return "\n".join(lines)


def _parse_tool_calls_from_text(text: str) -> List[Dict[str, Any]]:
    """Scan an LLM reply for tool call markers."""
    calls: List[Dict[str, Any]] = []
    for m in _TOOL_CALL_RE.finditer(text):
        name = m.group(1)
        try:
            args = json.loads(m.group(2))
        except json.JSONDecodeError:
            try:
                # Last-ditch: replace single quotes
                args = json.loads(m.group(2).replace("'", '"'))
            except Exception:
                continue
        calls.append({"id": f"call_{len(calls)}", "name": name, "args": args})
    if calls:
        return calls
    for m in _TOOL_CALL_JSON_RE.finditer(text):
        name = m.group(1)
        try:
            args = json.loads(m.group(2))
        except json.JSONDecodeError:
            continue
        calls.append({"id": f"call_{len(calls)}", "name": name, "args": args})
    return calls


class GeminiChatModel(BaseChatModel):
    """
    LangChain-compatible chat model that delegates to ``gemini_client.generate_content``.

    Only ``invoke`` / ``ainvoke`` are implemented; that is enough for
    ``create_agent`` and ``with_structured_output``. ``bind_tools`` is
    supported via text-mode tool-calling (see module docstring).
    """

    model_name: str = "models/gemini-2.5-flash"
    step: str = "feedback_agent_evaluate"
    temperature: float = 0.0
    _bound_tools: List[Any] = []

    @property
    def _llm_type(self) -> str:
        return "gemini-custom"

    def bind_tools(self, tools: List[Any], **kwargs: Any) -> "GeminiChatModel":
        clone = self.model_copy()
        clone._bound_tools = list(tools or [])
        return clone

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        from app.feature.feature_up_cv.core.gemini_client import (
            GeminiConfig,
            generate_content,
        )

        prompt = _messages_to_prompt(messages)
        if self._bound_tools:
            tool_block = _format_tools_for_prompt(self._bound_tools)
            # Inject tools at the end of the prompt.
            prompt = f"{prompt}\n\n{tool_block}"
        text = generate_content(
            prompt=prompt,
            step=self.step,
            config=GeminiConfig(model=self.model_name, temperature=self.temperature),
        )
        text = text or ""
        tool_calls = _parse_tool_calls_from_text(text) if self._bound_tools else []
        msg = AIMessage(content=text, tool_calls=tool_calls)
        return ChatResult(generations=[ChatGeneration(message=msg)])

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        # The underlying client is sync; run it in a thread to avoid blocking
        # the event loop. The base implementation already does this for us
        # when we only define ``_generate``; for clarity we delegate.
        return await super()._agenerate(
            messages, stop=stop, run_manager=run_manager, **kwargs
        )


class _StructuredOutputRunnable(Runnable):
    """Wraps a chat model so the output is parsed into a Pydantic model."""

    def __init__(self, inner: Runnable, schema: Type[_T]) -> None:
        self.inner = inner
        self.schema = schema

    def invoke(self, input: Any, config: Any = None, **kwargs: Any) -> _T:  # type: ignore[override]
        result: Any = self.inner.invoke(input, config=config, **kwargs)
        return self._coerce(result)

    async def ainvoke(self, input: Any, config: Any = None, **kwargs: Any) -> _T:  # type: ignore[override]
        result: Any = await self.inner.ainvoke(input, config=config, **kwargs)
        return self._coerce(result)

    def _coerce(self, result: Any) -> _T:
        if isinstance(result, BaseMessage):
            text = result.content if isinstance(result.content, str) else str(result.content)
        else:
            text = str(result)
        candidate = _extract_json_block(text) or text
        try:
            data: Dict[str, Any] = json.loads(candidate)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Structured output: JSON parse failed: {e}\nraw: {text[:300]}"
            ) from e
        return self.schema.model_validate(data)


def get_gemini_chat_model(
    model: Optional[str] = None,
    step: str = "feedback_agent_evaluate",
    temperature: float = 0.0,
) -> GeminiChatModel:
    """Return a configured ``GeminiChatModel`` for use in LangChain chains."""
    return GeminiChatModel(
        model_name=model or "models/gemini-2.5-flash",
        step=step,
        temperature=temperature,
    )


def with_structured_output(
    chat: GeminiChatModel,
    schema: Type[_T],
) -> Runnable:
    """Minimal stand-in for ``BaseChatModel.with_structured_output``.

    Pydantic v2 schemas are supported; OpenAI function-calling style is
    not used (Gemini is accessed via plain text prompt).
    """
    return _StructuredOutputRunnable(chat, schema)
