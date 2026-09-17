import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agent import TeacherAgent

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


@app.post("/chat")
def chat(req: ChatRequest):
    def event_stream():
        for event in agent.chat_stream(req.message):
            if event["type"] == "segments":
                word_segments = [s for s in event["segments"] if s["type"] == "word"]
                logger.info(
                    "chat: %r -> %d segment(s), %d clip(s): %s",
                    req.message,
                    len(event["segments"]),
                    len(word_segments),
                    word_segments,
                )
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/audio/{clip_id}")
def audio(clip_id: str):
    path = agent.clips.get_path(clip_id)
    if path is None:
        logger.warning("audio: unknown clip_id %r (known: %s)", clip_id, list(agent.clips.clips.keys()))
        raise HTTPException(status_code=404, detail="Clip not found")
    logger.info("audio: serving clip_id %r from %s", clip_id, path)
    return FileResponse(path, media_type="audio/wav")
