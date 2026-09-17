from agent import TeacherAgent


def main() -> None:
    print("Loading Russian teacher agent...")
    agent = TeacherAgent()
    print("Ready. Chat away, or type 'quit' to exit.\n")

    while True:
        text = input("You> ").strip()
        if text.lower() in {"quit", "exit"}:
            break
        if not text:
            continue

        reply = agent.chat(text)
        print(f"Teacher> {reply}\n")


if __name__ == "__main__":
    main()
