"""Etapa 1 · Perfil de las fuentes.

Para cada fuente registrada en configs/sources.yaml produce:
  inventario_archivos.csv   un renglón por archivo (ruta, extensión, tamaño, sha256)
  esquema_columnas.csv      perfil por columna de cada archivo tabular
  eventos_por_fuente.csv    tipos de evento de interacción y sus conteos
  menciones_heuristicas.csv menciones textuales de H1/H4/H5/H6 por fuente
  resumen_fuentes.csv       hechos por fuente (unidad, n, participantes, …)
  hechos_fuentes.json       hechos booleanos que usa la etapa 2

Los "hechos" se obtienen con una sonda (probe_*) por fuente que inspecciona
los datos reales; no se copian de la documentación de los autores.
"""

from __future__ import annotations

import collections
import hashlib
import json
import re
import zipfile
from pathlib import Path

import pandas as pd
import polars as pl

from . import config

HASH_CACHE = config.INTERIM / "hash_cache.json"
TEXT_EXT = {".csv", ".json", ".md", ".txt", ".ipynb", ".rtf", ".docx", ".xlsx"}


# ----------------------------------------------------------------- utilidades
def sha256(path: Path, cache: dict) -> str:
    st = path.stat()
    key = f"{path}|{st.st_size}|{int(st.st_mtime)}"
    if key not in cache:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 22), b""):
                h.update(chunk)
        cache[key] = h.hexdigest()
    return cache[key]


def _files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    return sorted(p for p in root.rglob("*") if p.is_file() and p.name != ".DS_Store" and "__MACOSX" not in p.parts)


def inventory(with_hash: bool = True) -> pd.DataFrame:
    cache = json.loads(HASH_CACHE.read_text()) if HASH_CACHE.exists() else {}
    rows = []
    for sid, src in config.sources().items():
        root = config.ROOT / src["path"]
        if not root.exists():
            rows.append(dict(source=sid, relpath=None, ext=None, size_bytes=0, sha256=None, exists=False))
            continue
        for f in _files(root):
            rows.append(dict(source=sid, relpath=str(f.relative_to(config.ROOT)), ext=f.suffix.lower() or "(none)",
                             size_bytes=f.stat().st_size, sha256=sha256(f, cache) if with_hash else None, exists=True))
    HASH_CACHE.parent.mkdir(parents=True, exist_ok=True)
    HASH_CACHE.write_text(json.dumps(cache))
    return pd.DataFrame(rows)


def _profile_frame(df: pd.DataFrame, sid: str, relpath: str) -> list[dict]:
    out = []
    for c in df.columns:
        s = df[c]
        num = pd.to_numeric(s, errors="coerce")
        is_num = num.notna().sum() >= 0.9 * s.notna().sum() and s.notna().any()
        top = s.dropna().astype(str).value_counts().head(3)
        out.append(dict(
            source=sid, file=relpath, column=str(c), dtype="numeric" if is_num else "text",
            n=len(s), null_pct=round(100 * s.isna().mean(), 2), n_unique=s.nunique(dropna=True),
            min=num.min() if is_num else None, max=num.max() if is_num else None,
            mean=round(num.mean(), 4) if is_num else None,
            top_values="; ".join(f"{k[:40]}({v})" for k, v in top.items()) if not is_num else None,
        ))
    return out


def schema_profile() -> pd.DataFrame:
    rows: list[dict] = []
    for sid, src in config.sources().items():
        root = config.ROOT / src["path"]
        if not root.exists():
            continue
        for f in _files(root):
            rel = str(f.relative_to(config.ROOT))
            try:
                if sid == "S01_web_emotions_28489601":
                    rows += _profile_large_csv(f, sid, rel)
                elif f.suffix.lower() == ".csv" and f.stat().st_size < 200e6:
                    sep = ";" if f.open(encoding="utf-8", errors="replace").readline().count(";") > 2 else ","
                    rows += _profile_frame(pd.read_csv(f, sep=sep, low_memory=False), sid, rel)
                elif f.suffix.lower() == ".xlsx":
                    for sheet, df in pd.read_excel(f, sheet_name=None).items():
                        rows += _profile_frame(df, sid, f"{rel}::{sheet}")
            except Exception as exc:  # se registra, no se oculta
                rows.append(dict(source=sid, file=rel, column="<error>", dtype=type(exc).__name__, top_values=str(exc)[:200]))
    return pd.DataFrame(rows)


