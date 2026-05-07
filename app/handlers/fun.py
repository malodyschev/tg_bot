import re
from collections import Counter
from datetime import timedelta

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.config import Settings
from app.repositories.command_usages import CommandUsageRepository
from app.repositories.messages import MessageRepository
from app.services.summary import SummaryService

router = Router()

DEFAULT_LIMIT = 100
LIMIT_EXEMPT_USER_ID = 693505334
LIMIT_EXHAUSTED_MESSAGE = "Отдыхай в таверне сынок лимит исчерпан😎"
ACCESS_DENIED_MESSAGE = "500 рублей на карту мне и даю доступ"

STOP_WORDS = {
    "а",
    "без",
    "был",
    "была",
    "были",
    "быть",
    "в",
    "во",
    "вот",
    "все",
    "да",
    "для",
    "до",
    "его",
    "если",
    "же",
    "за",
    "и",
    "или",
    "как",
    "кто",
    "мне",
    "мы",
    "на",
    "не",
    "но",
    "ну",
    "он",
    "она",
    "они",
    "по",
    "про",
    "с",
    "со",
    "так",
    "там",
    "то",
    "ты",
    "у",
    "что",
    "это",
    "я",
}


@router.message(Command("drama"))
async def drama(
    message: Message,
    summary_service: SummaryService,
    command_usage_repository: CommandUsageRepository,
    settings: Settings,
) -> None:
    if not _check_chat_access(message, settings):
        await message.answer(ACCESS_DENIED_MESSAGE)
        return

    if not await _check_limit(message, command_usage_repository, "drama"):
        return

    limit = _parse_optional_limit(message.text)
    if limit is None:
        await message.answer("Используй формат: /drama или /drama 200")
        return

    status_message = await message.answer("Ищу драму в этом балагане...")
    answer = await summary_service.drama_chat(message.chat.id, limit)
    await _send_answer(message, status_message, answer)


@router.message(Command("who"))
async def who(
    message: Message,
    summary_service: SummaryService,
    command_usage_repository: CommandUsageRepository,
    settings: Settings,
) -> None:
    if not _check_chat_access(message, settings):
        await message.answer(ACCESS_DENIED_MESSAGE)
        return

    if not await _check_limit(message, command_usage_repository, "who"):
        return

    limit = _parse_optional_limit(message.text)
    if limit is None:
        await message.answer("Используй формат: /who или /who 200")
        return

    status_message = await message.answer("Выбираю главного персонажа серии...")
    answer = await summary_service.main_character_chat(message.chat.id, limit)
    await _send_answer(message, status_message, answer)


@router.message(Command("lore"))
async def lore(
    message: Message,
    summary_service: SummaryService,
    command_usage_repository: CommandUsageRepository,
    settings: Settings,
) -> None:
    if not _check_chat_access(message, settings):
        await message.answer(ACCESS_DENIED_MESSAGE)
        return

    if not await _check_limit(message, command_usage_repository, "lore"):
        return

    argument = _command_argument(message.text)
    status_message = await message.answer("Копаю лор, ща будет...")

    if not argument:
        answer = await summary_service.lore_chat(message.chat.id, DEFAULT_LIMIT)
    elif argument.isdigit():
        answer = await summary_service.lore_chat(message.chat.id, int(argument))
    else:
        answer = await summary_service.search_lore(message.chat.id, argument)

    await _send_answer(message, status_message, answer)


@router.message(Command("top_words"))
async def top_words(
    message: Message,
    message_repository: MessageRepository,
    command_usage_repository: CommandUsageRepository,
    settings: Settings,
) -> None:
    if not _check_chat_access(message, settings):
        await message.answer(ACCESS_DENIED_MESSAGE)
        return

    if not await _check_limit(message, command_usage_repository, "top_words"):
        return

    limit = _parse_optional_limit(message.text)
    if limit is None:
        await message.answer("Используй формат: /top_words или /top_words 200")
        return

    messages = await message_repository.get_latest(message.chat.id, limit)
    if not messages:
        await message.answer("Пока нет сохраненных сообщений для подсчета слов.")
        return

    words = Counter()
    for stored_message in messages:
        for word in re.findall(r"[A-Za-zА-Яа-яЁё0-9]+", stored_message.text.lower()):
            if len(word) < 2 or word in STOP_WORDS:
                continue
            words[word] += 1

    if not words:
        await message.answer("Нормальных слов не нашел, один шум какой-то.")
        return

    lines = ["Топ словесного мусора:"]
    for index, (word, count) in enumerate(words.most_common(15), start=1):
        lines.append(f"{index}. {word} - {count}")

    await message.answer("\n".join(lines))


@router.message(Command("promt"))
async def promt(
    message: Message,
    summary_service: SummaryService,
    command_usage_repository: CommandUsageRepository,
    settings: Settings,
) -> None:
    if not _check_chat_access(message, settings):
        await message.answer(ACCESS_DENIED_MESSAGE)
        return

    user_prompt = _command_argument(message.text).strip()
    if not user_prompt:
        await message.answer('Используй формат: /promt "твой запрос"')
        return

    user_prompt = user_prompt.strip('"').strip("'").strip()
    if not await _check_limit(message, command_usage_repository, "promt"):
        return

    status_message = await message.answer("Ща спрошу у железки...")
    answer = await summary_service.custom_prompt_chat(message.chat.id, user_prompt)
    await _send_answer(message, status_message, answer)


def _check_chat_access(message: Message, settings: Settings) -> bool:
    return (
        not settings.allowed_chat_ids
        or message.chat.id in settings.allowed_chat_ids
    )


async def _check_limit(
    message: Message,
    command_usage_repository: CommandUsageRepository,
    command: str,
) -> bool:
    user = message.from_user
    if user is None:
        await message.answer(LIMIT_EXHAUSTED_MESSAGE)
        return False

    if user.id == LIMIT_EXEMPT_USER_ID:
        return True

    is_allowed = await command_usage_repository.try_register(
        chat_id=message.chat.id,
        user_id=user.id,
        command=command,
        max_requests=1,
        window=timedelta(hours=24),
    )
    if not is_allowed:
        await message.answer(LIMIT_EXHAUSTED_MESSAGE)
        return False

    return True


def _parse_optional_limit(text: str | None) -> int | None:
    argument = _command_argument(text)
    if not argument:
        return DEFAULT_LIMIT

    try:
        limit = int(argument.replace("_", ""))
    except ValueError:
        return None

    if limit <= 0:
        return None

    return limit


def _command_argument(text: str | None) -> str:
    if not text:
        return ""

    parts = text.split(maxsplit=1)
    if len(parts) != 2:
        return ""

    return parts[1].strip()


async def _send_answer(
    message: Message,
    status_message: Message,
    answer: str,
) -> None:
    chunks = _split_for_telegram(answer)
    await status_message.edit_text(chunks[0])
    for chunk in chunks[1:]:
        await message.answer(chunk)


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
