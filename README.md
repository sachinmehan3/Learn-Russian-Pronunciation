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

This starts a chat with the teacher agent. The agent decides on its own when to
speak Russian out loud — it has a `speak_russian` tool backed by the Silero TTS
wrapper, and calls it whenever it wants you to hear pronunciation. Audio plays
automatically through your speakers (via the stdlib `winsound` module, Windows-only).

The first run downloads the Silero `v5_5_ru` model via `torch.hub` and caches it
locally. `v5_5_ru` is used over the older `v4_ru` because it adds auto-stress,
homograph resolution, and question-intonation support (questions carry distinct
intonation in Russian, which matters for pronunciation practice).

The agent has no system prompt or fixed curriculum by design — it's a general
helpful chat agent that happens to have Russian TTS available as a tool. It also
has no persistence: each run starts a fresh conversation.

## Project structure

```
src/
  tts.py     - Silero TTS wrapper (model loading + synthesis, plain and SSML)
  agent.py   - TeacherAgent: OpenAI-compatible chat client + speak_russian tool
  main.py    - CLI entry point (chat loop)
```

## Available speakers

`v5_5_ru` ships with these voices: `aidar`, `baya`, `kseniya`, `xenia`, `eugene`.
Default is `xenia`.
