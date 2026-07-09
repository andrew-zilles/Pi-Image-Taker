from __future__ import annotations

import mimetypes
import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import Optional


def send_call_recording(
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    recipient: str,
    number_dialed: str,
    recording_path: Optional[Path],
    transcript_path: Optional[Path],
) -> None:
    msg = EmailMessage()
    msg["Subject"] = f"Phone booth call recording - {number_dialed}"
    msg["From"] = smtp_user
    msg["To"] = recipient

    transcript_text = ""
    if transcript_path and transcript_path.exists():
        transcript_text = transcript_path.read_text()

    msg.set_content(
        f"Call to {number_dialed} has ended. Recording and transcript are attached.\n\n"
        f"--- Transcript ---\n{transcript_text or '(no speech detected)'}\n"
    )

    for path in (recording_path, transcript_path):
        if path is None or not path.exists():
            continue
        mime_type, _ = mimetypes.guess_type(path.name)
        maintype, subtype = (mime_type or "application/octet-stream").split("/", 1)
        msg.add_attachment(path.read_bytes(), maintype=maintype, subtype=subtype, filename=path.name)

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(msg)
