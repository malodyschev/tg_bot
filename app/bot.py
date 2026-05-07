from aiogram import Bot, Dispatcher

from app.config import load_settings
from app.db import close_db, create_session_factory, init_db
from app.handlers.messages import router as messages_router
from app.handlers.fun import router as fun_router
from app.handlers.summary import router as summary_router
from app.repositories.command_usages import CommandUsageRepository
from app.repositories.messages import MessageRepository
from app.repositories.summary_requests import SummaryRequestRepository
from app.services.gigachat import GigaChatClient
from app.services.summary import SummaryService


async def run_bot() -> None:
    settings = load_settings()

    engine, session_factory = create_session_factory(settings.database_path)
    await init_db(engine)

    message_repository = MessageRepository(
        session_factory,
        settings.max_messages_per_chat,
    )
    command_usage_repository = CommandUsageRepository(session_factory)
    summary_request_repository = SummaryRequestRepository(session_factory)
    summary_service = SummaryService(
        message_repository=message_repository,
        llm_client=GigaChatClient(settings),
        max_summary_messages=settings.max_summary_messages,
    )

    bot = Bot(token=settings.telegram_bot_token)
    dispatcher = Dispatcher()
    dispatcher["message_repository"] = message_repository
    dispatcher["command_usage_repository"] = command_usage_repository
    dispatcher["summary_request_repository"] = summary_request_repository
    dispatcher["summary_service"] = summary_service
    dispatcher["settings"] = settings

    dispatcher.include_router(summary_router)
    dispatcher.include_router(fun_router)
    dispatcher.include_router(messages_router)

    try:
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()
        await close_db(engine)
