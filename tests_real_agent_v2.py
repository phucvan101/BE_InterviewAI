"""
Real-agent evaluation suite for FeedbackAgentV2 (LangChain + LangGraph).

Runs 10 real-world cases against the live Gemini model via the
LangChain adapter, and grades the agent on:

  * schema compliance       (does it emit valid JSON)
  * complaint validity      (is_valid_complaint reasonable)
  * learning decisions      (synonyms, patterns, thresholds, rules)
  * tool-calling            (does V2 actually call tools during the loop)
  * end-to-end side-effects (apply_learning succeeds without errors)

Run::

    conda run -n interviewAI python tests_real_agent_v2.py

This script writes a per-case JSONL record into
``storage/agent_real_eval/<case_id>.jsonl`` and prints a summary
table to stdout.
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

REPO = Path(r"c:\Users\pc\Documents\code\DATN\BE_InterviewAI")
sys.path.insert(0, str(REPO))

logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("real_eval")
log.setLevel(logging.INFO)

from app.feature.feature_up_cv.feedback_agent.agent_v2 import (
    FeedbackAgentV2,
    get_feedback_agent,
    get_react_graph,
)
from app.feature.feature_up_cv.feedback_agent.pending_rules import (
    PendingRuleStore,
    get_pending_rule_store,
)
from app.feature.feature_up_cv.feedback_agent.observability import get_trace_stats
from app.feature.feature_up_cv.feedback_agent.prompts import FeedbackEvaluation
from app.feature.feature_up_cv.feedback_agent.memory_faiss import get_agent_memory
from app.feature.feature_up_cv.feedback_agent.synonym_manager import (
    get_synonym_manager,
)
from app.feature.feature_up_cv.feedback_agent.synonym_manager import _DEFAULT_YAML as _SYNONYMS_FILE
from app.feature.feature_up_cv.feedback_agent.pattern_manager import get_pattern_manager
from app.feature.feature_up_cv.feedback_agent.pattern_manager import _DEFAULT_YAML as _PATTERNS_FILE
from app.feature.feature_up_cv.feedback_agent.threshold_manager import get_threshold_manager
from app.feature.feature_up_cv.feedback_agent.threshold_manager import _DEFAULT_YAML as _THRESHOLDS_FILE

# Backup the YAMLs in case the agent mutates them
_BACKUP_DIR = REPO / "storage" / "agent_real_eval" / "_backups"
_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
for f in [_SYNONYMS_FILE, _PATTERNS_FILE, _THRESHOLDS_FILE]:
    if f.exists():
        dst = _BACKUP_DIR / f.name
        if not dst.exists():
            dst.write_text(f.read_text(encoding="utf-8"), encoding="utf-8")

_EVAL_DIR = REPO / "storage" / "agent_real_eval"
_EVAL_DIR.mkdir(parents=True, exist_ok=True)


# ── Grading dimensions ──────────────────────────────────────────
@dataclass
class Grade:
    case_id: str
    description: str
    schema_ok: bool = False
    evaluation: Optional[FeedbackEvaluation] = None
    valid_complaint_correct: Optional[bool] = None
    learning_correct: Optional[bool] = None
    tool_invoked: bool = False
    tool_names: List[str] = field(default_factory=list)
    apply_ok: bool = False
    apply_result: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    latency_sec: float = 0.0
    notes: List[str] = field(default_factory=list)
    score: int = 0

    def compute_score(self) -> None:
        items = [
            self.schema_ok,                      # 20
            self.valid_complaint_correct in (True, None),  # 20
            self.learning_correct in (True, None),  # 25
            self.apply_ok,                        # 25
            self.error is None,                   # 10
        ]
        weights = [20, 20, 25, 25, 10]
        total = sum(w for w, ok in zip(weights, items) if ok)
        # Tool use is a bonus, not a requirement — Gemini text-mode
        # often answers short cases without tool calls, which is fine.
        if self.tool_invoked:
            total = min(100, total + 5)
        self.score = total


# ── Test cases ──────────────────────────────────────────────────
CV_FE_JUNIOR = """
Nguyễn Văn A — Front-End Developer
Kinh nghiệm: 2 năm
Kỹ năng: JavaScript, React, HTML, CSS, Tailwind, Git, Figma
Dự án:
- Xây dựng landing page cho shop bán hoa dùng React + Tailwind (2024)
- Clone giao diện Tiki bằng HTML/CSS thuần (2023)
"""

JD_FE_JUNIOR = """
Công ty TNHH ABC tuyển Front-End Developer (Fresher/Junior)
Yêu cầu:
- 0-2 năm kinh nghiệm
- ReactJS, JavaScript, HTML/CSS
- Có kinh nghiệm TailwindCSS là lợi thế
- Biết Git, Figma
Mô tả: Tham gia phát triển SPA cho khách hàng Nhật, làm việc với designer.
"""

CV_FULLSTACK = """
Trần Thị B — Full-stack Developer
5 năm kinh nghiệm Node.js
Kỹ năng: JavaScript, TypeScript, Node.js, Express.js, MongoDB, Docker, AWS, React
Kinh nghiệm:
- Lead backend team 2 năm tại fintech startup
- Tích hợp cổng thanh toán VNPay, Momo
- Xây dựng microservice với Docker + AWS ECS
"""

JD_BACKEND = """
Senior Backend Engineer — Công ty Fintech
- 4+ năm Node.js
- Express.js hoặc Nest.js
- MongoDB, PostgreSQL
- Docker, AWS
- Tích hợp payment gateway
"""

CV_PHP_DEV = """
Lê Văn C — PHP Developer
6 năm kinh nghiệm
Kỹ năng: PHP, Laravel, MySQL, jQuery, HTML, CSS
"""

JD_PYTHON = """
Python/Django Backend Developer
- 3+ năm Python
- Django hoặc FastAPI
- PostgreSQL, Redis
"""

CV_DEVOPS = """
Phạm Thị D — DevOps Engineer
4 năm kinh nghiệm
Kỹ năng: Docker, Kubernetes, AWS, Terraform, Jenkins, Linux, Bash
"""

JD_DEVOPS = """
DevOps Engineer
- 3+ năm kinh nghiệm
- K8s, Docker, AWS/GCP
- CI/CD pipelines
- Infrastructure as Code
"""

CV_DATA = """
Hoàng Văn E — Data Engineer
3 năm kinh nghiệm
Python, SQL, Airflow, Spark, BigQuery, ETL pipelines
"""

JD_DATA_SR = """
Senior Data Engineer
- 5+ năm kinh nghiệm
- Spark, Kafka
- Cloud (AWS/GCP/Azure)
- Streaming pipelines
"""

CV_FRESHER = """
Sinh viên năm cuối F — mới ra trường
Thực tập 3 tháng tại startup, làm React
Kỹ năng: HTML, CSS, JavaScript cơ bản, Git
"""

JD_SR_FE = """
Senior Front-End Engineer
- 5+ năm React/Vue
- TypeScript, GraphQL
- Testing, CI/CD
- Lương U.S. client
"""

CV_GOOGLE = """
Vũ Văn G — Mobile Developer
- React Native, Flutter, iOS Swift, Android Kotlin
- 4 năm kinh nghiệm
- Google Play Store, Apple App Store
"""

JD_GOOGLE_FE = """
Front-End Engineer
- ReactJS, TypeScript
- Google Analytics, A/B testing
- Công ty sản phẩm SaaS quy mô lớn
"""

CV_TESTER = """
Đỗ Thị H — QA/Tester
3 năm kinh nghiệm
- Manual testing, Selenium, Postman
- JIRA, TestRail
"""

JD_QA_AUTO = """
Senior QA Automation Engineer
- 4+ năm kinh nghiệm
- Playwright / Cypress
- CI/CD tích hợp test
"""

CV_IOT = """
Đặng Văn I — IoT Engineer
- 3 năm kinh nghiệm
- C/C++, Embedded C, FreeRTOS, STM32, MQTT
"""

JD_IOT_TL = """
IoT Team Lead
- 5+ năm embedded
- C/C++, FreeRTOS
- Quản lý team 3-5 người
"""

CV_REACT_TS = """
Bùi Thị K — Front-End Developer
- 2 năm kinh nghiệm React
- TypeScript, Next.js, React Query
- Dự án: e-commerce site với React + TypeScript
"""

JD_NEXTJS = """
Senior Front-End (Next.js)
- 4+ năm Next.js, React
- TypeScript bắt buộc
- SSR, ISR, app router
"""


# ── Cases ───────────────────────────────────────────────────────
CASES: List[Dict[str, Any]] = [
    {
        "id": "r1_synonym_react_typescript",
        "description": "React+TypeScript compound bị miss → pattern compound_skill",
        "cv_text": CV_REACT_TS,
        "jd_text": JD_NEXTJS,
        "current_scores": {"skills_score": 10, "experience_score": 20},
        "feedback_text": "Hệ thống không nhận ra React + TypeScript là một kỹ năng mạnh. JD nói rõ TypeScript bắt buộc, tôi có 2 năm TypeScript + React.",
        "expect_complaint_valid": True,
        "expect_learning_action": ["new_patterns", "new_synonyms"],
    },
    {
        "id": "r2_synonym_express_nest",
        "description": "Express.js vs Nest.js — synonym bị miss",
        "cv_text": CV_FULLSTACK,
        "jd_text": JD_BACKEND,
        "current_scores": {"skills_score": 18},
        "feedback_text": "Tôi dùng Express.js nhiều năm nhưng JD yêu cầu 'Express.js hoặc Nest.js' — hệ thống chỉ match mỗi Express.js mà không thấy Nest.js cũng cùng họ Node.js framework.",
        "expect_complaint_valid": True,
        "expect_learning_action": ["new_synonyms"],
    },
    {
        "id": "r3_pattern_payment_integration",
        "description": "Tích hợp cổng thanh toán — context_phrase",
        "cv_text": CV_FULLSTACK,
        "jd_text": JD_BACKEND,
        "current_scores": {"skills_score": 15},
        "feedback_text": "CV tôi có ghi 'tích hợp cổng thanh toán VNPay, Momo' nhưng hệ thống không match vào yêu cầu 'tích hợp payment gateway'. Cụm từ tự nhiên này nên được hiểu là payment-integration.",
        "expect_complaint_valid": True,
        "expect_learning_action": ["new_patterns"],
    },
    {
        "id": "r4_threshold_natural_language",
        "description": "Threshold quá cao cho technical_skill khi CV mô tả tự nhiên",
        "cv_text": CV_FULLSTACK,
        "jd_text": JD_BACKEND,
        "current_scores": {"skills_score": 12},
        "feedback_text": "Tôi có đầy đủ kỹ năng nhưng điểm skills vẫn thấp. Hệ thống nên nới threshold perfect_match cho technical_skill vì CV mô tả tự nhiên kiểu Việt Nam.",
        "expect_complaint_valid": True,
        "expect_learning_action": ["threshold_adjustments"],
    },
    {
        "id": "r5_invalid_complaint_skill_mismatch",
        "description": "Khiếu nại sai: PHP dev xin việc Python",
        "cv_text": CV_PHP_DEV,
        "jd_text": JD_PYTHON,
        "current_scores": {"skills_score": 5, "experience_score": 10},
        "feedback_text": "Tôi thấy điểm skills quá thấp, tôi có 6 năm kinh nghiệm backend, JD nói backend thì tôi hợp lý.",
        "expect_complaint_valid": False,
        "expect_learning_action": [],
    },
    {
        "id": "r6_underqualified_seniority",
        "description": "Fresher xin việc Senior — khiếu nại về seniority score",
        "cv_text": CV_FRESHER,
        "jd_text": JD_SR_FE,
        "current_scores": {"experience_score": 2},
        "feedback_text": "Tôi làm React quen rồi, JD có React nên tôi xứng đáng được điểm experience cao hơn.",
        "expect_complaint_valid": False,
        "expect_learning_action": [],
    },
    {
        "id": "r7_underqualified_years",
        "description": "Data engineer 3 năm xin job Senior 5+ năm",
        "cv_text": CV_DATA,
        "jd_text": JD_DATA_SR,
        "current_scores": {"experience_score": 25},
        "feedback_text": "Tôi thấy JD nói 5+ năm là max nhưng tôi làm tương đương 3 năm mà ghi '5+'. Điểm experience nên cao hơn.",
        "expect_complaint_valid": False,
        "expect_learning_action": [],
    },
    {
        "id": "r8_overqualified_penalty",
        "description": "Mobile dev bị penalty vì JD Frontend có chữ 'Google'",
        "cv_text": CV_GOOGLE,
        "jd_text": JD_GOOGLE_FE,
        "current_scores": {"experience_score": 15},
        "feedback_text": "Tôi có Google Play Store, Apple App Store — JD nói 'Google Analytics' cũng là Google. Hệ thống match nhầm.",
        "expect_complaint_valid": True,
        "expect_learning_action": ["new_synonyms"],  # probably not, but try
    },
    {
        "id": "r9_company_fit_missing_data",
        "description": "CV không upload CI file nhưng JD có tên công ty",
        "cv_text": CV_FULLSTACK,
        "jd_text": "Công ty VNG Corporation đang tuyển Senior Backend Engineer làm fintech. " + JD_BACKEND,
        "current_scores": {"company_fit_score": 0},
        "feedback_text": "Điểm company_fit = 0 nhưng JD có ghi tên công ty VNG Corporation, hệ thống nên tự tra cứu.",
        "expect_complaint_valid": True,
        "expect_learning_action": ["learned_rule"],
    },
    {
        "id": "r10_learned_rule_generalisation",
        "description": "Rút ra learned_rule tổng quát cho Nest.js = Express.js",
        "cv_text": CV_FULLSTACK,
        "jd_text": JD_BACKEND,
        "current_scores": {"skills_score": 20},
        "feedback_text": "Nest.js là framework được xây trên Express.js, hai cái này thực tế cùng họ Node.js framework, nên ghi nhớ cho lần sau.",
        "expect_complaint_valid": True,
        "expect_learning_action": ["learned_rule"],
    },
]


# ── Run a single case ──────────────────────────────────────────
async def _run_case(case: Dict[str, Any], v2: FeedbackAgentV2) -> Grade:
    grade = Grade(case_id=case["id"], description=case["description"])
    t0 = time.perf_counter()
    try:
        # Use evaluate_with_trace to also capture the message trace
        result = await v2.evaluate_with_trace(
            cv_text=case["cv_text"],
            jd_text=case["jd_text"],
            feedback_text=case["feedback_text"],
            current_scores=case.get("current_scores"),
        )
        grade.latency_sec = time.perf_counter() - t0
        ev: Optional[FeedbackEvaluation] = result.get("evaluation")
        grade.evaluation = ev

        if ev is None:
            grade.error = "no_evaluation_returned"
            grade.compute_score()
            return grade

        # ── schema_ok ─────────────────────────────────────
        grade.schema_ok = True

        # ── tool_invoked ──────────────────────────────────
        msgs = result.get("messages", [])
        invoked_names: List[str] = []
        for m in msgs:
            tcs = m.get("tool_calls") or []
            for tc in tcs:
                n = tc.get("name") if isinstance(tc, dict) else None
                if n:
                    invoked_names.append(n)
        grade.tool_invoked = bool(invoked_names)
        grade.tool_names = invoked_names

        # ── complaint validity ───────────────────────────
        grade.valid_complaint_correct = (
            ev.is_valid_complaint == case["expect_complaint_valid"]
        )
        if not grade.valid_complaint_correct:
            grade.notes.append(
                f"is_valid_complaint={ev.is_valid_complaint} (expected {case['expect_complaint_valid']})"
            )

        # ── learning decisions ───────────────────────────
        actions_taken: List[str] = []
        if ev.new_synonyms:
            actions_taken.append("new_synonyms")
        if ev.new_patterns:
            actions_taken.append("new_patterns")
        if ev.threshold_adjustments:
            actions_taken.append("threshold_adjustments")
        if ev.learned_rule:
            actions_taken.append("learned_rule")
        if ev.proposed_overrides:
            actions_taken.append("proposed_overrides")
        if ev.proposed_adjustments:
            actions_taken.append("proposed_adjustments")
        if ev.proposed_new_rule_type:
            actions_taken.append("proposed_new_rule_type")

        expected_actions = case.get("expect_learning_action", [])
        if not expected_actions:
            # should NOT take learning action
            if not actions_taken:
                grade.learning_correct = True
            else:
                grade.learning_correct = False
                grade.notes.append(f"unexpected learning: {actions_taken}")
        else:
            # should take AT LEAST one of the expected actions
            hit = any(a in actions_taken for a in expected_actions)
            grade.learning_correct = hit
            if not hit:
                grade.notes.append(
                    f"expected {expected_actions}, got {actions_taken}"
                )

        # ── apply_learning side-effects ──────────────────
        try:
            apply_result = v2.apply_learning(ev)
            grade.apply_ok = True
            grade.apply_result = apply_result
        except Exception as e:
            grade.error = f"apply_failed: {e}"
            grade.notes.append(f"apply_learning raised: {e}")

    except Exception as e:
        grade.latency_sec = time.perf_counter() - t0
        grade.error = f"evaluate_crashed: {e}"
        grade.notes.append(f"traceback in logs")
        log.exception("case %s crashed", case["id"])

    grade.compute_score()
    return grade


# ── Write grade to JSONL ───────────────────────────────────────
def _dump_grade(grade: Grade, case: Dict[str, Any]) -> None:
    path = _EVAL_DIR / f"{grade.case_id}.jsonl"

    def _default(o: Any) -> Any:
        if isinstance(o, set):
            return sorted(list(o))
        if hasattr(o, "model_dump"):
            return o.model_dump()
        return str(o)

    record = {
        "case": {k: v for k, v in case.items() if k not in ("cv_text", "jd_text")},
        "grade": {
            "case_id": grade.case_id,
            "description": grade.description,
            "schema_ok": grade.schema_ok,
            "valid_complaint_correct": grade.valid_complaint_correct,
            "learning_correct": grade.learning_correct,
            "tool_invoked": grade.tool_invoked,
            "tool_names": grade.tool_names,
            "apply_ok": grade.apply_ok,
            "error": grade.error,
            "latency_sec": round(grade.latency_sec, 2),
            "score": grade.score,
            "notes": grade.notes,
            "evaluation": (
                grade.evaluation.model_dump() if grade.evaluation else None
            ),
            "apply_result": grade.apply_result,
        },
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False, default=_default) + "\n")


# ── Main ───────────────────────────────────────────────────────
async def _main() -> int:
    v2 = FeedbackAgentV2()
    grades: List[Grade] = []

    for case in CASES:
        log.info("=== %s ===", case["id"])
        g = await _run_case(case, v2)
        _dump_grade(g, case)
        grades.append(g)
        status = "PASS" if g.score >= 60 else "FAIL"
        print(
            f"[{g.score:3d}%] {status} {g.case_id}: {g.description[:60]} "
            f"({g.latency_sec:.1f}s, tools={g.tool_names or '[]'})"
        )
        for n in g.notes:
            print(f"    ! {n}")
        if g.evaluation is not None:
            print(
                f"      is_valid={g.evaluation.is_valid_complaint}, "
                f"learned_rule={bool(g.evaluation.learned_rule)}, "
                f"syns={len(g.evaluation.new_synonyms or [])}, "
                f"pats={len(g.evaluation.new_patterns or [])}"
            )

    # Summary
    total = sum(g.score for g in grades)
    avg = total / len(grades)
    print(f"\n=== AGGREGATE: {avg:.1f} / 100 ===")
    print(f"Tool invocations across all cases: {sum(1 for g in grades if g.tool_invoked)}/{len(grades)}")
    print(f"Eval dump: {_EVAL_DIR}")

    return 0 if avg >= 60 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
