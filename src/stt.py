import collections
import logging
import tempfile
import threading
import typing
from pathlib import Path

import soundfile as sf
import torch
import torchaudio

logger = logging.getLogger("uvicorn.error")

MODEL_NAME = "v2_ctc"
SAMPLE_RATE = 16000
MAX_SECONDS = 30


def _allow_config_globals() -> None:
    """GigaAM's checkpoint stores its config as omegaconf objects.

    PyTorch 2.6 made torch.load refuse non-tensor globals by default. Allowlisting
    just these config types keeps that protection for everything else.
    """
    import omegaconf
    from omegaconf.base import ContainerMetadata, Metadata
    from omegaconf.nodes import AnyNode

    torch.serialization.add_safe_globals([
        omegaconf.DictConfig,
        omegaconf.ListConfig,
        ContainerMetadata,
        Metadata,
        AnyNode,
        typing.Any,
        dict,
        list,
        int,
        str,
        bool,
        float,
        collections.defaultdict,
    ])


def load_audio(path: str, sample_rate: int = SAMPLE_RATE, return_format: str = "float"):
    """Stands in for GigaAM's loader, which shells out to ffmpeg."""
    audio, sr = sf.read(path, dtype="float32", always_2d=True)
    wav = torch.from_numpy(audio.mean(axis=1))
    if sr != sample_rate:
        wav = torchaudio.functional.resample(wav, sr, sample_rate)
    if return_format == "float":
        return wav
    return (wav * 32768.0).to(torch.int16)


class RussianSTT:
    """GigaAM v2 CTC speech recognition, loaded on first use.

    The model is ~444MB and takes a couple of seconds to load, so the first
    transcription pays that cost rather than every startup.
    """

    def __init__(self, model_name: str = MODEL_NAME):
        self.model_name = model_name
        self._model = None
        self._load_lock = threading.Lock()
        self._run_lock = threading.Lock()

    @property
    def loaded(self) -> bool:
        return self._model is not None

    def _model_or_load(self):
        if self._model is None:
            with self._load_lock:
                if self._model is None:
                    _allow_config_globals()
                    import gigaam
                    import gigaam.model

                    gigaam.model.load_audio = load_audio
                    logger.info("loading GigaAM %s (first run downloads it)", self.model_name)
                    self._model = gigaam.load_model(
                        self.model_name, fp16_encoder=False, device="cpu"
                    )
                    logger.info("GigaAM ready")
        return self._model

    def transcribe_wav(self, audio: bytes) -> str:
        """Transcribe WAV bytes. Raises ValueError if they aren't usable audio."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio)
            path = Path(tmp.name)
        try:
            try:
                info = sf.info(path)
            except Exception as e:
                raise ValueError("That doesn't look like a WAV recording.") from e
            if info.frames == 0:
                raise ValueError("The recording was empty.")
            if info.duration > MAX_SECONDS:
                raise ValueError(f"Recording is too long (max {MAX_SECONDS} seconds).")

            model = self._model_or_load()
            with self._run_lock:
                text = model.transcribe(str(path))
            logger.info("transcribed %.1fs of audio -> %r", info.duration, text)
            return text.strip()
        finally:
            path.unlink(missing_ok=True)
