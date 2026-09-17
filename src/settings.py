import logging
import os
import threading
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger("uvicorn.error")

SETTINGS_PATH = Path(__file__).resolve().parent.parent / "settings.json"
DEFAULT_BASE_URL = "https://api.openai.com/v1"

DEFAULT_SYSTEM_PROMPT = (
    "You are a Russian teacher helping an English speaker learn Russian. "
    "Whenever you introduce a Russian word or phrase, write it in Cyrillic script "
    "(e.g. привет), and include an English transliteration in parentheses right "
    "after it (e.g. привет (privet)) so the student can read how it sounds. "
    "Always mark the stressed vowel of every Russian word that has more than one "
    "vowel with a combining acute accent placed right after that vowel (e.g. "
    "приве́т, здра́вствуйте, до́брое у́тро). This shows the student where the stress "
    "falls, and the audio is pronounced with exactly the stress you mark. Don't "
    "mark ё, which is always stressed."
)

ReasoningEffort = Literal["none", "minimal", "low", "medium", "high", "xhigh", "max"]


def normalize_base_url(url: str) -> str:
    return url.strip().rstrip("/")


class Settings(BaseModel):
    base_url: str = DEFAULT_BASE_URL
    api_key: str = ""
    model: str = ""
    # None means "don't send this parameter; use the model's default".
    temperature: float | None = Field(default=None, ge=0, le=2)
    top_p: float | None = Field(default=None, ge=0, le=1)
    max_tokens: int | None = Field(default=None, ge=1)
    reasoning_effort: ReasoningEffort | None = "high"
    system_prompt: str | None = None

    @field_validator("base_url")
    @classmethod
    def _normalize_url(cls, v: str) -> str:
        return normalize_base_url(v)

    @field_validator("api_key", "model")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()

    @field_validator("system_prompt")
    @classmethod
    def _blank_prompt_is_default(cls, v: str | None) -> str | None:
        return v if v and v.strip() and v.strip() != DEFAULT_SYSTEM_PROMPT else None

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.api_key and self.model)

    @property
    def effective_system_prompt(self) -> str:
        return self.system_prompt or DEFAULT_SYSTEM_PROMPT

    def request_params(self) -> dict:
        params = {}
        if self.temperature is not None:
            params["temperature"] = self.temperature
        if self.top_p is not None:
            params["top_p"] = self.top_p
        if self.max_tokens is not None:
            params["max_completion_tokens"] = self.max_tokens
        if self.reasoning_effort is not None:
            params["reasoning_effort"] = self.reasoning_effort
        return params

    def public(self) -> dict:
        """Everything the UI needs, with the API key reduced to a hint."""
        data = self.model_dump(exclude={"api_key"})
        data["api_key_hint"] = f"…{self.api_key[-4:]}" if self.api_key else None
        data["configured"] = self.configured
        data["system_prompt"] = self.effective_system_prompt
        data["default_system_prompt"] = DEFAULT_SYSTEM_PROMPT
        return data


class SettingsUpdate(BaseModel):
    """Partial update: only fields present in the request are changed.

    api_key is write-only: omit it (or send null) to keep the saved key.
    """

    base_url: str | None = None
    api_key: str | None = None
    model: str | None = None
    temperature: float | None = Field(default=None, ge=0, le=2)
    top_p: float | None = Field(default=None, ge=0, le=1)
    max_tokens: int | None = Field(default=None, ge=1)
    reasoning_effort: ReasoningEffort | None = None
    system_prompt: str | None = None

    def changes(self) -> dict:
        changes = self.model_dump(exclude_unset=True)
        for key in ("base_url", "model"):
            if changes.get(key) is None:
                changes.pop(key, None)
        if not changes.get("api_key"):
            changes.pop("api_key", None)
        return changes


class SettingsStore:
    def __init__(self, path: Path = SETTINGS_PATH):
        self.path = path
        self._lock = threading.Lock()
        self.current = self._load()

    def _load(self) -> Settings:
        if not self.path.exists():
            return Settings()
        try:
            return Settings.model_validate_json(self.path.read_text(encoding="utf-8"))
        except ValueError as e:
            logger.warning("ignoring unreadable %s: %s", self.path.name, e)
            return Settings()

    def update(self, changes: dict) -> Settings:
        with self._lock:
            merged = Settings.model_validate({**self.current.model_dump(), **changes})
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(merged.model_dump_json(indent=2), encoding="utf-8")
            os.replace(tmp, self.path)
            self.current = merged
            return merged
