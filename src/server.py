from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agent import ChatReply, TeacherAgent

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
    return agent.chat(req.message)


@app.get("/audio/{clip_id}")
def audio(clip_id: str):
    path = agent.clips.get_path(clip_id)
    if path is None:
        raise HTTPException(status_code=404, detail="Clip not found")
    return FileResponse(path, media_type="audio/wav")
