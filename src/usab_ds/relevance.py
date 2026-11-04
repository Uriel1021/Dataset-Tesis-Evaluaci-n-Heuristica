"""Etapa 2 · Elegibilidad de fuentes y correspondencias Nielsen ↔ ISO.

Salidas en reports/02_relevancia:
  matriz_elegibilidad.csv          fuente × criterio (C1–C6) → rol asignado y motivo
  crosswalk_heuristicas_iso.csv    tabla plana del marco de correspondencia
  matriz_fuente_heuristica.csv     fuente × heurística: etiquetas, indicadores y rasgos DOM disponibles
  matriz_fuente_iso.csv            fuente × medida ISO/IEC 25022 calculable
  plantilla_validacion_expertos.csv  ítems para validar el crosswalk (CVR de Lawshe)
"""

from __future__ import annotations

import json

import pandas as pd

from . import config, dom_static
from .adapters import a11y_cua, dashboards, web_emotions

BEHAVIOR_ADAPTERS = {
    web_emotions.SOURCE: web_emotions.CAPABILITIES,
    a11y_cua.SOURCE: a11y_cua.CAPABILITIES,
    dashboards.SOURCE: dashboards.CAPABILITIES,
}
LABEL_SOURCES = ("S03_vt_llm_prototypes_29042675", "S04_catching_ux_flaws", "S06_p3m")

# qué atributo de sesión necesita cada medida ISO
ISO_REQUIRES = {
    "iso_effectiveness_task_completion": "success",
    "iso_efficiency_task_time_s": "duration",
    "iso_efficiency_actions": "actions",
    "iso_efficiency_time_based": "success",
    "iso_satisfaction_perceived_ease": "difficulty_after",
    "iso_satisfaction_affective_valence": "emotion",
}
SESSION_ATTRS = {
    web_emotions.SOURCE: {"duration", "actions", "emotion"},
    a11y_cua.SOURCE: {"duration", "actions", "success", "difficulty_after"},
    dashboards.SOURCE: {"duration", "actions"},
}


def _facts() -> dict:
    p = config.REPORT_STAGE1 / "hechos_fuentes.json"
    if not p.exists():
        raise FileNotFoundError("Ejecute primero la etapa 1 (python -m usab_ds stage1)")
    return json.loads(p.read_text())


def eligibility() -> pd.DataFrame:
    crit = config.load("inclusion_criteria")
    facts = _facts()
    rows = []
    for sid, f in facts.items():
        r = {"source": sid, "name": config.sources()[sid]["name"]}
        for cid, c in crit["criteria"].items():
            r[cid] = bool(f.get(c["fact"]))
        roles, why = [], []
        for role, rule in crit["roles"].items():
            missing = [c for c in rule["all_of"] if not r[c]]
            if not missing:
                roles.append(role)
            else:
                why.append(f"{role}: falla {', '.join(missing)}")
        r["roles"] = "+".join(roles) if roles else "excluded"
        r["motivo"] = "cumple todos los criterios del rol" if roles else "; ".join(why)
        rows.append(r)
    return pd.DataFrame(rows)


def crosswalk_table() -> pd.DataFrame:
    cw = config.load("crosswalk")
    ind = config.load("indicators")["indicators"]
    rows = []
    for h, spec in cw["heuristics"].items():
        inds = [k for k, v in ind.items() if h in (v.get("heuristics") or [])]
        doms = [k for k, (hh, _) in dom_static.FEATURES.items() if hh == h]
        for link in spec["iso25010"]:
            rows.append(dict(
                heuristic=h, heuristic_name=spec["name"], heuristic_name_es=spec["name_es"],
                iso25010_2011=f"{link['char_2011']} › {link['sub_2011']}",
                iso25010_2023=f"{link['char_2023']} › {link['sub_2023']}",
                link_evidence=link["evidence"], quality_in_use=", ".join(spec["quality_in_use"]),
                wcag=", ".join(spec["wcag"]), behavioral_indicators=", ".join(inds), dom_features=", ".join(doms),
                refs="; ".join(cw["references"][r] for r in spec["refs"]),
            ))
    return pd.DataFrame(rows)


