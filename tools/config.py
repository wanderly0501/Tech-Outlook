"""
tools/config.py

Shared paths and constants used across tools/ and the two agents.
Keeping these in one place means every module agrees on where
memory files, the DB, and reports live regardless of the working
directory the agent was launched from.
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

MEMORY_DIR = PROJECT_ROOT / "memory"
KNOWLEDGE_DIR = PROJECT_ROOT / "knowledge"
REPORTS_DIR = PROJECT_ROOT / "reports"
PROMPTS_DIR = PROJECT_ROOT / "prompts"

DB_PATH = KNOWLEDGE_DIR / "articles.db"

MEMORY_DIR.mkdir(parents=True, exist_ok=True)
KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

MEMORY_FILES = {"session", "top_of_mind", "preferences", "user_history"}

# Which agent is allowed to write which memory files. Enforced in
# tools/update_memory.py in addition to the tool-schema enum restriction
# each agent declares, per REQUIREMENTS.md.
MEMORY_WRITE_PERMISSIONS = {
    "pipeline": {"session", "top_of_mind"},
    "chat": {"preferences", "user_history"},
}
