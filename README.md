# Telegram Summary Bot

Бот для Telegram-чата: сохраняет сообщения в SQLite и делает сводки через GigaChat.
Основная команда - `/summary n`, где `n` - сколько последних сообщений взять.

## Быстрый Старт

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Заполни `.env`, потом запускай:

```bash
python3 main.py
```

## Настройки

Основные переменные в `.env`:

```env
TELEGRAM_BOT_TOKEN=...
GIGACHAT_CREDENTIALS=...
GIGACHAT_SCOPE=GIGACHAT_API_PERS
GIGACHAT_MODEL=GigaChat
GIGACHAT_VERIFY_SSL_CERTS=false
DATABASE_PATH=bot.sqlite3
MAX_MESSAGES_PER_CHAT=3000
MAX_SUMMARY_MESSAGES=500
ALLOWED_CHAT_IDS=-1003464847907
```

- `TELEGRAM_BOT_TOKEN` - токен из BotFather.
- `GIGACHAT_CREDENTIALS` - Authorization Key от GigaChat.
- `GIGACHAT_VERIFY_SSL_CERTS=false` - удобно для MVP, чтобы не упереться в сертификаты.
- `MAX_MESSAGES_PER_CHAT=3000` - сколько сообщений хранить на каждый чат.
- `MAX_SUMMARY_MESSAGES=500` - максимум сообщений за один запрос к нейронке.
- `ALLOWED_CHAT_IDS` - список разрешённых чатов через запятую.

Если `ALLOWED_CHAT_IDS` пустой, команды работают во всех чатах.

## Права И Доступ

Чтобы бот видел обычные сообщения в группе, в BotFather нужно выключить privacy mode:

```text
/mybots -> выбрать бота -> Bot Settings -> Group Privacy -> Turn off
```

После этого лучше удалить бота из чата и добавить заново.

Если чат не входит в `ALLOWED_CHAT_IDS`, бот не пойдёт в GigaChat и ответит:

```text
500 рублей на карту мне и даю доступ
```

Для супергрупп ID обычно выглядит так:

```text
-1003464847907
```

## Команды

`/summary` или `/summary 100`

Делает краткое саммари. Без числа берёт последние 100 сообщений. Учитывает имена участников, не цензурирует мат из переписки и отвечает неформально.

`/drama` или `/drama 200`

Вытаскивает конфликты, подколы, эмоциональные всплески и прочую драму. Без числа берёт последние 100 сообщений.

`/top_words` или `/top_words 200`

Считает самые частые слова локально, без GigaChat. Без числа берёт последние 100 сообщений.

`/who` или `/who 200`

Выбирает главного персонажа последних сообщений: кто был в центре движухи, кого обсуждали или кто больше всех внёс хаоса.

`/lore` или `/lore 200`

Собирает внутренний лор чата: мемы, повторяющиеся темы, обещания, странные сюжетные линии.

`/lore Митяй`

Ищет сообщения по запросу и объясняет лор вокруг найденной темы.

`/promt "кто сегодня главный нытик?"`

Выполняет твой кастомный запрос по последним 100 сообщениям чата.

## Лимиты

Для обычных участников лимит персональный:

```text
каждую команду можно вызвать 1 раз за последние 24 часа
```

Это касается:

- `/summary`
- `/drama`
- `/top_words`
- `/who`
- `/lore`
- `/promt`

Пользователь с Telegram ID `693505334` лимитом не ограничен.

Если лимит у обычного участника закончился:

```text
Отдыхай в таверне сынок лимит исчерпан😎
```

## Импорт Истории

Telegram Bot API не отдаёт старые сообщения после добавления бота в чат. Историю можно импортировать из Telegram Desktop:

1. Экспортируй чат в JSON без медиа.
2. Положи файл, например, в `exports/result.json`.
3. Запусти:

```bash
source .venv/bin/activate
python import_telegram_export.py exports/result.json
```

Для супергруппы импортёр сам преобразует ID из экспорта в формат Bot API `-100...`.

Если нужно указать ID вручную:

```bash
python import_telegram_export.py exports/result.json --chat-id -1003464847907
```

## Структура

- `app/handlers` - Telegram-команды и обработка сообщений.
- `app/db_models.py` - SQLAlchemy ORM-модели.
- `app/repositories` - работа с SQLite через SQLAlchemy.
- `app/services` - бизнес-логика и GigaChat.
- `import_telegram_export.py` - импорт JSON-экспорта Telegram Desktop.