def _profile_large_csv(f: Path, sid: str, rel: str) -> list[dict]:
    if f.name == "aggregates.csv":  # 7 GB: solo esquema y conteo de filas
        lf = pl.scan_csv(f, infer_schema_length=1000)
        cols = lf.collect_schema().names()
        n = lf.select(pl.len()).collect().item()
        groups = collections.Counter(c.split(".")[0] for c in cols)
        return [dict(source=sid, file=rel, column=f"<{g}.*>", dtype="grupo de columnas", n=n,
                     top_values=f"{k} columnas") for g, k in groups.items()]
    lf = pl.scan_csv(f, infer_schema_length=10000, schema_overrides={c: pl.Float64 for c in (
        "emotions.joy", "emotions.sadness", "emotions.anger")})
    sch = lf.collect_schema()
    exprs = []
    for c, t in sch.items():
        exprs += [pl.col(c).null_count().alias(f"{c}|null"), pl.col(c).n_unique().alias(f"{c}|nu")]
        if t.is_numeric():
            exprs += [pl.col(c).min().alias(f"{c}|min"), pl.col(c).max().alias(f"{c}|max"), pl.col(c).mean().alias(f"{c}|mean")]
        if t == pl.Boolean:
            exprs += [pl.col(c).sum().alias(f"{c}|true")]
    st = lf.select([pl.len().alias("__n"), *exprs]).collect(engine="streaming").row(0, named=True)
    n = st["__n"]
    out = []
    for c, t in sch.items():
        out.append(dict(source=sid, file=rel, column=c, dtype=str(t), n=n, null_pct=round(100 * st[f"{c}|null"] / n, 2),
                        n_unique=st[f"{c}|nu"], min=st.get(f"{c}|min"), max=st.get(f"{c}|max"),
                        mean=st.get(f"{c}|mean"),
                        top_values=f"true={st[f'{c}|true']}" if f"{c}|true" in st else None))
    return out


def _text_of(f: Path) -> str:
    ext = f.suffix.lower()
    try:
        if ext == ".docx":
            import docx
            return "\n".join(p.text for p in docx.Document(f).paragraphs)
        if ext == ".xlsx":
            return "\n".join(df.astype(str).to_csv() for df in pd.read_excel(f, sheet_name=None, header=None).values())
        return f.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def heuristic_mentions() -> pd.DataFrame:
    """Cuenta menciones textuales de las heurísticas objetivo (evidencia, no etiqueta)."""
    cw = config.load("crosswalk")["heuristics"]
    pats = {h: re.compile("|".join(re.escape(a) for a in [v["name"], *v["aliases"]]), re.I) for h, v in cw.items()}
    rows = []
    for sid, src in config.sources().items():
        root = config.ROOT / src["path"]
        files = [f for f in _files(root) if f.suffix.lower() in TEXT_EXT and f.stat().st_size < 30e6] if root.exists() else []
        files = [f for f in files if "a11y_tree" not in f.name][:2000]
        cnt = collections.Counter()
        nfiles = collections.Counter()
        for f in files:
            txt = _text_of(f)
            for h, p in pats.items():
                k = len(p.findall(txt))
                cnt[h] += k
                nfiles[h] += k > 0
        for h in pats:
            rows.append(dict(source=sid, heuristic=h, mentions=cnt[h], files_with_mention=nfiles[h], files_scanned=len(files)))
    return pd.DataFrame(rows)


