from datetime import datetime

from pydantic import BaseModel, ConfigDict


class StoredMessage(BaseModel):
    model_config = ConfigDict(frozen=True)

    chat_id: int
    telegram_message_id: int
    user_id: int | None
    username: str | None
    first_name: str | None
    text: str
    created_at: datetime

    @property
    def author_name(self) -> str:
        if self.first_name:
            return self.first_name
        if self.username:
            return self.username
        if self.user_id:
            return f"user_{self.user_id}"
        return "unknown_user"
