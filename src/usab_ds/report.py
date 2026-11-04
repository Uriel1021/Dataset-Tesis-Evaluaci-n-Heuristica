"""Informes Markdown de cada etapa, generados a partir de los CSV producidos.

No contienen cifras escritas a mano: todo se lee de las salidas del pipeline,
de modo que al volver a ejecutarlo los informes se actualizan solos.
"""

from __future__ import annotations

import json

import pandas as pd

from . import config


def _md(df: pd.DataFrame, floatfmt: str = ".3g") -> str:
    def fmt(v):
        if isinstance(v, float):
            return "" if pd.isna(v) else format(v, floatfmt)
        return "" if v is None or (not isinstance(v, (list, dict)) and pd.isna(v)) else str(v).replace("|", "\\|").replace("\n", " ")
    head = "| " + " | ".join(map(str, df.columns)) + " |"
    sep = "|" + "|".join("---" for _ in df.columns) + "|"
    body = ["| " + " | ".join(fmt(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join([head, sep, *body])


def stage1() -> None:
    d = config.REPORT_STAGE1
    if not (d / "resumen_fuentes.csv").exists():
        return
    s = pd.read_csv(d / "resumen_fuentes.csv")
    m = pd.read_csv(d / "menciones_heuristicas.csv").pivot_table(index="source", columns="heuristic", values="mentions").reset_index()
    ev = pd.read_csv(d / "eventos_por_fuente.csv")
    txt = [
        "# Etapa 1 · Perfil de las fuentes",
        "",
        "Generado por `python -m usab_ds stage1`. Cada cifra proviene de leer los archivos reales "
        "(ver `src/usab_ds/profiling.py`, funciones `probe_*`).",
        "",
        "## Resumen por fuente",
        "",
        _md(s[["source", "platform", "unit", "n_files", "size_mb", "n_rows_or_units", "n_participants", "n_interfaces", "notes"]]),
        "",
        "## Menciones textuales de las heurísticas objetivo",
        "",
        "Conteo de apariciones del nombre de la heurística en los archivos de texto de cada fuente. "
        "Es evidencia de *presencia temática*, no una etiqueta.",
        "",
        _md(m),
        "",
        "## Tipos de evento de interacción",
        "",
        _md(ev),
        "",
        "## Archivos de detalle",
        "",
        "- `inventario_archivos.csv`: un renglón por archivo con sha256 (base de la reproducibilidad).",
        "- `esquema_columnas.csv`: tipo, % nulos, únicos, mín/máx/media o valores frecuentes por columna.",
        "- `hechos_fuentes.json`: hechos booleanos que evalúa la etapa 2.",
    ]
    (d / "README.md").write_text("\n".join(txt), encoding="utf-8")


def stage2() -> None:
    d = config.REPORT_STAGE2
    if not (d / "matriz_elegibilidad.csv").exists():
        return
    el = pd.read_csv(d / "matriz_elegibilidad.csv")
    crit = config.load("inclusion_criteria")["criteria"]
    cw = pd.read_csv(d / "crosswalk_heuristicas_iso.csv")
    sh = pd.read_csv(d / "matriz_fuente_heuristica.csv")
    iso = pd.read_csv(d / "matriz_fuente_iso.csv")
    sh = sh[sh.roles != "excluded"]
    txt = [
        "# Etapa 2 · Elegibilidad y correspondencias",
        "",
        "## Criterios",
        "",
        *[f"- **{k}**: {v['description']}" for k, v in crit.items()],
        "",
        "Roles: `behavior` = C1∧C2∧C3∧C5 · `labels` = C1∧C2∧C4∧C5 · `bridge` = C1∧C2∧C6.",
        "",
        "## Matriz de elegibilidad",
        "",
        _md(el.drop(columns=["name"]).replace({True: "✔", False: "✘"})),
        "",
        "## Marco de correspondencia Nielsen ↔ ISO/IEC 25010 ↔ medidas",
        "",
        _md(cw.drop(columns=["refs"])),
        "",
        "`link_evidence`: *normative* = lo establece la norma; *operational* = hipótesis de este trabajo que debe "
        "validarse con la plantilla `plantilla_validacion_expertos.csv` (CVR de Lawshe).",
        "",
        "## Fuente × heurística",
        "",
        _md(sh),
        "",
        "## Fuente × medida ISO/IEC 25022",
        "",
        _md(iso),
    ]
    (d / "README.md").write_text("\n".join(txt), encoding="utf-8")


def stage3() -> None:
    p = config.PROCESSED
    if not (p / "manifest.json").exists():
        return
    man = json.loads((p / "manifest.json").read_text())
    s = pd.read_parquet(p / "sessions.parquet")
    il = pd.read_parquet(p / "interface_labels.parquet")
    rel = pd.read_csv(p / "reliability.csv")
    rel = rel[rel.heuristic.isin(list(config.TARGET_HEURISTICS) + ["all"])]
    main = s[s.include_main]
    iso = ["iso_effectiveness_task_completion", "iso_efficiency_task_time_s", "iso_efficiency_actions",
           "iso_efficiency_time_based", "iso_satisfaction_perceived_ease", "iso_satisfaction_affective_valence"]
    ind = [k for k, v in config.load("indicators")["indicators"].items() if v.get("heuristics")]
    cov = main.groupby("source")[iso + ind].apply(lambda g: (100 * g.notna().mean()).round(0)).T.reset_index(names="column")
    med = main.groupby("source")[iso + ind].median().T.reset_index(names="column")
    grp = s.groupby(["source", "user_group", "assistive_tech"]).agg(
        sesiones=("session_id", "size"), validas=("quality_ok", "sum"),
        exito=("iso_effectiveness_task_completion", "mean"), tiempo_mediana_s=("iso_efficiency_task_time_s", "median")).reset_index()
    vcols = [f"{h}_violation" for h in config.TARGET_HEURISTICS]
    lab = il.groupby(["source", "evaluator_type"]).agg(
        interfaces=("interface_id", "nunique"), **{f"{c}_prev": (c, "mean") for c in vcols}).reset_index()
    txt = [
        "# Etapa 3 · Dataset final `data/processed/usab_v2`",
        "",
        f"Construido: {man['created_utc']} · commit `{man['git_commit']}` · código sin commitear: {man['code_or_config_uncommitted']}",
        "",
        "## Tamaño",
        "",
        _md(pd.DataFrame([man["counts"]["sessions_by_source"], man["counts"]["sessions_main_by_source"]],
                         index=["sesiones", "muestra principal (humanos, quality_ok)"]).reset_index(names="")),
        "",
        f"Juicios heurísticos: {man['counts']['judgements']:,} ({man['counts']['judgements_in_scope']:,} sobre H1/H4/H5/H6) · "
        f"interfaces etiquetadas: {man['counts']['interfaces']} · páginas con rasgos DOM: {man['counts']['pages_static']:,}",
        "",
        "## Nivel 1 · sesiones por grupo de usuario",
        "",
        _md(grp),
        "",
        "### Cobertura (% no nulo) en la muestra principal",
        "",
        "NaN significa que la fuente no captura lo necesario; nunca se imputa.",
        "",
        _md(cov),
        "",
        "### Medianas en la muestra principal",
        "",
        _md(med),
        "",
        "## Nivel 2 · prevalencia de violación por fuente y evaluador",
        "",
        _md(lab),
        "",
        "## Fiabilidad (α de Krippendorff, nominal)",
        "",
        "NaN cuando no hay variación (todas las evaluaciones coinciden en el mismo valor): α no está definido.",
        "",
        _md(rel),
    ]
    (config.REPORT_STAGE3 / "README.md").write_text("\n".join(txt), encoding="utf-8")


def write_all() -> None:
    config.ensure_dirs()
    stage1()
    stage2()
    stage3()
