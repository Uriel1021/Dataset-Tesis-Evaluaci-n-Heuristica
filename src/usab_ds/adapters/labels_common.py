"""Esquema común de la tabla larga de evaluaciones heurísticas.

Una fila = (fuente, interfaz, evaluador/ronda, heurística).

violation           1 = se reporta al menos un problema con severidad ≥ 1
                    0 = negativo explícito (IssueFound=false / sección sin problemas)
                        o negativo por ausencia (ver negative_by_absence)
negative_by_absence True si el 0 se infiere porque el evaluador no reportó esa
                    heurística (evidencia más débil que un negativo explícito)
severity_max        severidad máxima Nielsen 0–4 (Nielsen, 1994b)
"""

from __future__ import annotations

import pandas as pd

from .. import config

LABEL_COLUMNS = {
    "source": "string",
    "interface_id": "string",
    "interface_name": "string",
    "platform": "string",            # web | prototype
    "artifact_evaluated": "string",  # code | screenshot | prototype_image
    "fidelity": "string",
    "evaluator_id": "string",
    "evaluator_type": "string",      # llm | llm_expert_validated | human
    "evaluation_round": "Int64",
    "heuristic": "string",
    "heuristic_raw": "string",
    "in_scope": "boolean",
    "violation": "Int64",
    "negative_by_absence": "boolean",
    "severity_max": "Float64",
    "n_issues": "Int64",
    "evidence_text": "string",
}


def label_frame(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    for c in LABEL_COLUMNS:
        if c not in df.columns:
            df[c] = pd.NA
    df["in_scope"] = df["heuristic"].isin(config.TARGET_HEURISTICS)
    df["evidence_text"] = df["evidence_text"].astype("string").str.slice(0, 500)
    return df[list(LABEL_COLUMNS)].astype(LABEL_COLUMNS)
