import asyncio
import logging

from aiogram import Bot

from app.config import Settings
from app.repositories.funpay_seen_reviews import FunPaySeenReviewRepository
from app.services.funpay import FunPayError, FunPayReview, FunPayService

logger = logging.getLogger(__name__)


class FunPayMonitor:
    def __init__(
        self,
        bot: Bot,
        settings: Settings,
        funpay_service: FunPayService,
        seen_review_repository: FunPaySeenReviewRepository,
    ) -> None:
        self._bot = bot
        self._settings = settings
        self._funpay_service = funpay_service
        self._seen_review_repository = seen_review_repository

    async def run(self) -> None:
        chat_id = self._settings.funpay_monitor_chat_id
        if chat_id is None:
            logger.info("FunPay monitor disabled: FUNPAY_MONITOR_CHAT_ID is not set")
            return

        interval_seconds = self._settings.funpay_monitor_interval_minutes * 60
        if interval_seconds <= 0:
            logger.warning("FunPay monitor interval must be positive")
            return

        logger.info(
            "FunPay monitor started: chat_id=%s interval_minutes=%s",
            chat_id,
            self._settings.funpay_monitor_interval_minutes,
        )
        while True:
            await self._check_once(chat_id)
            await asyncio.sleep(interval_seconds)

    async def _check_once(self, chat_id: int) -> None:
        try:
            logger.info("FunPay monitor check started")
            recent_reviews = await self._funpay_service.collect_recent_reviews()
            seen_fingerprints = await self._seen_review_repository.get_seen_fingerprints()
            migrated_legacy_fingerprints = {
                review.legacy_fingerprint
                for review in recent_reviews
                if review.legacy_fingerprint in seen_fingerprints
                and review.fingerprint not in seen_fingerprints
            }
            new_reviews = [
                review
                for review in recent_reviews
                if review.fingerprint not in seen_fingerprints
                and review.legacy_fingerprint not in seen_fingerprints
            ]
            logger.info(
                "FunPay monitor check parsed: recent=%s seen=%s new=%s legacy_migrated=%s",
                len(recent_reviews),
                len(seen_fingerprints),
                len(new_reviews),
                len(migrated_legacy_fingerprints),
            )

            await self._seen_review_repository.remember_many(recent_reviews)
            await self._seen_review_repository.forget_fingerprints(
                migrated_legacy_fingerprints
            )

            if not seen_fingerprints:
                logger.info(
                    "FunPay monitor initialized with current reviews: remembered=%s",
                    len(recent_reviews),
                )
                return

            for review in reversed(new_reviews):
                logger.info(
                    "FunPay monitor sending new review: detail=%s price=%s has_text=%s",
                    review.detail,
                    review.price_eur,
                    bool(review.text),
                )
                await self._bot.send_message(
                    chat_id=chat_id,
                    text=_format_new_review(review),
                )
            logger.info("FunPay monitor check finished")
        except FunPayError:
            logger.exception("FunPay monitor failed")
        except Exception:
            logger.exception("Unexpected FunPay monitor failure")


def _format_new_review(review: FunPayReview) -> str:
    lines = [
        "Новый отзыв на FunPay:",
        review.detail,
        f"Сумма: {review.price_eur} €",
    ]
    if review.text:
        lines.append(f"Отзыв: {review.text}")

    return "\n".join(lines)
