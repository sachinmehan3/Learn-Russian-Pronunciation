import html
import logging
import os
import re
import uuid

from dotenv import load_dotenv
from openai import OpenAI

from clips import ClipStore
from tts import DEFAULT_SPEAKER, RussianTTS

load_dotenv()

logger = logging.getLogger("uvicorn.error")

SYSTEM_PROMPT = (
    "You are a Russian teacher helping an English speaker learn Russian. "
    "Whenever you introduce a Russian word or phrase, write it in Cyrillic script "
    "(e.g. привет), and include an English transliteration in parentheses right "
    "after it (e.g. привет (privet)) so the student can read how it sounds."
)

# Matches a run of Cyrillic word(s), allowing single spaces/hyphens between them
# so a whole phrase (e.g. "доброе утро") becomes one clip instead of two.
CYRILLIC_RUN = re.compile(r"[А-Яа-яЁё]+(?:[ \-][А-Яа-яЁё]+)*")

MARKDOWN_CODE = re.compile(r"`(.+?)`")
MARKDOWN_BOLD = re.compile(r"\*\*(.+?)\*\*")
MARKDOWN_ITALIC = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")


class Chat:
    def __init__(self, voice: str):
        self.voice = voice
        self.history = [{"role": "system", "content": SYSTEM_PROMPT}]


class TeacherAgent:
    def __init__(self):
        self.client = OpenAI(
            api_key=os.environ["OPENAI_API_KEY"],
            base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        )
        self.model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        self.reasoning_effort = os.environ.get("OPENAI_REASONING_EFFORT", "high") or None
        self.tts = RussianTTS()
        self.clips = ClipStore(self.tts)
        self.chats: dict[str, Chat] = {}

    @property
    def voices(self) -> list[str]:
        return self.tts.speakers

    @property
    def default_voice(self) -> str:
        return DEFAULT_SPEAKER

    def new_chat(self, voice: str) -> str:
        chat_id = uuid.uuid4().hex
        self.chats[chat_id] = Chat(voice)
        logger.info("new chat %s (voice=%s)", chat_id, voice)
        return chat_id

    def chat_stream(self, chat_id: str, user_message: str):
        """Yields dict events as the reply is generated:
        {"type": "delta", "content": str}   - a chunk of streamed reply text
        {"type": "text_done"}               - reply text finished, synthesis starting
        {"type": "html", "html": str}       - final rendered reply, markdown converted
                                               to HTML with clickable Cyrillic words
        """
        chat = self.chats[chat_id]
        logger.info("[%s] user: %s", chat_id, user_message)
        chat.history.append({"role": "user", "content": user_message})

        kwargs = dict(model=self.model, messages=chat.history, stream=True)
        if self.reasoning_effort:
            kwargs["reasoning_effort"] = self.reasoning_effort
        stream = self.client.chat.completions.create(**kwargs)

        chunks = []
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                chunks.append(delta)
                yield {"type": "delta", "content": delta}

        text = "".join(chunks)
        logger.info("[%s] assistant: %s", chat_id, text)
        chat.history.append({"role": "assistant", "content": text})
        yield {"type": "text_done"}

        yield {"type": "html", "html": self._render_html(text, chat.voice)}

    def _render_html(self, text: str, voice: str) -> str:
        rendered = html.escape(text)
        rendered = MARKDOWN_CODE.sub(r"<code>\1</code>", rendered)
        rendered = MARKDOWN_BOLD.sub(r"<strong>\1</strong>", rendered)
        rendered = MARKDOWN_ITALIC.sub(r"<em>\1</em>", rendered)
        return CYRILLIC_RUN.sub(lambda m: self._word_button(m.group(), voice), rendered)

    def _word_button(self, word: str, voice: str) -> str:
        clip_id = self.clips.create(word, voice)
        logger.info("clip created for %r (voice=%s) -> %s", word, voice, clip_id)
        return (
            f'<button type="button" class="word-btn" '
            f'data-clip-id="{clip_id}" data-voice="{voice}">{word}</button>'
        )
