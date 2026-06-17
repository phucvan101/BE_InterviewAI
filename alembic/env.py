import asyncio
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from app.core.config import settings  # noqa: E402
from app.core.database import Base  # noqa: E402
from app.feature.auth import models as _auth_models  # noqa: F401,E402
from app.feature.audit import models as _audit_models  # noqa: F401,E402
from app.feature.admin.roles import models as _role_models  # noqa: F401,E402
from app.feature.feature_up_cv.auth import models as _cv_models  # noqa: F401,E402
from app.feature.conversation.model import (  # noqa: F401,E402
    Conversation,
    ConversationMessage,
    ConversationAnalysisReport,
)

# Feedback Agent models - OPTIONAL.
# Imported conditionally so that branches without the feedback_agent package
# (e.g. rebuild_feature_upCV) keep ``Base.metadata`` clean and `alembic upgrade`
# continues to work without errors. The two new tables (score_overrides and
# feedback_logs) are only created on branches where the agent is present
# and the corresponding migration has been merged in.
try:
    from app.feature.feature_up_cv.auth.models import (  # noqa: F401,E402
        score_override as _score_override_model,
    )
    from app.feature.feature_up_cv.auth.models import (  # noqa: F401,E402
        feedback_log as _feedback_log_model,
    )
except ImportError:
    # Branch does not include the feedback_agent module - safe to ignore.
    pass

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# This sets the target metadata for 'autogenerate'
target_metadata = Base.metadata

def run_migrations_offline() -> None:
    url = settings.DATABASE_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = settings.DATABASE_URL

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
