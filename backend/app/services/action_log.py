from sqlalchemy.ext.asyncio import AsyncSession

from app.models.action_log import ActionLog
from app.models.user import User


async def log_action(
    session: AsyncSession,
    actor: User,
    action: str,
    entity_type: str,
    entity_id: int,
    details: str = "",
) -> None:
    """Record one key operation into the audit trail.

    Adds the row to the caller's session so it commits atomically with the
    operation being logged — the caller is responsible for the commit.
    """
    session.add(
        ActionLog(
            actor_id=actor.id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
        )
    )