def _caps_satisfied(requires: list[str], caps: set) -> bool:
    return all(r == "any" or r in caps for r in requires)


def source_heuristic_matrix(labels: pd.DataFrame | None = None) -> pd.DataFrame:
    ind = config.load("indicators")["indicators"]
    elig = eligibility().set_index("source")
    rows = []
    for sid in elig.index:
        caps = BEHAVIOR_ADAPTERS.get(sid, set())
        for h in config.TARGET_HEURISTICS:
            linked = [k for k, v in ind.items() if h in (v.get("heuristics") or [])]
            ok = [k for k in linked if caps and _caps_satisfied(ind[k]["requires"], caps)]
            n_lab = None
            if labels is not None and sid in LABEL_SOURCES:
                sub = labels[(labels.source == sid) & (labels.heuristic == h)]
                n_lab = int(sub.violation.notna().sum())
            has_html = bool(elig.loc[sid, "C6_html_available"]) and "bridge" in elig.loc[sid, "roles"]
            rows.append(dict(
                source=sid, heuristic=h, roles=elig.loc[sid, "roles"],
                explicit_labels=n_lab if n_lab is not None else 0,
                indicators_computable=len(ok), indicators_linked=len(linked), indicators=", ".join(ok),
                dom_features=sum(1 for _, (hh, _) in dom_static.FEATURES.items() if hh == h) if has_html else 0,
            ))
    return pd.DataFrame(rows)


def source_iso_matrix() -> pd.DataFrame:
    cw = config.load("crosswalk")["iso_measures"]
    rows = []
    for sid, attrs in SESSION_ATTRS.items():
        for m, req in ISO_REQUIRES.items():
            rows.append(dict(source=sid, iso_measure=m, iso_characteristic=cw[m]["iso_char"],
                             standard=cw[m]["standard"], computable=req in attrs, requires=req))
    rows.append(dict(source=dashboards.SOURCE, iso_measure="iso_effectiveness_answer_correct / NASA-TLX",
                     iso_characteristic="Effectiveness / Satisfaction", standard="iso25022",
                     computable=True, requires="tabla experimental separada (sin clave con los logs)"))
    return pd.DataFrame(rows)


def expert_template() -> pd.DataFrame:
    """Un ítem por vínculo indicador→heurística y rasgo DOM→heurística.

    Cada experto marca: 3 = esencial, 2 = útil pero no esencial, 1 = no necesario.
    CVR = (n_e − N/2) / (N/2), con n_e = expertos que marcan 'esencial' (Lawshe, 1975).
    """
    ind = config.load("indicators")["indicators"]
    rows = []
    for k, v in ind.items():
        for h in v.get("heuristics") or []:
            rows.append(dict(item=f"{k}→{h}", tipo="indicador conductual", heuristic=h, definicion=v["definition"],
                             evidencia_actual=v["evidence"], experto_1=None, experto_2=None, experto_3=None))
    for k, (h, why) in dom_static.FEATURES.items():
        if h:
            rows.append(dict(item=f"{k}→{h}", tipo="rasgo DOM", heuristic=h, definicion=why, evidencia_actual="normative (WCAG)",
                             experto_1=None, experto_2=None, experto_3=None))
    return pd.DataFrame(rows)


def run(labels: pd.DataFrame | None = None) -> pd.DataFrame:
    config.ensure_dirs()
    out = config.REPORT_STAGE2
    el = eligibility()
    el.to_csv(out / "matriz_elegibilidad.csv", index=False)
    crosswalk_table().to_csv(out / "crosswalk_heuristicas_iso.csv", index=False)
    source_heuristic_matrix(labels).to_csv(out / "matriz_fuente_heuristica.csv", index=False)
    source_iso_matrix().to_csv(out / "matriz_fuente_iso.csv", index=False)
    expert_template().to_csv(out / "plantilla_validacion_expertos.csv", index=False)
    return el
