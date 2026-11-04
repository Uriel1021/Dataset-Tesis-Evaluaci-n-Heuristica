"""Backend FastAPI para la extensión de evaluación heurística (H1, H4, H5, H6).

Ejecutar en local (desde la raíz del proyecto):
    entornoTesis/bin/uvicorn backend.app.main:app --reload --port 8000
Documentación interactiva:  http://127.0.0.1:8000/docs   (Swagger)
                            http://127.0.0.1:8000/redoc
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config, model_service
from .api import router
from .db import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    model_service.bundle()          # carga el modelo una sola vez al arrancar
    yield


app = FastAPI(
    title="Usabilidad web · API de evaluación heurística",
    version="1.0.0",
    description="Recibe la telemetría de la extensión web, calcula métricas de interacción e ISO/IEC 25022 y "
                "evalúa las heurísticas de Nielsen H1, H4, H5 y H6 con el Random Forest multi-salida.",
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origin_regex=config.CORS_ORIGIN_REGEX, allow_credentials=False,
                   allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"], allow_headers=["*"])
app.include_router(router, prefix=config.API_PREFIX)


@app.get("/health", tags=["sistema"], summary="Estado del servicio")
def health():
    b = model_service.bundle()
    return {"status": "ok", "model_version": b["version"], "auth_required": bool(config.API_KEY)}
