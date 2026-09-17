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
```

Then start the app and set up the model connection in the UI
(*Settings > Connections*) — there's nothing to configure on disk first.

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
- **Sidebar (left, collapsible)** — *New chat*, your saved chats (named by date
  until you rename them; use the ⋯ menu to rename or delete), and
  *Settings → Preferences*.
- **Settings → Connections** is where the model lives: base URL, API key, and model
  (the list is fetched from the server; you can also type a name). Below that are
  temperature, top-p, max output tokens, reasoning effort and the system prompt —
  leave a number empty to use the model's own default. Saved settings apply from
  your next message.
- **Settings → Preferences → Voice** sets the default voice for *new* chats. The
  current chat keeps the voice it started with. This one preference is saved in the
  browser's localStorage.

Chats are saved to `chats/<id>.jsonl`: a meta line (title, voice, created date)
followed by one line per message. A chat is only written once its first message
is sent. Audio isn't saved between runs — each chat's clips live in
`audio_output/<chat-id>/`, the whole folder is wiped on startup, and words in
reopened chats are synthesized the first time they're clicked. Deleting a chat
deletes its audio with it.

### Stress marks

The teacher marks stress with a combining acute accent (приве́т). The word regex
keeps those marks inside the word, and `tts.py` converts them to Silero's own
notation (прив+ет) before synthesis — Silero silently ignores the accent
character otherwise, so the marked stress is what you actually hear.

The first run downloads the Silero `v5_5_ru` model via `torch.hub` and caches it
locally. `v5_5_ru` is used over the older `v4_ru` because it adds auto-stress,
homograph resolution, and question-intonation support (questions carry distinct
intonation in Russian, which matters for pronunciation practice).

## Project structure

```
src/
  tts.py            - Silero TTS wrapper (normal or slow synthesis, any speaker,
                      stress-mark conversion)
  store.py          - ChatStore: chats persisted as JSONL files
  settings.py       - SettingsStore: connection + model settings in settings.json
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
| GET  | `/settings` | Current settings (API key masked to a hint) |
| PATCH | `/settings` | Update any subset of settings |
| POST | `/settings/models` `{base_url, api_key}` | List the models a provider offers |
| GET  | `/chats` | Saved chats, most recently active first |
| POST | `/chats` `{voice}` | Start a chat with a fixed voice |
| GET  | `/chats/{id}` | A chat with its rendered messages |
| PATCH | `/chats/{id}` `{title}` | Rename (blank title reverts to the date) |
| DELETE | `/chats/{id}` | Delete a chat |
| POST | `/chats/{id}/messages` `{message}` | Stream a reply (SSE: `delta`, `text_done`, `html`) |
| POST | `/clips` `{text, voice, slow}` | Get or create a clip variant (Cyrillic text only) |
| GET  | `/audio/{clip_id}` | The clip's wav |

## Available speakers

`v5_5_ru` ships with these voices: `aidar`, `baya`, `kseniya`, `xenia`, `eugene`.
Default is `xenia`.

## Settings and your API key

Settings are stored in `settings.json` at the project root (gitignored), written by
the app — not by you. The API key is never sent back to the browser: `GET /settings`
returns only a hint like `…a1b2`, and saving without touching the key field keeps the
stored one.

`POST /settings/models` will only use the saved key for the saved base URL. Listing
models for a different URL requires a key in the request, so a request can't redirect
your saved key to another host.

Model parameters are only sent when set. An empty temperature, top-p or max-tokens
field means the parameter is left out of the request entirely, which matters because
reasoning models reject some of them.
