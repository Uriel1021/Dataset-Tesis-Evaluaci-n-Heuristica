"""Rutas del proyecto y carga de configuración.

Todo el pipeline lee sus parámetros de configs/*.yaml; ningún umbral
vive en el código. Las salidas se escriben en:

    reports/01_perfil_fuentes   etapa 1 (características de cada fuente)
    reports/02_relevancia       etapa 2 (elegibilidad + correspondencias)
    reports/03_dataset          etapa 3 (informe de construcción)
    data/interim                artefactos intermedios (eventos canónicos)
    data/processed/usab_v2      dataset final
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIGS = ROOT / "configs"
DATA = ROOT / "data"
INTERIM = DATA / "interim"
PROCESSED = DATA / "processed" / "usab_v2"
REPORTS = ROOT / "reports"
REPORT_STAGE1 = REPORTS / "01_perfil_fuentes"
REPORT_STAGE2 = REPORTS / "02_relevancia"
REPORT_STAGE3 = REPORTS / "03_dataset"

TARGET_HEURISTICS = ("H1", "H4", "H5", "H6")


@lru_cache(maxsize=None)
def load(name: str) -> dict:
    """Carga configs/<name>.yaml."""
    with open(CONFIGS / f"{name}.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def sources() -> dict:
    return load("sources")["sources"]


def source_path(source_id: str) -> Path:
    return ROOT / sources()[source_id]["path"]


def params() -> dict:
    return load("indicators")["params"]


def ensure_dirs() -> None:
    for p in (INTERIM, PROCESSED, REPORT_STAGE1, REPORT_STAGE2, REPORT_STAGE3):
        p.mkdir(parents=True, exist_ok=True)


def heuristic_alias_map() -> dict[str, str]:
    """Nombre normalizado (minúsculas) -> código H1..H10."""
    cw = load("crosswalk")
    out: dict[str, str] = {}
    for code, h in cw["heuristics"].items():
        for a in [h["name"], *h.get("aliases", [])]:
            out[normalize_text(a)] = code
    for code, aliases in cw["other_heuristics"].items():
        for a in aliases:
            out[normalize_text(a)] = code
    return out


def normalize_text(s: str) -> str:
    import re

    s = s.lower().strip()
    s = re.sub(r"^\s*(h?\d+\s*[\).:\-]\s*)", "", s)  # "4) Consistency..." / "H4: ..."
    s = s.replace("&", "and")
    s = re.sub(r"[^a-z ,]", " ", s)
    return re.sub(r"\s+", " ", s).strip(" ,")


def heuristic_code(name: str) -> str | None:
    """Mapea un nombre de heurística escrito libremente a H1..H10."""
    if name is None:
        return None
    amap = heuristic_alias_map()
    n = normalize_text(str(name))
    if n in amap:
        return amap[n]
    # coincidencia por inclusión (p. ej. "the visibility of system status principle")
    for alias, code in sorted(amap.items(), key=lambda kv: -len(kv[0])):
        if alias in n:
            return code
    return None
