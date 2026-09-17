import pathlib
import uuid

from tts import RussianTTS


class ClipStore:
    """Registry of synthesized Russian audio clips, keyed by clip_id.

    Decoupled from playback: create() only synthesizes and remembers the file;
    something else (an HTTP endpoint, a click) decides when to actually play it.
    """

    def __init__(self, tts: RussianTTS, output_dir: str = "audio_output"):
        self.tts = tts
        self.output_dir = pathlib.Path(output_dir)
        self.clips: dict[str, str] = {}

    def create(self, text: str) -> str:
        clip_id = uuid.uuid4().hex
        output_path = str(self.output_dir / f"{clip_id}.wav")
        if "<speak" in text:
            path = self.tts.synthesize_ssml(text, output_path=output_path)
        else:
            path = self.tts.synthesize(text, output_path=output_path)
        self.clips[clip_id] = path
        return clip_id

    def get_path(self, clip_id: str) -> str | None:
        return self.clips.get(clip_id)

    def clear(self) -> None:
        for path in self.clips.values():
            pathlib.Path(path).unlink(missing_ok=True)
        self.clips.clear()