# ----------------------------------------------------------------- sondas
def probe_S01():
    lf = pl.scan_csv(config.source_path("S01_web_emotions_28489601") / "interactions.csv",
                     schema_overrides={"emotions.joy": pl.Float64, "emotions.sadness": pl.Float64, "emotions.anger": pl.Float64})
    st = lf.select(pl.len().alias("rows"), pl.col("user_id").n_unique().alias("users"), pl.col("url").n_unique().alias("urls"),
                   pl.col("timestamp").min().alias("t0"), pl.col("timestamp").max().alias("t1"),
                   pl.col("mouse.clicks").sum().alias("click_samples"), pl.col("keyboard").sum().alias("key_samples"),
                   pl.col("emotions.exist").sum().alias("emotion_samples")).collect(engine="streaming").row(0, named=True)
    dt = lf.select(pl.col("timestamp").diff().over("user_id").median()).collect(engine="streaming").item()
    return dict(
        facts=dict(readable=True, web_context=True, has_timestamped_interactions=True, has_target_heuristic_labels=False,
                   disaggregated=True, has_html=False),
        unit="usuario × visita", n_rows=st["rows"], n_participants=st["users"], n_interfaces=st["urls"],
        period=f"{pd.to_datetime(st['t0'], unit='ms').date()} – {pd.to_datetime(st['t1'], unit='ms').date()}",
        sampling_ms_median=dt,
        events={"click_samples": st["click_samples"], "key_samples": st["key_samples"], "emotion_samples": st["emotion_samples"]},
        notes="Muestreo de estado ~100 ms (no log de eventos). Sin etiquetas de usabilidad ni tareas; incluye emociones faciales.",
    )


def probe_S02():
    from .adapters import a11y_cua
    root = config.source_path("S02_a11y_cua")
    groups, browser, success, apps = collections.Counter(), collections.Counter(), collections.Counter(), collections.Counter()
    ev = collections.Counter()
    for task_dir, meta in a11y_cua.iter_task_dirs(root):
        g = task_dir.relative_to(root).parts[0]
        m = json.loads(meta.read_text(encoding="utf-8"))
        groups[g] += 1
        success[(g, m["task"].get("success"))] += 1
        a = [x.get("app", "").lower() for x in m["session"].get("applications", [])]
        apps.update(a)
        browser[g] += any(x in a11y_cua.BROWSERS for x in a)
    for f in root.glob("*/*/*/web_logs/web_tab*.json"):
        if not f.name.endswith("_a11y_tree.json"):
            ev.update("web:" + i.get("type", "?") for i in json.loads(f.read_text(encoding="utf-8")).get("interactions", []))
    for f in root.glob("*/*/*/*.exe.json"):
        if any(b in f.name for b in a11y_cua.BROWSERS):
            for e in json.loads(f.read_text(encoding="utf-8")):
                if isinstance(e, dict):
                    t = e.get("event")
                    ev["os_browser:" + (t.get("type") if isinstance(t, dict) else str(t))] += 1
    n_html = sum(1 for _ in root.glob("*/*/*/web_logs/*.html"))
    return dict(
        facts=dict(readable=True, web_context=True, has_timestamped_interactions=True, has_target_heuristic_labels=False,
                   disaggregated=True, has_html=n_html > 0),
        unit="participante × tarea", n_rows=sum(groups.values()),
        n_participants=sum(1 for g in ("BLVU", "SU") for _ in (root / g).iterdir() if _.is_dir()),
        n_interfaces=None, tasks_by_group=dict(groups), tasks_with_browser=dict(browser),
        success_by_group={f"{g}|{s}": n for (g, s), n in success.items()}, n_html_snapshots=n_html,
        top_apps=dict(apps.most_common(8)), events=dict(ev),
        notes="Humanos ciegos/baja visión (BLVU) y videntes (SU) + agentes CUA (Claude Sonnet 4.5, Qwen3-VL). "
              "Tiene éxito de tarea y dificultad percibida; sin etiquetas Nielsen.",
    )


def probe_S03():
    from .adapters import vt_prototypes
    lab = vt_prototypes.build_labels()
    root = config.source_path("S03_vt_llm_prototypes_29042675")
    irr = pd.read_csv(root / "IRR_Results.csv")
    return dict(
        facts=dict(readable=True, web_context=True, has_timestamped_interactions=False, has_target_heuristic_labels=True,
                   disaggregated=True, has_html=False),
        unit="prototipo × ronda × heurística", n_rows=len(lab), n_interfaces=lab.interface_id.nunique(),
        n_documents=sum(1 for _ in root.rglob("*.docx")),
        labels_found_pct=round(100 * lab.violation.notna().mean(), 1),
        target_violation_rate={h: round(float(v), 3) for h, v in lab[lab.in_scope].groupby("heuristic").violation.mean().items()},
        irr_columns=len(irr.columns),
        notes="Evaluador: GPT-4o sobre imágenes de prototipos Figma/Behance (alta y baja fidelidad). "
              "IRR_Results.csv tiene estructura mixta y no se usa como etiqueta.",
    )


