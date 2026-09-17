import logging
import os

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, ValidationError

from clips import ClipStore
from tts import RussianTTS

load_dotenv()

logger = logging.getLogger("uvicorn.error")


class CreateClipArgs(BaseModel):
    text: str


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "create_pronunciation_clip",
            "description": (
                "Create a clickable audio clip so the user can hear the given "
                "Russian text pronounced. `text` must be Cyrillic (e.g. "
                "'привет', not 'privet') -- the voice model cannot pronounce "
                "romanized text."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Cyrillic Russian text to pronounce.",
                    }
                },
                "required": ["text"],
            },
        },
    }
]


class TeacherAgent:
    def __init__(self):
        self.client = OpenAI(
            api_key=os.environ["OPENAI_API_KEY"],
            base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        )
        self.model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        self.reasoning_effort = os.environ.get("OPENAI_REASONING_EFFORT", "high") or None
        self.clips = ClipStore(RussianTTS())
        self.history = []

    def chat(self, user_message: str) -> dict:
        logger.info("user: %s", user_message)
        self.history.append({"role": "user", "content": user_message})
        new_clips = []

        while True:
            kwargs = dict(model=self.model, messages=self.history, tools=TOOLS)
            if self.reasoning_effort:
                kwargs["reasoning_effort"] = self.reasoning_effort
            completion = self.client.chat.completions.create(**kwargs)
            message = completion.choices[0].message

            if message.tool_calls:
                logger.info(
                    "agent requested %d tool call(s)", len(message.tool_calls)
                )
                self.history.append(message.model_dump(exclude_none=True))
                for tool_call in message.tool_calls:
                    logger.info(
                        "tool_call[%s]: %s(%s)",
                        tool_call.id,
                        tool_call.function.name,
                        tool_call.function.arguments,
                    )
                    try:
                        args = CreateClipArgs.model_validate_json(
                            tool_call.function.arguments
                        )
                        clip_id = self.clips.create(args.text)
                        new_clips.append({"clip_id": clip_id, "text": args.text})
                        result = f"Spoken: {args.text}"
                    except ValidationError as e:
                        result = f"Error: invalid arguments - {e}"
                    logger.info("tool_result[%s]: %s", tool_call.id, result)
                    self.history.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": result,
                        }
                    )
                continue

            logger.info("assistant: %s", message.content)
            self.history.append({"role": "assistant", "content": message.content})
            return {"text": message.content, "clips": new_clips}
