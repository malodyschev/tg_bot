import asyncio
import logging

from aiogram import Bot

from app.config import Settings

logger = logging.getLogger(__name__)


class DiplomaReminder:
    def __init__(self, bot: Bot, settings: Settings) -> None:
        self._bot = bot
        self._settings = settings

    async def run(self) -> None:
        chat_id = self._settings.diploma_reminder_chat_id
        if chat_id is None:
            return

        interval_seconds = self._settings.diploma_reminder_interval_hours * 60 * 60
        if interval_seconds <= 0:
            logger.warning("Diploma reminder interval must be positive")
            return

        while True:
            await self._send_reminder(chat_id)
            await asyncio.sleep(interval_seconds)

    async def _send_reminder(self, chat_id: int) -> None:
        try:
            await self._bot.send_message(
                chat_id=chat_id,
                text=self._settings.diploma_reminder_text,
            )
        except Exception:
            logger.exception("Failed to send diploma reminder")
