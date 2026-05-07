from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, insert, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db_models import CommandUsageOrm


class CommandUsageRepository:
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def try_register(
        self,
        chat_id: int,
        user_id: int,
        command: str,
        max_requests: int,
        window: timedelta,
    ) -> bool:
        window_start = datetime.now(UTC) - window

        async with self._session_factory() as session:
            await session.execute(
                delete(CommandUsageOrm).where(
                    CommandUsageOrm.created_at < window_start
                )
            )

            usages_count = await session.scalar(
                select(func.count())
                .select_from(CommandUsageOrm)
                .where(CommandUsageOrm.chat_id == chat_id)
                .where(CommandUsageOrm.user_id == user_id)
                .where(CommandUsageOrm.command == command)
                .where(CommandUsageOrm.created_at >= window_start)
            )

            if usages_count is not None and usages_count >= max_requests:
                await session.commit()
                return False

            await session.execute(
                insert(CommandUsageOrm).values(
                    chat_id=chat_id,
                    user_id=user_id,
                    command=command,
                    created_at=datetime.now(UTC),
                )
            )
            await session.commit()

        return True
