import pathlib
import threading
import uuid

from tts import RussianTTS

OUTPUT_DIR = pathlib.Path(__file__).resolve().parent.parent / "audio_output"


class ClipStore:
    """Registry of synthesized audio clips, keyed by clip_id.

    Clips are cached by (text, speaker, slow), so asking for the same variant
    twice returns the existing clip instead of re-synthesizing it.
    """

    def __init__(self, tts: RussianTTS, output_dir: pathlib.Path = OUTPUT_DIR):
        self.tts = tts
        self.output_dir = output_dir
        self.clips: dict[str, str] = {}
        self._by_key: dict[tuple[str, str, bool], str] = {}
        # Chat streaming and /clips requests run on different threads but share
        # one model; synthesis is serialized to keep that safe.
        self._lock = threading.Lock()

    def create(self, text: str, speaker: str, slow: bool = False) -> str:
        key = (text, speaker, slow)
        with self._lock:
            if key in self._by_key:
                return self._by_key[key]
            clip_id = uuid.uuid4().hex
            path = self.tts.synthesize(
                text,
                output_path=str(self.output_dir / f"{clip_id}.wav"),
                speaker=speaker,
                slow=slow,
            )
            self.clips[clip_id] = path
            self._by_key[key] = clip_id
            return clip_id

    def get_path(self, clip_id: str) -> str | None:
        return self.clips.get(clip_id)

    def clear(self) -> None:
        with self._lock:
            for path in self.output_dir.glob("*.wav"):
                path.unlink(missing_ok=True)
            self.clips.clear()
            self._by_key.clear()
