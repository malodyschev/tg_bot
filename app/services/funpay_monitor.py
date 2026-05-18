import asyncio
import logging
from decimal import Decimal

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

        interval_seconds = self._settings.funpay_report_interval_hours * 60 * 60
        if interval_seconds <= 0:
            logger.warning("FunPay report interval must be positive")
            return

        logger.info(
            "FunPay daily report monitor started: chat_id=%s interval_hours=%s",
            chat_id,
            self._settings.funpay_report_interval_hours,
        )

        await self._startup_sync()

        while True:
            await asyncio.sleep(interval_seconds)
            await self._check_once(chat_id)

    async def _startup_sync(self) -> None:
        try:
            logger.info("FunPay startup sync started")
            stats = await self._funpay_service.collect_stats()
            reviews = stats.all_reviews
            seen_fingerprints = await self._seen_review_repository.get_seen_fingerprints()
            should_backfill_history = (
                0
                < len(seen_fingerprints)
                <= self._settings.funpay_recent_reviews_count
                < len(reviews)
            )
            migrated_legacy_fingerprints = {
                review.legacy_fingerprint
                for review in reviews
                if review.legacy_fingerprint in seen_fingerprints
                and review.fingerprint not in seen_fingerprints
            }

            if not seen_fingerprints or should_backfill_history:
                await self._seen_review_repository.remember_many(reviews)
                await self._seen_review_repository.forget_fingerprints(
                    migrated_legacy_fingerprints
                )
                logger.info(
                    "FunPay startup sync backfilled reviews without sending: remembered=%s previous_seen=%s legacy_migrated=%s",
                    len(reviews),
                    len(seen_fingerprints),
                    len(migrated_legacy_fingerprints),
                )
                return

            if migrated_legacy_fingerprints:
                await self._seen_review_repository.remember_many(reviews)
                await self._seen_review_repository.forget_fingerprints(
                    migrated_legacy_fingerprints
                )
                logger.info(
                    "FunPay startup sync migrated legacy fingerprints without sending: legacy_migrated=%s",
                    len(migrated_legacy_fingerprints),
                )
                return

            logger.info(
                "FunPay startup sync skipped: seen=%s fetched=%s",
                len(seen_fingerprints),
                len(reviews),
            )
        except FunPayError:
            logger.exception("FunPay startup sync failed")
        except Exception:
            logger.exception("Unexpected FunPay startup sync failure")

    async def _check_once(self, chat_id: int) -> None:
        try:
            logger.info("FunPay daily report check started")
            stats = await self._funpay_service.collect_stats()
            reviews = stats.all_reviews
            seen_fingerprints = await self._seen_review_repository.get_seen_fingerprints()
            should_backfill_history = (
                0
                < len(seen_fingerprints)
                <= self._settings.funpay_recent_reviews_count
                < len(reviews)
            )
            migrated_legacy_fingerprints = {
                review.legacy_fingerprint
                for review in reviews
                if review.legacy_fingerprint in seen_fingerprints
                and review.fingerprint not in seen_fingerprints
            }
            new_reviews = [
                review
                for review in reviews
                if review.fingerprint not in seen_fingerprints
                and review.legacy_fingerprint not in seen_fingerprints
            ]
            logger.info(
                "FunPay daily report parsed: fetched=%s seen=%s new=%s legacy_migrated=%s total=%s",
                len(reviews),
                len(seen_fingerprints),
                len(new_reviews),
                len(migrated_legacy_fingerprints),
                stats.total_sum_eur,
            )

            await self._seen_review_repository.remember_many(reviews)
            await self._seen_review_repository.forget_fingerprints(
                migrated_legacy_fingerprints
            )

            if not seen_fingerprints:
                logger.info(
                    "FunPay daily report initialized with current reviews: remembered=%s",
                    len(reviews),
                )
                return

            if should_backfill_history:
                logger.info(
                    "FunPay daily report backfilled full history without sending: remembered=%s previous_seen=%s",
                    len(reviews),
                    len(seen_fingerprints),
                )
                return

            report = _format_daily_report(new_reviews)
            for chunk in _split_for_telegram(report):
                await self._bot.send_message(chat_id=chat_id, text=chunk)
            logger.info(
                "FunPay daily report sent: new=%s sum=%s",
                len(new_reviews),
                _sum_reviews(new_reviews),
            )
        except FunPayError:
            logger.exception("FunPay monitor failed")
        except Exception:
            logger.exception("Unexpected FunPay monitor failure")


def _format_daily_report(new_reviews: list[FunPayReview]) -> str:
    total_sum = _sum_reviews(new_reviews)
    lines = [
        "Дневной отчет FunPay:",
        f"Новых отзывов: {len(new_reviews)}",
        f"Сумма по новым отзывам: {total_sum} €",
    ]

    if not new_reviews:
        return "\n".join(lines)

    lines.append("")
    lines.append("Отзывы:")
    for index, review in enumerate(reversed(new_reviews), start=1):
        lines.append(f"{index}. {review.detail} — {review.price_eur} €")
        if review.text:
            lines.append(f"   Текст: {review.text}")

    return "\n".join(lines)


def _sum_reviews(reviews: list[FunPayReview]) -> Decimal:
    return sum((review.price_eur for review in reviews), Decimal("0"))


def _split_for_telegram(text: str, chunk_size: int = 3900) -> list[str]:
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    current = ""
    for line in text.split("\n"):
        if len(line) > chunk_size:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(
                line[index : index + chunk_size]
                for index in range(0, len(line), chunk_size)
            )
            continue

        candidate = f"{current}\n{line}".strip()
        if len(candidate) <= chunk_size:
            current = candidate
            continue

        if current:
            chunks.append(current)
        current = line

    if current:
        chunks.append(current)

    return chunks
