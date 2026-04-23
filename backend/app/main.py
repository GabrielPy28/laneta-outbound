from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth.router import router as auth_router
from app.api.campaign_active.router import router as campaign_active_router
from app.api.health.router import router as health_router
from app.api.leads.router import router as leads_router
from app.api.hubspot.router import router as hubspot_router
from app.api.root.router import router as root_router
from app.api.smartlead.router import router as smartlead_router
from app.core.config import get_settings
from app.lifespan import lifespan

app = FastAPI(
    title="La Neta — Outbound API",
    description="API de orquestación outbound (HubSpot, Smartlead, Celery).",
    version="0.1.0",
    lifespan=lifespan,
    swagger_ui_parameters={"defaultModelsExpandDepth": -1},
)

_settings = get_settings()
_cors_list = [
    o.strip()
    for o in (_settings.cors_origins or "").split(",")
    if o.strip()
]
# Frontend producción (Vercel)
_vercel_origins = (
    "https://laneta-outbound.vercel.app",
    "https://gmr-pages.vercel.app",
)
for _o in _vercel_origins:
    if _o not in _cors_list:
        _cors_list.append(_o)
if _cors_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(root_router)
app.include_router(health_router)
app.include_router(hubspot_router, prefix="/api/v1/hubspot")
app.include_router(smartlead_router, prefix="/api/v1/smartlead")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(leads_router, prefix="/api/v1/leads")
app.include_router(campaign_active_router, prefix="/api/v1/campaign-active")
