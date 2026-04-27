from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.core.config import Settings
from app.integrations.google_calendar.client import GOOGLE_CALENDAR_SCOPES

GOOGLE_POSTMASTER_SCOPES: tuple[str, ...] = (
    "https://www.googleapis.com/auth/postmaster.readonly",
    "https://www.googleapis.com/auth/postmaster.traffic.readonly",
)

GOOGLE_OAUTH_SCOPES: tuple[str, ...] = tuple(
    dict.fromkeys((*GOOGLE_CALENDAR_SCOPES, *GOOGLE_POSTMASTER_SCOPES))
)


class GooglePostmasterError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        body: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


def _resolve_path(path_str: str) -> Path:
    p = Path(path_str.strip())
    return p if p.is_absolute() else Path.cwd() / p


def _client_id_secret_from_credentials_file(cred_path: Path) -> tuple[str | None, str | None]:
    if not cred_path.is_file():
        return None, None
    try:
        raw = json.loads(cred_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, None
    block = raw.get("installed") or raw.get("web") or {}
    cid = block.get("client_id")
    secret = block.get("client_secret")
    return (
        str(cid).strip() if cid else None,
        str(secret).strip() if secret else None,
    )


def _ensure_postmaster_scope_granted(creds: Credentials) -> None:
    granted = set(creds.scopes or [])
    if not (
        "https://www.googleapis.com/auth/postmaster.readonly" in granted
        or "https://www.googleapis.com/auth/postmaster.traffic.readonly" in granted
        or "https://www.googleapis.com/auth/postmaster" in granted
    ):
        raise GooglePostmasterError(
            "Falta un scope de Postmaster. Para API v2 usa "
            "`https://www.googleapis.com/auth/postmaster.traffic.readonly`; "
            "si combinas con v1, incluye también `postmaster.readonly`. "
            "Regenera token con `python scripts/generate_google_token.py`."
        )


def _date_proto(d: date) -> dict[str, int]:
    return {"year": d.year, "month": d.month, "day": d.day}


def _numeric_from_statistic_value(raw: Any) -> float | None:
    if not isinstance(raw, dict):
        return None
    dv = raw.get("doubleValue")
    if dv is not None:
        try:
            return float(dv)
        except (TypeError, ValueError):
            pass
    fv = raw.get("floatValue")
    if fv is not None:
        try:
            return float(fv)
        except (TypeError, ValueError):
            pass
    iv = raw.get("intValue")
    if iv not in (None, ""):
        try:
            return float(iv)
        except (TypeError, ValueError):
            pass
    sv = raw.get("stringValue")
    if sv is not None and str(sv).strip() != "":
        try:
            return float(str(sv).strip())
        except (TypeError, ValueError):
            pass
    return None


def _time_query_range(start: date, end: date) -> dict[str, Any]:
    """Rango inclusivo (DateRanges en discovery v2)."""
    return {
        "timeQuery": {
            "dateRanges": {
                "dateRanges": [
                    {
                        "start": _date_proto(start),
                        "end": _date_proto(end),
                    }
                ]
            }
        }
    }


def _time_query_datelist_recent(end: date, *, days: int) -> dict[str, Any]:
    """Fallback si el rango largo devuelve 400: últimos `days` días como lista explícita."""
    n = max(1, min(days, 31))
    dates = [_date_proto(end - timedelta(days=i)) for i in range(n)]
    return {"timeQuery": {"dateList": {"dates": dates}}}


def _paginate_domain_stats(
    service: object,
    *,
    parent: str,
    time_payload: dict[str, Any],
    metric_definitions: list[dict[str, Any]],
    page_size: int,
) -> list[dict[str, Any]]:
    """Ejecuta domainStats.query con paginación para un conjunto de métricas."""
    out: list[dict[str, Any]] = []
    page_token: str | None = None
    ps = max(1, min(page_size, 200))
    while True:
        body: dict[str, Any] = {
            **time_payload,
            "metricDefinitions": metric_definitions,
            "pageSize": ps,
        }
        if page_token:
            body["pageToken"] = page_token
        payload = (
            service.domains()
            .domainStats()
            .query(parent=parent, body=body)
            .execute()
        )
        chunk = payload.get("domainStats", [])
        if not isinstance(chunk, list):
            raise GooglePostmasterError("Google Postmaster v2 devolvió un formato inesperado.")
        out.extend(r for r in chunk if isinstance(r, dict))
        page_token = payload.get("nextPageToken")
        if not page_token:
            break
    return out


def _fetch_domain_stats_in_batches(
    service: object,
    *,
    parent: str,
    start: date,
    end: date,
    page_size: int,
) -> list[dict[str, Any]]:
    """
    Varias llamadas pequeñas; filtros sin espacios (`auth_type=spf`).
    Si el rango de fechas da 400, reintenta con `dateList` (últimos 14 días).
    """
    ps = page_size
    rows: list[dict[str, Any]] = []

    time_payload = _time_query_range(start, end)
    spam_def = [{"name": "spam_rate", "baseMetric": {"standardMetric": "SPAM_RATE"}}]
    try:
        rows.extend(
            _paginate_domain_stats(
                service,
                parent=parent,
                time_payload=time_payload,
                metric_definitions=spam_def,
                page_size=ps,
            )
        )
    except HttpError as exc:
        if getattr(exc.resp, "status", None) != 400:
            raise
        time_payload = _time_query_datelist_recent(end, days=14)
        rows.extend(
            _paginate_domain_stats(
                service,
                parent=parent,
                time_payload=time_payload,
                metric_definitions=spam_def,
                page_size=ps,
            )
        )

    optional_defs: list[list[dict[str, Any]]] = [
        [{"name": "delivery_error_rate", "baseMetric": {"standardMetric": "DELIVERY_ERROR_RATE"}}],
        [
            {
                "name": "spf",
                "baseMetric": {"standardMetric": "AUTH_SUCCESS_RATE"},
                "filter": "auth_type=spf",
            },
            {
                "name": "dkim",
                "baseMetric": {"standardMetric": "AUTH_SUCCESS_RATE"},
                "filter": "auth_type=dkim",
            },
            {
                "name": "dmarc",
                "baseMetric": {"standardMetric": "AUTH_SUCCESS_RATE"},
                "filter": "auth_type=dmarc",
            },
        ],
        [
            {
                "name": "tls_inbound",
                "baseMetric": {"standardMetric": "TLS_ENCRYPTION_RATE"},
                "filter": "traffic_direction=inbound",
            },
        ],
    ]

    for defs in optional_defs:
        try:
            rows.extend(
                _paginate_domain_stats(
                    service,
                    parent=parent,
                    time_payload=time_payload,
                    metric_definitions=defs,
                    page_size=ps,
                )
            )
        except HttpError:
            for single in defs:
                try:
                    rows.extend(
                        _paginate_domain_stats(
                            service,
                            parent=parent,
                            time_payload=time_payload,
                            metric_definitions=[single],
                            page_size=ps,
                        )
                    )
                except HttpError:
                    continue

    return rows


def _domain_stats_to_traffic_snapshot(domain: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Por cada métrica v2 toma el valor del **día más reciente** donde exista dato.
    Así DKIM/SPF no se pierden si solo aparecen en fechas distintas al spam del último día.
    """
    best: dict[str, tuple[tuple[int, int, int], float]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        dt = row.get("date")
        if not isinstance(dt, dict):
            continue
        try:
            y, m, d = int(dt["year"]), int(dt["month"]), int(dt["day"])
        except (KeyError, TypeError, ValueError):
            continue
        day_key = (y, m, d)
        name = str(row.get("metric") or "").strip()
        val = _numeric_from_statistic_value(row.get("value"))
        if not name or val is None:
            continue
        prev = best.get(name)
        if prev is None or day_key > prev[0]:
            best[name] = (day_key, val)

    if not best:
        return {}

    max_day = max(t[0] for t in best.values())
    y, m, d = max_day
    mets = {k: v[1] for k, v in best.items()}
    return {
        "name": f"domains/{domain}/trafficStats/{y:04d}{m:02d}{d:02d}",
        "date": {"year": y, "month": m, "day": d},
        "domainReputation": None,
        "spamRate": mets.get("spam_rate"),
        "userReportedSpamRatio": None,
        "dkimSuccessRate": mets.get("dkim"),
        "spfSuccessRate": mets.get("spf"),
        "dmarcSuccessRate": mets.get("dmarc"),
        "inboundEncryptionRatio": mets.get("tls_inbound"),
        "deliveryErrorRate": mets.get("delivery_error_rate"),
    }


def _day_tuple_from_traffic_stat(row: dict[str, Any]) -> tuple[int, int, int]:
    dt = row.get("date")
    if isinstance(dt, dict):
        try:
            return (int(dt["year"]), int(dt["month"]), int(dt["day"]))
        except (KeyError, TypeError, ValueError):
            pass
    name = str(row.get("name") or "")
    suffix = "/trafficStats/"
    if suffix in name:
        tail = name.split(suffix, 1)[-1].strip().split("/", 1)[0]
        if len(tail) >= 8 and tail.isdigit():
            y, md = int(tail[:4]), tail[4:]
            return (y, int(md[:2]), int(md[2:4]))
    return (0, 0, 0)


def _merge_v1_traffic_snapshot(
    creds: Credentials,
    *,
    domain: str,
    snap: dict[str, Any],
    start: date,
    end: date,
    page_size: int,
) -> dict[str, Any]:
    """
    Postmaster UI sigue exponiendo muchos KPI en API v1 `trafficStats`.
    Si el token tiene `postmaster.readonly`, fusionamos filas donde v2 dejó null.
    """
    granted = set(creds.scopes or [])
    if (
        "https://www.googleapis.com/auth/postmaster.readonly" not in granted
        and "https://www.googleapis.com/auth/postmaster" not in granted
    ):
        return snap

    parent = f"domains/{domain}"
    try:
        svc = build("gmailpostmastertools", "v1", credentials=creds, cache_discovery=False)
    except Exception:
        return snap

    rows: list[dict[str, Any]] = []
    page_token: str | None = None
    try:
        while True:
            payload = (
                svc.domains()
                .trafficStats()
                .list(
                    parent=parent,
                    pageSize=min(100, max(page_size, 50)),
                    startDate_year=start.year,
                    startDate_month=start.month,
                    startDate_day=start.day,
                    endDate_year=end.year,
                    endDate_month=end.month,
                    endDate_day=end.day,
                    pageToken=page_token,
                )
                .execute()
            )
            chunk = payload.get("trafficStats", [])
            if not isinstance(chunk, list):
                break
            rows.extend(r for r in chunk if isinstance(r, dict))
            page_token = payload.get("nextPageToken")
            if not page_token:
                break
    except HttpError:
        return snap

    if not rows:
        return snap

    latest = max(rows, key=_day_tuple_from_traffic_stat)

    _ratio_to_rate = (
        ("dkimSuccessRatio", "dkimSuccessRate"),
        ("spfSuccessRatio", "spfSuccessRate"),
        ("dmarcSuccessRatio", "dmarcSuccessRate"),
        ("inboundEncryptionRatio", "inboundEncryptionRatio"),
    )
    for src, dst in _ratio_to_rate:
        v = latest.get(src)
        if v is None:
            continue
        if snap.get(dst) is None:
            snap[dst] = v

    rep = latest.get("domainReputation")
    if rep == "REPUTATION_CATEGORY_UNSPECIFIED":
        rep = None
    if snap.get("domainReputation") is None and rep:
        snap["domainReputation"] = rep

    if snap.get("userReportedSpamRatio") is None and latest.get("userReportedSpamRatio") is not None:
        snap["userReportedSpamRatio"] = latest["userReportedSpamRatio"]

    if snap.get("spamRate") is None:
        sr = latest.get("spamRate")
        if sr is None:
            sr = latest.get("spamRatio")
        if sr is not None:
            snap["spamRate"] = sr

    v1_day = _day_tuple_from_traffic_stat(latest)
    if v1_day != (0, 0, 0):
        vy, vm, vd = v1_day
        snap.setdefault("v1_reference_date", {"year": vy, "month": vm, "day": vd})

    return snap


def _load_credentials(settings: Settings) -> Credentials:
    cred_path = _resolve_path(settings.google_oauth_credentials_file)
    token_path = _resolve_path(settings.google_oauth_token_file)

    file_cid, file_secret = _client_id_secret_from_credentials_file(cred_path)
    client_id = (settings.google_oauth_client_id or "").strip() or file_cid
    client_secret = (settings.google_oauth_client_secret or "").strip() or file_secret
    refresh_env = (settings.google_oauth_refresh_token or "").strip() or None

    combined_scopes = list(GOOGLE_OAUTH_SCOPES)

    # 1) Preferir token.json: refleja el último consentimiento.
    token_missing_postmaster = False
    if token_path.is_file():
        try:
            creds = Credentials.from_authorized_user_file(str(token_path))
        except (OSError, ValueError):
            creds = None
        if creds is not None and getattr(creds, "refresh_token", None):
            try:
                if not creds.valid:
                    creds.refresh(Request())
            except RefreshError:
                creds = None
            else:
                try:
                    token_path.write_text(creds.to_json(), encoding="utf-8")
                except OSError:
                    pass
                try:
                    _ensure_postmaster_scope_granted(creds)
                    return creds
                except GooglePostmasterError:
                    token_missing_postmaster = True

    # 2) Variables de entorno (mismo Client ID/secret/refresh que Calendar).
    if refresh_env and client_id and client_secret:
        creds = Credentials(
            token=None,
            refresh_token=refresh_env,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=combined_scopes,
        )
        try:
            creds.refresh(Request())
        except RefreshError as exc:
            raise GooglePostmasterError(
                "No se pudo refrescar el token OAuth (invalid_scope u otro error). "
            ) from exc
        try:
            token_path.write_text(creds.to_json(), encoding="utf-8")
        except OSError:
            pass
        _ensure_postmaster_scope_granted(creds)
        return creds

    if token_missing_postmaster:
        raise GooglePostmasterError(
            "token.json no incluye el scope de Postmaster (o el refresh falló) y "
            "no hay credenciales válidas en .env. Actualiza token.json con un consentimiento "
        )
    raise GooglePostmasterError(
        "Google Postmaster no configurado: falta token OAuth. "
    )


def list_traffic_stats(
    settings: Settings,
    *,
    domain: str,
    page_size: int = 10,
) -> list[dict[str, Any]]:
    """
    Obtiene métricas vía API **v2** `domains.domainStats.query` y devuelve una lista
    con un único elemento en formato compatible con TrafficStats v1 para el scorer.
    """
    creds = _load_credentials(settings)
    clean = domain.strip()
    parent = f"domains/{clean}"
    try:
        service = build("gmailpostmastertools", "v2", credentials=creds, cache_discovery=False)
    except Exception as exc:
        raise GooglePostmasterError(f"No se pudo inicializar Postmaster API v2: {exc}") from exc

    end = date.today()
    start = end - timedelta(days=31)
    ps = max(page_size, 50)

    try:
        raw_rows = _fetch_domain_stats_in_batches(
            service,
            parent=parent,
            start=start,
            end=end,
            page_size=ps,
        )
    except HttpError as exc:
        err_text = getattr(exc, "content", None) or str(exc)
        raise GooglePostmasterError(
            f"Google Postmaster request falló: {exc!s}",
            status_code=getattr(exc.resp, "status", None),
            body=str(err_text)[:2000],
        ) from exc

    snap = _domain_stats_to_traffic_snapshot(clean, raw_rows)
    if not snap:
        return []
    snap = _merge_v1_traffic_snapshot(
        creds,
        domain=clean,
        snap=snap,
        start=start,
        end=end,
        page_size=ps,
    )
    return [snap]
