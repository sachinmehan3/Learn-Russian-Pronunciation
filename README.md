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

The backend then does all the audio-linking work itself: it scans the reply for
Cyrillic runs with a regex, synthesizes each one via Silero, and splits the reply
into a sequence of segments — plain text and "word" segments (the exact Cyrillic
substring plus a `clip_id`). The model never has to know clip_ids exist at all,
which is what makes this reliable: earlier designs asked the model to reference a
clip_id it got from a tool call, and it would sometimes invent a plausible-looking
one instead of using the real one. Now there's nothing for it to get wrong — the
matching is done entirely on our side, deterministically, after the fact.

The frontend renders each "word" segment as a clickable button inline, exactly
where it occurs in the sentence — click it to hear that exact clip, as many times
as you want.

Clips stay clickable for the whole session (they live in the `TeacherAgent`'s
in-memory `ClipStore`, backed by `audio_output/*.wav`). They're wiped at the start
of the next run, not persisted across restarts.

The first run downloads the Silero `v5_5_ru` model via `torch.hub` and caches it
locally. `v5_5_ru` is used over the older `v4_ru` because it adds auto-stress,
homograph resolution, and question-intonation support (questions carry distinct
intonation in Russian, which matters for pronunciation practice).

## Project structure

```
src/
  tts.py           - Silero TTS wrapper (model loading + plain-text synthesis)
  clips.py         - ClipStore: synthesizes and registers clips by id, for later playback
  agent.py         - TeacherAgent: system-prompted OpenAI-compatible chat client (no
                     tools); regex-detects Cyrillic runs in the reply and splits it
                     into text/word segments, synthesizing a clip for each word
  server.py        - FastAPI app: POST /chat, GET /audio/{clip_id}, serves static/
  static/index.html - Chat UI: renders text/word segments inline, word segments are
                     clickable buttons that play their clip
  main.py          - Entry point: launches the server and opens the browser
```

## Available speakers

`v5_5_ru` ships with these voices: `aidar`, `baya`, `kseniya`, `xenia`, `eugene`.
Default is `xenia`.
