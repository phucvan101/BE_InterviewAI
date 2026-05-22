# -*- coding: utf-8 -*-
"""
run_evaluation.py — Main entry point for the CV-JD scoring benchmark.

Usage:
    python -m app.feature.feature_up_cv.Evaluation.run_evaluation

Environment variables required:
    OPENROUTER_API_KEY  — API key for LLM reference scoring
    GEMINI_API_KEY     — API key used by the system's scoring engine (already in env)

Optional:
    MAX_PAIRS          — number of pairs to evaluate (default: 30)
    OUTPUT_DIR         — output directory for results (default: ./Evaluation/results)
"""
import os
import sys
from pathlib import Path

# ── resolve paths ──────────────────────────────────────────────────────────────
EVAL_DIR = Path(__file__).resolve().parent
FEATURE_DIR = EVAL_DIR.parent
PROJECT_ROOT = FEATURE_DIR.parent.parent.parent  # BE_InterviewAI

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ── config ─────────────────────────────────────────────────────────────────────
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
MAX_PAIRS = int(os.environ.get("MAX_PAIRS", "30"))
OUTPUT_DIR = EVAL_DIR / "results"
RESULTS_DIR = Path(os.environ.get("OUTPUT_DIR", str(OUTPUT_DIR)))


def main():
    print("=" * 70)
    print("CV-JD SCORING BENCHMARK")
    print("=" * 70)

    if not OPENROUTER_API_KEY:
        print("\nERROR: OPENROUTER_API_KEY is not set.")
        print("Set it in your environment or .env file:")
        print("    export OPENROUTER_API_KEY=sk-or-...")
        sys.exit(1)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    from app.feature.feature_up_cv.Evaluation.benchmark_runner import run_benchmark
    from app.feature.feature_up_cv.Evaluation.report_generator import generate_report

    # ── Run benchmark ──────────────────────────────────────────────────────────
    print(f"\nOutput directory: {RESULTS_DIR}")
    print(f"Max pairs: {MAX_PAIRS}\n")

    results = run_benchmark(
        openrouter_api_key=OPENROUTER_API_KEY,
        output_dir=str(RESULTS_DIR),
        max_pairs=MAX_PAIRS,
        delay_between_calls=1.5,
    )

    # ── Generate report ────────────────────────────────────────────────────────
    report_path = EVAL_DIR / "evaluation_report.md"
    print(f"\nGenerating report: {report_path}")
    generate_report(results, str(report_path))

    print("\n" + "=" * 70)
    print("BENCHMARK COMPLETE")
    print(f"  Results JSON: {RESULTS_DIR / 'benchmark_results_*.json'}")
    print(f"  Report MD:    {report_path}")
    print("=" * 70)


if __name__ == "__main__":
    main()
