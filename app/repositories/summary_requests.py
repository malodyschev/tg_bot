from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, insert, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db_models import SummaryRequestOrm


class SummaryRequestRepository:
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def try_register(
        self,
        chat_id: int,
        user_id: int | None,
        max_requests: int,
        window: timedelta,
    ) -> bool:
        window_start = datetime.now(UTC) - window

        async with self._session_factory() as session:
            await session.execute(
                delete(SummaryRequestOrm).where(
                    SummaryRequestOrm.created_at < window_start
                )
            )

            requests_count = await session.scalar(
                select(func.count())
                .select_from(SummaryRequestOrm)
                .where(SummaryRequestOrm.chat_id == chat_id)
                .where(SummaryRequestOrm.user_id == user_id)
                .where(SummaryRequestOrm.created_at >= window_start)
            )

            if requests_count is not None and requests_count >= max_requests:
                await session.commit()
                return False

            await session.execute(
                insert(SummaryRequestOrm).values(
                    chat_id=chat_id,
                    user_id=user_id,
                    created_at=datetime.now(UTC),
                )
            )
            await session.commit()

        return True
