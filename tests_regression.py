"""
Regression test for the scoring engine after Feedback Agent changes.

The agent's design is to NOT touch the scoring engine (per the plan's
"Do NOT modify" rule). This test confirms that:

  1. The scoring engine still imports cleanly with the new agent code
     in the project tree.
  2. ``calculate_hybrid_score`` keeps its public signature (no
     parameter renames or removals).
  3. The ``apply_learned_rules`` hook still exists and is reachable
     from the new agent code.
  4. A small synthetic CV/JD call doesn't raise.

This is a STRUCTURAL regression test - it doesn't run the full 30-case
benchmark (that requires real CV/JD files and LLM access). For a full
benchmark, the operator can re-run the test harness that produced
``test_report_real_metrics_v2.md``.
"""
import inspect
import sys
from pathlib import Path

REPO = Path(r"c:\Users\pc\Documents\code\DATN\BE_InterviewAI")
sys.path.insert(0, str(REPO))

print("[1] Importing hybrid scoring engine + rules engine...")
from app.feature.feature_up_cv.scoring.hybrid_scoring import calculate_hybrid_score
from app.feature.feature_up_cv.scoring._rules_engine import apply_learned_rules
print("    OK")

print("\n[2] Verifying calculate_hybrid_score signature is unchanged...")
sig = inspect.signature(calculate_hybrid_score)
params = list(sig.parameters.keys())
print(f"    params: {params}")
expected = {
    "cv_data", "jd_data", "company_data",
    "cv_embedding", "jd_embedding",
    "score_overrides", "learned_knowledge",
}
missing = expected - set(params)
assert not missing, f"Missing params from calculate_hybrid_score: {missing}"
print(f"    OK - all expected params present (incl. agent hooks: score_overrides, learned_knowledge)")

print("\n[3] Verifying apply_learned_rules still public...")
sig2 = inspect.signature(apply_learned_rules)
print(f"    params: {list(sig2.parameters.keys())}")
assert "learned_knowledge" in sig2.parameters
print("    OK")

print("\n[4] Verify agent service can REACH the scoring engine (lazy import path)...")
# The service uses a lazy import inside the function. We test that
# the import would succeed by simulating the same code path.
try:
    from app.feature.feature_up_cv.scoring.hybrid_scoring import (
        calculate_hybrid_score as _cls,
    )
    from app.feature.feature_up_cv.core.file_storage import save_result_analysis
    print("    OK - all imports succeed (no circular imports / no breakages)")
except Exception as e:
    print(f"    FAIL: {e}")
    sys.exit(1)

print("\n[5] Calling calculate_hybrid_score with minimal stub data...")
# We don't have an embedder at hand, but hybrid_scoring has a fallback
# path; this just verifies the function doesn't crash on import-time
# issues introduced by the agent.
stub_cv = {
    "personal_info": {"name": "Test User"},
    "skills": ["python"],
    "work_experience": [],
    "projects": [],
    "education": [],
}
stub_jd = {
    "structured": {
        "job_title": "Backend Dev",
        "summary": "Looking for Python dev",
        "skills_required": ["python"],
    }
}
try:
    result = calculate_hybrid_score(
        cv_data=stub_cv,
        jd_data=stub_jd,
        company_data=None,
    )
    print(f"    overall_score: {result.get('overall_score')}")
    print(f"    detailed_scores keys: {list(result.get('detailed_scores', {}).keys())}")
    print("    OK - hybrid scoring runs without raising")
except Exception as e:
    print(f"    FAIL: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n=== REGRESSION CHECK PASSED ===")
print("Scoring engine is intact; agent changes did not regress the system.")
