"""Etapa 4 · Dataset único de entrenamiento.

data/processed/usab_v2/training/
  training_dataset.(parquet|csv)  una fila por sesión de A11y-CUA con HTML:
                                    X  = interacción + medidas ISO + contexto (one-hot); dom_* se excluyen (fuga)
                                    Y  = y_H1, y_H4, y_H5, y_H6 (rúbrica, 0/1/NA) + severidad
                                    fold = partición agrupada por participante
  feature_spec.json               rol de cada columna (id, group, feature, target, meta)
  README.md                       ficha del dataset

Decisiones:
  * Solo A11y-CUA: es la única fuente con interacciones Y HTML de las páginas
    vistas, condición necesaria para tener X e Y en la misma fila.
  * Y: inspección con rúbrica (configs/rubric.yaml); Y de sesión = mitad o más de las páginas evaluables violan;
    NA si ninguna página fue evaluable o aún no hay etiquetas.
  * No se imputan faltantes: la imputación debe ajustarse dentro de cada fold
    de entrenamiento para no filtrar información del fold de prueba.
  * Folds: 4 grupos por participante, estratificados por user_group (BLV/sighted),
    para que ninguna persona aparezca a la vez en entrenamiento y prueba.
    Los agentes (CUA) quedan con fold = -1 y fuera de la muestra principal.
  * Se excluyen de X los z-scores y los índices proxy (son transformaciones
    de las mismas variables) y los identificadores.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from . import config, dom_static

OUT = config.PROCESSED / "training"
CONTEXT = ["user_group", "assistive_tech_participant", "task_group", "familiarity", "difficulty_before"]
ISO_FEATURES = ["iso_efficiency_task_time_s", "iso_efficiency_actions"]
ISO_OUTCOMES = ["iso_effectiveness_task_completion", "iso_efficiency_time_based", "iso_satisfaction_perceived_ease"]
N_FOLDS = 4


def _folds(df: pd.DataFrame) -> pd.Series:
    fold = pd.Series(-1, index=df.index, dtype="int64")
    hum = df[df.is_human.fillna(False).astype(bool)]
    for _, g in hum.groupby("user_group"):
        for i, p in enumerate(sorted(g.participant_id.unique())):
            fold[df.participant_id == p] = i % N_FOLDS
    return fold


def build(log=print, label_source: str = "rubric") -> pd.DataFrame:
    OUT.mkdir(parents=True, exist_ok=True)
    s = pd.read_parquet(config.PROCESSED / "sessions.parquet")
    s = s[(s.source == "S02_a11y_cua") & s.quality_ok & s.dom_pages.notna()].copy()

    # ---- Y: inspección con rúbrica (configs/rubric.yaml) o, si se pide, etiquetas silver por LLM
    src = {"rubric": "rubric_page_labels.parquet", "silver": "silver_page_labels.parquet"}[label_source]
    lab_path = config.PROCESSED / src
    if lab_path.exists():
        pl = pd.read_parquet(lab_path)
        pl = pl[(pl.kind == "a11y") & pl.heuristic.notna()]
        pl = pl.assign(v=pd.to_numeric(pl.violation, errors="coerce"))
        agg = pl.groupby(["session_id", "heuristic"]).agg(
            rate=("v", "mean"), any=("v", "max"), sev=("severity_max", "max"), pages_assessed=("v", "count")).reset_index()
        # Y principal: la mitad o más de las páginas evaluables de la sesión violan la heurística.
        # (con "alguna página" la etiqueta crecería mecánicamente con el número de páginas visitadas)
        agg["y"] = (agg.rate >= 0.5).astype(float).where(agg.rate.notna())
        wide = agg.pivot(index="session_id", columns="heuristic", values=["y", "any", "rate", "sev", "pages_assessed"])
        names = {"y": "y", "any": "y_any", "rate": "y_rate", "sev": "y_sev", "pages_assessed": "pages_assessed"}
        wide.columns = [f"{names[a]}_{h}" for a, h in wide.columns]
        s = s.merge(wide.reset_index(), on="session_id", how="left")
        status = {"rubric": "rúbrica de inspección (configs/rubric.yaml)", "silver": "silver (LLM)"}[label_source]
    else:
        status = f"pendiente: falta {src}"
    for h in config.TARGET_HEURISTICS:
        for pre in ("y", "y_any", "y_rate", "y_sev", "pages_assessed"):
            if f"{pre}_{h}" not in s:
                s[f"{pre}_{h}"] = np.nan
        s[f"y_{h}"] = pd.to_numeric(s[f"y_{h}"], errors="coerce").astype("Int64")
        s[f"y_any_{h}"] = pd.to_numeric(s[f"y_any_{h}"], errors="coerce").astype("Int64")
    s["label_status"] = np.where(s[[f"y_{h}" for h in config.TARGET_HEURISTICS]].notna().any(axis=1), "labeled", "unlabeled")

    # ---- X
    ind = config.load("indicators")["indicators"]
    behav = [k for k in ind if k in s]
    dom = [f"{k}_mean" for k in dom_static.FEATURES if f"{k}_mean" in s] + ["dom_pages"]
    ctx = pd.get_dummies(s[CONTEXT].fillna("NA").astype(str), prefix=[f"ctx_{c}" for c in CONTEXT], dtype="int8")
    s = pd.concat([s.reset_index(drop=True), ctx.reset_index(drop=True)], axis=1)
    # Los rasgos DOM NO entran en X: Y se obtiene del mismo HTML y el modelo aprendería la regla (fuga de información).
    features = behav + ISO_FEATURES + ISO_OUTCOMES + list(ctx.columns)
    # quitar columnas sin información en esta tabla
    dropped = [c for c in features if s[c].notna().sum() == 0 or s[c].nunique(dropna=True) <= 1]
    features = [c for c in features if c not in dropped]
    for c in features:
        s[c] = pd.to_numeric(s[c], errors="coerce").astype("float64")

    s["fold"] = _folds(s)
    s["include_main"] = s.is_human.fillna(False).astype(bool)
    ids = ["session_id", "participant_id", "task_id", "source"]
    meta = ["user_group", "assistive_tech_participant", "is_human", "include_main", "label_status", "task_title", "url_domain"]
    targets = [f"y_{h}" for h in config.TARGET_HEURISTICS]
    aux = [f"{pre}_{h}" for pre in ("y_any", "y_rate", "y_sev", "pages_assessed") for h in config.TARGET_HEURISTICS]
    leak = [c for c in dom if c in s]
    df = s[ids + ["fold"] + meta + targets + aux + features + leak]
    for ext in ("parquet", "csv"):
        p = OUT / f"training_dataset.{ext}"
        df.to_parquet(p, index=False) if ext == "parquet" else df.to_csv(p, index=False)

    spec = dict(
        label_status=status, unit="participante × tarea (A11y-CUA) con snapshot HTML",
        id_columns=ids, group_column="participant_id", fold_column="fold", n_folds=N_FOLDS,
        meta_columns=meta, target_columns=targets, auxiliary_target_columns=aux,
        feature_columns=features,
        feature_groups=dict(
            behavior=[c for c in features if c in behav], iso_process=[c for c in features if c in ISO_FEATURES],
            iso_outcome=[c for c in features if c in ISO_OUTCOMES],
            context=[c for c in features if c.startswith("ctx_")]),
        excluded_from_X_leakage=leak,
        dropped_no_information=dropped,
        notes=[
            "No hay imputación: ajústela dentro de cada fold de entrenamiento.",
            "Las columnas dom_* están en el archivo solo para análisis: NO deben usarse como X (Y proviene del mismo HTML).",
            "y_H* = mitad o más de las páginas evaluables violan; y_any_H* = alguna página; y_rate_H* = proporción.",
            "iso_outcome (éxito, facilidad percibida) son resultados de la tarea: pruebe el modelo con y sin ellos.",
            "Muestra principal: include_main == True (humanos). Agentes con fold = -1.",
            "Evalúe con validación cruzada agrupada por participant_id usando la columna fold.",
        ],
    )
    (OUT / "feature_spec.json").write_text(json.dumps(spec, indent=2, ensure_ascii=False))
    _card(df, spec)
    log(f"  training_dataset: {len(df)} filas ({int(df.include_main.sum())} humanas) · {len(features)} variables X · "
        f"etiquetas: {status}")
    return df


def _card(df: pd.DataFrame, spec: dict) -> None:
    from .report import _md
    main = df[df.include_main]
    t = [{"heuristic": h, "etiquetadas": int(main[f"y_{h}"].notna().sum()),
          "prevalencia": main[f"y_{h}"].astype("Float64").mean()} for h in config.TARGET_HEURISTICS]
    f = main.groupby("fold").agg(filas=("session_id", "size"), participantes=("participant_id", "nunique")).reset_index()
    cov = pd.DataFrame([{"grupo": g, "variables": len(cols),
                         "cobertura_media_%": round(100 * main[cols].notna().mean().mean(), 1) if cols else None}
                        for g, cols in spec["feature_groups"].items()])
    txt = [
        "# Dataset de entrenamiento (`training_dataset`)",
        "",
        f"Estado de las etiquetas: **{spec['label_status']}**",
        "",
        f"- Unidad: {spec['unit']}",
        f"- Filas: {len(df)} ({len(main)} humanas en la muestra principal, {main.participant_id.nunique()} participantes)",
        f"- Variables X: {len(spec['feature_columns'])}",
        "",
        "## Objetivos (muestra principal)",
        "",
        _md(pd.DataFrame(t)),
        "",
        "## Folds agrupados por participante",
        "",
        _md(f),
        "",
        "## Grupos de variables",
        "",
        _md(cov),
        "",
        "## Uso",
        "",
        "```python",
        "import json, pandas as pd",
        "df = pd.read_parquet('data/processed/usab_v2/training/training_dataset.parquet')",
        "spec = json.load(open('data/processed/usab_v2/training/feature_spec.json'))",
        "main = df[df.include_main & df['y_H1'].notna()]",
        "X, y, folds = main[spec['feature_columns']], main['y_H1'].astype(int), main['fold']",
        "# for k in range(spec['n_folds']): train = folds != k; test = folds == k",
        "```",
        "",
        "## Notas",
        "",
        *[f"- {n}" for n in spec["notes"]],
    ]
    (OUT / "README.md").write_text("\n".join(txt), encoding="utf-8")
