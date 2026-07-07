# Desktop App

A native desktop shell for Tech Lookout — a system-tray app instead
of a terminal or browser tab. Built by importing the existing `webui/app.py`
Flask instance and `pipeline_agent.run_pipeline` as-is; nothing in the rest
of the project was changed to add this.

## Run

From the project root:

```bash
pip install -r requirements.txt         # if not already installed
pip install -r desktop/requirements.txt # adds pywebview, pystray, pillow
python desktop/app.py
```

A native window opens with the same chat UI as `webui/`, and a tray icon
appears in the system tray.

## What it does

- **Chat window** — the existing Flask chat app (`webui/app.py`), rendered
  in a native `pywebview` window instead of a browser tab.
- **Background scheduler** — runs the daily pipeline for *yesterday's* date
  at 00:01, same trigger logic as `scheduler.py`, but embedded in this
  process — no separate `python scheduler.py` needed alongside it.
- **Tray menu**:
  - *Open Chat* — shows the window again if it's hidden (also the default
    double-click action)
  - *Run Pipeline Now* — triggers an off-schedule pipeline run for
    yesterday's date, in the background
  - *Quit* — actually exits the app (window + tray + scheduler)

## Notes

- Closing the window (the X button) hides it rather than quitting — the
  tray icon and scheduler keep running. Use "Quit" from the tray menu to
  fully exit.
- Only one pipeline run executes at a time; if you click "Run Pipeline Now"
  while the scheduled run (or another manual run) is already in progress,
  the new trigger is ignored rather than overlapping.
- Needs a real desktop/display session — this creates an actual OS window,
  it won't run headless.
- To launch without a console window on Windows, run it with `pythonw.exe`
  instead of `python.exe`.
- Requires the two `run(...)` calls behind the scenes (Flask + scheduler
  loop) to have `pipeline_agent.py` and `webui/app.py` importable, so keep
  this launched from an environment where the project's own
  `requirements.txt` is installed too.
