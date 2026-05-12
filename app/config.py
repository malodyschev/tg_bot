import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    telegram_proxy_url: str | None
    gigachat_credentials: str
    gigachat_scope: str
    gigachat_model: str
    gigachat_verify_ssl_certs: bool
    database_path: Path
    max_messages_per_chat: int
    max_summary_messages: int
    allowed_chat_ids: frozenset[int]
    diploma_reminder_chat_id: int | None
    diploma_reminder_text: str
    diploma_reminder_interval_hours: float
    funpay_start_url: str | None
    funpay_cookie: str | None
    funpay_reviews_url: str
    funpay_recent_reviews_count: int
    funpay_max_pages: int
    funpay_monitor_chat_id: int | None
    funpay_report_interval_hours: float


def load_settings() -> Settings:
    load_dotenv()

    return Settings(
        telegram_bot_token=_required("TELEGRAM_BOT_TOKEN"),
        telegram_proxy_url=os.getenv("TELEGRAM_PROXY_URL") or None,
        gigachat_credentials=_required("GIGACHAT_CREDENTIALS"),
        gigachat_scope=os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS"),
        gigachat_model=os.getenv("GIGACHAT_MODEL", "GigaChat"),
        gigachat_verify_ssl_certs=_as_bool(
            os.getenv("GIGACHAT_VERIFY_SSL_CERTS", "true")
        ),
        database_path=Path(os.getenv("DATABASE_PATH", "bot.sqlite3")),
        max_messages_per_chat=int(os.getenv("MAX_MESSAGES_PER_CHAT", "3000")),
        max_summary_messages=int(os.getenv("MAX_SUMMARY_MESSAGES", "500")),
        allowed_chat_ids=_as_int_set(os.getenv("ALLOWED_CHAT_IDS", "")),
        diploma_reminder_chat_id=_optional_int(
            os.getenv("DIPLOMA_REMINDER_CHAT_ID")
        ),
        diploma_reminder_text=os.getenv(
            "DIPLOMA_REMINDER_TEXT",
            "@iaroslav_komkov как там с дипломом?",
        ),
        diploma_reminder_interval_hours=float(
            os.getenv("DIPLOMA_REMINDER_INTERVAL_HOURS", "12")
        ),
        funpay_start_url=os.getenv("FUNPAY_START_URL") or None,
        funpay_cookie=os.getenv("FUNPAY_COOKIE") or None,
        funpay_reviews_url=os.getenv(
            "FUNPAY_REVIEWS_URL",
            "https://funpay.com/users/reviews",
        ),
        funpay_recent_reviews_count=int(
            os.getenv("FUNPAY_RECENT_REVIEWS_COUNT", "5")
        ),
        funpay_max_pages=int(os.getenv("FUNPAY_MAX_PAGES", "200")),
        funpay_monitor_chat_id=_optional_int(os.getenv("FUNPAY_MONITOR_CHAT_ID")),
        funpay_report_interval_hours=float(
            os.getenv("FUNPAY_REPORT_INTERVAL_HOURS", "24")
        ),
    )


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Environment variable {name} is required")
    return value


def _as_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _optional_int(value: str | None) -> int | None:
    if not value:
        return None
    return int(value)


def _as_int_set(value: str) -> frozenset[int]:
    chat_ids = set()
    for raw_item in value.split(","):
        item = raw_item.strip()
        if not item:
            continue
        chat_ids.add(int(item))
    return frozenset(chat_ids)
