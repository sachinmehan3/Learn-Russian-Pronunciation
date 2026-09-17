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

## Usage

```bash
python src/main.py
```

The first run downloads the Silero `v4_ru` model (~50MB) via `torch.hub` and caches it
locally. Enter Russian text at the prompt; a `.wav` file is written to `audio_output/`.

## Project structure

```
src/
  tts.py    - Silero TTS wrapper (model loading + synthesis)
  main.py   - CLI entry point
```

## Available speakers

`v4_ru` ships with these voices: `aidar`, `baya`, `kseniya`, `xenia`, `eugene`, `random`.
Default is `xenia`.
