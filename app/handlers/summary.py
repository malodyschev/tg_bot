from datetime import timedelta

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.config import Settings
from app.repositories.summary_requests import SummaryRequestRepository
from app.services.summary import SummaryService

router = Router()

LIMIT_EXEMPT_USER_ID = 693505334
SUMMARY_REQUESTS_PER_DAY = 1


@router.message(Command("summary"))
async def summarize(
    message: Message,
    summary_service: SummaryService,
    summary_request_repository: SummaryRequestRepository,
    settings: Settings,
) -> None:
    if (
        settings.allowed_chat_ids
        and message.chat.id not in settings.allowed_chat_ids
    ):
        await message.answer("500 рублей на карту мне и даю доступ")
        return

    requested_limit = _parse_limit(message.text)
    if requested_limit is None:
        await message.answer("Используй формат: /summary 100")
        return

    if requested_limit <= 0:
        await message.answer("Количество сообщений должно быть больше нуля.")
        return

    if requested_limit > summary_service.max_summary_messages:
        await message.answer(
            "Слишком много сообщений за раз. "
            f"Максимум: {summary_service.max_summary_messages}."
        )
        return

    if not await _check_limit(message, summary_request_repository):
        return

    status_message = await message.answer("Анализирую хуйню, которую тут понаписали...")

    try:
        summary = await summary_service.summarize_chat(
            chat_id=message.chat.id,
            requested_limit=requested_limit,
        )
    except Exception:
        await status_message.edit_text(
            "Саммари не будет, токены от ебаного ГагаЧада закончились...Админ банкрот...."
        )
        raise

    chunks = _split_for_telegram(summary)
    await status_message.edit_text(chunks[0])
    for chunk in chunks[1:]:
        await message.answer(chunk)


async def _check_limit(
    message: Message,
    summary_request_repository: SummaryRequestRepository,
) -> bool:
    user = message.from_user
    if user is None:
        await message.answer("Вы кого задудосить решили дети шлюх ебаных")
        return False

    if user.id == LIMIT_EXEMPT_USER_ID:
        return True

    is_allowed = await summary_request_repository.try_register(
        chat_id=message.chat.id,
        user_id=user.id,
        max_requests=SUMMARY_REQUESTS_PER_DAY,
        window=timedelta(hours=24),
    )
    if not is_allowed:
        await message.answer("Вы кого задудосить решили дети шлюх ебаных")
        return False

    return True


def _parse_limit(text: str | None) -> int | None:
    if not text:
        return None

    parts = text.split(maxsplit=1)
    if len(parts) != 2:
        return None

    try:
        return int(parts[1].replace("_", ""))
    except ValueError:
        return None


def _split_for_telegram(text: str, chunk_size: int = 3900) -> list[str]:
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    current = ""
    for paragraph in text.split("\n"):
        if len(paragraph) > chunk_size:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(
                paragraph[index : index + chunk_size]
                for index in range(0, len(paragraph), chunk_size)
            )
            continue

        candidate = f"{current}\n{paragraph}".strip()
        if len(candidate) <= chunk_size:
            current = candidate
            continue

        if current:
            chunks.append(current)
        current = paragraph

    if current:
        chunks.append(current)

    return chunks
