import html
import logging
import os
import re

from dotenv import load_dotenv
from openai import OpenAI

from clips import ClipStore
from store import Chat, ChatStore
from tts import DEFAULT_SPEAKER, RussianTTS

load_dotenv()

logger = logging.getLogger("uvicorn.error")

SYSTEM_PROMPT = (
    "You are a Russian teacher helping an English speaker learn Russian. "
    "Whenever you introduce a Russian word or phrase, write it in Cyrillic script "
    "(e.g. привет), and include an English transliteration in parentheses right "
    "after it (e.g. привет (privet)) so the student can read how it sounds. "
    "Always mark the stressed vowel of every Russian word that has more than one "
    "vowel with a combining acute accent placed right after that vowel (e.g. "
    "приве́т, здра́вствуйте, до́брое у́тро). This shows the student where the stress "
    "falls, and the audio is pronounced with exactly the stress you mark. Don't "
    "mark ё, which is always stressed."
)

# Matches a run of Cyrillic word(s), allowing single spaces/hyphens between them
# so a whole phrase (e.g. "доброе утро") becomes one clip instead of two. U+0301
# (combining acute accent) is allowed inside words so stress-marked words like
# "приве́т" stay in one piece.
_WORD = "[А-Яа-яЁё][А-Яа-яЁё\u0301]*"
CYRILLIC_RUN = re.compile(f"{_WORD}(?:[ \\-]{_WORD})*")

MARKDOWN_CODE = re.compile(r"`(.+?)`")
MARKDOWN_BOLD = re.compile(r"\*\*(.+?)\*\*")
MARKDOWN_ITALIC = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")


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
        self.chats = ChatStore()

    @property
    def voices(self) -> list[str]:
        return self.tts.speakers

    @property
    def default_voice(self) -> str:
        return DEFAULT_SPEAKER

    def chat_stream(self, chat: Chat, user_message: str):
        """Yields dict events as the reply is generated:
        {"type": "delta", "content": str}   - a chunk of streamed reply text
        {"type": "text_done"}               - reply text finished, synthesis starting
        {"type": "html", "html": str}       - final rendered reply, markdown converted
                                               to HTML with clickable Cyrillic words
        """
        logger.info("[%s] user: %s", chat.id, user_message)
        self.chats.add_message(chat, "user", user_message)

        messages = [{"role": "system", "content": SYSTEM_PROMPT}, *chat.messages]
        kwargs = dict(model=self.model, messages=messages, stream=True)
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
        logger.info("[%s] assistant: %s", chat.id, text)
        self.chats.add_message(chat, "assistant", text)
        yield {"type": "text_done"}

        yield {"type": "html", "html": self.render_html(text, chat.voice, synthesize=True)}

    def render_html(self, text: str, voice: str, synthesize: bool) -> str:
        """Markdown -> HTML with each Cyrillic run wrapped in a word button.

        With synthesize=True each word's clip is created up front so the first
        click plays instantly; otherwise (e.g. reopening an old chat) clips are
        created on demand when a word is clicked.
        """
        rendered = html.escape(text)
        rendered = MARKDOWN_CODE.sub(r"<code>\1</code>", rendered)
        rendered = MARKDOWN_BOLD.sub(r"<strong>\1</strong>", rendered)
        rendered = MARKDOWN_ITALIC.sub(r"<em>\1</em>", rendered)
        return CYRILLIC_RUN.sub(
            lambda m: self._word_button(m.group(), voice, synthesize), rendered
        )

    def _word_button(self, word: str, voice: str, synthesize: bool) -> str:
        clip_attr = ""
        if synthesize:
            clip_id = self.clips.create(word, voice)
            logger.info("clip created for %r (voice=%s) -> %s", word, voice, clip_id)
            clip_attr = f' data-clip-id="{clip_id}"'
        return (
            f'<button type="button" class="word-btn"{clip_attr} '
            f'data-voice="{voice}">{word}</button>'
        )
