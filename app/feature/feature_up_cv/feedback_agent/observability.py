"""
Phase 6 — Observability for the Feedback Agent.

Two layers:

  1. **Structured logging** — every call to ``FeedbackAgent.evaluate``
     emits a JSON record with: timestamp, latency, evaluation summary,
     tool calls, errors. Records go to:

        storage/agent_traces/agent_traces.jsonl

     (one JSON object per line, tail-able with `jq` / `less`).

  2. **LangSmith bridge** (optional) — when ``LANGSMITH_API_KEY`` is
     present in the environment, the wrapper pushes the same record to
     the LangSmith cloud via the official ``langsmith`` SDK. The local
     JSONL is always written so tests can run offline.

This module is intentionally light — no third-party deps beyond what
the rest of the project already uses. It works in the conda env
without any extra pip install.
"""
from __future__ import annotations

import json
import logging
import os
import time
import threading
import traceback
import uuid
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


# ── Storage ──────────────────────────────────────────────────────
_TRACE_DIR = Path(
    os.getenv("AGENT_TRACE_DIR")
    or (Path(__file__).resolve().parents[1] / "storage" / "agent_traces")
)
_TRACE_DIR.mkdir(parents=True, exist_ok=True)
_TRACE_FILE = _TRACE_DIR / "agent_traces.jsonl"

_trace_lock = threading.Lock()


def _write_record(record: Dict[str, Any]) -> None:
    """Append a single trace record to the JSONL file (thread-safe)."""
    try:
        with _trace_lock:
            with _TRACE_FILE.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except Exception as e:  # never raise from logging
        logger.warning("[Observability] failed to write trace: %s", e)


def _push_langsmith(record: Dict[str, Any]) -> None:
    """Best-effort push to LangSmith if available (no-op otherwise)."""
    if not os.getenv("LANGSMITH_API_KEY"):
        return
    try:
        from langsmith import Client  # type: ignore

        client = Client()
        client.create_run(
            name=record.get("name", "feedback_agent_call"),
            run_type="chain",
            inputs=record.get("inputs", {}),
            outputs=record.get("outputs", {}),
            error=record.get("error"),
            start_time=datetime.fromisoformat(record["started_at"]),
            end_time=datetime.fromisoformat(record["ended_at"]),
            run_id=uuid.UUID(record["run_id"]),
            extra=record.get("extra", {}),
        )
    except Exception as e:
        logger.debug("[Observability] langsmith push skipped: %s", e)


# ── Decorator ────────────────────────────────────────────────────
def trace_agent_call(
    *,
    name: str = "feedback_agent.evaluate",
    capture_args: bool = True,
) -> Callable:
    """
    Wrap any async function that returns a ``FeedbackEvaluation`` (or
    any Pydantic model) so the call is recorded.

    Usage::

        @trace_agent_call(name="evaluate")
        async def evaluate(self, cv_text, jd_text, ...):
            ...
    """
    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            run_id = str(uuid.uuid4())
            started = datetime.now(timezone.utc).isoformat()
            t0 = time.perf_counter()
            error: Optional[str] = None
            result: Any = None
            try:
                result = await fn(*args, **kwargs)
                return result
            except Exception as e:
                error = repr(e)
                logger.error("[%s] exception: %s\n%s", name, e, traceback.format_exc())
                raise
            finally:
                elapsed_ms = (time.perf_counter() - t0) * 1000
                record: Dict[str, Any] = {
                    "run_id": run_id,
                    "name": name,
                    "started_at": started,
                    "ended_at": datetime.now(timezone.utc).isoformat(),
                    "latency_ms": round(elapsed_ms, 2),
                    "error": error,
                }
                if capture_args:
                    try:
                        record["inputs"] = _safe_inputs(args, kwargs)
                    except Exception:
                        record["inputs"] = {"_truncated": True}
                if result is not None and hasattr(result, "model_dump"):
                    try:
                        record["outputs"] = result.model_dump()
                    except Exception:
                        record["outputs"] = {"_truncated": True}
                elif result is not None:
                    record["outputs"] = {"_type": type(result).__name__}
                _write_record(record)
                _push_langsmith(record)

        @wraps(fn)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            run_id = str(uuid.uuid4())
            started = datetime.now(timezone.utc).isoformat()
            t0 = time.perf_counter()
            error: Optional[str] = None
            result: Any = None
            try:
                result = fn(*args, **kwargs)
                return result
            except Exception as e:
                error = repr(e)
                logger.error("[%s] exception: %s\n%s", name, e, traceback.format_exc())
                raise
            finally:
                elapsed_ms = (time.perf_counter() - t0) * 1000
                record: Dict[str, Any] = {
                    "run_id": run_id,
                    "name": name,
                    "started_at": started,
                    "ended_at": datetime.now(timezone.utc).isoformat(),
                    "latency_ms": round(elapsed_ms, 2),
                    "error": error,
                }
                if capture_args:
                    try:
                        record["inputs"] = _safe_inputs(args, kwargs)
                    except Exception:
                        record["inputs"] = {"_truncated": True}
                if result is not None and hasattr(result, "model_dump"):
                    try:
                        record["outputs"] = result.model_dump()
                    except Exception:
                        record["outputs"] = {"_truncated": True}
                _write_record(record)
                _push_langsmith(record)

        # Pick wrapper based on coroutine-ness
        import inspect
        if inspect.iscoroutinefunction(fn):
            return async_wrapper
        return sync_wrapper
    return decorator


def _safe_inputs(args: tuple, kwargs: dict) -> Dict[str, Any]:
    """Stringify args so we never leak Pydantic internals / huge blobs."""
    out: Dict[str, Any] = {}
    if args and hasattr(args[0], "__class__"):
        # First positional is `self`; skip to keep trace compact.
        args = args[1:]
    for i, a in enumerate(args):
        out[f"arg_{i}"] = _short(a)
    for k, v in kwargs.items():
        out[k] = _short(v)
    return out


def _short(value: Any, max_len: int = 2000) -> Any:
    if isinstance(value, str):
        if len(value) > max_len:
            return value[:max_len] + f"... (truncated, total {len(value)} chars)"
        return value
    if isinstance(value, dict):
        return {k: _short(v, max_len) for k, v in value.items()}
    if isinstance(value, list):
        return [_short(v, max_len) for v in value[:50]]
    return value


# ── Health check helper ──────────────────────────────────────────
def get_trace_stats() -> Dict[str, Any]:
    """Quick stats for ops dashboards."""
    if not _TRACE_FILE.exists():
        return {"count": 0, "by_status": {}, "avg_latency_ms": None}
    count = 0
    errors = 0
    total_latency = 0.0
    with _TRACE_FILE.open("r", encoding="utf-8") as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except Exception:
                continue
            count += 1
            total_latency += float(rec.get("latency_ms") or 0)
            if rec.get("error"):
                errors += 1
    return {
        "count": count,
        "by_status": {"ok": count - errors, "error": errors},
        "avg_latency_ms": round(total_latency / count, 2) if count else None,
        "trace_file": str(_TRACE_FILE),
    }
