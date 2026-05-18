import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession

from app.config import load_settings
from app.db import close_db, create_session_factory, init_db
from app.handlers.messages import router as messages_router
from app.handlers.fun import router as fun_router
from app.handlers.summary import router as summary_router
from app.repositories.command_usages import CommandUsageRepository
from app.repositories.funpay_seen_reviews import FunPaySeenReviewRepository
from app.repositories.messages import MessageRepository
from app.services.gigachat import GigaChatClient
from app.services.funpay import FunPayService
from app.services.funpay_monitor import FunPayMonitor
from app.services.reminder import DiplomaReminder
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
    funpay_seen_review_repository = FunPaySeenReviewRepository(session_factory)
    summary_service = SummaryService(
        message_repository=message_repository,
        llm_client=GigaChatClient(settings),
        max_summary_messages=settings.max_summary_messages,
    )
    funpay_service = FunPayService(settings)

    session = AiohttpSession(proxy=settings.telegram_proxy_url)
    bot = Bot(token=settings.telegram_bot_token, session=session)
    dispatcher = Dispatcher()
    dispatcher["message_repository"] = message_repository
    dispatcher["command_usage_repository"] = command_usage_repository
    dispatcher["funpay_service"] = funpay_service
    dispatcher["summary_service"] = summary_service
    dispatcher["settings"] = settings

    dispatcher.include_router(summary_router)
    dispatcher.include_router(fun_router)
    dispatcher.include_router(messages_router)

    funpay_monitor = FunPayMonitor(
        bot=bot,
        settings=settings,
        funpay_service=funpay_service,
        seen_review_repository=funpay_seen_review_repository,
    )
    funpay_monitor_task = asyncio.create_task(funpay_monitor.run())

    try:
        await dispatcher.start_polling(bot)
    finally:
        funpay_monitor_task.cancel()
        await asyncio.gather(
            funpay_monitor_task,
            return_exceptions=True,
        )
        await bot.session.close()
        await close_db(engine)
