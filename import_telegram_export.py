import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import load_settings
from app.db import close_db, create_session_factory, init_db
from app.models import StoredMessage
from app.repositories.messages import MessageRepository


async def main() -> None:
    args = _parse_args()
    settings = load_settings()

    export = json.loads(args.export_path.read_text(encoding="utf-8"))
    chat_id = args.chat_id or _export_chat_id_to_bot_chat_id(export)

    engine, session_factory = create_session_factory(settings.database_path)
    await init_db(engine)

    repository = MessageRepository(session_factory, settings.max_messages_per_chat)
    imported_count = 0

    try:
        for raw_message in export.get("messages", []):
            message = _parse_message(raw_message, chat_id)
            if message is None:
                continue

            await repository.add(message)
            imported_count += 1
    finally:
        await close_db(engine)

    print(f"Imported {imported_count} messages into chat_id={chat_id}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import Telegram Desktop JSON export into bot SQLite database."
    )
    parser.add_argument(
        "export_path",
        type=Path,
        help="Path to Telegram Desktop result.json export.",
    )
    parser.add_argument(
        "--chat-id",
        type=int,
        help="Bot API chat_id. If omitted, it is inferred from export metadata.",
    )

    return parser.parse_args()


def _export_chat_id_to_bot_chat_id(export: dict[str, Any]) -> int:
    raw_chat_id = int(export["id"])
    chat_type = str(export.get("type", ""))

    if raw_chat_id < 0:
        return raw_chat_id
    if "supergroup" in chat_type:
        return int(f"-100{raw_chat_id}")

    return raw_chat_id


def _parse_message(
    raw_message: dict[str, Any],
    chat_id: int,
) -> StoredMessage | None:
    if raw_message.get("type") != "message":
        return None

    text = _extract_text(raw_message.get("text"))
    if not text:
        return None

    return StoredMessage(
        chat_id=chat_id,
        telegram_message_id=int(raw_message["id"]),
        user_id=_parse_user_id(raw_message.get("from_id")),
        username=None,
        first_name=raw_message.get("from"),
        text=text,
        created_at=_parse_datetime(raw_message),
    )


def _extract_text(raw_text: Any) -> str:
    if isinstance(raw_text, str):
        return raw_text.strip()

    if isinstance(raw_text, list):
        parts = []
        for item in raw_text:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(str(item.get("text", "")))
        return "".join(parts).strip()

    return ""


def _parse_user_id(raw_user_id: Any) -> int | None:
    if not isinstance(raw_user_id, str):
        return None
    if not raw_user_id.startswith("user"):
        return None

    try:
        return int(raw_user_id.removeprefix("user"))
    except ValueError:
        return None


def _parse_datetime(raw_message: dict[str, Any]) -> datetime:
    if raw_message.get("date_unixtime"):
        return datetime.fromtimestamp(int(raw_message["date_unixtime"]), UTC)

    return datetime.fromisoformat(raw_message["date"]).replace(tzinfo=UTC)


if __name__ == "__main__":
    asyncio.run(main())
