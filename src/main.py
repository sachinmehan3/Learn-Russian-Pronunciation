from tts import RussianTTS

SPEAKERS = ["aidar", "baya", "kseniya", "xenia", "eugene", "random"]


def main() -> None:
    print("Loading Silero Russian TTS model (first run downloads it)...")
    tts = RussianTTS()
    print("Model loaded. Type Russian text to synthesize, or 'quit' to exit.\n")

    counter = 0
    while True:
        text = input("Russian text> ").strip()
        if text.lower() in {"quit", "exit"}:
            break
        if not text:
            continue

        counter += 1
        output_path = f"audio_output/phrase_{counter}.wav"
        path = tts.synthesize(text, speaker="xenia", output_path=output_path)
        print(f"Saved: {path}\n")


if __name__ == "__main__":
    main()
