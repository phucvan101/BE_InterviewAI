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
    max_retry: int = 7
    base_wait_sec: int = 4
    max_wait_sec: int = 65


def _parse_retry_delay_seconds(err_text: str) -> int | None:
    if not err_text:
        return None
    
    # Try to match Google Generative AI Python generic message (e.g., "retry in 44s")
    m = re.search(r"retry in\s+(\d+(?:\.\d+)?)s", err_text, re.IGNORECASE)
    if not m:
        # Try to match the raw JSON payload message that we sometimes get wrapped inside Exception
        # e.g.: {'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '44s'}
        m = re.search(r"retryDelay['\"\s]*:['\"\s]*(\d+(?:\.\d+)?)s", err_text, re.IGNORECASE)

    if not m:
        return None
    try:
        return max(1, int(float(m.group(1))))
    except Exception:
        return None


def _classify_gemini_error(e: Exception) -> tuple[str, int | None]:
    msg = str(e) or ""
    retry_delay = _parse_retry_delay_seconds(msg)

    # 503 (Model High Demand)
    if "503" in msg or "service unavailable" in msg.lower() or getattr(e, "code", None) == 503:
        return ("service_unavailable", retry_delay)

    # 429 (Rate Limit vs Quota)
    descriptions = re.findall(r'[\'"]description[\'"]\s*:\s*[\'"]([^\'"]+)[\'"]', msg, re.IGNORECASE)
    
    # Decisions base ONLY on details[].violations[].description as requested
    for desc in descriptions:
        desc_lower = desc.lower()
        if "requests per minute" in desc_lower or "rate limit" in desc_lower or "per minute limit" in desc_lower:
            return ("rate_limited", retry_delay)
        if "quota exceeded" in desc_lower or "free_tier" in desc_lower or "daily limit" in desc_lower:
            return ("quota_exceeded", retry_delay)

    # Default to rate_limited if code is 429 but we couldn't match descriptions
    # (or if we need a safe fallback for 429 throttling)
    if getattr(e, "code", None) == 429 or "429" in msg or "resource_exhausted" in msg.lower():
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
    gemini_api_key_str = os.getenv("GEMINI_API_KEY", "")
    api_keys = [k.strip() for k in gemini_api_key_str.split(",") if k.strip()]

    model_name = os.getenv("MODEL_NAME", "models/gemini-2.5-flash")
    cfg = config or GeminiConfig(model=model_name)

    if not api_keys:
        raise ValueError(f"[step={step}] Missing GEMINI_API_KEY in environment")

    last_exc: Exception | None = None
    wait_sec = max(1, int(cfg.base_wait_sec))
    current_key_idx = random.randint(0, len(api_keys) - 1)
    
    start_time = time.time()
    max_duration_sec = 120.0
    attempt = 0
    keys_tried_in_cycle = 0

    while True:
        if time.time() - start_time > max_duration_sec:
            print(f"❌ [step={step}] Exceeded 2 minutes timeout.")
            raise Exception("runtime error, hãy thử lại sau")

        attempt += 1
        keys_tried_in_cycle += 1
        try:
            client = genai.Client(api_key=api_keys[current_key_idx])
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
                print(f"❌ [step={step}] Quota exceeded (429) - Stop immediately.")
                raise GeminiQuotaExceededError("quota exceed (429)") from e

            if kind == "service_unavailable":
                print(f"❌ [step={step}] Server high demand (503) - Stop immediately.")
                raise Exception("Server high demand (503)") from e

            if kind == "rate_limited":
                if len(api_keys) > 1:
                    old_key = api_keys[current_key_idx]
                    current_key_idx = (current_key_idx + 1) % len(api_keys)
                    print(f"⚠️ [step={step}] {kind} for key ending in ...{old_key[-4:]}.")
                    print(f"🔄 Switching to next API key. Attempt {attempt}...")
                    
                    # Allow quick rotation if we haven't completed a full cycle
                    if keys_tried_in_cycle < len(api_keys):
                        time.sleep(1 + random.uniform(0, 0.5))
                        continue
                    else:
                        print(f"⏳ All {len(api_keys)} keys used. Falling back to wait strategy...")
                        keys_tried_in_cycle = 0 # reset cycle counter

                # Calculate wait time but ensure it doesn't cross the 2 minute limit unnecessarily
                chosen = retry_delay if retry_delay is not None else wait_sec
                raw_wait = min(cfg.max_wait_sec, max(1, int(chosen))) + random.uniform(0, 0.5)
                remaining_time = max_duration_sec - (time.time() - start_time)
                
                # If waiting is going to push us over the limit, just wait whatever time is left
                actual_wait = min(raw_wait, remaining_time)
                if actual_wait <= 0:
                    raise Exception("runtime error, hãy thử lại sau") from e
                    
                print(f"⚠️ [step={step}] {kind}. Waiting {actual_wait:.1f}s before next cycle...")
                time.sleep(actual_wait)
                wait_sec = min(cfg.max_wait_sec, wait_sec * 2)
                continue

            # If it's a completely unrecoverable error (not 429 or 503)
            print(f"❌ [step={step}] Unrecoverable error: {str(e)}")
            raise Exception("runtime error, hãy thử lại sau") from e

