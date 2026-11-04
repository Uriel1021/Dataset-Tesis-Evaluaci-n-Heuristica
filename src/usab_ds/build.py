"""Etapa 3 · Construcción del dataset final (dos niveles enlazados).

data/processed/usab_v2/
  sessions.(parquet|csv)              Nivel 1 · una fila por sesión de navegador:
                                      contexto de uso, medidas ISO/IEC 25022,
                                      indicadores conductuales, z robustos,
                                      puntajes proxy H1/H4/H5/H6 y rasgos DOM.
  heuristic_evaluations.(parquet|csv) Nivel 2 · tabla larga de juicios heurísticos
                                      (fuente × interfaz × evaluador × heurística).
  interface_labels.(parquet|csv)      Nivel 2 · interfaz × tipo de evaluador con
                                      H1/H4/H5/H6 agregadas + rasgos DOM si hay HTML.
  pages_static.(parquet|csv)          Puente · rasgos DOM por página (sesiones y sitios).
  dashboards_experiment.(parquet|csv) Calidad en uso del experimento Dashboards
                                      (no unible a los logs).
  reliability.csv                     α de Krippendorff por fuente × heurística.
  data_dictionary.csv                 Definición de cada columna.
  manifest.json                       Hashes de entradas/salidas, versiones, parámetros.
"""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from importlib import metadata

import numpy as np
import pandas as pd

from . import config, dom_static, metrics, relevance
from .adapters import a11y_cua, catching, dashboards, p3m, vt_prototypes, web_emotions

BEHAVIOR = (web_emotions, a11y_cua, dashboards)
LABELS = (vt_prototypes, catching, p3m)


