from aiogram import F, Router
from aiogram.types import Message

from app.models import StoredMessage
from app.repositories.messages import MessageRepository

router = Router()


@router.message(F.text)
async def store_text_message(
    message: Message,
    message_repository: MessageRepository,
) -> None:
    if not message.text or message.text.startswith("/"):
        return

    user = message.from_user
    await message_repository.add(
        StoredMessage(
            chat_id=message.chat.id,
            telegram_message_id=message.message_id,
            user_id=user.id if user else None,
            username=user.username if user else None,
            first_name=user.first_name if user else None,
            text=message.text,
            created_at=message.date,
        )
    )
