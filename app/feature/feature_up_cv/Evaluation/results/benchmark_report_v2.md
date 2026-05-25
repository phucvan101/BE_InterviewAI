# CV-JD Scoring Benchmark Report v2

**Generated:** 2026-05-23 15:42:27 | **Pairs evaluated:** 40/40 | System errors: 0 | LLM errors: 0

> **Benchmark v2 Design:** 8 distinct CVs × 8 distinct JDs = 40 unique pairs. Covers 7 industry domains (tech_data, tech_software, operations, marketing, hr, finance, tech_devops) and 3 seniority levels (Fresher/Entry, Mid, Senior). Case types: Match-High, Match-Medium, Match-Low, Domain-Mismatch.

> **Reference scoring method:** Assistant's own reasoning applying the rubric: Experience (0-50) + Skills (0-30) + Education (0-10) + Career Objectives (0-10) = Total (0-100). No external API required.

## 1. Summary

| Metric | System | LLM Reference |
|---|---|---|
| Mean Overall Score | 28.3 | 33.8 |
| Std Dev | 21.1 | 18.1 |
| **Pearson Correlation (r)** | **0.891** | |
| **MAE (|System − LLM|)** | **9.1 pts** | |
| **RMSE** | **11.0 pts** | |
| **Std of Diff** | **11.1 pts** | |

## 2. Rating Distribution

| Rating | Threshold | Count | Percentage |
|---|---|---|---:|---:|
| 🟢 Excellent | |diff| ≤ 5 pts | **13** | 32.5% |
| 🟡 Good | 5 < |diff| ≤ 15 pts | **22** | 55.0% |
| 🟠 Fair | 15 < |diff| ≤ 25 pts | **5** | 12.5% |
| 🔴 Poor | |diff| > 25 pts | **0** | 0.0% |

**Overall agreement rate** (Excellent + Good): **35/40 (87.5%)**

## 3. MAE by Case Type

| Case Type | # Pairs | MAE (|System − LLM|) | Signed Bias | Pearson r |
|---|---|---:|---:|---:|
| 🟢 Match-High | 5 | 1.4 | -0.2 | 0.982 |
| 🟡 Match-Medium | 11 | 11.0 | -10.3 | 0.822 |
| 🟠 Match-Low | 6 | 8.5 | +0.5 | 0.953 |
| 🔴 Domain Mismatch | 18 | 10.3 | -6.2 | 0.379 |

*Bias > 0: System scores higher than LLM. Bias < 0: System scores lower than LLM.*

## 4. Component-Level Analysis

| Component | MAE (|diff|) | Signed Bias | Max range | Status |
|---|---|---:|---:|---:|---|
| Experience (0-50) | **5.5** | +0.5 | ±50 | ✅ OK |
| Skills (0-30) | **4.5** | -3.5 | ±30 | ✅ OK |
| Education (0-10) | **2.0** | -1.5 | ±10 | ✅ OK |
| Career Objectives (0-10) | **1.9** | -1.4 | ±10 | ✅ OK |

*Signed bias > 0: System consistently rates this component higher than LLM.*

## 5. Timing

| Metric | Value |
|---|---:|
| Avg system scoring time | 2399.7 ms/pair |
| Avg LLM scoring time | 0.0 s/pair |
| Total system time | 96.0 s |
| Total LLM time | 0.0 min |

## 6. Per-Pair Results

