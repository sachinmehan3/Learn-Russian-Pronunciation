import json
import logging
import os
import re
import threading
import uuid
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("uvicorn.error")

CHATS_DIR = Path(__file__).resolve().parent.parent / "chats"
CHAT_ID = re.compile(r"[0-9a-f]{32}")


class Chat:
    def __init__(self, chat_id, voice, title=None, created_at=None, messages=None):
        self.id = chat_id
        self.voice = voice
        self.title = title
        self.created_at = created_at or datetime.now().isoformat(timespec="seconds")
        self.messages: list[dict] = messages or []
        self.deleted = False

    def summary(self) -> dict:
        return {
            "chat_id": self.id,
            "title": self.title,
            "voice": self.voice,
            "created_at": self.created_at,
        }


class ChatStore:
    """Chats persisted as one JSONL file each: a meta line, then one line per message.

    A chat only gets a file once its first message is added, so opening
    "New chat" without sending anything leaves nothing behind.
    """

    def __init__(self, directory: Path = CHATS_DIR):
        self.dir = directory
        self.dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, Chat] = {}
        self._lock = threading.Lock()

    def _path(self, chat_id: str) -> Path:
        return self.dir / f"{chat_id}.jsonl"

    def create(self, voice: str) -> Chat:
        chat = Chat(uuid.uuid4().hex, voice)
        with self._lock:
            self._cache[chat.id] = chat
        return chat

    def get(self, chat_id: str) -> Chat | None:
        if not CHAT_ID.fullmatch(chat_id):
            return None
        with self._lock:
            if chat_id in self._cache:
                return self._cache[chat_id]
            path = self._path(chat_id)
            if not path.exists():
                return None
            chat = self._load(path)
            self._cache[chat_id] = chat
            return chat

    def list(self) -> list[dict]:
        with self._lock:
            paths = sorted(
                self.dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True
            )
            summaries = []
            for path in paths:
                try:
                    with path.open(encoding="utf-8") as f:
                        meta = json.loads(f.readline())
                    summaries.append(
                        Chat(meta["chat_id"], meta["voice"], meta.get("title"), meta["created_at"]).summary()
                    )
                except (ValueError, KeyError) as e:
                    logger.warning("skipping unreadable chat file %s: %s", path.name, e)
            return summaries

    def add_message(self, chat: Chat, role: str, content: str) -> None:
        with self._lock:
            chat.messages.append({"role": role, "content": content})
            if chat.deleted:
                return
            path = self._path(chat.id)
            is_new = not path.exists()
            with path.open("a", encoding="utf-8") as f:
                if is_new:
                    f.write(self._meta_line(chat))
                f.write(self._message_line(role, content))

    def rename(self, chat: Chat, title: str | None) -> None:
        with self._lock:
            chat.title = title
            if chat.deleted:
                return
            path = self._path(chat.id)
            old_mtime = path.stat().st_mtime if path.exists() else None
            tmp = path.with_suffix(".tmp")
            with tmp.open("w", encoding="utf-8") as f:
                f.write(self._meta_line(chat))
                for m in chat.messages:
                    f.write(self._message_line(m["role"], m["content"]))
            os.replace(tmp, path)
            # Renaming shouldn't bump a chat to the top of the recency-sorted list.
            if old_mtime is not None:
                os.utime(path, (old_mtime, old_mtime))

    def delete(self, chat: Chat) -> None:
        with self._lock:
            chat.deleted = True
            self._cache.pop(chat.id, None)
            self._path(chat.id).unlink(missing_ok=True)

    @staticmethod
    def _meta_line(chat: Chat) -> str:
        return json.dumps({"type": "meta", **chat.summary()}, ensure_ascii=False) + "\n"

    @staticmethod
    def _message_line(role: str, content: str) -> str:
        return json.dumps({"type": "message", "role": role, "content": content}, ensure_ascii=False) + "\n"

    @staticmethod
    def _load(path: Path) -> Chat:
        meta, messages = None, []
        with path.open(encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                record = json.loads(line)
                if record["type"] == "meta":
                    meta = record
                elif record["type"] == "message":
                    messages.append({"role": record["role"], "content": record["content"]})
        return Chat(meta["chat_id"], meta["voice"], meta.get("title"), meta["created_at"], messages)
