CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    telegram_message_id INTEGER NOT NULL,
    user_id INTEGER,
    username TEXT,
    first_name TEXT,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(chat_id, telegram_message_id)
);

CREATE INDEX IF NOT EXISTS idx_messages_chat_message_id
ON messages(chat_id, telegram_message_id);

CREATE TABLE IF NOT EXISTS command_usages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    command TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_command_usages_chat_user_command_created
ON command_usages(chat_id, user_id, command, created_at);
