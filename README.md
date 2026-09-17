# Russian Pronunciation Tutor

A local, offline text-to-speech tool for practicing Russian pronunciation, built on
[Silero TTS](https://github.com/snakers4/silero-models). Silero was chosen because it
handles Russian stress placement and homograph resolution automatically (e.g. замо́к vs
за́мок), which matters a lot for pronunciation practice and which generic multilingual
TTS models tend to get wrong. It also runs entirely on CPU, so it doesn't compete with
a GPU-hungry LLM or Whisper for VRAM.

## Setup

```bash
python -m venv venv

# Windows (PowerShell)
venv\Scripts\Activate.ps1
# Windows (Git Bash)
source venv/Scripts/activate

pip install -r requirements.txt

cp .env.example .env
# then edit .env with your OPENAI_API_KEY (and OPENAI_BASE_URL/OPENAI_MODEL if
# you're using a non-OpenAI, OpenAI-compatible provider)
```

## Usage

```bash
python src/main.py
```

This starts a local web server and opens `http://127.0.0.1:8000` in your browser.
Chat with the teacher agent there. Whenever it introduces a Russian word or phrase,
that word appears as a clickable button in the reply — click it to hear it spoken,
as many times as you want. Each word gets its own independent audio clip, so
multiple pronunciations in the same reply (e.g. an informal and a formal greeting)
don't overwrite each other.

Clips stay clickable for the whole session (they live in the `TeacherAgent`'s
in-memory `ClipStore`, backed by `audio_output/*.wav`). They're wiped at the start
of the next run, not persisted across restarts.

The first run downloads the Silero `v5_5_ru` model via `torch.hub` and caches it
locally. `v5_5_ru` is used over the older `v4_ru` because it adds auto-stress,
homograph resolution, and question-intonation support (questions carry distinct
intonation in Russian, which matters for pronunciation practice).

The agent has no system prompt or fixed curriculum by design — it's a general
helpful chat agent that happens to have a `create_pronunciation_clip` tool available.
It also has no cross-run persistence: each run starts a fresh conversation.

## Project structure

```
src/
  tts.py           - Silero TTS wrapper (model loading + synthesis, plain and SSML)
  clips.py         - ClipStore: synthesizes and registers clips by id, for later playback
  agent.py         - TeacherAgent: OpenAI-compatible chat client, structured (ChatReply)
                     replies so words can be tied to specific audio clips
  server.py        - FastAPI app: POST /chat, GET /audio/{clip_id}, serves static/
  static/index.html - Chat UI: renders text/word segments, word segments are
                     clickable buttons that play their clip
  main.py          - Entry point: launches the server and opens the browser
```

## Available speakers

`v5_5_ru` ships with these voices: `aidar`, `baya`, `kseniya`, `xenia`, `eugene`.
Default is `xenia`.
