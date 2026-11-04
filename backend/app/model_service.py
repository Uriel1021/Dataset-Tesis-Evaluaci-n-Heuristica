"""Servicio del modelo: eventos → métricas (mismo código del entrenamiento) → Random Forest multi-salida."""

from __future__ import annotations

import json
import sys
from functools import lru_cache

import numpy as np
import pandas as pd

from . import config

sys.path.insert(0, str(config.ROOT / "src"))      # usab_ds (definición de métricas y clase del modelo)

from usab_ds import events as ev_schema  # noqa: E402
from usab_ds import metrics  # noqa: E402

HEURISTICS = {"H1": "Visibilidad del estado del sistema", "H4": "Consistencia y estándares",
              "H5": "Prevención de errores", "H6": "Reconocer antes que recordar"}

# La extensión captura eventos DOM completos: declara todas las capacidades del esquema canónico.
EXTENSION_CAPABILITIES = {"click", "key", "scroll", "scroll_y", "mouse_move", "nav_back", "page_view", "focus", "blur",
                          "input", "hover", "target_tag", "target_id", "key_name"}
DIFFICULTY_EASE = {"easy": 0.75, "low": 0.75, "medium": 0.5, "hard": 0.25, "high": 0.25}


@lru_cache(maxsize=1)
def bundle() -> dict:
    import joblib
    b = joblib.load(config.MODEL_PATH)
    b["version"] = f"{config.MODEL_PATH.stem}"
    return b


def model_info() -> dict:
    b = bundle()
    F = b["features"]
    info = dict(model_version=b["version"], strategy=b.get("strategy"), base_estimator=b.get("base"),
                heuristics=HEURISTICS, thresholds={k[2:]: round(v, 4) for k, v in b["thresholds"].items()},
                n_features=len(F), feature_groups={
                    "comportamiento_e_ISO": [f for f in F if not f.startswith(("ctx_", "intra_"))],
                    "contexto": [f for f in F if f.startswith("ctx_")],
                    "normalizacion_intra_participante": [f for f in F if f.startswith("intra_")]})
    if config.MODEL_REPORT.exists():
        rep = pd.read_csv(config.MODEL_REPORT)
        info["test_metrics_30pct"] = rep[["heuristica", "f1", "mcc", "sensibilidad", "especificidad", "roc_auc"]] \
            .round(3).to_dict("records")
    return info


def categories() -> dict:
    out: dict[str, list[str]] = {}
    for f in bundle()["features"]:
        if f.startswith("ctx_"):
            for var in ("user_group", "assistive_tech_participant", "task_group", "familiarity", "difficulty_before"):
                pre = f"ctx_{var}_"
                if f.startswith(pre):
                    out.setdefault(var, []).append(f[len(pre):])
    return out


# ----------------------------------------------------------------- features
def session_features(session: dict, events: list[dict], participant: dict) -> tuple[dict, list[str]]:
    """Calcula las métricas de UNA sesión con usab_ds.metrics (idéntico al entrenamiento)."""
    warnings: list[str] = []
    sid = session["id"]
    ev = pd.DataFrame([{"source": "extension", "session_id": sid, "ts_ms": e["ts_ms"], "event": e["type"],
                        "x": e.get("x"), "y": e.get("y"), "scroll_y": e.get("scroll_y"), "key": e.get("key"),
                        "target_id": e.get("target_id"), "target_tag": e.get("target_tag"),
                        "target_role": e.get("target_role"), "url": e.get("url")} for e in events])
    ev = ev_schema.frame(ev)
    start = session["started_at_ms"]
    end = session.get("ended_at_ms") or int(ev.ts_ms.max())
    if not session.get("ended_at_ms"):
        warnings.append("La sesión no tiene ended_at_ms: se usó el último evento como fin.")
    s = ev_schema.session_frame([dict(source="extension", session_id=sid, participant_id=participant["id"],
                                      user_group=participant["user_group"], is_human=True,
                                      assistive_tech=participant["assistive_tech"], task_id=session.get("task_id"),
                                      task_group=session.get("task_group"), familiarity=session.get("familiarity"),
                                      difficulty_before=session.get("difficulty_before"),
                                      difficulty_after=session.get("difficulty_after"), success=session.get("success"),
                                      start_ms=start, end_ms=end)])
    row = metrics.compute(s, ev, EXTENSION_CAPABILITIES).iloc[0].to_dict()
    da = (session.get("difficulty_after") or "").lower()
    row["iso_satisfaction_perceived_ease"] = DIFFICULTY_EASE.get(da, np.nan)
    if not row.get("quality_ok"):
        warnings.append("Sesión corta o con pocos eventos (quality_ok = False): la predicción es poco fiable.")
    if session.get("success") is None:
        warnings.append("Sin 'success': la efectividad ISO se imputa con la mediana del entrenamiento.")
    return row, warnings


def _context_onehot(session: dict, participant: dict, warnings: list[str]) -> dict:
    cats = categories()
    vals = dict(user_group=participant["user_group"], assistive_tech_participant=participant["assistive_tech"],
                task_group=session.get("task_group"), familiarity=session.get("familiarity"),
                difficulty_before=session.get("difficulty_before"))
    out = {}
    for var, levels in cats.items():
        v = vals.get(var)
        v = "NA" if v is None else str(v)
        if v not in levels and v != "NA":
            warnings.append(f"{var}='{v}' no existe en el entrenamiento ({levels}); se codifica como desconocido.")
        for lv in levels:
            out[f"ctx_{var}_{lv}"] = 1.0 if lv == v else 0.0
    return out


def build_vector(current: dict, history: list[dict], session: dict, participant: dict, warnings: list[str]) -> dict:
    """Ensambla el vector en el orden exacto de bundle['features'].

    Las variables intra_* son el percentil de la sesión dentro de las sesiones del mismo
    participante (incluida la actual), igual que en el entrenamiento.
    """
    F = bundle()["features"]
    vec = {f: current.get(f, np.nan) for f in F if not f.startswith(("ctx_", "intra_"))}
    vec.update(_context_onehot(session, participant, warnings))
    intra = [f for f in F if f.startswith("intra_")]
    if intra:
        frame = pd.DataFrame(history + [current])
        for f in intra:
            base = f[len("intra_"):]
            col = pd.to_numeric(frame.get(base), errors="coerce") if base in frame else pd.Series([np.nan] * len(frame))
            vec[f] = float(col.rank(pct=True).iloc[-1]) if pd.notna(col.iloc[-1]) else np.nan
        if len(history) < 5:
            warnings.append(f"El participante tiene {len(history)} sesiones previas evaluadas; la normalización "
                            "intra-participante es más fiable con ≥ 5.")
    return {f: (None if pd.isna(vec.get(f, np.nan)) else float(vec[f])) for f in F}


def predict(vector: dict) -> tuple[dict, dict, dict]:
    b = bundle()
    X = np.array([[np.nan if vector[f] is None else vector[f] for f in b["features"]]], dtype=float)
    P = b["model"].predict_proba_frame(X).iloc[0]
    probs = {k[2:]: float(v) for k, v in P.items()}
    thr = {k[2:]: float(v) for k, v in b["thresholds"].items()}
    preds = {h: int(probs[h] >= thr[h]) for h in probs}
    return probs, preds, thr


def jsonable(d: dict) -> dict:
    return json.loads(json.dumps(d, default=lambda o: None if isinstance(o, float) and np.isnan(o) else str(o)))
