import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agent import CYRILLIC_RUN, TeacherAgent

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


class MessageRequest(BaseModel):
    message: str


class ClipRequest(BaseModel):
    text: str
    voice: str
    slow: bool = False


def require_voice(voice: str) -> None:
    if voice not in agent.voices:
        raise HTTPException(status_code=400, detail=f"Unknown voice {voice!r}")


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/voices")
def voices():
    return {"voices": agent.voices, "default": agent.default_voice}


@app.post("/chats")
def new_chat(req: NewChatRequest):
    require_voice(req.voice)
    return {"chat_id": agent.new_chat(req.voice), "voice": req.voice}


@app.post("/chats/{chat_id}/messages")
def send_message(chat_id: str, req: MessageRequest):
    if chat_id not in agent.chats:
        raise HTTPException(status_code=404, detail="Chat not found")

    def event_stream():
        for event in agent.chat_stream(chat_id, req.message):
            if event["type"] == "html":
                logger.info("[%s] rendered: %s", chat_id, event["html"])
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/clips")
def create_clip(req: ClipRequest):
    require_voice(req.voice)
    if not CYRILLIC_RUN.fullmatch(req.text):
        raise HTTPException(status_code=400, detail="Text must be Cyrillic")
    clip_id = agent.clips.create(req.text, req.voice, slow=req.slow)
    logger.info("clip %r (voice=%s, slow=%s) -> %s", req.text, req.voice, req.slow, clip_id)
    return {"clip_id": clip_id}


@app.get("/audio/{clip_id}")
def audio(clip_id: str):
    path = agent.clips.get_path(clip_id)
    if path is None:
        logger.warning("audio: unknown clip_id %r", clip_id)
        raise HTTPException(status_code=404, detail="Clip not found")
    return FileResponse(path, media_type="audio/wav")
