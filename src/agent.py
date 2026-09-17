import os
from typing import Literal, Union

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError

from clips import ClipStore
from tts import RussianTTS

load_dotenv()


class CreateClipArgs(BaseModel):
    text: str


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "create_pronunciation_clip",
            "description": (
                "Synthesize Russian audio for the given text and register it for "
                "later playback -- this does NOT play it immediately. Returns a "
                "clip_id. Reference that exact clip_id in a 'word' segment of your "
                "structured reply so the user can click it to hear the audio, as "
                "many times as they want. `text` must be Cyrillic (e.g. 'привет', "
                "not 'privet') -- the voice model cannot pronounce romanized text. "
                "It can also be SSML wrapped in <speak>...</speak> for "
                "pacing/emphasis."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Cyrillic Russian text (or Cyrillic SSML).",
                    }
                },
                "required": ["text"],
            },
        },
    }
]


class TextSegment(BaseModel):
    type: Literal["text"]
    content: str = Field(description="A chunk of plain reply text.")


class WordSegment(BaseModel):
    type: Literal["word"]
    display: str = Field(
        description="Label shown on the clickable button, e.g. a transliteration or the Cyrillic word."
    )
    clip_id: str = Field(
        description="The clip_id returned by a create_pronunciation_clip call for this exact word. Never invent one."
    )


class ChatReply(BaseModel):
    segments: list[Union[TextSegment, WordSegment]] = Field(
        description=(
            "Your reply broken into segments, in reading order. Any Russian word "
            "or phrase you've created a pronunciation clip for must be its own "
            "'word' segment; everything else is 'text' segments."
        )
    )


class TeacherAgent:
    def __init__(self):
        self.client = OpenAI(
            api_key=os.environ["OPENAI_API_KEY"],
            base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        )
        self.model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        self.clips = ClipStore(RussianTTS())
        self.history = []

    def chat(self, user_message: str) -> ChatReply:
        self.history.append({"role": "user", "content": user_message})

        while True:
            completion = self.client.chat.completions.parse(
                model=self.model,
                messages=self.history,
                tools=TOOLS,
                response_format=ChatReply,
            )
            message = completion.choices[0].message

            if message.tool_calls:
                self.history.append(message.model_dump(exclude_none=True))
                for tool_call in message.tool_calls:
                    try:
                        args = CreateClipArgs.model_validate_json(
                            tool_call.function.arguments
                        )
                        clip_id = self.clips.create(args.text)
                        result = f"clip_id: {clip_id}"
                    except ValidationError as e:
                        result = f"Error: invalid arguments - {e}"
                    self.history.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": result,
                        }
                    )
                continue

            self.history.append({"role": "assistant", "content": message.content})
            return message.parsed
