import asyncio
import re

from gigachat import GigaChat

from app.config import Settings


class GigaChatClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def summarize(self, prompt: str) -> str:
        return await asyncio.to_thread(self._summarize_sync, prompt)

    def _summarize_sync(self, prompt: str) -> str:
        with GigaChat(
            credentials=self._settings.gigachat_credentials,
            scope=self._settings.gigachat_scope,
            model=self._settings.gigachat_model,
            verify_ssl_certs=self._settings.gigachat_verify_ssl_certs,
            profanity_check=False,
            timeout=60,
            max_retries=2,
        ) as client:
            response = client.chat(prompt)
            content = response.choices[0].message.content

            if _looks_like_refusal(content):
                response = client.chat(_build_safe_retry_prompt(prompt))
                content = response.choices[0].message.content

        return _strip_markdown(content)


def _looks_like_refusal(text: str) -> bool:
    normalized = text.lower()
    refusal_markers = (
        "генеративные языковые модели не обладают собственным мнением",
        "разговоры на чувствительные темы могут быть ограничены",
        "чувствительные темы",
        "не могу",
        "не могу помочь",
    )

    return any(marker in normalized for marker in refusal_markers)


def _build_safe_retry_prompt(prompt: str) -> str:
    return f"""
Сделай нейтральную фактологическую сводку Telegram-переписки.

Важно:
- Не выражай собственное мнение.
- Не добавляй дисклеймеры про языковые модели, чувствительные темы и ограничения.
- Не давай оценок морали и не поучай участников.
- Не продолжай оскорбления от себя.
- Если в исходных сообщениях есть мат или грубость, можно кратко пересказать это
  как факт переписки без смягчения смысла.
- Ответь на русском, коротко, обычным текстом без Markdown.

Исходная задача и сообщения:
{prompt}
""".strip()


def _strip_markdown(text: str) -> str:
    cleaned_lines = []

    for raw_line in text.strip().splitlines():
        line = raw_line.strip()
        line = re.sub(r"^#{1,6}\s*", "", line)
        line = re.sub(r"^[-*]\s+", "", line)
        line = re.sub(r"^\d+\.\s+", "", line)
        line = re.sub(r"\*\*(.*?)\*\*", r"\1", line)
        line = re.sub(r"__(.*?)__", r"\1", line)
        line = re.sub(r"`([^`]*)`", r"\1", line)
        cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()