def probe_S04():
    from .adapters import catching
    lab = catching.build_labels()
    html = catching.html_sites()
    return dict(
        facts=dict(readable=True, web_context=True, has_timestamped_interactions=False, has_target_heuristic_labels=True,
                   disaggregated=True, has_html=bool(html)),
        unit="sitio × evaluación × heurística", n_rows=len(lab), n_interfaces=lab.interface_id.nunique(),
        evaluations_per_site=round(lab.groupby("interface_id").evaluation_round.nunique().mean(), 2),
        target_violation_rate={h: round(float(v), 3) for h, v in lab[lab.in_scope].groupby("heuristic").violation.mean().items()},
        sites_with_recovered_html=len({h["interface_id"] for h in html}), html_pages=len(html),
        notes="Tres evaluaciones GPT-4o del código de 30 plantillas web públicas.",
    )


def probe_S04b():
    from .adapters import catching
    html = catching.html_sites()
    lv = collections.Counter(h["match_level"] for h in html)
    return dict(facts=dict(readable=bool(html), web_context=True, has_timestamped_interactions=False,
                           has_target_heuristic_labels=False, disaggregated=True, has_html=bool(html)),
                unit="página HTML", n_rows=len(html), n_interfaces=len({h["interface_id"] for h in html}),
                match_levels=dict(lv), notes="HTML de repositorios recuperados en la v1; match_level indica la solidez del vínculo.")


def probe_S05():
    root = config.source_path("S05_serene")
    gt = pd.read_csv(root / "ground-truth.csv", sep=";")
    ans = json.loads((root / "answers.json").read_text(encoding="utf-8"))
    met = pd.read_csv(root / "metrics.csv")
    return dict(
        facts=dict(readable=True, web_context=True, has_timestamped_interactions=False, has_target_heuristic_labels=False,
                   disaggregated=True, has_html=False),
        unit="problema de usabilidad / participante", n_rows=len(gt), n_interfaces=gt.Webpage.nunique(),
        n_participants=len(ans), conditions=dict(collections.Counter(a.get("condition") for a in ans)),
        metric_columns=[c for c in met.columns if c.startswith("M")],
        notes="Problemas con severidad y elemento de UI, pero SIN asignación a heurísticas Nielsen; M1–M8 sin diccionario en los archivos.",
    )


def probe_S06():
    from .adapters import p3m
    lab = p3m.build_labels()
    return dict(
        facts=dict(readable=True, web_context=True, has_timestamped_interactions=False, has_target_heuristic_labels=True,
                   disaggregated=True, has_html=False),
        unit="captura × heurística", n_rows=len(lab), n_interfaces=lab.interface_id.nunique(),
        target_violation_rate={f"{h}|{t}": round(float(v), 3) for (h, t), v in
                               lab[lab.in_scope].groupby(["heuristic", "evaluator_type"]).violation.mean().items()},
        notes="Defectos propuestos por GPT-4 con validación experta (Is it a defect?). Solo positivos explícitos.",
    )


def probe_S07():
    x = pd.ExcelFile(config.source_path("S07_phr") / "Results-PHRs-usab-sust.xlsx")
    return dict(facts=dict(readable=True, web_context=True, has_timestamped_interactions=False, has_target_heuristic_labels=False,
                           disaggregated=False, has_html=False),
                unit="portal × tarea (agregado)", sheets=x.sheet_names,
                notes="Solo correlaciones y t-tests agregados; heurísticas H01–H08 adaptadas a PHR, no equivalentes a Nielsen.")


def probe_S08():
    from .adapters import dashboards
    ev = collections.Counter()
    n = 0
    with zipfile.ZipFile(dashboards._zip_path()) as zf:
        for name in zf.namelist():
            if name.endswith(".json") and not name.startswith("__MACOSX"):
                n += 1
                ev.update(re.findall(r'"event"\s*:\s*"(\w+)"', zf.read(name).decode("utf-8", errors="replace")))
    exp = dashboards.experimental_table()
    return dict(
        facts=dict(readable=True, web_context=True, has_timestamped_interactions=True, has_target_heuristic_labels=False,
                   disaggregated=True, has_html=False),
        unit="sesión de navegador", n_rows=n, n_participants_experiment=exp.participant_id.nunique(),
        experimental_rows=len(exp), design_issues=sorted(exp.design_issue.unique()), events=dict(ev),
        notes="Logs DOM completos. La tabla experimental (exactitud, tiempo, NASA-TLX) no comparte clave con los logs.",
    )


