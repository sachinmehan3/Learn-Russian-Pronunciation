import json
import os
import winsound

from dotenv import load_dotenv
from openai import OpenAI

from tts import RussianTTS

load_dotenv()

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "speak_russian",
            "description": (
                "Synthesize and play spoken Russian audio out loud for the given "
                "text, using a native Russian voice. Use this whenever it would "
                "help the user hear correct Russian pronunciation. `text` must be "
                "written in the Cyrillic alphabet (e.g. 'привет', not 'privet') "
                "-- the voice model cannot pronounce romanized/transliterated "
                "Russian. It can be plain Cyrillic text, or SSML wrapped in "
                "<speak>...</speak> to control pacing/emphasis (e.g. "
                "<prosody rate=\"x-slow\"> to slow down a hard word, "
                "<break time=\"500ms\"/> for a pause)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": (
                            "Russian text in Cyrillic script (or Cyrillic text "
                            "wrapped in SSML) to pronounce. Never romanized/Latin "
                            "transliteration."
                        ),
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
        self.tts = RussianTTS()
        self.history = []

    def speak_russian(self, text: str) -> str:
        if "<speak" in text:
            path = self.tts.synthesize_ssml(text)
        else:
            path = self.tts.synthesize(text)
        winsound.PlaySound(path, winsound.SND_FILENAME)
        return f"Played: {text}"

    def chat(self, user_message: str) -> str:
        self.history.append({"role": "user", "content": user_message})

        response = self.client.chat.completions.create(
            model=self.model,
            messages=self.history,
            tools=TOOLS,
        )
        message = response.choices[0].message

        while message.tool_calls:
            self.history.append(message.model_dump(exclude_none=True))

            for tool_call in message.tool_calls:
                args = json.loads(tool_call.function.arguments)
                result = self.speak_russian(args["text"])
                self.history.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result,
                    }
                )

            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.history,
                tools=TOOLS,
            )
            message = response.choices[0].message

        self.history.append({"role": "assistant", "content": message.content})
        return message.content
