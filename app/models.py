"""
Import all models here to register them with SQLAlchemy Base.
This file is used by Alembic to discover all models for migrations.
"""

from app.feature.auth.models.user import User
from app.feature.admin.roles.models.role import Role
from app.feature.audit.models.audit_log import AuditLog
from app.feature.conversation.model.conversation import Conversation
from app.feature.feature_up_cv.auth.models.analysis_session import AnalysisSession

__all__ = ["User", "Role", "AuditLog", "Conversation", "AnalysisSession"]
