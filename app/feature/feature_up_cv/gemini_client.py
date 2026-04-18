from __future__ import annotations

import os
import random
import re
import time
from dataclasses import dataclass

from dotenv import load_dotenv
from google import genai


load_dotenv()


class GeminiQuotaExceededError(Exception):
    """Gemini project/model quota exhausted (e.g. free-tier daily limit)."""


class GeminiRateLimitedError(Exception):
    """Gemini temporarily rate-limited requests (429 throttling)."""


@dataclass(frozen=True)
class GeminiConfig:
    model: str
    temperature: float = 0.0
    max_retry: int = 5
    base_wait_sec: int = 2
    max_wait_sec: int = 30


def _parse_retry_delay_seconds(err_text: str) -> int | None:
    if not err_text:
        return None
    m = re.search(r"retry in\s+(\d+(?:\.\d+)?)s", err_text, re.IGNORECASE)
    if not m:
        return None
    try:
        return max(1, int(float(m.group(1))))
    except Exception:
        return None


def _classify_gemini_error(e: Exception) -> tuple[str, int | None]:
    msg = str(e) or ""
    retry_delay = _parse_retry_delay_seconds(msg)

    # Free-tier / daily project quota
    if "quota exceeded" in msg.lower() or "generate_content_free_tier_requests" in msg:
        return ("quota_exceeded", retry_delay)

    # Transient throttling / overload
    if "429" in msg or "rate limit" in msg.lower() or "resource_exhausted" in msg.lower():
        return ("rate_limited", retry_delay)

    return ("other", retry_delay)


def generate_content(
    *,
    prompt: str,
    step: str,
    config: GeminiConfig | None = None,
) -> str:
    """
    Shared Gemini call with:
    - quota vs rate-limit classification
    - exponential backoff + jitter
    - step-tagged exceptions for precise debugging
    """
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    model_name = os.getenv("MODEL_NAME", "models/gemini-2.5-flash")
    cfg = config or GeminiConfig(model=model_name)

    if not gemini_api_key:
        raise ValueError(f"[step={step}] Missing GEMINI_API_KEY in environment")

    client = genai.Client(api_key=gemini_api_key)

    last_exc: Exception | None = None
    wait_sec = max(1, int(cfg.base_wait_sec))

    for attempt in range(1, cfg.max_retry + 1):
        try:
            resp = client.models.generate_content(
                model=cfg.model,
                contents=prompt,
                config={"temperature": cfg.temperature},
            )
            text = getattr(resp, "text", None)
            if not text:
                raise Exception("Gemini returned empty response")
            return text
        except Exception as e:
            last_exc = e
            kind, retry_delay = _classify_gemini_error(e)

            if kind == "quota_exceeded":
                raise GeminiQuotaExceededError(f"[step={step}] {str(e)}")

            if kind == "rate_limited":
                if attempt >= cfg.max_retry:
                    raise GeminiRateLimitedError(
                        f"[step={step}] Gemini rate limited after retries. Last error: {str(e)}"
                    )
                chosen = retry_delay if retry_delay is not None else wait_sec
            else:
                if attempt >= cfg.max_retry:
                    raise Exception(f"[step={step}] Gemini failed after retries. Last error: {str(e)}")
                chosen = wait_sec

            jitter = random.uniform(0, 0.5)
            time.sleep(min(cfg.max_wait_sec, max(1, int(chosen))) + jitter)
            wait_sec = min(cfg.max_wait_sec, wait_sec * 2)

    raise Exception(f"[step={step}] Gemini failed after retries. Last error: {last_exc}")

