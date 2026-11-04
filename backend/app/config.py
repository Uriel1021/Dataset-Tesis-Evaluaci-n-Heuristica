"""Configuración del backend (variables de entorno con valores por defecto para uso local)."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # raíz del proyecto
BACKEND = ROOT / "backend"

DATABASE_URL = os.getenv("USAB_DATABASE_URL", f"sqlite:///{BACKEND / 'data' / 'usab.db'}")
MODEL_PATH = Path(os.getenv("USAB_MODEL_PATH", ROOT / "models" / "modelo_multietiqueta_H1_H4_H5_H6.joblib"))
MODEL_REPORT = ROOT / "reports" / "06_modelo_multietiqueta" / "resultados_test_30_por_heuristica.csv"

# Clave opcional. Si USAB_API_KEY no está definida, la API no exige autenticación (modo local).
API_KEY = os.getenv("USAB_API_KEY") or None

# Orígenes permitidos: extensiones de Chrome/Edge/Firefox y localhost.
CORS_ORIGIN_REGEX = os.getenv(
    "USAB_CORS_ORIGIN_REGEX",
    r"^(chrome-extension|moz-extension|safari-web-extension)://.*$|^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
)

MAX_EVENTS_PER_BATCH = int(os.getenv("USAB_MAX_EVENTS_PER_BATCH", "5000"))
API_PREFIX = "/api/v1"
