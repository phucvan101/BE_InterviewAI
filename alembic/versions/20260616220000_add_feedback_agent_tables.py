"""add_feedback_agent_tables

Revision ID: 20260616220000
Revises: b23551a6ec8d
Create Date: 2026-06-16 22:00:00.000000

This migration adds two tables used by the optional Feedback Agent module:

- score_overrides: audit trail of section-level score overrides applied
  by the agent (or manually) per (user, cv, jd, section).
- feedback_logs: full audit log of every user feedback processed by the
  agent, including the LLM evaluation, applied overrides and snapshot
  texts for forensic analysis.

Both tables are isolated from the core scoring flow. They are referenced
only when the ``feedback_agent`` package and its SQLAlchemy models are
imported (which only happens in branches where the agent is enabled —
see alembic/env.py for the conditional import).

Reverting this migration is safe: it drops both tables, leaving the rest
of the schema untouched.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260616220000"
down_revision: Union[str, None] = "b23551a6ec8d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── score_overrides ─────────────────────────────────────────────────────
    op.create_table(
        "score_overrides",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("id_cv", sa.Integer(), nullable=False),
        sa.Column("id_jd", sa.Integer(), nullable=False),
        sa.Column("id_session", sa.Integer(), nullable=True),
        sa.Column(
            "section",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column("original_value", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("override_value", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column(
            "source",
            sa.String(length=32),
            nullable=False,
            server_default="agent_auto",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["id_cv"], ["cv_profiles.id_cv"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["id_jd"], ["job_descriptions.id_jd"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["id_session"],
            ["analysis_sessions.id_session"],
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_score_overrides_user_id", "score_overrides", ["user_id"])
    op.create_index("ix_score_overrides_id_cv", "score_overrides", ["id_cv"])
    op.create_index("ix_score_overrides_id_jd", "score_overrides", ["id_jd"])
    op.create_index(
        "ix_score_overrides_session", "score_overrides", ["id_session"]
    )

    # ── feedback_logs ────────────────────────────────────────────────────────
    op.create_table(
        "feedback_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("id_session", sa.Integer(), nullable=True),
        sa.Column("id_cv", sa.Integer(), nullable=True),
        sa.Column("id_jd", sa.Integer(), nullable=True),
        sa.Column("cv_text", sa.Text(), nullable=True),
        sa.Column("jd_text", sa.Text(), nullable=True),
        sa.Column("feedback_text", sa.Text(), nullable=False),
        # JSONB on Postgres, JSON fallback on SQLite for local tests
        sa.Column(
            "agent_evaluation",
            sa.JSON().with_variant(
                sa.dialects.postgresql.JSONB(), "postgresql"
            ),
            nullable=True,
        ),
        sa.Column(
            "applied_overrides",
            sa.JSON().with_variant(
                sa.dialects.postgresql.JSONB(), "postgresql"
            ),
            nullable=True,
        ),
        sa.Column("is_valid", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("learned_rule", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["id_session"],
            ["analysis_sessions.id_session"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["id_cv"], ["cv_profiles.id_cv"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["id_jd"], ["job_descriptions.id_jd"], ondelete="SET NULL"),
    )
    op.create_index("ix_feedback_logs_user_id", "feedback_logs", ["user_id"])
    op.create_index(
        "ix_feedback_logs_session", "feedback_logs", ["id_session"]
    )
    op.create_index(
        "ix_feedback_logs_created_at", "feedback_logs", ["created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_feedback_logs_created_at", table_name="feedback_logs")
    op.drop_index("ix_feedback_logs_session", table_name="feedback_logs")
    op.drop_index("ix_feedback_logs_user_id", table_name="feedback_logs")
    op.drop_table("feedback_logs")

    op.drop_index("ix_score_overrides_session", table_name="score_overrides")
    op.drop_index("ix_score_overrides_id_jd", table_name="score_overrides")
    op.drop_index("ix_score_overrides_id_cv", table_name="score_overrides")
    op.drop_index("ix_score_overrides_user_id", table_name="score_overrides")
    op.drop_table("score_overrides")
