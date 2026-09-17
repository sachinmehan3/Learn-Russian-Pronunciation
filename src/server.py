import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
import openai
from pydantic import BaseModel

from agent import CYRILLIC_RUN, TeacherAgent, describe_api_error
from settings import SettingsUpdate, normalize_base_url

logger = logging.getLogger("uvicorn.error")

STATIC_DIR = Path(__file__).parent / "static"

agent = TeacherAgent()


@asynccontextmanager
async def lifespan(app: FastAPI):
    agent.clips.clear()
    yield


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class NewChatRequest(BaseModel):
    voice: str


class RenameChatRequest(BaseModel):
    title: str


class MessageRequest(BaseModel):
    message: str


class ClipRequest(BaseModel):
    chat_id: str
    text: str
    voice: str
    slow: bool = False


class ModelsRequest(BaseModel):
    base_url: str
    api_key: str | None = None


def require_voice(voice: str) -> None:
    if voice not in agent.voices:
        raise HTTPException(status_code=400, detail=f"Unknown voice {voice!r}")


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/voices")
def voices():
    return {"voices": agent.voices, "default": agent.default_voice}


@app.get("/settings")
def get_settings():
    return agent.settings.current.public()


@app.patch("/settings")
def update_settings(req: SettingsUpdate):
    updated = agent.settings.update(req.changes())
    logger.info("settings updated: %s", sorted(req.changes()))
    return updated.public()


@app.post("/settings/models")
def list_models(req: ModelsRequest):
    base_url = normalize_base_url(req.base_url)
    api_key = (req.api_key or "").strip()
    saved = agent.settings.current
    # The saved key is only ever sent to the saved URL, so a request can't
    # redirect it to an arbitrary host.
    if not api_key and base_url == saved.base_url:
        api_key = saved.api_key
    if not base_url or not api_key:
        raise HTTPException(status_code=400, detail="Enter a base URL and API key first.")
    try:
        return {"models": agent.list_models(base_url, api_key)}
    except openai.APIError as e:
        raise HTTPException(status_code=400, detail=describe_api_error(e))


def require_chat(chat_id: str):
    chat = agent.chats.get(chat_id)
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat not found")
    return chat


@app.get("/chats")
def list_chats():
    return {"chats": agent.chats.list()}


@app.post("/chats")
def new_chat(req: NewChatRequest):
    require_voice(req.voice)
    chat = agent.chats.create(req.voice)
    logger.info("new chat %s (voice=%s)", chat.id, chat.voice)
    return chat.summary()


@app.get("/chats/{chat_id}")
def get_chat(chat_id: str):
    chat = require_chat(chat_id)
    messages = []
    for m in chat.messages:
        if m["role"] == "user":
            messages.append({"role": "user", "text": m["content"]})
        else:
            html = agent.render_html(m["content"], chat.voice, chat.id, synthesize=False)
            messages.append({"role": "assistant", "html": html})
    return {**chat.summary(), "messages": messages}


@app.patch("/chats/{chat_id}")
def rename_chat(chat_id: str, req: RenameChatRequest):
    chat = require_chat(chat_id)
    agent.chats.rename(chat, req.title.strip()[:100] or None)
    return chat.summary()


@app.delete("/chats/{chat_id}", status_code=204)
def delete_chat(chat_id: str):
    chat = require_chat(chat_id)
    agent.chats.delete(chat)
    agent.clips.delete_chat(chat.id)


@app.post("/chats/{chat_id}/messages")
def send_message(chat_id: str, req: MessageRequest):
    chat = require_chat(chat_id)
    if not agent.settings.current.configured:
        raise HTTPException(
            status_code=409,
            detail="Connect a model first in Settings > Connections.",
        )

    def event_stream():
        for event in agent.chat_stream(chat, req.message):
            if event["type"] == "html":
                logger.info("[%s] rendered: %s", chat_id, event["html"])
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/clips")
def create_clip(req: ClipRequest):
    chat = require_chat(req.chat_id)
    require_voice(req.voice)
    if not CYRILLIC_RUN.fullmatch(req.text):
        raise HTTPException(status_code=400, detail="Text must be Cyrillic")
    clip_id = agent.clips.create(chat.id, req.text, req.voice, slow=req.slow)
    logger.info("clip %r (voice=%s, slow=%s) -> %s", req.text, req.voice, req.slow, clip_id)
    return {"clip_id": clip_id}


@app.get("/audio/{clip_id}")
def audio(clip_id: str):
    path = agent.clips.get_path(clip_id)
    if path is None:
        logger.warning("audio: unknown clip_id %r", clip_id)
        raise HTTPException(status_code=404, detail="Clip not found")
    return FileResponse(path, media_type="audio/wav")
