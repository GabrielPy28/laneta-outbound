"""Ejecución batch del resumen Postmaster para los dominios definidos en `worker.postmaster_domains`."""

from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import UTC, datetime
from html import escape
from typing import Any

from app.core.config import Settings, get_settings
from app.db.session import create_session
from app.models.postmaster_report import PostmasterReport
from app.services.postmaster_domain_status import get_domain_status_report
from app.services.smtp_mail import send_plain_text_email

logger = logging.getLogger(__name__)


def _format_metric_value(v: Any) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.6g}"
    return str(v)


def format_postmaster_batch_email_body(payload: dict[str, Any]) -> str:
    """Genera el cuerpo del correo a partir del resultado del batch."""
    lines: list[str] = [
        "Resumen Postmaster Tools (ejecución programada)",
        "",
        f"Dominios solicitados: {payload.get('domains_requested', 0)}",
        f"Consultas exitosas: {payload.get('results_count', 0)}",
        f"Fallos: {payload.get('errors_count', 0)}",
        "",
    ]
    results = payload.get("results") or []
    errors = payload.get("errors") or []

    if results:
        lines.append("--- Resultados por dominio ---")
        lines.append("")
        for row in results:
            if not isinstance(row, dict):
                continue
            domain = row.get("domain", "?")
            lines.append(f"Dominio: {domain}")
            lines.append(f"  Estado: {row.get('status', '?')} | Score: {row.get('score', '?')}")
            if row.get("evaluated_date"):
                lines.append(f"  Fecha referencia: {row.get('evaluated_date')}")
            lines.append(f"  Acción: {row.get('action', '?')}")
            lines.append(f"  Resumen: {row.get('summary', '')}")
            metrics = row.get("key_metrics") or {}
            if isinstance(metrics, dict) and metrics:
                lines.append("  Métricas:")
                for key in sorted(metrics.keys()):
                    lines.append(f"    {key}: {_format_metric_value(metrics.get(key))}")
            lines.append("")

    if errors:
        lines.append("--- Errores ---")
        lines.append("")
        for err in errors:
            if not isinstance(err, dict):
                continue
            lines.append(f"  {err.get('domain', '?')}: {err.get('error', '')}")
        lines.append("")

    lines.append("—")
    lines.append("Mensaje automático del worker Postmaster (La Neta).")
    return "\n".join(lines)


def _status_badge_html(status: str) -> str:
    key = (status or "").strip().lower()
    mapping = {
        "bien": ("#0f766e", "#ccfbf1", "Bien"),
        "ordinario": ("#92400e", "#fef3c7", "Ordinario"),
        "mal": ("#991b1b", "#fee2e2", "Mal"),
    }
    fg, bg, text = mapping.get(key, ("#334155", "#e2e8f0", escape(status or "N/A")))
    return (
        f"<span style='display:inline-block;padding:4px 10px;border-radius:999px;"
        f"font-weight:700;font-size:12px;color:{fg};background:{bg};'>{text}</span>"
    )


