"""Envío de correo por SMTP (p. ej. Google Workspace / Gmail)."""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from app.core.config import Settings

logger = logging.getLogger(__name__)


def send_plain_text_email(
    settings: Settings,
    *,
    to_addresses: list[str],
    subject: str,
    body: str,
    html_body: str | None = None,
    from_address: str | None = None,
) -> None:
    """Envía un mensaje SMTP (texto plano y opcionalmente HTML)."""
    user = (settings.smtp_user or "").strip()
    password = settings.smtp_password or ""
    if not user or not password:
        raise ValueError("SMTP_USER y SMTP_PASSWORD son obligatorios para enviar correo.")

    sender = (from_address or user).strip()
    recipients = [a.strip() for a in to_addresses if a and str(a).strip()]
    cc_recipients = ["gabriel@laneta.com", "daniel@laneta.com"]
    if not recipients:
        raise ValueError("No hay destinatarios válidos.")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg['Cc'] = ", ".join(cc_recipients)
    msg.set_content(body, subtype="plain", charset="utf-8")
    if html_body:
        msg.add_alternative(html_body, subtype="html", charset="utf-8")

    host = (settings.smtp_host or "smtp.gmail.com").strip()
    port = int(settings.smtp_port)

    logger.info(
        "SMTP envío a %s (host=%s port=%s)",
        recipients,
        host,
        port,
    )

    if settings.smtp_use_ssl:
        import ssl

        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(host, port, timeout=60, context=context) as smtp:
            smtp.login(user, password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=60) as smtp:
            smtp.starttls()
            smtp.login(user, password)
            smtp.send_message(msg)
