import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    gigachat_credentials: str
    gigachat_scope: str
    gigachat_model: str
    gigachat_verify_ssl_certs: bool
    database_path: Path
    max_messages_per_chat: int
    max_summary_messages: int
    allowed_chat_ids: frozenset[int]


def load_settings() -> Settings:
    load_dotenv()

    return Settings(
        telegram_bot_token=_required("TELEGRAM_BOT_TOKEN"),
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
    )


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Environment variable {name} is required")
    return value


def _as_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _as_int_set(value: str) -> frozenset[int]:
    chat_ids = set()
    for raw_item in value.split(","):
        item = raw_item.strip()
        if not item:
            continue
        chat_ids.add(int(item))
    return frozenset(chat_ids)
