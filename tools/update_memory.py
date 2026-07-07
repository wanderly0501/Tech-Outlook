"""
tools/update_memory.py

Writes to memory/*.md. Each agent declares which files it's allowed
to touch in its own tool schema (an enum restriction Claude sees), but
that only stops a well-behaved Claude from *asking* for the wrong
file — it doesn't stop a bug in the dispatcher. `caller` is the
defense-in-depth check: each agent's dispatch() fixes `caller` in code
before invoking this function, so a permission violation fails here
even if the schema enum were ever loosened or bypassed.
"""

from datetime import datetime, timezone

from tools.config import MEMORY_DIR, MEMORY_FILES, MEMORY_WRITE_PERMISSIONS


def update_memory(file: str, content: str, mode: str = "overwrite", caller: str | None = None) -> dict:
    if file not in MEMORY_FILES:
        raise ValueError(f"Unknown memory file '{file}'. Valid: {sorted(MEMORY_FILES)}")

    if caller is not None and file not in MEMORY_WRITE_PERMISSIONS.get(caller, set()):
        raise PermissionError(f"'{caller}' agent is not permitted to write memory/{file}.md")

    if mode not in ("overwrite", "append"):
        raise ValueError("mode must be 'overwrite' or 'append'")

    path = MEMORY_DIR / f"{file}.md"
    file_mode = "a" if mode == "append" else "w"
    needs_separator = mode == "append" and path.exists() and path.stat().st_size > 0

    with open(path, file_mode, encoding="utf-8") as f:
        if needs_separator:
            f.write("\n\n")
        f.write(content.strip())
        f.write("\n")

    return {
        "success": True,
        "file": file,
        "written_at": datetime.now(timezone.utc).isoformat(),
    }
