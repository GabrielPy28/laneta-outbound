from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, status
from fastapi import Depends, Query
from sqlalchemy import select

from app.api.auth_deps import get_access_token_payload
from app.api.deps import DbSession
from app.api.postmaster.schemas import (
    PostmasterDomainStatusResponse,
    PostmasterReportDetail,
    PostmasterReportListItem,
)
from app.core.config import get_settings
from app.integrations.google_postmaster.client import GooglePostmasterError
from app.models.postmaster_report import PostmasterReport
from app.services.postmaster_domain_status import get_domain_status_report

router = APIRouter(tags=["postmaster"])


@router.get(
    "/domains/{domain_name}/status",
    response_model=PostmasterDomainStatusResponse,
    summary="Resumen de salud del dominio con Google Postmaster",
    description=(
        "Devuelve una evaluación simplificada del dominio (`bien`, `ordinario`, `mal`) "
        "y una acción recomendada (`sin_accion`, `monitoreo_interno`, `cuarentena`) "
        "con base en métricas clave de Google Postmaster."
    ),
)
def get_postmaster_domain_status(domain_name: str) -> PostmasterDomainStatusResponse:
    settings = get_settings()
    try:
        report = get_domain_status_report(settings, domain=domain_name)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except GooglePostmasterError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return PostmasterDomainStatusResponse(
        domain=report.domain,
        evaluated_date=report.evaluated_date,
        status=report.status,
        action=report.action,
        summary=report.summary,
        score=report.score,
        key_metrics=report.key_metrics,
    )


@router.get(
    "/reports",
    response_model=list[PostmasterReportListItem],
    summary="Lista de reportes Postmaster persistidos",
    description="Devuelve los reportes guardados para consulta histórica en dashboard.",
)
def list_postmaster_reports(
    db: DbSession,
    _payload: dict[str, Any] = Depends(get_access_token_payload),
    limit: int = Query(25, ge=1, le=100),
) -> list[PostmasterReportListItem]:
    stmt = select(PostmasterReport).order_by(PostmasterReport.created_at.desc()).limit(limit)
    rows = db.scalars(stmt).all()
    return [
        PostmasterReportListItem(
            id=row.id,
            report_type=row.report_type,
            domains_requested=row.domains_requested,
            results_count=row.results_count,
            errors_count=row.errors_count,
            email_sent=row.email_sent,
            email_to=row.email_to,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.get(
    "/reports/{report_id}",
    response_model=PostmasterReportDetail,
    summary="Detalle de un reporte Postmaster persistido",
)
def get_postmaster_report_detail(
    report_id: uuid.UUID,
    db: DbSession,
    _payload: dict[str, Any] = Depends(get_access_token_payload),
) -> PostmasterReportDetail:
    row = db.get(PostmasterReport, report_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reporte no encontrado.")
    return PostmasterReportDetail(
        id=row.id,
        report_type=row.report_type,
        domains_requested=row.domains_requested,
        results_count=row.results_count,
        errors_count=row.errors_count,
        email_sent=row.email_sent,
        email_to=row.email_to,
        email_error=row.email_error,
        payload=row.payload or {},
        created_at=row.created_at,
    )