# ----------------------------------------------------------------- utilidades
def _sha(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def _save(df: pd.DataFrame, name: str) -> list[dict]:
    out = []
    for ext in ("parquet", "csv"):
        p = config.PROCESSED / f"{name}.{ext}"
        df.to_parquet(p, index=False) if ext == "parquet" else df.to_csv(p, index=False)
        out.append(dict(file=p.name, rows=len(df), columns=df.shape[1], sha256=_sha(p)))
    return out


def _dom_job(item: dict) -> dict:
    feats = dom_static.features_from_file(item["path"])
    return {**{k: v for k, v in item.items() if k != "path"}, "relpath": str(item["path"].relative_to(config.ROOT)), **feats}


# ----------------------------------------------------------------- nivel 1
def build_sessions(log) -> tuple[pd.DataFrame, pd.DataFrame]:
    parts = []
    for mod in BEHAVIOR:
        log(f"  · {mod.SOURCE}: eventos canónicos")
        sess, ev = mod.build()
        ev.to_parquet(config.INTERIM / f"events_{mod.SOURCE}.parquet", index=False)
        log(f"    {len(sess):,} sesiones · {len(ev):,} eventos")
        parts.append(metrics.compute(sess, ev, mod.CAPABILITIES))
        del ev
    df = pd.concat(parts, ignore_index=True)

    # medidas de satisfacción (ISO/IEC 25022)
    df["iso_satisfaction_perceived_ease"] = df["difficulty_after"].map(a11y_cua.perceived_ease).astype("Float64")
    df["iso_satisfaction_affective_valence"] = df.get("emotion_valence_mean")

    # rasgos DOM de las páginas vistas en la sesión (A11y-CUA)
    log("  · rasgos DOM de snapshots A11y-CUA")
    pages = a11y_cua.html_pages()
    with ProcessPoolExecutor() as pool:
        dom = pd.DataFrame(list(pool.map(_dom_job, pages, chunksize=8)))
    feat_cols = list(dom_static.FEATURES)
    per_session = dom.groupby("session_id")[feat_cols].mean().add_suffix("_mean").reset_index()
    per_session["dom_pages"] = dom.groupby("session_id").size().values
    df = df.merge(per_session, on="session_id", how="left")

    df = metrics.add_proxy_scores(df)
    df["include_main"] = df["is_human"].fillna(False).astype(bool) & df["quality_ok"].fillna(False).astype(bool)
    return df, dom


# ----------------------------------------------------------------- nivel 2
def krippendorff_alpha_nominal(units: list[list]) -> float:
    """α nominal (Krippendorff, 2011) para unidades con ≥ 2 valores no nulos."""
    vals = sorted({v for u in units for v in u})
    if len(vals) < 2:
        return np.nan  # sin variación: α no está definido
    idx = {v: i for i, v in enumerate(vals)}
    o = np.zeros((len(vals), len(vals)))
    for u in units:
        m = len(u)
        if m < 2:
            continue
        for i, a in enumerate(u):
            for j, b in enumerate(u):
                if i != j:
                    o[idx[a], idx[b]] += 1 / (m - 1)
    n = o.sum()
    nc = o.sum(axis=1)
    do = n - np.trace(o)
    de = (n * n - (nc ** 2).sum()) / (n - 1)
    return float(1 - do / de) if de else np.nan


def build_labels(log, html_pages: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    long = pd.concat([m.build_labels() for m in LABELS], ignore_index=True)
    log(f"  · {len(long):,} juicios heurísticos de {long.interface_id.nunique()} interfaces")

    # fiabilidad entre evaluaciones (rondas / evaluadores)
    rel = []
    for (src, h, et), g in long.groupby(["source", "heuristic", "evaluator_type"]):
        units = [list(s.dropna().astype(int)) for _, s in g.groupby("interface_id").violation]
        rel.append(dict(source=src, heuristic=h, evaluator_type=et, n_interfaces=sum(len(u) >= 2 for u in units),
                        prevalence=round(float(g.violation.mean()), 3) if g.violation.notna().any() else np.nan,
                        krippendorff_alpha=krippendorff_alpha_nominal(units)))
    p = long[long.source == p3m.SOURCE].pivot_table(index=["interface_id", "heuristic"], columns="evaluator_type",
                                                    values="violation", aggfunc="first")
    rel.append(dict(source=p3m.SOURCE, heuristic="all", evaluator_type="llm vs llm_expert_validated",
                    n_interfaces=len(p), prevalence=np.nan,
                    krippendorff_alpha=krippendorff_alpha_nominal(p[["llm", "llm_expert_validated"]].values.tolist())))
    reliability = pd.DataFrame(rel)

    # agregación por interfaz × tipo de evaluador
    tgt = long[long.in_scope]
    # interface_name NO es clave: cambia entre rondas ("Baking shop" / "Bakery")
    agg = tgt.groupby(["source", "interface_id", "platform", "artifact_evaluated", "fidelity",
                       "evaluator_type", "heuristic"], dropna=False).agg(
        interface_name=("interface_name", lambda s: " | ".join(sorted(set(s.dropna())))),
        n=("violation", "count"), rate=("violation", "mean"), sev=("severity_max", "mean")).reset_index()
    agg["rate"] = agg["rate"].astype(float)
    agg["sev"] = agg["sev"].astype(float)
    agg["majority"] = np.where(agg["rate"] > 0.5, 1, np.where(agg["rate"] < 0.5, 0, np.nan))
    agg.loc[agg["n"] == 0, "majority"] = np.nan
    agg["agreement"] = np.maximum(agg["rate"], 1 - agg["rate"])
    names_by_id = agg.groupby("interface_id").interface_name.first()
    wide = agg.pivot_table(index=["source", "interface_id", "platform", "artifact_evaluated",
                                  "fidelity", "evaluator_type"],
                           columns="heuristic", values=["majority", "rate", "sev", "n", "agreement"], dropna=False)
    names = {"majority": "violation", "rate": "violation_rate", "sev": "severity_mean", "n": "n_judgements",
             "agreement": "agreement"}
    wide.columns = [f"{h}_{names[m]}" for m, h in wide.columns]
    wide = wide.reset_index()
    wide.insert(2, "interface_name", wide.interface_id.map(names_by_id))
    cols = [c for h in config.TARGET_HEURISTICS for c in wide.columns if c.startswith(f"{h}_")]
    wide = wide[[c for c in wide.columns if not c.startswith("H")] + cols]
    wide = wide.dropna(subset=[c for c in cols if c.endswith("_n_judgements")], how="all")

    # rasgos DOM por sitio (Catching): media sobre páginas, por nivel de vínculo
    if len(html_pages):
        feat = list(dom_static.FEATURES)
        site = html_pages.groupby("interface_id").agg(
            dom_pages=("page_id", "size"), dom_match_level=("match_level", lambda s: "|".join(sorted(set(s)))),
            **{f"{c}_mean": (c, "mean") for c in feat}).reset_index()
        wide = wide.merge(site, on="interface_id", how="left")
    return long, wide, reliability


# ----------------------------------------------------------------- diccionario
META_DESC = {
    "source": "Identificador de la fuente (configs/sources.yaml).",
    "session_id": "Identificador único de sesión <fuente>:<id local>.",
    "participant_id": "Participante (seudónimo de la fuente) o nombre del agente.",
    "user_group": "BLV (ciego/baja visión) | sighted | agent | unknown.",
    "is_human": "False para agentes de uso de computadora (CUA).",
    "assistive_tech": "Tecnología de apoyo: none | screen_reader | magnifier | unknown.",
    "agent_condition": "Condición del agente (Default | Magnifier | Screen Reader).",
    "task_id": "Identificador de tarea en la fuente.", "task_title": "Título de la tarea.",
    "task_group": "Categoría de la tarea.", "familiarity": "Familiaridad declarada con la tarea.",
    "difficulty_before": "Dificultad esperada antes de la tarea.", "difficulty_after": "Dificultad percibida tras la tarea.",
    "success": "Éxito de la tarea reportado por la fuente.", "start_ms": "Inicio (epoch ms).", "end_ms": "Fin (epoch ms).",
    "url_domain": "Dominio de la primera URL de la sesión.", "browser": "Navegador.",
    "n_events": "Eventos canónicos en la sesión.", "quality_ok": "Duración ≥ min_session_seconds y eventos ≥ min_session_events.",
    "include_main": "Muestra principal: humano y quality_ok.",
    "emotion_valence_mean": "Valencia media (escala de la fuente).", "emotion_engagement_mean": "Engagement medio (escala de la fuente).",
    "emotion_samples": "Muestras con emoción detectada.", "dom_pages": "Páginas HTML usadas para los rasgos DOM.",
    "dom_match_level": "Solidez del vínculo HTML↔sitio (CONFIRMED | NAME_MATCH).",
    "interface_id": "Identificador de interfaz <fuente>:<id>.", "interface_name": "Nombre original.",
    "platform": "web | prototype.", "artifact_evaluated": "code | screenshot | prototype_image.",
    "fidelity": "Fidelidad del prototipo o 'implemented'.", "evaluator_type": "llm | llm_expert_validated | human.",
    "assistive_tech_participant": "Tecnologías de apoyo detectadas en cualquier tarea del participante (A11y-CUA, R7b).",
    # nivel 2 · tabla larga
    "evaluator_id": "Modelo o evaluador (GPT-4o, GPT-4, GPT-4+expert).",
    "evaluation_round": "Ronda / número de evaluación independiente.",
    "heuristic": "Código Nielsen H1–H10 normalizado con configs/crosswalk.yaml.",
    "heuristic_raw": "Nombre de la heurística tal como aparece en la fuente.",
    "in_scope": "True para H1, H4, H5 y H6.",
    "violation": "1 = al menos un problema con severidad ≥ 1; 0 = negativo; NA = sección no encontrada.",
    "negative_by_absence": "El 0 se infiere porque la heurística no fue reportada (evidencia débil).",
    "severity_max": "Severidad Nielsen máxima reportada (0–4).",
    "n_issues": "Problemas reportados con severidad ≥ 1.",
    "evidence_text": "Extracto (≤ 500 caracteres) de la descripción de los problemas.",
    # puente
    "page_id": "Identificador de página HTML.", "url": "URL de la página (si se conoce).",
    "relpath": "Ruta del HTML relativa a la raíz del proyecto.", "repo": "Repositorio de GitHub de origen (Catching).",
    "match_level": "SESSION_SNAPSHOT (A11y-CUA) | CONFIRMED | NAME_MATCH (Catching).",
    # experimento Dashboards (columnas de la fuente)
    "dashboard": "Dashboard (1–8).", "design_issue": "Problema de diseño manipulado en el experimento.",
    "condition": "Baseline | Intervention.", "question": "Pregunta de la tarea.",
    "iso_effectiveness_answer_correct": "Respuesta correcta (1/0) · ISO/IEC 25022 efectividad.",
    "iso_efficiency_task_time_raw": "Tiempo de respuesta · ISO/IEC 25022 eficiencia (unidad no declarada por la fuente).",
    "SGLT": "Columna original de la fuente; sin diccionario publicado.",
    "avg_others": "Media de NASA-TLX sin 'performance' (calculada por la fuente).",
    "avg_all": "Media de las 6 subescalas NASA-TLX (calculada por la fuente; Hart y Staveland, 1988).",
    **{f"nasa_tlx_{k}": f"NASA-TLX · {k} (Hart y Staveland, 1988) · satisfacción/carga" for k in
       ("mental", "physical", "temporal", "performance", "effort", "frustration")},
}


def data_dictionary(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    cw = config.load("crosswalk")
    ind = config.load("indicators")["indicators"]
    rows = []
    for tname, df in tables.items():
        for c in df.columns:
            base = c.removeprefix("z_").removesuffix("_mean") if c.startswith(("z_", "dom_")) else c
            d = dict(table=tname, column=c, dtype=str(df[c].dtype), non_null_pct=round(100 * df[c].notna().mean(), 1),
                     description=None, iso_characteristic=None, heuristic=None, evidence=None)
            if c in META_DESC:
                d["description"] = META_DESC[c]
            if c in cw["iso_measures"]:
                m = cw["iso_measures"][c]
                d.update(description=m["definition"], iso_characteristic=m["iso_char"], evidence=m["evidence"])
            if base in ind:
                spec = ind[base]
                d.update(description=("z robusto intra-fuente de: " if c.startswith("z_") else "") + spec["definition"],
                         heuristic=", ".join(spec.get("heuristics") or []) or None, evidence=spec["evidence"])
            if base in dom_static.FEATURES:
                h, why = dom_static.FEATURES[base]
                d.update(description=f"Rasgo DOM (media por página): {why}", heuristic=h, evidence="normative (WCAG)" if h else None)
            for h in config.TARGET_HEURISTICS:
                if c.startswith(f"{h}_"):
                    d["heuristic"] = h
                    if c.endswith("_proxy_z"):
                        d.update(description="Índice exploratorio: media de z de los indicadores ligados (no es etiqueta).", evidence="operational")
                    elif c.endswith("_proxy_n_indicators"):
                        d["description"] = "Indicadores disponibles para el índice proxy."
                    elif c.endswith("_violation"):
                        d["description"] = "Violación por mayoría de juicios (rate > 0.5 → 1; = 0.5 → NA)."
                    elif c.endswith("_violation_rate"):
                        d["description"] = "Proporción de juicios que reportan violación."
                    elif c.endswith("_severity_mean"):
                        d["description"] = "Severidad Nielsen 0–4 media."
                    elif c.endswith("_n_judgements"):
                        d["description"] = "Número de juicios no nulos."
                    elif c.endswith("_agreement"):
                        d["description"] = "Acuerdo con la mayoría max(p, 1−p)."
            rows.append(d)
    return pd.DataFrame(rows)


# ----------------------------------------------------------------- etapa 3
def _git_commit() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=config.ROOT, text=True).strip()
    except Exception:
        return None


def _git_dirty() -> bool | None:
    try:
        return bool(subprocess.check_output(["git", "status", "--porcelain", "--", "src", "configs"], cwd=config.ROOT, text=True).strip())
    except Exception:
        return None


def run(log=print) -> dict:
    config.ensure_dirs()
    elig = relevance.eligibility().set_index("source")
    for mod in BEHAVIOR:
        assert "behavior" in elig.loc[mod.SOURCE, "roles"], f"{mod.SOURCE} no cumple los criterios de comportamiento"
    for mod in LABELS:
        assert "labels" in elig.loc[mod.SOURCE, "roles"], f"{mod.SOURCE} no cumple los criterios de etiquetas"

    log("[3/5] Nivel 1 · sesiones de navegador")
    sessions, dom_a11y = build_sessions(log)

    log("[4/5] Nivel 2 · evaluaciones heurísticas + puente HTML")
    with ProcessPoolExecutor() as pool:
        dom_catch = pd.DataFrame(list(pool.map(_dom_job, catching.html_sites(), chunksize=4)))
    long, wide, reliability = build_labels(log, dom_catch)
    pages = pd.concat([dom_a11y.assign(match_level="SESSION_SNAPSHOT"), dom_catch], ignore_index=True)
    experiment = dashboards.experimental_table()

    log("[5/5] Escritura, diccionario y manifiesto")
    tables = {"sessions": sessions, "heuristic_evaluations": long, "interface_labels": wide,
              "pages_static": pages, "dashboards_experiment": experiment}
    outputs = []
    for name, df in tables.items():
        outputs += _save(df, name)
    reliability.to_csv(config.PROCESSED / "reliability.csv", index=False)
    dd = data_dictionary(tables)
    dd.to_csv(config.PROCESSED / "data_dictionary.csv", index=False)
    relevance.run(long)  # matriz fuente × heurística con conteos reales de etiquetas

    inv = pd.read_csv(config.REPORT_STAGE1 / "inventario_archivos.csv")
    used = [m.SOURCE for m in BEHAVIOR + LABELS] + [catching.BRIDGE]
    pkgs = {p: metadata.version(p) for p in ("pandas", "polars", "numpy", "pyarrow", "lxml", "python-docx", "openpyxl", "PyYAML")}
    manifest = dict(
        created_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        git_commit=_git_commit(), code_or_config_uncommitted=_git_dirty(),
        python=platform.python_version(), packages=pkgs,
        configs={p.name: _sha(p) for p in sorted(config.CONFIGS.glob("*.yaml"))},
        params=config.params(),
        inputs=inv[inv.source.isin(used)][["source", "relpath", "size_bytes", "sha256"]].to_dict("records"),
        outputs=outputs,
        counts=dict(
            sessions=len(sessions), sessions_main=int(sessions.include_main.sum()),
            sessions_by_source=sessions.groupby("source").size().to_dict(),
            sessions_main_by_source=sessions[sessions.include_main].groupby("source").size().to_dict(),
            judgements=len(long), judgements_in_scope=int(long.in_scope.sum()),
            interfaces=int(long.interface_id.nunique()), pages_static=len(pages),
        ),
    )
    (config.PROCESSED / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False, default=str))
    return dict(tables=tables, reliability=reliability, dictionary=dd, manifest=manifest)