def format_postmaster_batch_email_html(payload: dict[str, Any]) -> str:
    """Plantilla HTML profesional para el resumen del batch Postmaster."""
    generated_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    domains_requested = int(payload.get("domains_requested", 0) or 0)
    results_count = int(payload.get("results_count", 0) or 0)
    errors_count = int(payload.get("errors_count", 0) or 0)
    results = payload.get("results") or []
    errors = payload.get("errors") or []

    card_style = (
        "background:#ffffff;border:1px solid #e2e8f0;border-radius:12px;"
        "padding:16px;margin:0 0 14px 0;"
    )
    html_parts: list[str] = [
        "<!doctype html>",
        "<html><body style='margin:0;padding:24px;background:#f8fafc;"
        "font-family:Arial,Helvetica,sans-serif;color:#0f172a;'>",
        "<div style='max-width:900px;margin:0 auto;'>",
        "<div style='background:linear-gradient(120deg,#0f172a,#1d4ed8);color:#ffffff;"
        "padding:24px;border-radius:14px;margin-bottom:16px;'>",
        "<h2 style='margin:0 0 8px 0;font-size:24px;'>Reporte Programado de Salud de Dominios</h2>",
        "<p style='margin:0;font-size:14px;line-height:1.6;'>"
        "Este correo se envía automáticamente como parte del monitoreo operativo de "
        "entregabilidad en Google Postmaster Tools. El objetivo es anticipar riesgos de reputación "
        "y tomar acciones preventivas sobre los dominios de envío."
        "</p>",
        "</div>",
        "<div style='display:flex;gap:10px;flex-wrap:wrap;margin-bottom:18px;'>",
        "<div style='background:#e2e8f0;padding:10px 14px;border-radius:10px;font-size:13px;'>"
        f"<strong>Generado:</strong> {escape(generated_at)}</div>",
        "<div style='background:#dbeafe;padding:10px 14px;border-radius:10px;font-size:13px;'>"
        f"<strong>Dominios solicitados:</strong> {domains_requested}</div>",
        "<div style='background:#dcfce7;padding:10px 14px;border-radius:10px;font-size:13px;'>"
        f"<strong>Consultas exitosas:</strong> {results_count}</div>",
        "<div style='background:#fee2e2;padding:10px 14px;border-radius:10px;font-size:13px;'>"
        f"<strong>Fallos:</strong> {errors_count}</div>",
        "</div>",
    ]

    if results:
        html_parts.append("<h3 style='margin:0 0 10px 0;'>Resultados por dominio</h3>")
        for row in results:
            if not isinstance(row, dict):
                continue
            domain = escape(str(row.get("domain", "?")))
            status = str(row.get("status", ""))
            score = escape(str(row.get("score", "N/A")))
            action = escape(str(row.get("action", "N/A")))
            summary = escape(str(row.get("summary", "")))
            evaluated_date = escape(str(row.get("evaluated_date") or "N/D"))
            html_parts.append(f"<div style='{card_style}'>")
            html_parts.append(
                "<div style='display:flex;justify-content:space-between;gap:8px;align-items:center;'>"
                f"<div><div style='font-size:18px;font-weight:700;'>{domain}</div>"
                f"<div style='font-size:13px;color:#475569;'>Fecha de referencia: {evaluated_date}</div></div>"
                f"<div>{_status_badge_html(status)}</div></div>"
            )
            html_parts.append(
                "<div style='margin-top:12px;font-size:14px;line-height:1.65;'>"
                f"<strong>Score:</strong> {score}<br>"
                f"<strong>Acción recomendada:</strong> {action}<br>"
                f"<strong>Resumen:</strong> {summary}</div>"
            )
            metrics = row.get("key_metrics") or {}
            if isinstance(metrics, dict) and metrics:
                html_parts.append(
                    "<table style='width:100%;border-collapse:collapse;margin-top:12px;font-size:13px;'>"
                    "<thead><tr>"
                    "<th style='text-align:left;background:#f1f5f9;padding:8px;border:1px solid #e2e8f0;'>Métrica</th>"
                    "<th style='text-align:left;background:#f1f5f9;padding:8px;border:1px solid #e2e8f0;'>Valor</th>"
                    "</tr></thead><tbody>"
                )
                for key in sorted(metrics.keys()):
                    val = escape(_format_metric_value(metrics.get(key)))
                    metric = escape(str(key))
                    html_parts.append(
                        "<tr>"
                        f"<td style='padding:8px;border:1px solid #e2e8f0;'>{metric}</td>"
                        f"<td style='padding:8px;border:1px solid #e2e8f0;'>{val}</td>"
                        "</tr>"
                    )
                html_parts.append("</tbody></table>")
            html_parts.append("</div>")

    if errors:
        html_parts.append("<h3 style='margin:6px 0 10px 0;color:#991b1b;'>Incidencias detectadas</h3>")
        html_parts.append(
            "<div style='background:#fff1f2;border:1px solid #fecdd3;border-radius:12px;padding:12px;'>"
            "<ul style='margin:0;padding-left:18px;'>"
        )
        for err in errors:
            if not isinstance(err, dict):
                continue
            domain = escape(str(err.get("domain", "?")))
            msg = escape(str(err.get("error", "")))
            html_parts.append(f"<li><strong>{domain}</strong>: {msg}</li>")
        html_parts.append("</ul></div>")

    html_parts.extend(
        [
            "<p style='margin:18px 0 0 0;font-size:12px;color:#475569;'>"
            "Mensaje automático del worker Postmaster de La Neta. "
            "Si necesitas soporte, responde a este correo y comparte el dominio afectado."
            "</p>",
            "</div></body></html>",
        ]
    )
    return "".join(html_parts)


