import asyncio
import hashlib
import logging
import re
import time
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Optional

import requests
from bs4 import BeautifulSoup

from app.config import Settings

PRICE_RE = re.compile(r",\s*([0-9]+(?:[.,][0-9]+)?)\s*€")
logger = logging.getLogger(__name__)


class FunPayError(RuntimeError):
    pass


@dataclass(frozen=True)
class FunPayReview:
    detail: str
    price_eur: Decimal
    text: str | None = None

    @property
    def fingerprint(self) -> str:
        raw = f"{self.detail}|{self.price_eur}|{self.text or ''}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @property
    def legacy_fingerprint(self) -> str:
        raw = f"{self.detail}|{self.price_eur}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class FunPayStats:
    total_sum_eur: Decimal
    total_reviews: int
    recent_reviews: list[FunPayReview]

    @property
    def recent_sum_eur(self) -> Decimal:
        return sum((review.price_eur for review in self.recent_reviews), Decimal("0"))


class FunPayService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def collect_stats(self) -> FunPayStats:
        logger.info("FunPay stats collection requested")
        return await asyncio.to_thread(self._collect_stats_sync)

    async def collect_recent_reviews(self) -> list[FunPayReview]:
        logger.info("FunPay recent reviews collection requested")
        return await asyncio.to_thread(self._collect_recent_reviews_sync)

    def _collect_recent_reviews_sync(self) -> list[FunPayReview]:
        if not self._settings.funpay_start_url:
            raise FunPayError("FUNPAY_START_URL не задан")
        if not self._settings.funpay_cookie:
            raise FunPayError("FUNPAY_COOKIE не задан")

        logger.info("FunPay recent reviews fetch started")
        session = requests.Session()
        html = self._fetch_initial_page(
            session,
            self._settings.funpay_start_url,
            self._build_headers(),
        )
        _raise_if_login_or_block_page(html)
        page_reviews, user_id, _ = self._parse_reviews_html(html)

        if not user_id:
            raise FunPayError(
                "не нашел user_id на первой странице. "
                "Скорее всего, FUNPAY_START_URL не та ссылка или cookie протухли"
            )

        recent_reviews = page_reviews[: self._settings.funpay_recent_reviews_count]
        logger.info(
            "FunPay recent reviews fetch finished: parsed=%s returned=%s",
            len(page_reviews),
            len(recent_reviews),
        )
        return recent_reviews

    def _collect_stats_sync(self) -> FunPayStats:
        if not self._settings.funpay_start_url:
            raise FunPayError("FUNPAY_START_URL не задан")
        if not self._settings.funpay_cookie:
            raise FunPayError("FUNPAY_COOKIE не задан")

        logger.info(
            "FunPay stats fetch started: max_pages=%s recent_count=%s",
            self._settings.funpay_max_pages,
            self._settings.funpay_recent_reviews_count,
        )
        session = requests.Session()
        headers = self._build_headers()

        html = self._fetch_initial_page(
            session,
            self._settings.funpay_start_url,
            headers,
        )
        _raise_if_login_or_block_page(html)
        page_reviews, user_id, continue_token = self._parse_reviews_html(html)

        if not user_id:
            raise FunPayError(
                "не нашел user_id на первой странице. "
                "Скорее всего, FUNPAY_START_URL не та ссылка или cookie протухли"
            )

        all_reviews = list(page_reviews)
        seen_tokens: set[str] = set()
        page_num = 1

        while (
            continue_token
            and continue_token not in seen_tokens
            and page_num < self._settings.funpay_max_pages
        ):
            seen_tokens.add(continue_token)
            page_num += 1

            chunk_html = self._fetch_reviews_chunk(
                session=session,
                user_id=user_id,
                continue_token=continue_token,
                headers=headers,
            )
            _raise_if_login_or_block_page(chunk_html)
            page_reviews, _, next_continue = self._parse_reviews_html(chunk_html)
            logger.info(
                "FunPay stats page parsed: page=%s reviews=%s has_next=%s",
                page_num,
                len(page_reviews),
                bool(next_continue),
            )

            if not page_reviews:
                break

            all_reviews.extend(page_reviews)

            if next_continue == continue_token:
                break

            continue_token = next_continue
            time.sleep(0.5)

        total_sum = sum((review.price_eur for review in all_reviews), Decimal("0"))
        recent_reviews = all_reviews[: self._settings.funpay_recent_reviews_count]
        logger.info(
            "FunPay stats fetch finished: reviews=%s total=%s recent=%s",
            len(all_reviews),
            total_sum,
            len(recent_reviews),
        )

        return FunPayStats(
            total_sum_eur=total_sum,
            total_reviews=len(all_reviews),
            recent_reviews=recent_reviews,
        )

    def _build_headers(self) -> dict[str, str]:
        return {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/147.0.0.0 Safari/537.36"
            ),
            "Referer": self._settings.funpay_start_url or "https://funpay.com/",
            "Origin": "https://funpay.com",
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Cookie": self._settings.funpay_cookie or "",
        }

    def _fetch_initial_page(
        self,
        session: requests.Session,
        url: str,
        headers: dict[str, str],
    ) -> str:
        logger.info("FunPay initial page request started")
        response = session.get(url, headers=headers, timeout=30)
        _raise_for_status(response)
        logger.info(
            "FunPay initial page request finished: status=%s bytes=%s",
            response.status_code,
            len(response.text),
        )
        return response.text

    def _fetch_reviews_chunk(
        self,
        session: requests.Session,
        user_id: str,
        continue_token: str,
        headers: dict[str, str],
    ) -> str:
        logger.info("FunPay reviews chunk request started")
        response = session.post(
            self._settings.funpay_reviews_url,
            headers=headers,
            data={
                "user_id": user_id,
                "continue": continue_token,
                "filter": "",
            },
            timeout=30,
        )
        _raise_for_status(response)
        logger.info(
            "FunPay reviews chunk request finished: status=%s bytes=%s",
            response.status_code,
            len(response.text),
        )
        return response.text

    def _parse_reviews_html(
        self,
        html: str,
    ) -> tuple[list[FunPayReview], Optional[str], Optional[str]]:
        soup = BeautifulSoup(html, "html.parser")

        reviews = []
        for item in soup.select(".review-item-detail"):
            detail = _clean_text(item.get_text(" ", strip=True))
            price = _extract_price_eur(detail)
            if price is None:
                continue

            container = item.find_parent(class_="review-item") or item.parent
            review_text = _extract_review_text(container)
            reviews.append(
                FunPayReview(
                    detail=detail,
                    price_eur=price,
                    text=review_text,
                )
            )

        user_id_input = soup.select_one('form.dyn-table-form input[name="user_id"]')
        continue_input = soup.select_one('form.dyn-table-form input[name="continue"]')

        user_id = user_id_input.get("value") if user_id_input else None
        continue_token = continue_input.get("value") if continue_input else None

        return reviews, user_id, continue_token


