"""
tools/send.py

Delivers a generated report: opens it locally and/or emails it via
Gmail SMTP using an app password from .env.
"""

import os
import smtplib
import webbrowser
from email.message import EmailMessage
from datetime import datetime, timezone
from pathlib import Path


def _send_interface(report_path: str) -> None:
    print(f"[report] {report_path}")
    webbrowser.open(Path(report_path).resolve().as_uri())


def _send_email(report_path: str, subject: str | None, recipient: str | None) -> None:
    gmail_user = os.environ["GMAIL_USER"]
    gmail_password = os.environ["GMAIL_APP_PASSWORD"]
    to_addr = recipient or os.environ.get("REPORT_RECIPIENT", gmail_user)

    msg = EmailMessage()
    msg["Subject"] = subject or f"Tech News Report — {datetime.now().strftime('%Y-%m-%d')}"
    msg["From"] = gmail_user
    msg["To"] = to_addr

    path = Path(report_path)
    body = path.read_text(encoding="utf-8")
    if path.suffix == ".html":
        msg.set_content("This report requires an HTML-capable email client.")
        msg.add_alternative(body, subtype="html")
    else:
        msg.set_content(body)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_user, gmail_password)
        server.send_message(msg)


def send(
    target: str,
    report_path: str,
    subject: str | None = None,
    recipient: str | None = None,
) -> dict:
    try:
        if target in ("interface", "both"):
            _send_interface(report_path)
        if target in ("email", "both"):
            _send_email(report_path, subject, recipient)
        return {
            "success": True,
            "target": target,
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "error": None,
        }
    except Exception as e:
        return {
            "success": False,
            "target": target,
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "error": str(e),
        }
