# Evaluation — CV-JD Hybrid Scoring Benchmark

## Overview

This module benchmarks the system's hybrid scoring engine against an independent LLM evaluator.
For each JD-CV pair, two scores are produced:

| Source | Description |
|---|---|
| **System** | `calculate_hybrid_score()` from `hybrid_scoring.py` — formula + embedding hybrid |
| **LLM** | Independent scoring by the evaluation LLM (claude-sonnet-4-20250514 via OpenRouter) using the same scoring rubric |

### Scoring Rubric (shared reference)

| Component | Max | Weight |
|---|---|---|
| Experience | 50 | 50% |
| Skills | 30 | 30% |
| Education | 10 | 10% |
| Career Objectives | 10 | 10% |
| **Total** | **100** | **100%** |

Component definitions mirror the system's internal scoring:

- **Experience (0-50)**: Work years relevance + seniority match + project relevance (for entry-level)
- **Skills (0-30)**: Technical skill overlap (keyword exact match) + semantic similarity boost (embedding)
- **Education (0-10)**: Degree level match + field relevance + certifications
- **Career Objectives (0-10)**: Alignment of CV stated goals with JD role/career path

---

## Folder Structure

```
Evaluation/
├── README.md          ← this file
├── benchmark_runner.py    # Main script — runs system + LLM scoring, saves results
├── dataset.py            # 30 JD-CV pairs definition
├── llm_scorer.py         # LLM-based independent scorer
├── system_scorer.py       # Wrapper around hybrid_scoring.calculate_hybrid_score
├── run_evaluation.py      # Orchestrator — runs all 30 pairs
├── report_generator.py    # Generates evaluation_report.md
└── evaluation_report.md   # Output benchmark report
```

---

## Running the Benchmark

```bash
cd BE_InterviewAI
python -m app.feature.feature_up_cv.Evaluation.run_evaluation
```

Requires environment variables:
- `OPENROUTER_API_KEY` — for LLM scoring
- `GEMINI_API_KEY` — for system scoring (already used by the app)