def _send_batch_report_email(settings: Settings, payload: dict[str, Any]) -> dict[str, Any]:
    """Intenta enviar el correo; devuelve metadatos sin lanzar si falla el SMTP."""
    user = (settings.smtp_user or "").strip()
    pwd = settings.smtp_password or ""
    if not user or not pwd:
        logger.warning(
            "Postmaster: no se envía correo (faltan SMTP_USER / SMTP_PASSWORD)."
        )
        return {"email_sent": False, "email_skip_reason": "smtp_not_configured"}

    to_addr = (settings.postmaster_report_to_email or "").strip()
    if not to_addr:
        logger.warning("Postmaster: POSTMASTER_REPORT_TO_EMAIL vacío; no se envía correo.")
        return {"email_sent": False, "email_skip_reason": "recipient_not_configured"}

    now = datetime.now(UTC)
    subject = f"Postmaster — resumen dominios ({now.date().isoformat()} UTC)"
    body = format_postmaster_batch_email_body(payload)
    html_body = format_postmaster_batch_email_html(payload)

    try:
        send_plain_text_email(
            settings,
            to_addresses=[to_addr],
            subject=subject,
            body=body,
            html_body=html_body,
        )
        logger.info("Postmaster: correo enviado a %s", to_addr)
        return {"email_sent": True, "email_to": to_addr}
    except Exception as exc:
        logger.exception("Postmaster: fallo al enviar correo: %s", exc)
        return {"email_sent": False, "email_error": str(exc)}


def run_postmaster_health_check_for_domains(
    settings: Settings,
    domain_names: tuple[str, ...],
) -> dict[str, Any]:
    """
    Consulta `get_domain_status_report` por dominio. No aborta ante un fallo:
    acumula errores por dominio.
    """
    results: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    for raw in domain_names:
        domain = str(raw).strip().lower()
        if not domain:
            continue
        try:
            report = get_domain_status_report(settings, domain=domain)
            row = asdict(report)
            results.append(row)
        except Exception as exc:
            logger.warning("Postmaster job falló para %s: %s", domain, exc)
            errors.append({"domain": domain, "error": str(exc)})

    logger.info(
        "Postmaster batch: dominios=%s ok=%s errores=%s",
        len(domain_names),
        len(results),
        len(errors),
    )
    return {
        "ok": True,
        "domains_requested": len(domain_names),
        "results_count": len(results),
        "errors_count": len(errors),
        "results": results,
        "errors": errors,
    }


def run_postmaster_health_check_job() -> dict[str, Any]:
    """Entrada para Celery: usa dominios definidos en `worker.postmaster_domains`."""
    from worker.postmaster_domains import POSTMASTER_BEAT_DOMAIN_NAMES

    settings = get_settings()
    payload = run_postmaster_health_check_for_domains(
        settings,
        POSTMASTER_BEAT_DOMAIN_NAMES,
    )
    email_meta = _send_batch_report_email(settings, payload)
    try:
        db = create_session()
        report = PostmasterReport(
            domains_requested=int(payload.get("domains_requested", 0) or 0),
            results_count=int(payload.get("results_count", 0) or 0),
            errors_count=int(payload.get("errors_count", 0) or 0),
            email_sent=bool(email_meta.get("email_sent", False)),
            email_to=str(email_meta.get("email_to") or "").strip() or None,
            email_error=str(email_meta.get("email_error") or "").strip() or None,
            payload=payload,
        )
        db.add(report)
        db.commit()
    except Exception as exc:
        logger.exception("Postmaster: no se pudo persistir el reporte batch: %s", exc)
    finally:
        if "db" in locals():
            db.close()
    out = dict(payload)
    out.update(email_meta)
    return out
