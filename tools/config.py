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

# Cap on rows in the articles table. Enforced in tools/db.py by deleting
# the oldest rows (by crawled_at) once this is exceeded, so the KB can't
# grow unbounded from years of daily crawls.
MAX_ARTICLES = 20000

MEMORY_DIR.mkdir(parents=True, exist_ok=True)
KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

MEMORY_FILES = {"pipeline_session", "top_of_mind", "preferences", "chat_session"}

# Which agent is allowed to write which memory files. Enforced in
# tools/update_memory.py in addition to the tool-schema enum restriction
# each agent declares, per REQUIREMENTS.md.
MEMORY_WRITE_PERMISSIONS = {
    "pipeline": {"pipeline_session", "top_of_mind"},
    "chat": {"preferences", "chat_session"},
}
