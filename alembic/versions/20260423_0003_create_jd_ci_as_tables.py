"""Create job_descriptions, company_infos, analysis_sessions tables and modify cv_profiles

Revision ID: 20260423_0003
Revises: 20260422_0002
Create Date: 2026-04-23
"""

from alembic import op
import sqlalchemy as sa


revision = "20260423_0003"
down_revision = "20260422_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Modify cv_profiles table FIRST (before creating tables that reference it)
    # Step 1: Rename id column to id_cv
    op.alter_column("cv_profiles", "id", new_column_name="id_cv")

    # Step 2: Drop columns
    op.drop_column("cv_profiles", "summary")
    op.drop_column("cv_profiles", "years_of_experience")
    op.drop_column("cv_profiles", "skills")
    op.drop_column("cv_profiles", "education")
    op.drop_column("cv_profiles", "work_experience")
    op.drop_column("cv_profiles", "updated_at")

    # Step 3: Rename cv_file_url to raw_file_url
    op.alter_column("cv_profiles", "cv_file_url", new_column_name="raw_file_url")

    # Step 4: Add new columns
    op.add_column("cv_profiles", sa.Column("parser_file_url", sa.String(255), nullable=True))
    op.add_column("cv_profiles", sa.Column("text_hashed", sa.String(255), nullable=True))

    # Create job_descriptions table
    op.create_table(
        "job_descriptions",
        sa.Column("id_jd", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("parser_file_url", sa.String(500), nullable=True),
        sa.Column("raw_file_url", sa.String(500), nullable=True),
        sa.Column("text_hashed", sa.String(255), nullable=True),
        sa.Column(
            "upload_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id_jd"),
    )
    op.create_index("ix_job_descriptions_user_id", "job_descriptions", ["user_id"])

    # Create company_infos table
    op.create_table(
        "company_infos",
        sa.Column("id_ci", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("parser_file_url", sa.String(500), nullable=True),
        sa.Column("raw_file_url", sa.String(500), nullable=True),
        sa.Column("text_hashed", sa.String(255), nullable=True),
        sa.Column(
            "upload_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id_ci"),
    )
    op.create_index("ix_company_infos_user_id", "company_infos", ["user_id"])

    # Create analysis_sessions table
    op.create_table(
        "analysis_sessions",
        sa.Column("id_session", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("id_cv", sa.Integer(), nullable=False),
        sa.Column("id_jd", sa.Integer(), nullable=False),
        sa.Column("id_ci", sa.Integer(), nullable=True),
        sa.Column("score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("experience_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("skills_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("education_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("companyfit_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("result_analysis_file_url", sa.String(500), nullable=True),
        sa.Column(
            "create_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["id_cv"], ["cv_profiles.id_cv"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["id_jd"], ["job_descriptions.id_jd"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["id_ci"], ["company_infos.id_ci"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id_session"),
    )
    op.create_index("ix_analysis_sessions_user_id", "analysis_sessions", ["user_id"])
    op.create_index("ix_analysis_sessions_id_cv", "analysis_sessions", ["id_cv"])
    op.create_index("ix_analysis_sessions_id_jd", "analysis_sessions", ["id_jd"])
    op.create_index("ix_analysis_sessions_id_ci", "analysis_sessions", ["id_ci"])


def downgrade() -> None:
    # Drop new tables
    op.drop_index("ix_analysis_sessions_id_ci", "analysis_sessions")
    op.drop_index("ix_analysis_sessions_id_jd", "analysis_sessions")
    op.drop_index("ix_analysis_sessions_id_cv", "analysis_sessions")
    op.drop_index("ix_analysis_sessions_user_id", "analysis_sessions")
    op.drop_table("analysis_sessions")

    op.drop_index("ix_company_infos_user_id", "company_infos")
    op.drop_table("company_infos")

    op.drop_index("ix_job_descriptions_user_id", "job_descriptions")
    op.drop_table("job_descriptions")

    # Reverse cv_profiles modifications
    # Remove new columns from cv_profiles
    op.drop_column("cv_profiles", "text_hashed")
    op.drop_column("cv_profiles", "parser_file_url")

    # Rename raw_file_url back to cv_file_url
    op.alter_column("cv_profiles", "raw_file_url", new_column_name="cv_file_url")

    # Add back dropped columns
    op.add_column("cv_profiles", sa.Column("work_experience", sa.Text(), nullable=True))
    op.add_column("cv_profiles", sa.Column("education", sa.Text(), nullable=True))
    op.add_column("cv_profiles", sa.Column("skills", sa.Text(), nullable=True))
    op.add_column("cv_profiles", sa.Column("years_of_experience", sa.Integer(), nullable=True))
    op.add_column("cv_profiles", sa.Column("summary", sa.Text(), nullable=True))
    op.add_column(
        "cv_profiles",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Rename id_cv back to id
    op.alter_column("cv_profiles", "id_cv", new_column_name="id")