def probe_S09():
    return dict(facts=dict(readable=False, web_context=True, has_timestamped_interactions=False,
                           has_target_heuristic_labels=False, disaggregated=False, has_html=False),
                unit=None, notes="Solo el PDF del artículo; no hay datos estructurados.")


def probe_S10():
    root = config.source_path("S10_uicrit_rico")
    u = pd.read_csv(root / "uicrit_public.csv")
    return dict(facts=dict(readable=True, web_context=False, has_timestamped_interactions=False,
                           has_target_heuristic_labels=False, disaggregated=True, has_html=False),
                unit="pantalla Android × tarea", n_rows=len(u), n_interfaces=u.rico_id.nunique(),
                rating_columns=[c for c in u.columns if "rating" in c or c in ("learnability", "efficency")],
                notes="Plataforma móvil (Android/RICO); ratings y críticas libres, sin heurísticas Nielsen explícitas.")


def probe_S11():
    root = config.source_path("S11_zenodo_21891322")
    return dict(facts=dict(readable=True, web_context=True, has_timestamped_interactions=False,
                           has_target_heuristic_labels=False, disaggregated=False, has_html=False),
                unit="interfaz", n_rows=len(list(root.glob("*.png"))),
                notes="Capturas, un notebook y un PDF; no hay tabla de juicios heurísticos reutilizable.")


def probe_S12():
    root = config.source_path("S12_delfi22")
    return dict(facts=dict(readable=True, web_context=False, has_timestamped_interactions=False,
                           has_target_heuristic_labels=False, disaggregated=True, has_html=False),
                unit="actividad LMS", n_rows=sum(len(pd.read_csv(f, sep=";")) for f in root.rglob("*.csv")),
                notes="Configuración de tareas y cuestionarios de Moodle; no evalúa una interfaz ni registra interacción.")


PROBES = {
    "S01_web_emotions_28489601": probe_S01, "S02_a11y_cua": probe_S02, "S03_vt_llm_prototypes_29042675": probe_S03,
    "S04_catching_ux_flaws": probe_S04, "S04b_catching_html": probe_S04b, "S05_serene": probe_S05, "S06_p3m": probe_S06,
    "S07_phr": probe_S07, "S08_dashboards": probe_S08, "S09_cultural_heritage": probe_S09, "S10_uicrit_rico": probe_S10,
    "S11_zenodo_21891322": probe_S11, "S12_delfi22": probe_S12,
}


# ----------------------------------------------------------------- etapa 1
def run(with_hash: bool = True) -> dict:
    config.ensure_dirs()
    out = config.REPORT_STAGE1
    inv = inventory(with_hash)
    inv.to_csv(out / "inventario_archivos.csv", index=False)
    schema_profile().to_csv(out / "esquema_columnas.csv", index=False)
    heuristic_mentions().to_csv(out / "menciones_heuristicas.csv", index=False)

    facts, summary, events = {}, [], []
    for sid, src in config.sources().items():
        info = PROBES[sid]()
        facts[sid] = info["facts"]
        sub = inv[inv.source == sid]
        exts = sub.ext.value_counts().head(6).to_dict()
        summary.append(dict(
            source=sid, name=src["name"], platform=src["platform"], unit=info.get("unit"),
            n_files=int(sub.exists.sum()), size_mb=round(sub.size_bytes.sum() / 1e6, 1),
            extensions="; ".join(f"{k}:{v}" for k, v in exts.items()),
            n_rows_or_units=info.get("n_rows"), n_participants=info.get("n_participants"),
            n_interfaces=info.get("n_interfaces"), reference=src.get("reference"), license=src.get("license"),
            notes=info.get("notes"),
            details=json.dumps({k: v for k, v in info.items() if k not in {"facts", "events", "notes", "unit"}},
                               ensure_ascii=False, default=str),
        ))
        for k, v in (info.get("events") or {}).items():
            events.append(dict(source=sid, event_type=k, count=v))
    pd.DataFrame(summary).to_csv(out / "resumen_fuentes.csv", index=False)
    pd.DataFrame(events).to_csv(out / "eventos_por_fuente.csv", index=False)
    (out / "hechos_fuentes.json").write_text(json.dumps(facts, indent=2, ensure_ascii=False))
    return facts
