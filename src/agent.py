import html
import logging
import os
import re

from dotenv import load_dotenv
from openai import OpenAI

from clips import ClipStore
from tts import RussianTTS

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


class TeacherAgent:
    def __init__(self):
        self.client = OpenAI(
            api_key=os.environ["OPENAI_API_KEY"],
            base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        )
        self.model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        self.reasoning_effort = os.environ.get("OPENAI_REASONING_EFFORT", "high") or None
        self.clips = ClipStore(RussianTTS())
        self.history = [{"role": "system", "content": SYSTEM_PROMPT}]

    def chat_stream(self, user_message: str):
        """Yields dict events as the reply is generated:
        {"type": "delta", "content": str}   - a chunk of streamed reply text
        {"type": "text_done"}               - reply text finished, synthesis starting
        {"type": "html", "html": str}       - final rendered reply, markdown converted
                                               to HTML with clickable Cyrillic words
        """
        logger.info("user: %s", user_message)
        self.history.append({"role": "user", "content": user_message})

        kwargs = dict(model=self.model, messages=self.history, stream=True)
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
        logger.info("assistant: %s", text)
        self.history.append({"role": "assistant", "content": text})
        yield {"type": "text_done"}

        yield {"type": "html", "html": self._render_html(text)}

    def _render_html(self, text: str) -> str:
        rendered = html.escape(text)
        rendered = MARKDOWN_CODE.sub(r"<code>\1</code>", rendered)
        rendered = MARKDOWN_BOLD.sub(r"<strong>\1</strong>", rendered)
        rendered = MARKDOWN_ITALIC.sub(r"<em>\1</em>", rendered)
        return CYRILLIC_RUN.sub(self._make_word_button, rendered)

    def _make_word_button(self, match: re.Match) -> str:
        cyrillic_text = match.group()
        clip_id = self.clips.create(cyrillic_text)
        logger.info("clip created for %r -> %s", cyrillic_text, clip_id)
        return (
            f'<button type="button" class="word-btn" '
            f'data-clip-id="{clip_id}">{cyrillic_text}</button>'
        )
