"""
tools/list_reports.py

Reads report history live from the reports table. This is the
always-fresh alternative to pipeline_session.md's single "latest report" line,
which is baked into the system prompt once at process startup and goes
stale the moment a new pipeline run happens without a restart — and
only ever covers the most recent report, never history.
"""

from tools import db


def list_reports(limit: int = 10, report_type: str | None = None) -> list[dict]:
    db.init_db()
    conn = db.get_connection()
    try:
        conditions = []
        params: list = []
        if report_type:
            conditions.append("report_type = ?")
            params.append(report_type)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        rows = conn.execute(
            f"""
            SELECT report_type, date, path, created_at
            FROM reports
            {where}
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (*params, limit),
        ).fetchall()
        return [
            {
                "report_type": row["report_type"],
                "date": row["date"],
                "path": row["path"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]
    finally:
        conn.close()
