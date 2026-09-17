# Russian Pronunciation Tutor

A local, offline tool for practicing Russian pronunciation with an AI teacher.

Click any Russian word in the conversation to hear native pronunciation, play it slower, or practice speaking it with instant feedback. Runs entirely on CPU with zero external audio binaries.

## Models Used

- **Text-to-Speech (TTS):** [Silero TTS](https://github.com/snakers4/silero-models) (`v5_5_ru`)  
  Runs locally on CPU. Handles Russian stress accents, homograph resolution (e.g. *замо́к* vs *за́мок*), and question intonation.
- **Speech Recognition (STT):** [GigaAM](https://github.com/salute-developers/GigaAM) (`v2_ctc` by SberDevices)  
  Runs locally on CPU. Trained on 700,000+ hours of Russian for voice input and pronunciation scoring with auto-silence detection.
- **Teacher LLM:** Connects to any OpenAI-compatible API (OpenAI, OpenRouter, Bedrock, Groq, Ollama, LM Studio) configured in the UI.

## Quickstart

```bash
# 1. Setup virtual environment
python -m venv venv
venv\Scripts\Activate.ps1    # Windows PowerShell (or source venv/Scripts/activate)

# 2. Install dependencies
pip install -r requirements.txt
pip install --no-deps gigaam
pip install tqdm hydra-core sentencepiece

# 3. Start application
python src/main.py
```

Open `http://127.0.0.1:8000`, configure your model connection under **Settings > Connections**, and start learning.

## Features

- **Click-to-Pronounce:** Click any Cyrillic word to hear it spoken, slow down playback, or change voices.
- **Speech Practice:** Practice pronouncing individual words or speaking full phrases with automatic silence detection (VAD).
- **Streaming Reasoning:** Live streaming of the model's thinking process.
- **Themes:** Choose between Default, Light, and Dark themes in Preferences.
