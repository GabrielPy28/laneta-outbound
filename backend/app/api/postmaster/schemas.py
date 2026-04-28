from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class PostmasterDomainStatusResponse(BaseModel):
    domain: str = Field(description="Dominio evaluado.")
    evaluated_date: str | None = Field(
        default=None,
        description="Fecha de las métricas usadas (YYYY-MM-DD) si existe.",
    )
    status: Literal["bien", "ordinario", "mal"] = Field(description="Semáforo simplificado.")
    action: Literal["sin_accion", "monitoreo_interno", "cuarentena"] = Field(
        description="Acción sugerida para operación del dominio.",
    )
    summary: str = Field(description="Resumen corto para el equipo.")
    score: int = Field(ge=0, le=100, description="Score agregado interno (0-100).")
    key_metrics: dict[str, Any] = Field(
        default_factory=dict,
        description="Métricas clave de Postmaster usadas para calcular el estado.",
    )


class PostmasterReportListItem(BaseModel):
    id: uuid.UUID = Field(description="ID del reporte persistido.")
    report_type: str = Field(description="Tipo de reporte.")
    domains_requested: int = Field(ge=0)
    results_count: int = Field(ge=0)
    errors_count: int = Field(ge=0)
    email_sent: bool
    email_to: str | None = None
    created_at: datetime = Field(description="Fecha ISO UTC de creación.")


class PostmasterReportDetail(PostmasterReportListItem):
    email_error: str | None = None
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Snapshot completo de la ejecución del reporte.",
    )
