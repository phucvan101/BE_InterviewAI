from .cv_profile import CVProfile
from .job_description import JobDescription
from .company_info import CompanyInfo
from .analysis_session import AnalysisSession

# Feedback Agent models (optional). Imported with try/except so that
# branches without the feedback_agent module (e.g. rebuild_feature_upCV)
# still import this package cleanly. The tables are only created when the
# agent is enabled and the corresponding migration is in place.
try:
    from .score_override import ScoreOverride  # noqa: F401
    from .feedback_log import FeedbackLog  # noqa: F401
    _agent_models_available = True
except ImportError:
    _agent_models_available = False


__all__ = [
    "CVProfile",
    "JobDescription",
    "CompanyInfo",
    "AnalysisSession",
    "ScoreOverride",
    "FeedbackLog",
]


def agent_models_available() -> bool:
    """Helper for runtime checks: are the optional agent models loaded?"""
    return _agent_models_available
