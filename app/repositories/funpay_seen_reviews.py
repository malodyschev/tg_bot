from datetime import UTC, datetime

from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db_models import FunPaySeenReviewOrm
from app.services.funpay import FunPayReview


class FunPaySeenReviewRepository:
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def get_seen_fingerprints(self) -> set[str]:
        async with self._session_factory() as session:
            result = await session.scalars(select(FunPaySeenReviewOrm.fingerprint))
            return set(result.all())

    async def remember_many(self, reviews: list[FunPayReview]) -> None:
        if not reviews:
            return

        async with self._session_factory() as session:
            for review in reviews:
                await session.execute(
                    insert(FunPaySeenReviewOrm)
                    .prefix_with("OR IGNORE")
                    .values(
                        fingerprint=review.fingerprint,
                        detail=review.detail,
                        price_eur=str(review.price_eur),
                        created_at=datetime.now(UTC),
                    )
                )
            await session.commit()

    async def forget_fingerprints(self, fingerprints: set[str]) -> None:
        if not fingerprints:
            return

        async with self._session_factory() as session:
            await session.execute(
                delete(FunPaySeenReviewOrm).where(
                    FunPaySeenReviewOrm.fingerprint.in_(fingerprints)
                )
            )
            await session.commit()
