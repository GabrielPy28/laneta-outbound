from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.integrations.google_postmaster.client import GooglePostmasterError, list_traffic_stats


class PostmasterNoMetricsError(LookupError):
    """Google Postmaster no devolvió series en la ventana consultada (p. ej. sin tráfico suficiente hacia Gmail)."""


POSTMASTER_NO_METRICS_MESSAGE = (
    "Sin métricas disponibles para este dominio en Google Postmaster."
)


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


def _float_metric(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _aggregate_worst_case_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Score conservador: peor valor observado en la ventana (máximos en tasas de problema,
    mínimos en tasas de éxito, reputación con mayor penalización).
    """
    worst_rep: str | None = None
    worst_rep_pen = -1
    spam_max: float | None = None
    user_spam_max: float | None = None
    dkim_min: float | None = None
    spf_min: float | None = None
    dmarc_min: float | None = None
    enc_min: float | None = None
    deliv_max: float | None = None

    for row in rows:
        rep = row.get("domainReputation")
        if rep == "REPUTATION_CATEGORY_UNSPECIFIED":
            rep = None
        if rep is not None:
            p = _domain_rep_penalty(str(rep))
            if p > worst_rep_pen:
                worst_rep_pen = p
                worst_rep = str(rep)

        sr = _float_metric(row.get("spamRate"))
        if sr is not None:
            spam_max = sr if spam_max is None else max(spam_max, sr)

        usr = _float_metric(row.get("userReportedSpamRatio"))
        if usr is not None:
            user_spam_max = usr if user_spam_max is None else max(user_spam_max, usr)

        dk = _float_metric(row.get("dkimSuccessRate"))
        if dk is not None:
            dkim_min = dk if dkim_min is None else min(dkim_min, dk)
        sp = _float_metric(row.get("spfSuccessRate"))
        if sp is not None:
            spf_min = sp if spf_min is None else min(spf_min, sp)
        dm = _float_metric(row.get("dmarcSuccessRate"))
        if dm is not None:
            dmarc_min = dm if dmarc_min is None else min(dmarc_min, dm)
        enc = _float_metric(row.get("inboundEncryptionRatio"))
        if enc is not None:
            enc_min = enc if enc_min is None else min(enc_min, enc)
        der = _float_metric(row.get("deliveryErrorRate"))
        if der is not None:
            deliv_max = der if deliv_max is None else max(deliv_max, der)

    return {
        "domainReputation": worst_rep,
        "spamRate": spam_max,
        "userReportedSpamRatio": user_spam_max,
        "dkimSuccessRate": dkim_min,
        "spfSuccessRate": spf_min,
        "dmarcSuccessRate": dmarc_min,
        "inboundEncryptionRatio": enc_min,
        "deliveryErrorRate": deliv_max,
    }


def _day_key(row: dict[str, Any]) -> tuple[int, int, int]:
    dt = row.get("date")
    if isinstance(dt, dict):
        try:
            return (int(dt["year"]), int(dt["month"]), int(dt["day"]))
        except (KeyError, TypeError, ValueError):
            pass
    return (0, 0, 0)


def _row_date_iso(row: dict[str, Any]) -> str | None:
    yy, mm, dd = _day_key(row)
    if yy == 0:
        return None
    try:
        return date(yy, mm, dd).isoformat()
    except ValueError:
        return None


def get_domain_status_report(settings: Settings, *, domain: str) -> DomainStatusReport:
    clean_domain = domain.strip().lower()
    if not clean_domain:
        raise ValueError("Debes enviar un dominio válido.")

    allowed = _load_allowed_domains(settings)
    if allowed and clean_domain not in allowed:
        raise LookupError("Dominio no encontrado en domains.json.")

    stats = list_traffic_stats(settings, domain=clean_domain, page_size=10)
    if not stats:
        raise PostmasterNoMetricsError(POSTMASTER_NO_METRICS_MESSAGE)

    worst = _aggregate_worst_case_metrics(stats)

    rep = worst.get("domainReputation")
    if rep == "REPUTATION_CATEGORY_UNSPECIFIED":
        rep = None
    spam_rate = worst.get("spamRate")
    user_spam_ratio = worst.get("userReportedSpamRatio")
    dkim = worst.get("dkimSuccessRate")
    spf = worst.get("spfSuccessRate")
    dmarc = worst.get("dmarcSuccessRate")
    inbound_encryption = worst.get("inboundEncryptionRatio")
    delivery_error_rate = worst.get("deliveryErrorRate")

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

    day_keys = [k for k in (_day_key(r) for r in stats) if k != (0, 0, 0)]
    evaluated_date: str | None = None
    if day_keys:
        yy, mm, dd = max(day_keys)
        evaluated_date = date(yy, mm, dd).isoformat()

    daily_history: list[dict[str, Any]] = []
    for row in stats[:31]:
        d_iso = _row_date_iso(row)
        if not d_iso:
            continue
        daily_history.append(
            {
                "date": d_iso,
                "domain_reputation": row.get("domainReputation"),
                "spam_rate": row.get("spamRate"),
                "user_reported_spam_ratio": row.get("userReportedSpamRatio"),
                "dkim_success_rate": row.get("dkimSuccessRate"),
                "spf_success_rate": row.get("spfSuccessRate"),
                "dmarc_success_rate": row.get("dmarcSuccessRate"),
                "inbound_encryption_ratio": row.get("inboundEncryptionRatio"),
                "delivery_error_rate": row.get("deliveryErrorRate"),
            }
        )

    metrics = {
        "domain_reputation": rep,
        "spam_rate": spam_rate,
        "user_reported_spam_ratio": user_spam_ratio,
        "dkim_success_rate": dkim,
        "spf_success_rate": spf,
        "dmarc_success_rate": dmarc,
        "inbound_encryption_ratio": inbound_encryption,
        "delivery_error_rate": delivery_error_rate,
        "score_uses_worst_in_window": True,
        "days_in_response": len(stats),
        "daily_history": daily_history,
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


__all__ = [
    "DomainStatusReport",
    "GooglePostmasterError",
    "POSTMASTER_NO_METRICS_MESSAGE",
    "PostmasterNoMetricsError",
    "get_domain_status_report",
]
