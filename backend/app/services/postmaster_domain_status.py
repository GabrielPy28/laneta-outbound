from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.integrations.google_postmaster.client import GooglePostmasterError, list_traffic_stats


@dataclass(slots=True)
class DomainStatusReport:
    domain: str
    status: str
    action: str
    summary: str
    score: int
    evaluated_date: str | None
    key_metrics: dict[str, Any]


def _resolve_path(path_str: str) -> Path:
    p = Path(path_str.strip())
    return p if p.is_absolute() else Path.cwd() / p


def _load_allowed_domains(settings: Settings) -> set[str]:
    path = _resolve_path(settings.domains_registry_file)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    items = raw.get("domains", [])
    if not isinstance(items, list):
        return set()
    out: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name.startswith("domains/"):
            continue
        domain = name.removeprefix("domains/").strip().lower()
        if domain:
            out.add(domain)
    return out


def _domain_rep_penalty(rep: str | None) -> int:
    key = (rep or "UNKNOWN").upper().strip()
    return {
        "HIGH": 0,
        "MEDIUM": 10,
        "LOW": 30,
        "BAD": 50,
        "UNKNOWN": 20,
    }.get(key, 20)


def _ratio_penalty(value: float | None, *, warn: float, bad: float, invert: bool = False) -> int:
    if value is None:
        return 8
    x = max(0.0, min(1.0, float(value)))
    if invert:
        if x < bad:
            return 20
        if x < warn:
            return 10
        return 0
    if x > bad:
        return 20
    if x > warn:
        return 10
    return 0


def _recommendation(status: str) -> tuple[str, str]:
    if status == "bien":
        return "sin_accion", "Sin alertas relevantes: el dominio puede operar con normalidad."
    if status == "ordinario":
        return (
            "monitoreo_interno",
            "Hay señales moderadas de riesgo; mantener monitoreo interno y revisar autenticación.",
        )
    return (
        "cuarentena",
        "Riesgo alto de entregabilidad/reputación; colocar el dominio en cuarentena y reducir envíos.",
    )


def get_domain_status_report(settings: Settings, *, domain: str) -> DomainStatusReport:
    clean_domain = domain.strip().lower()
    if not clean_domain:
        raise ValueError("Debes enviar un dominio válido.")

    allowed = _load_allowed_domains(settings)
    if allowed and clean_domain not in allowed:
        raise LookupError("Dominio no encontrado en domains.json.")

    stats = list_traffic_stats(settings, domain=clean_domain, page_size=10)
    if not stats:
        raise LookupError("Sin métricas disponibles para este dominio en Google Postmaster.")

    def _day_key(row: dict[str, Any]) -> tuple[int, int, int]:
        dt = row.get("date")
        if isinstance(dt, dict):
            try:
                return (int(dt["year"]), int(dt["month"]), int(dt["day"]))
            except (KeyError, TypeError, ValueError):
                pass
        return (0, 0, 0)

    latest = stats[0]
    if len(stats) > 1:
        latest = max(stats, key=_day_key)

    rep = latest.get("domainReputation")
    if rep == "REPUTATION_CATEGORY_UNSPECIFIED":
        rep = None
    spam_rate = latest.get("spamRate")
    user_spam_ratio = latest.get("userReportedSpamRatio")
    dkim = latest.get("dkimSuccessRate")
    spf = latest.get("spfSuccessRate")
    dmarc = latest.get("dmarcSuccessRate")
    inbound_encryption = latest.get("inboundEncryptionRatio")
    delivery_error_rate = latest.get("deliveryErrorRate")

    score = 100
    if rep is not None:
        score -= _domain_rep_penalty(str(rep))
    score -= _ratio_penalty(spam_rate, warn=0.01, bad=0.03)
    score -= _ratio_penalty(user_spam_ratio, warn=0.0015, bad=0.0035)
    score -= _ratio_penalty(dkim, warn=0.97, bad=0.9, invert=True)
    score -= _ratio_penalty(spf, warn=0.97, bad=0.9, invert=True)
    score -= _ratio_penalty(dmarc, warn=0.95, bad=0.85, invert=True)
    score -= _ratio_penalty(inbound_encryption, warn=0.9, bad=0.75, invert=True)
    score -= _ratio_penalty(delivery_error_rate, warn=0.02, bad=0.06)
    score = max(0, min(100, score))

    status = "bien" if score >= 80 else "ordinario" if score >= 55 else "mal"
    action, summary = _recommendation(status)

    evaluated_date: str | None = None
    day_candidates: list[tuple[int, int, int]] = []
    for fk in ("date", "v1_reference_date"):
        dt = latest.get(fk)
        if isinstance(dt, dict):
            try:
                day_candidates.append((int(dt["year"]), int(dt["month"]), int(dt["day"])))
            except (KeyError, TypeError, ValueError):
                continue
    if day_candidates:
        yy, mm, dd = max(day_candidates)
        evaluated_date = date(yy, mm, dd).isoformat()

    metrics = {
        "domain_reputation": rep,
        "spam_rate": spam_rate,
        "user_reported_spam_ratio": user_spam_ratio,
        "dkim_success_rate": dkim,
        "spf_success_rate": spf,
        "dmarc_success_rate": dmarc,
        "inbound_encryption_ratio": inbound_encryption,
        "delivery_error_rate": delivery_error_rate,
    }

    return DomainStatusReport(
        domain=clean_domain,
        status=status,
        action=action,
        summary=summary,
        score=score,
        evaluated_date=evaluated_date,
        key_metrics=metrics,
    )


__all__ = ["DomainStatusReport", "GooglePostmasterError", "get_domain_status_report"]