def _extract_price_eur(detail_text: str) -> Optional[Decimal]:
    if not detail_text:
        return None

    match = PRICE_RE.search(detail_text.strip())
    if not match:
        return None

    raw = match.group(1).replace(",", ".")
    try:
        return Decimal(raw)
    except InvalidOperation:
        return None


def _extract_review_text(container: object) -> str | None:
    if container is None:
        return None

    selectors = (
        ".review-item-text",
        ".review-item-comment",
        ".review-item-message",
        ".review-text",
        ".media-body > div:not(.review-item-detail)",
    )
    for selector in selectors:
        element = container.select_one(selector)
        if element is None:
            continue

        text = _clean_text(element.get_text(" ", strip=True))
        if text:
            return text

    # Fallback for small FunPay layout changes: take the whole review card,
    # remove obvious service blocks and leave the remaining user-visible text.
    container_copy = BeautifulSoup(str(container), "html.parser")
    for selector in (
        ".review-item-detail",
        ".review-item-date",
        ".review-item-rating",
        ".rating",
        ".media-user-name",
    ):
        for element in container_copy.select(selector):
            element.decompose()

    text = _clean_text(container_copy.get_text(" ", strip=True))
    return text or None


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _raise_for_status(response: requests.Response) -> None:
    try:
        response.raise_for_status()
    except requests.HTTPError as error:
        raise FunPayError(
            f"FunPay вернул HTTP {response.status_code}. "
            "Проверь cookie, ссылку и доступность страницы"
        ) from error


def _raise_if_login_or_block_page(html: str) -> None:
    lowered = html.lower()
    if "name=\"login\"" in lowered or "пароль" in lowered and "funpay" in lowered:
        raise FunPayError("FunPay отдал страницу логина. Cookie протухли или неполные")
    if "captcha" in lowered or "cloudflare" in lowered:
        raise FunPayError("FunPay отдал капчу/антибот. С сервера парсинг заблокирован")