| # | Case | CV | JD | Sys | LLM | Diff | Rating | Exp (S/L) | Skills (S/L) | Edu (S/L) | CO (S/L) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 🟢 MATCH_HIGH | Nguyễn Hoàng Nam | Data Analyst | **67** | **67** | +0 | 🟢 Excellent | 28/32 | 25/22 | 4/6 | 8/7 |
| 2 | 🟠 MATCH_LOW | Nguyễn Hoàng Nam | Senior Data Engineer | **50** | **35** | +15 | 🟡 Good | 35/18 | 4/8 | 4/5 | 6/4 |
| 3 | 🟡 MATCH_MEDIUM | Nguyễn Hoàng Nam | React Frontend Developer | **27** | **25** | +2 | 🟢 Excellent | 19/12 | 2/5 | 4/5 | 1/3 |
| 4 | 🔴 MISMATCH_DOMAIN | Nguyễn Hoàng Nam | Product Manager | **24** | **36** | -12 | 🟡 Good | 16/15 | 2/10 | 4/6 | 3/5 |
| 5 | 🔴 MISMATCH_DOMAIN | Nguyễn Hoàng Nam | Growth Marketing Specialist | **10** | **32** | -22 | 🟠 Fair | 6/14 | 1/8 | 2/6 | 1/4 |
| 6 | 🔴 MISMATCH_DOMAIN | Nguyễn Hoàng Nam | Technical Recruiter | **10** | **22** | -12 | 🟡 Good | 6/10 | 0/4 | 2/5 | 1/3 |
| 7 | 🔴 MISMATCH_DOMAIN | Nguyễn Hoàng Nam | Financial Analyst | **42** | **32** | +10 | 🟡 Good | 19/15 | 10/8 | 6/5 | 6/4 |
| 8 | 🔴 MISMATCH_DOMAIN | Nguyễn Hoàng Nam | Cloud Infrastructure Enginee | **30** | **18** | +12 | 🟡 Good | 20/8 | 3/3 | 4/5 | 2/2 |
| 9 | 🟡 MATCH_MEDIUM | Trần Minh Đức | Data Analyst | **47** | **61** | -14 | 🟡 Good | 28/28 | 8/20 | 5/8 | 6/5 |
| 10 | 🟢 MATCH_HIGH | Trần Minh Đức | Senior Data Engineer | **86** | **88** | -2 | 🟢 Excellent | 48/44 | 26/28 | 5/8 | 7/8 |
| 11 | 🟡 MATCH_MEDIUM | Trần Minh Đức | React Frontend Developer | **29** | **30** | -1 | 🟢 Excellent | 19/14 | 2/6 | 5/7 | 3/3 |
| 12 | 🔴 MISMATCH_DOMAIN | Trần Minh Đức | Product Manager | **23** | **32** | -9 | 🟡 Good | 16/14 | 2/8 | 5/7 | 1/3 |
| 13 | 🔴 MISMATCH_DOMAIN | Trần Minh Đức | Growth Marketing Specialist | **11** | **30** | -19 | 🟠 Fair | 6/13 | 1/7 | 3/7 | 1/3 |
| 14 | 🔴 MISMATCH_DOMAIN | Trần Minh Đức | Technical Recruiter | **10** | **22** | -12 | 🟡 Good | 6/10 | 0/4 | 3/6 | 1/2 |
| 15 | 🔴 MISMATCH_DOMAIN | Trần Minh Đức | Financial Analyst | **25** | **30** | -5 | 🟢 Excellent | 14/14 | 3/7 | 5/6 | 2/3 |
| 16 | 🟡 MATCH_MEDIUM | Trần Minh Đức | Cloud Infrastructure Enginee | **48** | **60** | -12 | 🟡 Good | 23/30 | 15/18 | 5/7 | 6/5 |
| 17 | 🟡 MATCH_MEDIUM | Lê Thị Hồng Phượng | Data Analyst | **26** | **37** | -11 | 🟡 Good | 19/18 | 0/9 | 6/5 | 1/5 |
| 18 | 🟠 MATCH_LOW | Lê Thị Hồng Phượng | Senior Data Engineer | **37** | **25** | +12 | 🟡 Good | 30/12 | 0/5 | 6/5 | 1/3 |
| 19 | 🟢 MATCH_HIGH | Lê Thị Hồng Phượng | React Frontend Developer | **70** | **69** | +1 | 🟢 Excellent | 28/32 | 29/24 | 4/6 | 8/7 |
| 20 | 🟡 MATCH_MEDIUM | Lê Thị Hồng Phượng | Product Manager | **9** | **31** | -22 | 🟠 Fair | 6/14 | 0/8 | 2/5 | 1/4 |
| 21 | 🔴 MISMATCH_DOMAIN | Lê Thị Hồng Phượng | Growth Marketing Specialist | **9** | **22** | -13 | 🟡 Good | 6/10 | 0/4 | 2/5 | 1/3 |
| 22 | 🔴 MISMATCH_DOMAIN | Lê Thị Hồng Phượng | Technical Recruiter | **9** | **22** | -13 | 🟡 Good | 6/10 | 0/4 | 2/5 | 1/3 |
| 23 | 🔴 MISMATCH_DOMAIN | Lê Thị Hồng Phượng | Financial Analyst | **9** | **20** | -11 | 🟡 Good | 6/10 | 0/3 | 2/5 | 1/2 |
| 24 | 🔴 MISMATCH_DOMAIN | Lê Thị Hồng Phượng | Cloud Infrastructure Enginee | **29** | **19** | +10 | 🟡 Good | 21/8 | 2/4 | 6/5 | 1/2 |
| 25 | 🟡 MATCH_MEDIUM | Phạm Văn Kiên | Data Analyst | **27** | **38** | -11 | 🟡 Good | 17/18 | 3/9 | 4/6 | 2/5 |
| 26 | 🟠 MATCH_LOW | Phạm Văn Kiên | Senior Data Engineer | **14** | **22** | -8 | 🟡 Good | 9/10 | 2/4 | 2/5 | 0/3 |
| 27 | 🟡 MATCH_MEDIUM | Phạm Văn Kiên | React Frontend Developer | **10** | **29** | -19 | 🟠 Fair | 6/14 | 0/6 | 2/5 | 1/4 |
| 28 | 🟢 MATCH_HIGH | Phạm Văn Kiên | Product Manager | **67** | **69** | -2 | 🟢 Excellent | 25/35 | 29/21 | 4/6 | 8/7 |
| 29 | 🟡 MATCH_MEDIUM | Phạm Văn Kiên | Growth Marketing Specialist | **28** | **38** | -10 | 🟡 Good | 17/18 | 4/9 | 4/6 | 2/5 |
| 30 | 🔴 MISMATCH_DOMAIN | Phạm Văn Kiên | Technical Recruiter | **23** | **23** | +0 | 🟢 Excellent | 17/10 | 0/5 | 4/5 | 1/3 |
| 31 | 🔴 MISMATCH_DOMAIN | Phạm Văn Kiên | Financial Analyst | **31** | **31** | +0 | 🟢 Excellent | 18/14 | 4/7 | 6/6 | 3/4 |
| 32 | 🔴 MISMATCH_DOMAIN | Phạm Văn Kiên | Cloud Infrastructure Enginee | **9** | **22** | -13 | 🟡 Good | 6/10 | 0/4 | 2/5 | 1/3 |
| 33 | 🟡 MATCH_MEDIUM | Vũ Minh Thư | Data Analyst | **7** | **24** | -17 | 🟠 Fair | 3/10 | 0/4 | 3/5 | 1/5 |
| 34 | 🟠 MATCH_LOW | Vũ Minh Thư | Senior Data Engineer | **5** | **13** | -8 | 🟡 Good | 1/5 | 0/2 | 3/4 | 1/2 |
| 35 | 🟠 MATCH_LOW | Vũ Minh Thư | React Frontend Developer | **7** | **14** | -7 | 🟡 Good | 3/5 | 0/2 | 3/4 | 1/3 |
| 36 | 🟠 MATCH_LOW | Vũ Minh Thư | Product Manager | **21** | **22** | -1 | 🟢 Excellent | 11/8 | 0/5 | 8/4 | 1/5 |
| 37 | 🟢 MATCH_HIGH | Đặng Thu Hà | Technical Recruiter | **71** | **69** | +2 | 🟢 Excellent | 28/32 | 28/24 | 6/6 | 8/7 |
| 38 | 🔴 MISMATCH_DOMAIN | Đặng Thu Hà | Product Manager | **28** | **23** | +5 | 🟢 Excellent | 21/10 | 0/5 | 6/5 | 1/3 |
| 39 | 🟡 MATCH_MEDIUM | Hoàng Thị Lan Anh | Financial Analyst | **40** | **38** | +2 | 🟢 Excellent | 28/16 | 3/10 | 6/6 | 3/6 |
| 40 | 🔴 MISMATCH_DOMAIN | Hoàng Thị Lan Anh | Cloud Infrastructure Enginee | **6** | **13** | -7 | 🟡 Good | 4/5 | 0/2 | 2/4 | 0/2 |

