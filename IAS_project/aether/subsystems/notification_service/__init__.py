"""
notification_service

Sends platform notifications via SMTP email and exposes simple event hooks.
"""

from .channels import SMTPEmailChannel, SMTPSettings

__all__ = [
    "SMTPEmailChannel",
    "SMTPSettings",
]
