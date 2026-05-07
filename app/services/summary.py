from typing import Protocol

from app.models import StoredMessage
from app.repositories.messages import MessageRepository


class LlmClient(Protocol):
    async def summarize(self, prompt: str) -> str:
        raise NotImplementedError


class SummaryService:
    def __init__(
        self,
        message_repository: MessageRepository,
        llm_client: LlmClient,
        max_summary_messages: int,
    ) -> None:
        self._message_repository = message_repository
        self._llm_client = llm_client
        self._max_summary_messages = max_summary_messages

    async def summarize_chat(self, chat_id: int, requested_limit: int) -> str:
        limit = min(requested_limit, self._max_summary_messages)
        messages = await self._message_repository.get_latest(chat_id, limit)

        if not messages:
            return "Пока нет сохраненных сообщений для саммари."

        prompt = self._build_prompt(messages)
        return await self._llm_client.summarize(prompt)

    async def drama_chat(self, chat_id: int, requested_limit: int) -> str:
        messages = await self._get_latest_messages(chat_id, requested_limit)
        if not messages:
            return "Пока нет сохраненных сообщений для драмы."

        prompt = self._build_drama_prompt(messages)
        return await self._llm_client.summarize(prompt)

    async def main_character_chat(self, chat_id: int, requested_limit: int) -> str:
        messages = await self._get_latest_messages(chat_id, requested_limit)
        if not messages:
            return "Пока нет сохраненных сообщений, героя серии не выбрать."

        prompt = self._build_who_prompt(messages)
        return await self._llm_client.summarize(prompt)

    async def lore_chat(self, chat_id: int, requested_limit: int) -> str:
        messages = await self._get_latest_messages(chat_id, requested_limit)
        if not messages:
            return "Пока нет сохраненных сообщений для лора."

        prompt = self._build_lore_prompt(messages)
        return await self._llm_client.summarize(prompt)

    async def search_lore(self, chat_id: int, query: str) -> str:
        messages = await self._message_repository.search(chat_id, query, limit=100)
        if not messages:
            return f'По запросу "{query}" ничего не нашел.'

        prompt = self._build_lore_search_prompt(query, messages)
        return await self._llm_client.summarize(prompt)

    @property
    def max_summary_messages(self) -> int:
        return self._max_summary_messages

    async def _get_latest_messages(
        self,
        chat_id: int,
        requested_limit: int,
    ) -> list[StoredMessage]:
        limit = min(requested_limit, self._max_summary_messages)
        return await self._message_repository.get_latest(chat_id, limit)

    def _build_prompt(self, messages: list[StoredMessage]) -> str:
        chat_text = "\n".join(
            f"{message.author_name}: {message.text}" for message in messages
        )

        return f"""
Ты редактор коротких сводок. Твоя задача - сжать переписку Telegram-чата
до полезного саммари, а не пересказывать сообщения по очереди.

Жесткие правила:
- Всегда отвечай на русском языке.
- Стиль ответа: очень неформальный, разговорный, грубоватый, с матом там,
  где он звучит естественно. Без канцелярита и делового тона.
- Не делай стенограмму и не перечисляй каждое сообщение.
- Не используй разделы "Участники", "Дата", "Содержание диалога" и похожие.
- Не пиши "сообщение N", "далее", "затем", если это просто порядок реплик.
- Упоминай автора только когда это важно для смысла: кто предложил, отказался,
  поссорился, взял задачу, кого обсуждали или кому что сказали.
- Не цензурируй мат, грубость и оскорбления, если они были в исходной переписке.
- Можно использовать мат для стиля, но не выдумывай новых персональных наездов,
  угроз или обвинений, которых нет в сообщениях.
- Не дублируй исходные фразы, кроме коротких цитат, если без них теряется смысл.
- Пиши коротко: 3-7 пунктов максимум.
- Не используй Markdown: никаких #, **жирного**, таблиц и декоративной разметки.
- Не пиши дисклеймеры про языковые модели, собственное мнение, чувствительные
  темы и ограничения. Просто делай сводку по сообщениям.

Формат ответа:
Короче, что было:
- что реально обсуждали;
- какие были решения, планы или открытые вопросы;
- какие конфликты, эмоции или важные шутки были;
- кто был ключевым участником в каждом важном моменте.

Сообщения:
{chat_text}
""".strip()

    def _build_drama_prompt(self, messages: list[StoredMessage]) -> str:
        return f"""
Ты делаешь рубрику "драма чата" по последним сообщениям.

Правила:
- Русский язык, максимально разговорно и неформально.
- Можно материться для стиля, но не выдумывай обвинений и угроз.
- Не пересказывай всё подряд. Вытащи только конфликты, подколы, нытьё,
  эмоциональные всплески, смешные наезды и кто кого задел.
- Если драмы почти нет, так и скажи, но всё равно найди самые живые моменты.
- 3-7 коротких пунктов.
- Не используй Markdown: никаких #, **жирного**, таблиц и декоративной разметки.
- Не пиши дисклеймеры про языковые модели, собственное мнение, чувствительные
  темы и ограничения. Просто делай сводку по сообщениям.

Формат:
Драма за последнее время:
- ...

Сообщения:
{self._format_messages(messages)}
""".strip()

    def _build_who_prompt(self, messages: list[StoredMessage]) -> str:
        return f"""
Выбери главного персонажа последних сообщений Telegram-чата.

Правила:
- Русский язык, очень неформально, можно с матом.
- Назови одного главного героя и 2-4 причины.
- Учитывай не только кто больше писал, но и кого больше обсуждали,
  кто устроил движ, кого подъёбывали или кто принёс главную тему.
- Не выдумывай факты, которых нет в сообщениях.
- Ответ должен быть коротким.
- Не используй Markdown: никаких #, **жирного**, таблиц и декоративной разметки.
- Не пиши дисклеймеры про языковые модели, собственное мнение, чувствительные
  темы и ограничения. Просто отвечай по сообщениям.

Формат:
Главный герой серии: <имя>
Почему:
- ...

Сообщения:
{self._format_messages(messages)}
""".strip()

    def _build_lore_prompt(self, messages: list[StoredMessage]) -> str:
        return f"""
Собери лор чата по последним сообщениям.

Правила:
- Русский язык, разговорно, можно грубо и с матом.
- Не делай обычное саммари. Нужны мемы, повторяющиеся приколы, внутренние
  темы, клички, долги, обещания, легенды и странные сюжетные линии.
- Не выдумывай, опирайся только на сообщения.
- 4-8 коротких пунктов.
- Не используй Markdown: никаких #, **жирного**, таблиц и декоративной разметки.
- Не пиши дисклеймеры про языковые модели, собственное мнение, чувствительные
  темы и ограничения. Просто собирай лор по сообщениям.

Формат:
Лор на сегодня:
- ...

Сообщения:
{self._format_messages(messages)}
""".strip()

    def _build_lore_search_prompt(
        self,
        query: str,
        messages: list[StoredMessage],
    ) -> str:
        return f"""
Объясни лор чата по поисковому запросу: "{query}".

Правила:
- Русский язык, неформально, можно с матом.
- Объясни, что за тема всплывала, кто участвовал и почему это смешно/важно.
- Не делай стенограмму и не выдумывай факты.
- 3-6 коротких пунктов.
- Не используй Markdown: никаких #, **жирного**, таблиц и декоративной разметки.
- Не пиши дисклеймеры про языковые модели, собственное мнение, чувствительные
  темы и ограничения. Просто объясняй лор по найденным сообщениям.

Найденные сообщения:
{self._format_messages(messages)}
""".strip()

    def _format_messages(self, messages: list[StoredMessage]) -> str:
        return "\n".join(
            f"{message.author_name}: {message.text}" for message in messages
        )
