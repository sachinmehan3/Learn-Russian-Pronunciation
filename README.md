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
Chat with the teacher agent there. The agent is a plain chatbot with a system prompt
telling it to teach Russian to an English speaker, writing new words/phrases in
Cyrillic with a transliteration alongside (e.g. "привет (privet)"). It has **no
tools** — it just replies with normal text.

The backend then does all the audio-linking work itself: once the reply finishes
streaming, it converts the Markdown to HTML and wraps every run of Cyrillic text in
a clickable button with its own synthesized clip. The model never has to know
clip_ids exist, so it can't get them wrong.

### In the UI

- **Click a Russian word** to open the pronunciation panel on the right. It plays
  the word, and lets you:
  - **Slower** — re-synthesizes the word with SSML `<prosody rate="x-slow">`.
  - **Voice** — re-synthesizes it in another voice.

  Every variant is cached by (text, voice, speed), so replaying is instant.
- **Sidebar (left, collapsible)** — *New chat*, plus *Settings → Preferences*.
- **Preferences → Voice** sets the default voice for *new* chats. The current chat
  keeps the voice it started with. The preference is saved in the browser's
  localStorage.

Chats and clips live in memory for the life of the server process; there's no chat
history across restarts, and `audio_output/` is wiped on startup.

The first run downloads the Silero `v5_5_ru` model via `torch.hub` and caches it
locally. `v5_5_ru` is used over the older `v4_ru` because it adds auto-stress,
homograph resolution, and question-intonation support (questions carry distinct
intonation in Russian, which matters for pronunciation practice).

## Project structure

```
src/
  tts.py            - Silero TTS wrapper (normal or slow synthesis, any speaker)
  clips.py          - ClipStore: cached clips keyed by (text, voice, slow)
  agent.py          - TeacherAgent: per-chat history + voice, streaming replies,
                      Markdown -> HTML with clickable Cyrillic words
  server.py         - FastAPI app (see API below)
  static/index.html - Chat UI: sidebar, chat, pronunciation panel, preferences
  main.py           - Entry point: launches the server and opens the browser
```

### API

| Method | Path | Purpose |
|---|---|---|
| GET  | `/voices` | Available voices and the server default |
| POST | `/chats` `{voice}` | Start a chat with a fixed voice |
| POST | `/chats/{id}/messages` `{message}` | Stream a reply (SSE: `delta`, `text_done`, `html`) |
| POST | `/clips` `{text, voice, slow}` | Get or create a clip variant (Cyrillic text only) |
| GET  | `/audio/{clip_id}` | The clip's wav |

## Available speakers

`v5_5_ru` ships with these voices: `aidar`, `baya`, `kseniya`, `xenia`, `eugene`.
Default is `xenia`.
