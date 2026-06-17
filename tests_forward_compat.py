"""
Forward-compat test: verifies the agent's alembic migration generates
the expected SQL on the new branch (i.e. when the agent module IS
present and the migration IS in the versions/ directory).
"""
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(r"c:\Users\pc\Documents\code\DATN\BE_InterviewAI")

print("[1] Running alembic upgrade to head (online) is not possible without DB;")
print("    using offline --sql mode to validate env.py + migrations.\n")

print("[2] Generating SQL for the agent's new migration (b23551a6ec8d -> 20260616220000)...")
result = subprocess.run(
    ["alembic", "upgrade", "b23551a6ec8d:20260616220000", "--sql"],
    cwd=str(REPO),
    capture_output=True,
    text=True,
    env={**os.environ, "PYTHONPATH": str(REPO)},
)
if result.returncode != 0:
    print(f"alembic FAILED:\n{result.stderr[-1500:]}")
    sys.exit(1)
sql = result.stdout
print(f"  OK - {len(sql.splitlines())} SQL lines generated")

# Look for our two tables
for table in ("score_overrides", "feedback_logs"):
    if f"CREATE TABLE {table}" in sql:
        print(f"  OK - '{table}' present in SQL")
    else:
        print(f"  FAIL - '{table}' MISSING in SQL:")
        print(sql[:3000])
        sys.exit(1)

# Check indexes
for idx in (
    "ix_score_overrides_user_id",
    "ix_score_overrides_id_cv",
    "ix_feedback_logs_user_id",
    "ix_feedback_logs_session",
    "ix_feedback_logs_created_at",
):
    if f"CREATE INDEX {idx}" in sql:
        print(f"  OK - index '{idx}' present")
    else:
        print(f"  FAIL - index '{idx}' MISSING")
        sys.exit(1)

# Sanity: foreign keys
if "REFERENCES users (id)" in sql:
    print("  OK - FK to users(id) present")
else:
    print("  FAIL - FK to users(id) MISSING")
    sys.exit(1)
if "REFERENCES cv_profiles (id_cv)" in sql:
    print("  OK - FK to cv_profiles(id_cv) present")
else:
    print("  FAIL - FK to cv_profiles(id_cv) MISSING")
    sys.exit(1)
if "REFERENCES job_descriptions (id_jd)" in sql:
    print("  OK - FK to job_descriptions(id_jd) present")
else:
    print("  FAIL - FK to job_descriptions(id_jd) MISSING")
    sys.exit(1)
if "REFERENCES analysis_sessions (id_session)" in sql:
    print("  OK - FK to analysis_sessions(id_session) present")
else:
    print("  FAIL - FK to analysis_sessions(id_session) MISSING")
    sys.exit(1)

# Sanity: JSONB for Postgres
if "JSONB" in sql:
    print("  OK - JSONB columns present (PostgreSQL)")
else:
    print("  WARN - JSONB not detected (running in PostgreSQL offline mode expected)")

print("\n=== FORWARD-COMPAT TEST PASSED ===")
print("The new agent migration generates the correct DDL.")
