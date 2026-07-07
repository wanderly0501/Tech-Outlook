"""
desktop/app.py

Native desktop shell for Tech Lookout. A system-tray app that:

  - hosts the existing chat web UI (webui/app.py's Flask instance) inside
    a native window via pywebview, instead of a browser tab
  - runs the daily pipeline in the background on the same 00:01 schedule
    as scheduler.py, so you don't need a separate `python scheduler.py`
    process running
  - adds a tray menu with "Open Chat" and "Run Pipeline Now"

Nothing under webui/, chat_agent.py, or pipeline_agent.py is modified —
this only imports and wires up what already exists.

Run (from the project root):
    python desktop/app.py

Closing the window hides it; the tray icon and scheduler keep running.
Use the tray menu's "Quit" to actually exit.
"""

import sys
import threading
import time
import urllib.request
from datetime import date, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import schedule
import webview
import pystray
from PIL import Image, ImageDraw

from webui.app import app as flask_app
from pipeline_agent import run_pipeline

HOST = "127.0.0.1"
PORT = 5000
URL = f"http://{HOST}:{PORT}"

_pipeline_lock = threading.Lock()
_window = None
_quitting = False


def _run_pipeline_for(target_date: str) -> None:
    if not _pipeline_lock.acquire(blocking=False):
        print("[desktop] Pipeline already running, ignoring this trigger.")
        return
    try:
        print(f"[desktop] Running pipeline for {target_date}...")
        run_pipeline(date=target_date)
        print(f"[desktop] Pipeline finished for {target_date}.")
    except Exception as e:
        print(f"[desktop] Pipeline run failed: {e}")
    finally:
        _pipeline_lock.release()


def _run_pipeline_for_yesterday() -> None:
    target_date = (date.today() - timedelta(days=1)).isoformat()
    _run_pipeline_for(target_date)


def _trigger_async(target_date_fn) -> None:
    threading.Thread(target=target_date_fn, daemon=True).start()


def _start_flask() -> None:
    flask_app.run(host=HOST, port=PORT, use_reloader=False, debug=False)


def _wait_for_server(timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(URL, timeout=1)
            return True
        except Exception:
            time.sleep(0.3)
    return False


def _start_scheduler_loop() -> None:
    schedule.every().day.at("00:01").do(lambda: _trigger_async(_run_pipeline_for_yesterday))
    while True:
        schedule.run_pending()
        time.sleep(60)


def _build_icon_image() -> Image.Image:
    size = 64
    image = Image.new("RGB", (size, size), "#6366f1")
    draw = ImageDraw.Draw(image)
    draw.rectangle((10, 14, size - 10, size - 14), fill="white")
    draw.rectangle((16, 22, size - 20, 28), fill="#6366f1")
    draw.rectangle((16, 34, size - 28, 40), fill="#6366f1")
    return image


def _open_chat(icon=None, item=None) -> None:
    if _window is not None:
        _window.show()


def _run_now(icon=None, item=None) -> None:
    _trigger_async(_run_pipeline_for_yesterday)


def _quit(icon=None, item=None) -> None:
    global _quitting
    _quitting = True
    if _window is not None:
        _window.destroy()
    icon.stop()


def _build_tray_icon() -> pystray.Icon:
    menu = pystray.Menu(
        pystray.MenuItem("Open Chat", _open_chat, default=True),
        pystray.MenuItem("Run Pipeline Now", _run_now),
        pystray.MenuItem("Quit", _quit),
    )
    return pystray.Icon("tech-lookout", _build_icon_image(), "Tech Lookout", menu)


def _on_closing() -> bool:
    """Closing the window hides it instead of destroying it — the tray
    icon and scheduler thread keep the app alive in the background."""
    if _quitting:
        return True
    _window.hide()
    return False


def main() -> None:
    global _window

    threading.Thread(target=_start_flask, daemon=True).start()
    if not _wait_for_server():
        print("[desktop] Warning: chat server didn't respond in time; opening window anyway.")

    threading.Thread(target=_start_scheduler_loop, daemon=True).start()

    icon = _build_tray_icon()
    threading.Thread(target=icon.run, daemon=True).start()

    _window = webview.create_window("Tech Lookout", URL, width=1000, height=720)
    _window.events.closing += _on_closing

    webview.start()
    icon.stop()


if __name__ == "__main__":
    main()
