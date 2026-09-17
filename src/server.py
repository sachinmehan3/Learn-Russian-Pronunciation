import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agent import ChatReply, TeacherAgent

logger = logging.getLogger("uvicorn.error")

STATIC_DIR = Path(__file__).parent / "static"

agent = TeacherAgent()


@asynccontextmanager
async def lifespan(app: FastAPI):
    agent.clips.clear()
    yield


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class ChatRequest(BaseModel):
    message: str


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/chat", response_model=ChatReply)
def chat(req: ChatRequest):
    reply = agent.chat(req.message)
    word_clip_ids = [s.clip_id for s in reply.segments if s.type == "word"]
    logger.info(
        "chat: %r -> %d segment(s), clip_ids referenced: %s known clip_ids: %s",
        req.message,
        len(reply.segments),
        word_clip_ids,
        list(agent.clips.clips.keys()),
    )
    return reply


@app.get("/audio/{clip_id}")
def audio(clip_id: str):
    path = agent.clips.get_path(clip_id)
    if path is None:
        logger.warning("audio: unknown clip_id %r (known: %s)", clip_id, list(agent.clips.clips.keys()))
        raise HTTPException(status_code=404, detail="Clip not found")
    logger.info("audio: serving clip_id %r from %s", clip_id, path)
    return FileResponse(path, media_type="audio/wav")
