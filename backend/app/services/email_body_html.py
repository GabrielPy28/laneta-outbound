"""Utilidades para conservar HTML y recortar citas en respuestas inbound (Gmail, etc.)."""

from __future__ import annotations

import re


# Primer bloque citado típico: thread completo debajo no se guarda.
_INBOUND_QUOTE_START = re.compile(
    r"(?is)"
    r"(<blockquote\b|"
    r"<div\b[^>]*\bclass\s*=\s*['\"][^'\"]*\bgmail_quote\b[^'\"]*['\"][^>]*>|"
    r"<div\b[^>]*\bclass\s*=\s*['\"][^'\"]*\bgmail_quote_container\b[^'\"]*['\"][^>]*>|"
    r"<div\b[^>]*\bid\s*=\s*['\"]divRplyFwdMsg['\"][^>]*>|"
    r"-----+\s*original message\s*-----+|"
    r"-----+\s*mensaje original\s*-----+|"
    r"________________________________)"
)


def extract_inbound_reply_html(html: str | None) -> str | None:
    """
    Devuelve solo el fragmento HTML de la respuesta nueva (sin el correo citado).
    Si no hay patrón de cita reconocido, devuelve el cuerpo completo.
    """
    if html is None:
        return None
    raw = str(html).strip()
    if not raw:
        return None
    m = _INBOUND_QUOTE_START.search(raw)
    if not m:
        return raw
    frag = raw[: m.start()].strip()
    frag = re.sub(r"(?is)(?:<br\s*/?>\s*)+\s*$", "", frag).strip()
    return frag or None


_RE_PREFIX = re.compile(r"^re:\s*", re.IGNORECASE)


def re_reply_subject(last_outbound_subject: str | None) -> str | None:
    """Asunto de respuesta: `Re: ` + último asunto outbound (sin duplicar Re:)."""
    if not last_outbound_subject:
        return None
    s = last_outbound_subject.strip()
    if not s:
        return None
    if _RE_PREFIX.match(s):
        return s
    return f"Re: {s}"
