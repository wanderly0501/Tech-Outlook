"""
tools/write_report.py

Renders the pipeline agent's report content (markdown body + chart
specs) to HTML (inline Chart.js) or Markdown (text tables in place of
charts), and records it in the reports table.
"""

import json
import html as html_lib
from datetime import datetime, timezone

from tools import db
from tools.config import REPORTS_DIR

try:
    import markdown as _markdown_lib
except ImportError:
    _markdown_lib = None


def _markdown_to_html(content: str) -> str:
    if _markdown_lib:
        return _markdown_lib.markdown(content, extensions=["tables"])
    # Minimal fallback if the `markdown` package isn't installed: escape
    # and preserve paragraph breaks rather than failing the report.
    escaped = html_lib.escape(content)
    return "".join(f"<p>{line}</p>" for line in escaped.split("\n\n") if line.strip())


def _chart_html(chart: dict, index: int) -> str:
    canvas_id = f"chart-{index}"
    chart_type = "bar" if chart.get("type") == "timeline" else chart.get("type", "pie")
    data = chart.get("data", {})
    labels = json.dumps(list(data.keys()))
    values = json.dumps(list(data.values()))
    title = html_lib.escape(chart.get("title", ""))
    return f"""
    <div class="chart-block">
      <h3>{title}</h3>
      <canvas id="{canvas_id}"></canvas>
    </div>
    <script>
      new Chart(document.getElementById("{canvas_id}"), {{
        type: "{chart_type}",
        data: {{
          labels: {labels},
          datasets: [{{ label: {json.dumps(title)}, data: {values},
            backgroundColor: ["#6366f1","#22c55e","#f59e0b","#ef4444","#06b6d4","#a855f7","#64748b"] }}]
        }}
      }});
    </script>
    """


def _render_html(content: str, report_type: str, date: str, charts: list[dict]) -> str:
    charts_html = "\n".join(_chart_html(c, i) for i, c in enumerate(charts or []))
    body_html = _markdown_to_html(content)
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>{report_type.title()} Report — {date}</title>
  <link rel="icon" type="image/png" href="../logo/logo.png">
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    body {{ font-family: -apple-system, Segoe UI, sans-serif; max-width: 860px; margin: 2rem auto; padding: 0 1rem; color: #1a1a1a; }}
    .chart-block {{ max-width: 480px; margin: 1.5rem 0; }}
    .title-row {{ display: flex; align-items: center; gap: 0.6rem; }}
    .title-row img {{ width: 32px; height: 32px; object-fit: contain; }}
    h1 {{ margin-bottom: 0.25rem; }}
    .meta {{ color: #666; margin-bottom: 1.5rem; }}
  </style>
</head>
<body>
  <div class="title-row">
    <img src="../logo/logo.png" alt="">
    <h1>{report_type.title()} Report</h1>
  </div>
  <div class="meta">{date}</div>
  {charts_html}
  {body_html}
</body>
</html>
"""


def _render_markdown(content: str, report_type: str, date: str, charts: list[dict]) -> str:
    lines = [f"# {report_type.title()} Report — {date}", ""]
    for chart in charts or []:
        lines.append(f"## {chart.get('title', 'Chart')}")
        lines.append("")
        lines.append("| Label | Value |")
        lines.append("|---|---|")
        for label, value in chart.get("data", {}).items():
            lines.append(f"| {label} | {value} |")
        lines.append("")
    lines.append(content)
    return "\n".join(lines)


def write_report(
    content: str,
    format: str = "html",
    report_type: str = "daily",
    date: str | None = None,
    charts: list[dict] | None = None,
) -> dict:
    date = date or datetime.now().strftime("%Y-%m-%d")
    ext = "html" if format == "html" else "md"
    path = REPORTS_DIR / f"{date}-{report_type}.{ext}"

    rendered = (
        _render_html(content, report_type, date, charts)
        if format == "html"
        else _render_markdown(content, report_type, date, charts)
    )
    path.write_text(rendered, encoding="utf-8")

    db.init_db()
    db.insert_report(report_type=report_type, date=date, path=str(path))

    return {
        "success": True,
        "path": str(path),
        "written_at": datetime.now(timezone.utc).isoformat(),
    }
