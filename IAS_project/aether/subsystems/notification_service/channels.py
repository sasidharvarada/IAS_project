"""
channels.py

Notification channels implementation.
"""

from __future__ import annotations

import os
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None


@dataclass
class SMTPSettings:
    host: str
    port: int
    username: str
    password: str
    from_email: str
    use_tls: bool = True

    @classmethod
    def from_env(cls) -> "SMTPSettings":
        if load_dotenv is not None:
            load_dotenv()

        host = os.getenv("SMTP_HOST", "")
        port = int(os.getenv("SMTP_PORT", "587"))
        username = os.getenv("SMTP_USERNAME", "")
        password = os.getenv("SMTP_PASSWORD", "")
        from_email = os.getenv("SMTP_FROM_EMAIL", username)
        use_tls = os.getenv("SMTP_USE_TLS", "true").lower() in {"1", "true", "yes", "on"}

        missing = [
            name
            for name, value in {
                "SMTP_HOST": host,
                "SMTP_USERNAME": username,
                "SMTP_PASSWORD": password,
                "SMTP_FROM_EMAIL": from_email,
            }.items()
            if not value
        ]
        if missing:
            raise ValueError(f"Missing SMTP environment values: {', '.join(missing)}")

        return cls(
            host=host,
            port=port,
            username=username,
            password=password,
            from_email=from_email,
            use_tls=use_tls,
        )


class SMTPEmailChannel:
    def __init__(self, settings: SMTPSettings):
        self.settings = settings

    def send_email(self, to_email: str, subject: str, body: str) -> dict:
        message = EmailMessage()
        message["From"] = self.settings.from_email
        message["To"] = to_email
        message["Subject"] = subject
        message.set_content(body)

        with smtplib.SMTP(self.settings.host, self.settings.port, timeout=10) as server:
            if self.settings.use_tls:
                context = ssl.create_default_context()
                server.starttls(context=context)
            server.login(self.settings.username, self.settings.password)
            server.send_message(message)

        return {
            "status": "sent",
            "to": to_email,
            "subject": subject,
            "from": self.settings.from_email,
        }
