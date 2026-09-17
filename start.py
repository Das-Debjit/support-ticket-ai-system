"""Starts the FastAPI backend and the Streamlit UI together."""

import subprocess
import sys
import time
import webbrowser

from dotenv import load_dotenv

load_dotenv()

API_HOST = "127.0.0.1"
API_PORT = "8000"
UI_PORT = "8501"


def main():
    print("Starting Support Ticket AI System...")
    print(f"  API -> http://{API_HOST}:{API_PORT}/docs")
    print(f"  UI  -> http://{API_HOST}:{UI_PORT}")
    print("Press Ctrl+C to stop both.\n")

    api_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.api:app", "--host", API_HOST, "--port", API_PORT]
    )

    time.sleep(2)

    ui_process = subprocess.Popen(
        [
            sys.executable, "-m", "streamlit", "run", "ui/streamlit_app.py",
            "--server.port", UI_PORT,
            "--server.headless", "true",
        ]
    )

    try:
        webbrowser.open(f"http://{API_HOST}:{UI_PORT}")
    except Exception:
        pass

    try:
        api_process.wait()
        ui_process.wait()
    except KeyboardInterrupt:
        print("\nStopping...")
        api_process.terminate()
        ui_process.terminate()


if __name__ == "__main__":
    main()