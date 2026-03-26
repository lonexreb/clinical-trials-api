from fastapi import APIRouter

from app.api.v1.export import router as export_router
from app.api.v1.health import router as health_router
from app.api.v1.trials import router as trials_router

v1_router = APIRouter()
v1_router.include_router(health_router)
v1_router.include_router(trials_router)
v1_router.include_router(export_router)
