import pathlib

import soundfile as sf
import torch


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

    def synthesize(
        self,
        text: str,
        speaker: str = "xenia",
        sample_rate: int = 48000,
        output_path: str = "audio_output/output.wav",
    ) -> str:
        audio = self.model.apply_tts(
            text=text,
            speaker=speaker,
            sample_rate=sample_rate,
        )
        return self._write(audio, sample_rate, output_path)

    def synthesize_ssml(
        self,
        ssml_text: str,
        speaker: str = "xenia",
        sample_rate: int = 48000,
        output_path: str = "audio_output/output.wav",
    ) -> str:
        """Same as synthesize(), but ssml_text may contain SSML markup
        (<speak>, <break>, <prosody>, <p>, <s>) for pauses/rate/pitch control."""
        audio = self.model.apply_tts(
            ssml_text=ssml_text,
            speaker=speaker,
            sample_rate=sample_rate,
        )
        return self._write(audio, sample_rate, output_path)

    @staticmethod
    def _write(audio, sample_rate: int, output_path: str) -> str:
        out_path = pathlib.Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(out_path, audio.numpy(), sample_rate)
        return str(out_path)