## 7. Analysis & Observations

- **Strong correlation (r=0.891):** System scores are highly correlated with LLM reference scores, indicating good ranking alignment.
- **Low MAE (9.1 pts):** System scores are close to LLM reference on average. Good overall accuracy.
- **High agreement rate (88%):** System and LLM agree on most pair assessments.
- **Largest disagreements:**
  - Pair 5: Nguyễn Hoàng Nam vs Growth Marketing Specialist (diff = -22, rating: 🟠 Fair)
  - Pair 20: Lê Thị Hồng Phượng vs Product Manager (diff = -22, rating: 🟠 Fair)
  - Pair 13: Trần Minh Đức vs Growth Marketing Specialist (diff = -19, rating: 🟠 Fair)
  - Pair 27: Phạm Văn Kiên vs React Frontend Developer (diff = -19, rating: 🟠 Fair)
  - Pair 33: Vũ Minh Thư vs Data Analyst (diff = -17, rating: 🟠 Fair)

## 8. Recommendations

- System performance is satisfactory. Continue monitoring and expanding the benchmark.
- Consider adding more diverse JD-CV pairs across additional industry verticals.

## 9. Methodology

| Item | Detail |
|---|---|
| **System scoring** | `hybrid_scoring.calculate_hybrid_score()` — formula-based with sentence-transformer embedding similarity |
| **Reference scoring** | Assistant's own reasoning applying the scoring rubric (Experience 0-50, Skills 0-30, Education 0-10, Career Objectives 0-10) |
| **Benchmark size** | 40 pairs: 8 CVs × 8 JDs (full cross-product) |
| **Domains covered** | tech_data, tech_software, tech_devops, operations, marketing, hr, finance |
| **Seniority levels** | Fresher / Entry · Mid · Senior |
| **Ground truth** | LLM reference scores as proxy — used for calibration reference only |
