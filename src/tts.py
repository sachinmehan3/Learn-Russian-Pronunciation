import html
import pathlib
import re

import soundfile as sf
import torch

DEFAULT_SPEAKER = "xenia"

STRESS_MARK = "\u0301"
_STRESSED_VOWEL = re.compile(f"([аеёиоуыэюяАЕЁИОУЫЭЮЯ]){STRESS_MARK}")


def to_silero_stress(text: str) -> str:
    """Convert combining-acute stress marks (приве́т) to Silero's notation (прив+ет).

    Silero silently ignores U+0301, so without this the marked stress never
    reaches the audio. Stray marks not following a vowel are dropped.
    """
    return _STRESSED_VOWEL.sub(r"+\1", text).replace(STRESS_MARK, "")


class RussianTTS:
    """Wrapper around Silero's Russian TTS model."""

    def __init__(self, device: str = "cpu", model_id: str = "v5_5_ru"):
        self.device = torch.device(device)
        self.model, _ = torch.hub.load(
            repo_or_dir="snakers4/silero-models",
            model="silero_tts",
            language="ru",
            speaker=model_id,
        )
        self.model.to(self.device)

    @property
    def speakers(self) -> list[str]:
        return list(self.model.speakers)

    def synthesize(
        self,
        text: str,
        output_path: str,
        speaker: str = DEFAULT_SPEAKER,
        slow: bool = False,
        sample_rate: int = 48000,
    ) -> str:
        text = to_silero_stress(text)
        if slow:
            ssml = f'<speak><prosody rate="x-slow">{html.escape(text)}</prosody></speak>'
            audio = self.model.apply_tts(
                ssml_text=ssml, speaker=speaker, sample_rate=sample_rate
            )
        else:
            audio = self.model.apply_tts(
                text=text, speaker=speaker, sample_rate=sample_rate
            )

        out_path = pathlib.Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(out_path, audio.numpy(), sample_rate)
        return str(out_path)
