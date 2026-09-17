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
    "You are a friendly Russian teacher helping an English speaker learn Russian. "
    "Whenever you introduce a Russian word or phrase, write it in Cyrillic script "
    "(e.g. привет), and include an English transliteration in parentheses right "
    "after it (e.g. привет (privet)) so the student can read how it sounds. Keep "
    "explanations clear, encouraging, and concise."
)

# Matches a run of Cyrillic word(s), allowing single spaces/hyphens between them
# so a whole phrase (e.g. "доброе утро") becomes one clip instead of two.
CYRILLIC_RUN = re.compile(r"[А-Яа-яЁё]+(?:[ \-][А-Яа-яЁё]+)*")


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

    def chat(self, user_message: str) -> dict:
        logger.info("user: %s", user_message)
        self.history.append({"role": "user", "content": user_message})

        kwargs = dict(model=self.model, messages=self.history)
        if self.reasoning_effort:
            kwargs["reasoning_effort"] = self.reasoning_effort
        completion = self.client.chat.completions.create(**kwargs)
        text = completion.choices[0].message.content

        logger.info("assistant: %s", text)
        self.history.append({"role": "assistant", "content": text})

        return {"segments": self._segment(text)}

    def _segment(self, text: str) -> list[dict]:
        segments = []
        last_end = 0
        for match in CYRILLIC_RUN.finditer(text):
            if match.start() > last_end:
                segments.append({"type": "text", "content": text[last_end : match.start()]})
            cyrillic_text = match.group()
            clip_id = self.clips.create(cyrillic_text)
            logger.info("clip created for %r -> %s", cyrillic_text, clip_id)
            segments.append({"type": "word", "content": cyrillic_text, "clip_id": clip_id})
            last_end = match.end()
        if last_end < len(text):
            segments.append({"type": "text", "content": text[last_end:]})
        return segments
