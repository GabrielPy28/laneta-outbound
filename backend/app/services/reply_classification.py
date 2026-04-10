"""Clasificación de intención en respuestas inbound (texto plano, sin HTML)."""

from __future__ import annotations

import re
from html.parser import HTMLParser


class _HTMLStripper(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []

    def handle_data(self, data: str) -> None:
        self._chunks.append(data)

    def get_text(self) -> str:
        return "".join(self._chunks)


def strip_html(html: str | None) -> str:
    if not html or not str(html).strip():
        return ""
    raw = str(html)
    stripper = _HTMLStripper()
    try:
        stripper.feed(raw)
        stripper.close()
    except Exception:
        return re.sub(r"<[^>]+>", " ", raw)
    text = stripper.get_text()
    return re.sub(r"\s+", " ", text).strip()


def classify_reply(text: str) -> str:
    """
    Nivel 1: interested | not_interested | later | out_of_office | unknown
    Orden: fuera de empresa → no interés → más tarde → interés.
    """
    t = text.lower()

    _office = (
        "not part of this company",
        "no longer with",
        "no longer at",
        "no longer work",
        "don't work here",
        "do not work here",
        "left the company",
        "at this company",
        "new job",
        "ya no trabajo",
        "ya no estoy",
        "ya no formo parte",
        "nuevo trabajo",
    )
    if any(x in t for x in _office):
        return "out_of_office"

    _not = (
        "not interested",
        "no thanks",
        "no thank you",
        "not for us",
        "please remove",
        "unsubscribe",
        "stop emailing",
        "don't contact",
        "do not contact",
        "no estoy interesado",
        "no me interesa",
        "borrenme",
        "desuscrib",
    )
    if any(x in t for x in _not):
        return "not_interested"

    _yes = (
        "interested",
        "sounds good",
        "let's talk",
        "lets talk",
        "let us talk",
        "i'm in",
        "im in",
        "tell me more",
        "schedule",
        "book a call",
        "me interesa",
        "estoy interesado",
        "estoy interesada",
        "hablemos",
        "agenda",
    )
    if any(x in t for x in _yes):
        return "interested"

    _later = (
        "not now",
        "busy",
        "reach out later",
        "follow up later",
        "circle back",
        "next quarter",
        "next month",
        "next week",
        "remind me",
        "más adelante",
        "después",
        "ahora no",
        "ocupado",
        "ocupada",
    )
    if any(x in t for x in _later):
        return "later"

    return "unknown"
