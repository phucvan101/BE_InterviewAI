# -*- coding: utf-8 -*-
"""
Benchmark runner — orchestrates system + LLM scoring for all 30 pairs.
"""
import json
import time
import random
from pathlib import Path
from datetime import datetime
from typing import Dict, List

from .dataset import get_all_pairs
from .system_scorer import score_with_system
from .llm_scorer import score_with_llm


def run_benchmark(
    openrouter_api_key: str,
    output_dir: str | None = None,
    max_pairs: int = 30,
    delay_between_calls: float = 1.0,
) -> List[Dict]:
    """
    Run the full benchmark for all (or up to max_pairs) pairs.

    Args:
        openrouter_api_key: OpenRouter API key for LLM scoring
        output_dir: directory to save raw results JSON
        max_pairs: max number of pairs to run (default 30)
        delay_between_calls: sleep between LLM calls to avoid rate limits

    Returns:
        List of result dicts (one per pair)
    """
    pairs = get_all_pairs()[:max_pairs]
    results = []

    print(f"\n{'='*70}")
    print(f"CV-JD BENCHMARK — {len(pairs)} pairs")
    print(f"Started: {datetime.now().isoformat()}")
    print(f"{'='*70}\n")

    for i, pair in enumerate(pairs, 1):
        pair_id = pair["pair_id"]
        cv_data = pair["cv"]
        jd_data = pair["jd"]
        case_type = pair["case_type"]
        note = pair["note"]

        print(f"[{i:02d}/{len(pairs)}] Pair {pair_id:02d} ({case_type}) — {note[:60]}...")
        print(f"    CV: {cv_data.get('personal_info', {}).get('name', 'Unknown')}")
        jd_title = jd_data.get('job_title', '') or jd_data.get('structured', {}).get('job_title', 'Unknown')
        print(f"    JD: {jd_title}")

        # System scoring
        t0 = time.perf_counter()
        system_result = score_with_system(cv_data, jd_data)
        system_time = time.perf_counter() - t0
        print(f"    System: {system_result.get('overall_score', 0):.1f}/100 | {system_time*1000:.0f}ms")
        if system_result.get("error"):
            print(f"    System ERROR: {system_result['error']}")

        # LLM scoring
        t0 = time.perf_counter()
        llm_result = score_with_llm(
            cv_data, jd_data,
            api_key=openrouter_api_key,
        )
        llm_time = time.perf_counter() - t0
        if llm_result.get("error"):
            print(f"    LLM ERROR: {llm_result['error']}")
        else:
            print(f"    LLM:     {llm_result.get('overall_score', 0):.1f}/100 | {llm_time:.1f}s")

        # Score difference
        diff = system_result.get("overall_score", 0) - llm_result.get("overall_score", 0)
        print(f"    Diff:    {diff:+.1f} (system - LLM)")

        results.append({
            "pair_id": pair_id,
            "case_type": case_type,
            "note": note,
            "cv_name": cv_data.get("personal_info", {}).get("name", "Unknown"),
            "jd_title": jd_title,
            "system": system_result,
            "llm": llm_result,
            "system_time_ms": round(system_time * 1000, 1),
            "llm_time_s": round(llm_time, 1),
        })

        if i < len(pairs):
            time.sleep(delay_between_calls)
        print()

    # Save results
    if output_dir:
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = out_path / f"benchmark_results_{ts}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\nResults saved to: {file_path}")

    return results
