from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db_models import MessageOrm
from app.models import StoredMessage


class MessageRepository:
    def __init__(
        self,
        session_factory: async_sessionmaker,
        max_messages_per_chat: int,
    ) -> None:
        self._session_factory = session_factory
        self._max_messages_per_chat = max_messages_per_chat

    async def add(self, message: StoredMessage) -> None:
        async with self._session_factory() as session:
            await session.execute(
                insert(MessageOrm)
                .prefix_with("OR IGNORE")
                .values(
                    chat_id=message.chat_id,
                    telegram_message_id=message.telegram_message_id,
                    user_id=message.user_id,
                    username=message.username,
                    first_name=message.first_name,
                    text=message.text,
                    created_at=message.created_at,
                )
            )
            await self._trim_chat(session, message.chat_id)
            await session.commit()

    async def get_latest(self, chat_id: int, limit: int) -> list[StoredMessage]:
        async with self._session_factory() as session:
            result = await session.scalars(
                select(MessageOrm)
                .where(MessageOrm.chat_id == chat_id)
                .order_by(MessageOrm.telegram_message_id.desc())
                .limit(limit)
            )
            messages = [_orm_to_message(row) for row in result.all()]

        return list(reversed(messages))

    async def search(self, chat_id: int, query: str, limit: int) -> list[StoredMessage]:
        normalized_query = query.lower()

        async with self._session_factory() as session:
            result = await session.scalars(
                select(MessageOrm)
                .where(MessageOrm.chat_id == chat_id)
                .order_by(MessageOrm.telegram_message_id.desc())
                .limit(self._max_messages_per_chat)
            )
            messages = [
                _orm_to_message(row)
                for row in result.all()
                if normalized_query in row.text.lower()
            ][:limit]

        return list(reversed(messages))

    async def _trim_chat(self, session: AsyncSession, chat_id: int) -> None:
        latest_ids = (
            select(MessageOrm.id)
            .where(MessageOrm.chat_id == chat_id)
            .order_by(MessageOrm.telegram_message_id.desc())
            .limit(self._max_messages_per_chat)
        )

        await session.execute(
            delete(MessageOrm)
            .where(MessageOrm.chat_id == chat_id)
            .where(MessageOrm.id.not_in(latest_ids))
        )


def _orm_to_message(row: MessageOrm) -> StoredMessage:
    return StoredMessage(
        chat_id=row.chat_id,
        telegram_message_id=row.telegram_message_id,
        user_id=row.user_id,
        username=row.username,
        first_name=row.first_name,
        text=row.text,
        created_at=row.created_at,
    )
