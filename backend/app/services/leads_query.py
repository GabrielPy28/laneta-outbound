"""Filtros reutilizables para listados de `Lead`."""

from __future__ import annotations

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from app.models.lead import Lead


def _strip(value: str | None) -> str | None:
    if value is None:
        return None
    t = value.strip()
    return t or None


def lead_filter_conditions(
    *,
    filter_name: str | None = None,
    filter_email: str | None = None,
    filter_company: str | None = None,
    filter_engagement: str | None = None,
    filter_campaign: str | None = None,
    filter_last_sequence: str | None = None,
) -> list:
    conds: list = []
    if n := _strip(filter_name):
        pat = f"%{n}%"
        conds.append(
            or_(
                Lead.first_name.ilike(pat),
                Lead.last_name.ilike(pat),
            )
        )
    if e := _strip(filter_email):
        conds.append(Lead.email.ilike(f"%{e}%"))
    if c := _strip(filter_company):
        conds.append(Lead.company_name.ilike(f"%{c}%"))
    if eng := _strip(filter_engagement):
        conds.append(Lead.engagement_status.ilike(f"%{eng}%"))
    if camp := _strip(filter_campaign):
        conds.append(Lead.campaign_id.ilike(f"%{camp}%"))
    if step := _strip(filter_last_sequence):
        conds.append(Lead.last_sequence_step.ilike(f"%{step}%"))
    return conds


def apply_lead_filters(stmt: Select, conditions: list) -> Select:
    if not conditions:
        return stmt
    return stmt.where(and_(*conditions))


def count_leads(session: Session, conditions: list) -> int:
    q = select(func.count()).select_from(Lead)
    q = apply_lead_filters(q, conditions)
    n = session.scalar(q)
    return int(n or 0)
