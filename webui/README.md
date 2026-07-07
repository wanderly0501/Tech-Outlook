# Web UI

A small local web front-end for the chat agent — a browser tab instead of
a terminal. Built as a thin Flask wrapper around `chat_agent.py`'s existing
`TOOLS`, `dispatch`, system prompt, and `save_conversation`; nothing in the
rest of the project was changed to add this.

## Run

From the project root:

```bash
pip install -r requirements.txt        # if not already installed
pip install -r webui/requirements.txt  # adds Flask
python webui/app.py
```

Then open http://127.0.0.1:5000

## What it does

- Chat pane talks to the same agent loop and tools as `python chat_agent.py`
  (one shared conversation at a time, matching the terminal REPL's model).
- Sidebar shows `top_of_mind.md`, the last pipeline run summary
  (`pipeline_session.md`), and links to generated reports in `reports/`.
- "End session & save" writes the conversation to the `conversations` table
  (same as quitting the terminal REPL) and starts a fresh conversation.

## Notes

- Single shared session, single process — this is a personal local tool, not
  multi-user. Two browser tabs share the same conversation state.
- No streaming yet: the agent loop runs to completion before the reply
  appears (a "Thinking…" bubble shows in the meantime).
