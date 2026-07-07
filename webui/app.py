"""
webui/app.py

Minimal local web UI for the chat agent. This wraps chat_agent.py's
existing building blocks (TOOLS, dispatch, system prompt, save_conversation)
in a small Flask app — chat_agent.py itself is untouched and still works
standalone as a terminal REPL.

Run:
    python webui/app.py
Then open http://127.0.0.1:5000
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flask import Flask, request, jsonify, render_template, send_from_directory

import chat_agent
from core.agent_loop import run_agent_loop, build_system_prompt
from tools.config import REPORTS_DIR, MEMORY_DIR, MEMORY_FILES, PROJECT_ROOT

LOGO_DIR = PROJECT_ROOT / "logo"

app = Flask(__name__)

_system_prompt = build_system_prompt(chat_agent.BASE_SYSTEM_PROMPT, chat_agent.MEMORY_PATHS)

# Single shared conversation, same one-session-at-a-time model as the
# terminal REPL in chat_agent.py — just fronted by a browser tab instead
# of stdin/stdout.
_state = {"messages": [], "started_at": None}


def _reset_session():
    _state["messages"] = []
    _state["started_at"] = datetime.now(timezone.utc).isoformat()


_reset_session()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/logo.png")
def logo():
    return send_from_directory(LOGO_DIR, "logo.png")


@app.route("/logo/<path:filename>")
def logo_asset(filename):
    # Generated reports (tools/write_report.py) reference the logo via a
    # relative "../logo/logo.png" path so it resolves correctly when a
    # report is opened directly via file://. Served through here at
    # /reports/<file>.html, that same relative path resolves to
    # /logo/logo.png — this route mirrors the on-disk layout so it
    # resolves correctly in both cases.
    return send_from_directory(LOGO_DIR, filename)


@app.route("/api/memory/<name>")
def get_memory(name):
    if name not in MEMORY_FILES:
        return jsonify({"error": f"unknown memory file '{name}'"}), 404
    path = MEMORY_DIR / f"{name}.md"
    content = path.read_text(encoding="utf-8") if path.exists() else ""
    return jsonify({"file": name, "content": content})


@app.route("/api/reports")
def list_reports():
    reports = sorted(
        (p.name for p in REPORTS_DIR.glob("*") if p.suffix in (".html", ".md")),
        reverse=True,
    )
    return jsonify({"reports": reports})


@app.route("/reports/<path:filename>")
def serve_report(filename):
    return send_from_directory(REPORTS_DIR, filename)


@app.route("/api/chat", methods=["POST"])
def chat():
    user_input = (request.json or {}).get("message", "").strip()
    if not user_input:
        return jsonify({"error": "empty message"}), 400

    _state["messages"].append({"role": "user", "content": user_input})

    try:
        reply = run_agent_loop(
            messages=_state["messages"],
            system_prompt=_system_prompt,
            tools=chat_agent.TOOLS,
            dispatch=chat_agent.dispatch,
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"reply": reply})


@app.route("/api/end_session", methods=["POST"])
def end_session():
    if _state["messages"]:
        chat_agent.close_session(_state["messages"], _system_prompt)
        chat_agent.save_conversation(_state["messages"], _state["started_at"])
    _reset_session()
    return jsonify({"success": True})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
