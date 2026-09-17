import logging
import pathlib
import shutil
import threading
import uuid

from tts import RussianTTS

logger = logging.getLogger("uvicorn.error")

OUTPUT_DIR = pathlib.Path(__file__).resolve().parent.parent / "audio_output"


class ClipStore:
    """Synthesized audio clips, owned by the chat they were made for.

    Each chat gets its own directory, so deleting a chat is just deleting that
    directory. Clips are cached per chat by (text, speaker, slow); the same word
    in two chats is synthesized twice, which keeps ownership unambiguous.
    """

    def __init__(self, tts: RussianTTS, output_dir: pathlib.Path = OUTPUT_DIR):
        self.tts = tts
        self.output_dir = output_dir
        self.clips: dict[str, str] = {}
        self._by_key: dict[tuple[str, str, str, bool], str] = {}
        self._by_chat: dict[str, set[str]] = {}
        # Chat streaming and /clips requests run on different threads but share
        # one model; synthesis is serialized to keep that safe.
        self._lock = threading.Lock()

    def create(self, chat_id: str, text: str, speaker: str, slow: bool = False) -> str:
        key = (chat_id, text, speaker, slow)
        with self._lock:
            if key in self._by_key:
                return self._by_key[key]
            clip_id = uuid.uuid4().hex
            chat_dir = self.output_dir / chat_id
            path = self.tts.synthesize(
                text,
                output_path=str(chat_dir / f"{clip_id}.wav"),
                speaker=speaker,
                slow=slow,
            )
            self.clips[clip_id] = path
            self._by_key[key] = clip_id
            self._by_chat.setdefault(chat_id, set()).add(clip_id)
            return clip_id

    def get_path(self, clip_id: str) -> str | None:
        return self.clips.get(clip_id)

    def delete_chat(self, chat_id: str) -> None:
        with self._lock:
            for clip_id in self._by_chat.pop(chat_id, ()):
                self.clips.pop(clip_id, None)
            self._by_key = {k: v for k, v in self._by_key.items() if k[0] != chat_id}
            shutil.rmtree(self.output_dir / chat_id, ignore_errors=True)
            logger.info("deleted audio for chat %s", chat_id)

    def clear(self) -> None:
        with self._lock:
            shutil.rmtree(self.output_dir, ignore_errors=True)
            self.output_dir.mkdir(parents=True, exist_ok=True)
            self.clips.clear()
            self._by_key.clear()
            self._by_chat.clear()
