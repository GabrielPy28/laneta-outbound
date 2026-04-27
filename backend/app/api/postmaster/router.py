from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.api.postmaster.schemas import PostmasterDomainStatusResponse
from app.core.config import get_settings
from app.integrations.google_postmaster.client import GooglePostmasterError
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
