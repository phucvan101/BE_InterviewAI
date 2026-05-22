# -*- coding: utf-8 -*-
"""
Report generator — produces evaluation_report.md from benchmark results.
"""
import math
from typing import Dict, List
from datetime import datetime


def _mean(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _std(values: List[float], mean_val: float) -> float:
    if len(values) < 2:
        return 0.0
    variance = sum((v - mean_val) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(variance)


def _pearson_r(xs: List[float], ys: List[float]) -> float:
    if len(xs) != len(ys) or len(xs) < 2:
        return 0.0
    n = len(xs)
    mx, my = _mean(xs), _mean(ys)
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (n - 1)
    sx, sy = _std(xs, mx), _std(ys, my)
    if sx == 0 or sy == 0:
        return 0.0
    return cov / (sx * sy)


def _mae(values: List[float]) -> float:
    return _mean([abs(v) for v in values])


def _rmse(values: List[float]) -> float:
    return math.sqrt(_mean([v ** 2 for v in values]))


def _round(v: float, decimals: int = 1) -> float:
    return round(v, decimals)


def generate_report(results: List[Dict], output_path: str) -> str:
    """
    Generate the markdown benchmark report and write it to output_path.

    Returns the report string.
    """
    n = len(results)
    assert n > 0, "No results to report"

    # ── Per-pair data ──────────────────────────────────────────────────────────
    pair_rows = []
    system_overalls, llm_overalls, diffs = [], [], []
    exp_diffs, skills_diffs, edu_diffs, co_diffs = [], [], [], []

    for r in results:
        sys_s = r["system"]
        llm_s = r["llm"]

        if sys_s.get("error") or llm_s.get("error"):
            continue

        sys_ov = sys_s.get("overall_score", 0)
        llm_ov = llm_s.get("overall_score", 0)
        diff = sys_ov - llm_ov

        system_overalls.append(sys_ov)
        llm_overalls.append(llm_ov)
        diffs.append(diff)

        exp_diffs.append(sys_s.get("experience_score", 0) - llm_s.get("experience_score", 0))
        skills_diffs.append(sys_s.get("skills_score", 0) - llm_s.get("skills_score", 0))
        edu_diffs.append(sys_s.get("education_score", 0) - llm_s.get("education_score", 0))
        co_diffs.append(sys_s.get("career_objectives_score", 0) - llm_s.get("career_objectives_score", 0))

        # Rating
        if abs(diff) <= 5:
            rating = "🟢 Excellent"
        elif abs(diff) <= 15:
            rating = "🟡 Good"
        elif abs(diff) <= 25:
            rating = "🟠 Fair"
        else:
            rating = "🔴 Poor"

        sys_exp = sys_s.get("experience_score", 0)
        llm_exp = llm_s.get("experience_score", 0)
        sys_sk = sys_s.get("skills_score", 0)
        llm_sk = llm_s.get("skills_score", 0)
        sys_edu = sys_s.get("education_score", 0)
        llm_edu = llm_s.get("education_score", 0)
        sys_co = sys_s.get("career_objectives_score", 0)
        llm_co = llm_s.get("career_objectives_score", 0)

        case_icon = {
            "MATCH_HIGH": "🟢",
            "MATCH_MEDIUM": "🟡",
            "MATCH_LOW": "🟠",
            "MISMATCH_DOMAIN": "🔴",
        }.get(r["case_type"], "⚪")

        sys_time = r.get("system_time_ms", 0)
        llm_time = r.get("llm_time_s", 0)

        row = {
            "pair_id": r["pair_id"],
            "case_icon": case_icon,
            "case_type": r["case_type"],
            "cv_name": r["cv_name"],
            "jd_title": r["jd_title"][:45],
            "sys_ov": sys_ov,
            "llm_ov": llm_ov,
            "diff": diff,
            "rating": rating,
            "sys_exp": sys_exp,
            "llm_exp": llm_exp,
            "sys_sk": sys_sk,
            "llm_sk": llm_sk,
            "sys_edu": sys_edu,
            "llm_edu": llm_edu,
            "sys_co": sys_co,
            "llm_co": llm_co,
            "sys_time_ms": sys_time,
            "llm_time_s": llm_time,
            "sys_err": sys_s.get("error"),
            "llm_err": llm_s.get("error"),
            "note": r["note"],
        }
        pair_rows.append(row)

    # ── Aggregate stats ───────────────────────────────────────────────────────
    valid = len(pair_rows)
    sys_mean = _mean(system_overalls)
    llm_mean = _mean(llm_overalls)
    sys_std = _std(system_overalls, sys_mean)
    llm_std = _std(llm_overalls, llm_mean)
    mae = _mae(diffs)
    rmse = _rmse(diffs)
    pearson = _pearson_r(system_overalls, llm_overalls)

    # Correlation by case type
    corr_by_type = {}
    for case_type in ["MATCH_HIGH", "MATCH_MEDIUM", "MATCH_LOW", "MISMATCH_DOMAIN"]:
        s_list = [r["sys_ov"] for r in pair_rows if r["case_type"] == case_type]
        l_list = [r["llm_ov"] for r in pair_rows if r["case_type"] == case_type]
        if len(s_list) >= 2:
            corr_by_type[case_type] = _round(_pearson_r(s_list, l_list), 3)

    # MAE by case type
    mae_by_type = {}
    for case_type in ["MATCH_HIGH", "MATCH_MEDIUM", "MATCH_LOW", "MISMATCH_DOMAIN"]:
        d_list = [r["diff"] for r in pair_rows if r["case_type"] == case_type]
        if d_list:
            mae_by_type[case_type] = _round(_mae(d_list), 1)

    # MAE by component
    mae_exp = _round(_mae(exp_diffs), 1)
    mae_sk = _round(_mae(skills_diffs), 1)
    mae_edu = _round(_mae(edu_diffs), 1)
    mae_co = _round(_mae(co_diffs), 1)
    std_diff = _round(_std(diffs, 0.0), 1)

    # Count ratings
    ratings = [r["rating"] for r in pair_rows]
    excellent = sum(1 for x in ratings if "Excellent" in x)
    good = sum(1 for x in ratings if "Good" in x)
    fair = sum(1 for x in ratings if "Fair" in x)
    poor = sum(1 for x in ratings if "Poor" in x)

    # System errors / LLM errors
    sys_errors = sum(1 for r in results if r["system"].get("error"))
    llm_errors = sum(1 for r in results if r["llm"].get("error"))

    # Timing
    total_sys_ms = sum(r.get("system_time_ms", 0) for r in results)
    total_llm_s = sum(r.get("llm_time_s", 0) for r in results)

    # ── Build report ──────────────────────────────────────────────────────────
    lines = []
    lines.append(f"# CV-JD Scoring Benchmark Report")
    lines.append(f"")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"**Pairs evaluated:** {valid}/{n} (errors: system={sys_errors}, LLM={llm_errors})")
    lines.append(f"")

    # ── 1. Summary ──────────────────────────────────────────────────────────────
    lines.append("## 1. Summary")
    lines.append("")
    lines.append("| Metric | System | LLM (Reference) |")
    lines.append("|---|---|---|")
    lines.append(f"| Mean Overall Score | {_round(sys_mean, 1)} | {_round(llm_mean, 1)} |")
    lines.append(f"| Std Dev | {_round(sys_std, 1)} | {_round(llm_std, 1)} |")
    lines.append("| | | |")
    lines.append(f"| **Correlation (Pearson r)** | **{_round(pearson, 3)}** | |")
    lines.append(f"| **MAE (System − LLM)** | **{_round(mae, 1)} pts** | |")
    lines.append(f"| **RMSE** | **{_round(rmse, 1)} pts** | |")
    lines.append(f"| **Std of Diff** | **{std_diff} pts** | |")
    lines.append("")

    # ── 2. Rating distribution ──────────────────────────────────────────────────
    lines.append("## 2. Rating Distribution (|diff| ≤ threshold)")
    lines.append("")
    lines.append(f"- 🟢 Excellent (|diff| ≤ 5 pts): **{excellent}** ({_round(excellent/valid*100)}%)")
    lines.append(f"- 🟡 Good (5 < |diff| ≤ 15 pts): **{good}** ({_round(good/valid*100)}%)")
    lines.append(f"- 🟠 Fair (15 < |diff| ≤ 25 pts): **{fair}** ({_round(fair/valid*100)}%)")
    lines.append(f"- 🔴 Poor (|diff| > 25 pts): **{poor}** ({_round(poor/valid*100)}%)")
    lines.append("")

    # ── 3. MAE by case type ───────────────────────────────────────────────────
    lines.append("## 3. MAE by Case Type")
    lines.append("")
    lines.append("| Case Type | Count | MAE (System − LLM) | Pearson r |")
    lines.append("|---|---|---|---:|")
    type_labels = {
        "MATCH_HIGH": "🟢 Match High",
        "MATCH_MEDIUM": "🟡 Match Medium",
        "MATCH_LOW": "🟠 Match Low",
        "MISMATCH_DOMAIN": "🔴 Domain Mismatch",
    }
    for case_type in ["MATCH_HIGH", "MATCH_MEDIUM", "MATCH_LOW", "MISMATCH_DOMAIN"]:
        count = sum(1 for r in pair_rows if r["case_type"] == case_type)
        mae_val = mae_by_type.get(case_type, "N/A")
        corr_val = corr_by_type.get(case_type, "N/A")
        label = type_labels.get(case_type, case_type)
        lines.append(f"| {label} | {count} | {mae_val} | {corr_val} |")
    lines.append("")

    # ── 4. Component-level MAE ─────────────────────────────────────────────────
    lines.append("## 4. Component-Level MAE")
    lines.append("")
    lines.append("| Component | MAE (System − LLM) | Max possible diff | Interpretation |")
    lines.append("|---|---|---|---|")
    lines.append(f"| Experience (0-50) | **{mae_exp}** | ±50 | {'⚠️ High — investigate' if abs(mae_exp) > 10 else '✅ Acceptable'} |")
    lines.append(f"| Skills (0-30) | **{mae_sk}** | ±30 | {'⚠️ High — investigate' if abs(mae_sk) > 8 else '✅ Acceptable'} |")
    lines.append(f"| Education (0-10) | **{mae_edu}** | ±10 | {'⚠️ High — investigate' if abs(mae_edu) > 3 else '✅ Acceptable'} |")
    lines.append(f"| Career Objectives (0-10) | **{mae_co}** | ±10 | {'⚠️ High — investigate' if abs(mae_co) > 3 else '✅ Acceptable'} |")
    lines.append("")

    # ── 5. Timing ──────────────────────────────────────────────────────────────
    lines.append("## 5. Timing")
    lines.append("")
    avg_sys_ms = _round(total_sys_ms / n, 1) if n else 0
    avg_llm_s = _round(total_llm_s / n, 1) if n else 0
    lines.append(f"- **Avg system scoring time:** {avg_sys_ms} ms/pair")
    lines.append(f"- **Avg LLM scoring time:** {avg_llm_s} s/pair")
    lines.append(f"- **Speed ratio:** LLM is ~{_round((avg_llm_s * 1000) / avg_sys_ms, 0)}× slower than system")
    lines.append("")

    # ── 6. Per-pair results ────────────────────────────────────────────────────
    lines.append("## 6. Per-Pair Results")
    lines.append("")
    lines.append("| # | Case | CV | JD | Sys | LLM | Diff | Rating | Exp (S/L) | Skills (S/L) | Edu (S/L) | CO (S/L) |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|")

    for r in sorted(pair_rows, key=lambda x: x["pair_id"]):
        lines.append(
            f"| {r['pair_id']} | {r['case_icon']} | "
            f"{r['cv_name'][:20]} | "
            f"{r['jd_title'][:30]} | "
            f"**{r['sys_ov']:.0f}** | "
            f"**{r['llm_ov']:.0f}** | "
            f"{r['diff']:+.0f} | "
            f"{r['rating']} | "
            f"{r['sys_exp']:.0f}/{r['llm_exp']:.0f} | "
            f"{r['sys_sk']:.0f}/{r['llm_sk']:.0f} | "
            f"{r['sys_edu']:.0f}/{r['llm_edu']:.0f} | "
            f"{r['sys_co']:.0f}/{r['llm_co']:.0f} |"
        )
    lines.append("")

    # ── 7. Analysis & Observations ─────────────────────────────────────────────
    lines.append("## 7. Analysis & Observations")
    lines.append("")

    # Auto-generate observations based on stats
    observations = []

    if pearson >= 0.8:
        observations.append(f"- **Strong correlation (r={_round(pearson,2)}):** The system's overall scores are highly correlated with LLM reference scores, indicating good ranking alignment.")
    elif pearson >= 0.6:
        observations.append(f"- **Moderate correlation (r={_round(pearson,2)}):** Scores show reasonable alignment but with notable divergence in some pairs. Consider reviewing high-diff pairs.")
    else:
        observations.append(f"- **Weak correlation (r={_round(pearson,2)}):** Significant divergence between system and LLM. Investigate scoring logic — this warrants a thorough review.")

    if mae <= 10:
        observations.append(f"- **Low MAE ({mae:.1f} pts):** System scores are close to LLM reference on average. Good overall accuracy.")
    elif mae <= 20:
        observations.append(f"- **Moderate MAE ({mae:.1f} pts):** System tends to deviate by ~{mae:.0f} pts from LLM. Some components may be systematically biased.")
    else:
        observations.append(f"- **High MAE ({mae:.1f} pts):** Large systematic bias detected. The scoring engine likely has a calibration issue — check component weights.")

    # Case type specific
    mismatch_mae = mae_by_type.get("MISMATCH_DOMAIN", 0)
    if mismatch_mae and abs(mismatch_mae) > 15:
        observations.append(f"- **Domain mismatch pairs show high MAE ({mismatch_mae:.1f}):** The system may over- or under-penalize cross-domain comparisons. Consider reviewing the domain penalty logic.")

    match_high_mae = mae_by_type.get("MATCH_HIGH", 0)
    if match_high_mae and abs(match_high_mae) > 10:
        observations.append(f"- **High-match pairs show MAE ({match_high_mae:.1f}):** System may not fully reward strong candidates. Check ceiling effects or bonus scoring.")

    # Component analysis
    if abs(mae_exp) > 10:
        observations.append(f"- **Experience component has high bias ({mae_exp:+.1f}):** The system's experience scoring formula may be too lenient or harsh compared to LLM judgment. Consider reviewing years-to-score mapping.")
    if abs(mae_sk) > 8:
        observations.append(f"- **Skills component has notable bias ({mae_sk:+.1f}):** Keyword matching or embedding similarity weighting may need recalibration.")
    if abs(mae_edu) > 3:
        observations.append(f"- **Education component deviates ({mae_edu:+.1f}):** Check degree-level scoring thresholds and field relevance evaluation.")
    if abs(mae_co) > 3:
        observations.append(f"- **Career objectives component deviates ({mae_co:+.1f}):** The career_objectives scoring logic may need review for semantic alignment.")

    # Worst pairs
    worst_pairs = sorted(pair_rows, key=lambda x: abs(x["diff"]), reverse=True)[:3]
    if worst_pairs:
        observations.append("- **Worst agreements:**")
        for r in worst_pairs:
            observations.append(
                f"  - Pair {r['pair_id']}: {r['cv_name'][:20]} vs {r['jd_title'][:30]} "
                f"(diff = {r['diff']:+.0f}, rating: {r['rating'].split()[0]})"
            )

    # Timing observation
    if avg_llm_s / (avg_sys_ms / 1000) > 50:
        observations.append(f"- **Speed advantage:** System scoring is ~{_round(avg_llm_s * 1000 / avg_sys_ms, 0)}× faster than LLM. This enables real-time scoring at scale.")

    for obs in observations:
        lines.append(obs)
    lines.append("")

    # ── 8. Recommendations ─────────────────────────────────────────────────────
    lines.append("## 8. Recommendations")
    lines.append("")
    recommendations = []

    if pearson < 0.8:
        recommendations.append("- Investigate pairs with diff > 25 pts to understand systematic biases.")
    if abs(mae_exp) > 10:
        recommendations.append("- Review experience scoring: years-to-score mapping, seniority detection, and project relevance weighting.")
    if abs(mae_sk) > 8:
        recommendations.append("- Review skills scoring: adjust keyword/embedding weight balance, consider expanding synonym groups.")
    if abs(mae_edu) > 3:
        recommendations.append("- Review education scoring: degree level thresholds, field relevance evaluation.")
    if abs(mae_co) > 3:
        recommendations.append("- Review career_objectives scoring: improve semantic alignment detection.")
    if mismatch_mae and abs(mismatch_mae) > 15:
        recommendations.append("- Revisit domain penalty formula to reduce over/under-penalization of cross-domain cases.")
    if excellent / valid < 0.5:
        recommendations.append(f"- Only {excellent}/{valid} pairs have |diff| ≤ 5. Consider re-calibrating the scoring weights.")
    if sys_errors > 0:
        recommendations.append(f"- {sys_errors} system scoring errors occurred. Review error logs and fix edge cases.")

    if not recommendations:
        recommendations.append("- System performance is satisfactory. Continue monitoring and collecting more evaluation data.")
        recommendations.append("- Consider expanding the benchmark with more diverse JD-CV pairs.")

    for rec in recommendations:
        lines.append(rec)
    lines.append("")

    # ── 9. Methodology ─────────────────────────────────────────────────────────
    lines.append("## 9. Methodology")
    lines.append("")
    lines.append(f"- **System scoring:** `hybrid_scoring.calculate_hybrid_score()` — formula-based scoring (experience 50%, skills 30%, education 10%, career objectives 10%) with embedding similarity boost (sentence-transformers).")
    lines.append(f"- **Reference scoring:** LLM (claude-sonnet-4-20250514 via OpenRouter) prompted with the same rubric, given full structured CV and JD data.")
    lines.append(f"- **Benchmark pairs:** {n} pairs spanning 4 case types: Match-High, Match-Medium, Match-Low, Domain-Mismatch.")
    lines.append(f"- **Ground truth:** LLM reference scores serve as proxy ground truth. They are not guaranteed to be 'correct' — use as calibration reference only.")
    lines.append("")

    report = "\n".join(lines)

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"Report written to: {output_path}")

    return report
