import logging
import re

import openai
from markdown_it import MarkdownIt

from clips import ClipStore
from settings import Settings, SettingsStore
from stt import RussianSTT
from store import Chat, ChatStore
from tts import DEFAULT_SPEAKER, RussianTTS

logger = logging.getLogger("uvicorn.error")

# Matches a run of Cyrillic word(s), allowing single spaces/hyphens between them
# so a whole phrase (e.g. "доброе утро") becomes one clip instead of two. U+0301
# (combining acute accent) is allowed inside words so stress-marked words like
# "приве́т" stay in one piece.
_WORD = "[А-Яа-яЁё][А-Яа-яЁё\u0301]*"
CYRILLIC_RUN = re.compile(f"{_WORD}(?:[ \\-]{_WORD})*")

# html=False keeps any raw HTML the model writes as escaped text.
MARKDOWN = MarkdownIt("gfm-like", {"html": False, "linkify": False})

TAG_SPLIT = re.compile(r"(<[^>]+>)")
TAG_NAME = re.compile(r"</?\s*([a-zA-Z0-9]+)")
# Inside these, a pronunciation button would be wrong or invalid markup.
NO_BUTTON_TAGS = {"code", "pre", "a"}


class TeacherAgent:
    def __init__(self):
        self.settings = SettingsStore()
        self.tts = RussianTTS()
        self.stt = RussianSTT()
        self.clips = ClipStore(self.tts)
        self.chats = ChatStore()
        self._client: openai.OpenAI | None = None
        self._client_key: tuple[str, str] | None = None

    @property
    def voices(self) -> list[str]:
        return self.tts.speakers

    @property
    def default_voice(self) -> str:
        return DEFAULT_SPEAKER

    def _client_for(self, settings: Settings) -> openai.OpenAI:
        key = (settings.base_url, settings.api_key)
        if self._client_key != key:
            self._client = openai.OpenAI(base_url=settings.base_url, api_key=settings.api_key)
            self._client_key = key
        return self._client

    @staticmethod
    def list_models(base_url: str, api_key: str) -> list[str]:
        client = openai.OpenAI(base_url=base_url, api_key=api_key, timeout=15, max_retries=0)
        return sorted(m.id for m in client.models.list())

    def chat_stream(self, chat: Chat, user_message: str):
        """Yields dict events as the reply is generated:
        {"type": "delta", "content": str}   - a chunk of streamed reply text
        {"type": "text_done"}               - reply text finished, synthesis starting
        {"type": "html", "html": str}       - final rendered reply, markdown converted
                                               to HTML with clickable Cyrillic words
        {"type": "error", "message": str}   - the API call failed; nothing was saved

        The user message and reply are saved together only once the reply
        succeeds, so a failed attempt (bad key, unknown model) leaves no trace.
        """
        settings = self.settings.current
        logger.info("[%s] user: %s", chat.id, user_message)
        messages = [
            {"role": "system", "content": settings.effective_system_prompt},
            *chat.messages,
            {"role": "user", "content": user_message},
        ]

        chunks = []
        try:
            stream = self._client_for(settings).chat.completions.create(
                model=settings.model,
                messages=messages,
                stream=True,
                **settings.request_params(),
            )
            for chunk in stream:
                # Some providers send chunks with no choices (e.g. usage reports).
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta.content
                if delta:
                    chunks.append(delta)
                    yield {"type": "delta", "content": delta}
        except openai.APIError as e:
            logger.warning("[%s] API error: %s", chat.id, e)
            yield {"type": "error", "message": describe_api_error(e)}
            return

        text = "".join(chunks)
        logger.info("[%s] assistant: %s", chat.id, text)
        self.chats.add_message(chat, "user", user_message)
        self.chats.add_message(chat, "assistant", text)
        yield {"type": "text_done"}

        yield {
            "type": "html",
            "html": self.render_html(text, chat.voice, chat.id, synthesize=True),
        }

    def render_html(self, text: str, voice: str, chat_id: str, synthesize: bool) -> str:
        """Markdown -> HTML with each Cyrillic run wrapped in a word button.

        With synthesize=True each word's clip is created up front so the first
        click plays instantly; otherwise (e.g. reopening an old chat) clips are
        created on demand when a word is clicked.
        """
        return self._link_words(MARKDOWN.render(text).strip(), voice, chat_id, synthesize)

    def _link_words(self, rendered: str, voice: str, chat_id: str, synthesize: bool) -> str:
        """Wrap Cyrillic runs in the rendered HTML's text, never inside tags.

        Markdown output is HTML, so substituting blindly could rewrite a tag or
        an attribute value. Splitting on tags keeps the substitution to text, and
        a depth counter skips content where a button doesn't belong.
        """
        out = []
        skip_depth = 0
        for part in TAG_SPLIT.split(rendered):
            if part.startswith("<") and part.endswith(">"):
                match = TAG_NAME.match(part)
                name = match.group(1).lower() if match else ""
                if name in NO_BUTTON_TAGS:
                    if part.startswith("</"):
                        skip_depth = max(0, skip_depth - 1)
                    elif not part.endswith("/>"):
                        skip_depth += 1
            elif not skip_depth and part:
                part = CYRILLIC_RUN.sub(
                    lambda m: self._word_button(m.group(), voice, chat_id, synthesize), part
                )
            out.append(part)
        return "".join(out)

    def _word_button(self, word: str, voice: str, chat_id: str, synthesize: bool) -> str:
        clip_attr = ""
        if synthesize:
            clip_id = self.clips.create(chat_id, word, voice)
            logger.info("clip created for %r (voice=%s) -> %s", word, voice, clip_id)
            clip_attr = f' data-clip-id="{clip_id}"'
        return (
            f'<button type="button" class="word-btn"{clip_attr} '
            f'data-voice="{voice}">{word}</button>'
        )


def describe_api_error(e: openai.APIError) -> str:
    if isinstance(e, openai.AuthenticationError):
        return "The API key was rejected. Check it in Settings > Connections."
    if isinstance(e, openai.NotFoundError):
        return "The model or URL wasn't found. Check Settings > Connections."
    if isinstance(e, openai.APIConnectionError):
        return "Couldn't reach the API. Check the base URL in Settings > Connections."
    return getattr(e, "message", None) or str(e)
