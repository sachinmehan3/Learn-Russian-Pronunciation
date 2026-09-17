import threading
import webbrowser

import uvicorn

URL = "http://127.0.0.1:8000"


def main() -> None:
    print(f"Starting Russian Pronunciation Tutor at {URL}")
    threading.Timer(1.0, lambda: webbrowser.open(URL)).start()
    uvicorn.run("server:app", host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
