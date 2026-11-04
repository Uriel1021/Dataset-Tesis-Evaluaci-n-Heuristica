"""Adaptador S06 · P3M (defectos GPT-4 por captura + validación experta).

Origen:
  1. GPT-4 - All Possible Defects per Screenshot.xlsx
       Screenshot, Internal ID, Usability Problem, Violated Usability Heuristics, Severity
  2. GPT-4 - Defects Consolidation.xlsx
       Classification (Main/Duplicate), Internal ID, ..., "Is it a defect?" (Yes/No)

Reglas:
  R1  Una celda de heurísticas puede listar varias ("A, B"): se separa y cada
      una se normaliza con el crosswalk.
  R2  Se generan dos evaluadores por captura:
        evaluator_type = llm                    → todo defecto propuesto por GPT-4
        evaluator_type = llm_expert_validated   → solo defectos con "Is it a defect?" = Yes
  R3  Las heurísticas no reportadas para una captura se registran como 0 con
      negative_by_absence = True (P3M no emite negativos explícitos).
"""

from __future__ import annotations

import re

import pandas as pd

from .. import config
from .labels_common import label_frame

SOURCE = "S06_p3m"


def _consolidation(path) -> pd.DataFrame:
    raw = pd.read_excel(path, header=None)
    hdr = raw.index[raw.apply(lambda r: r.astype(str).str.strip().eq("Internal ID").any(), axis=1)][0]
    df = raw.iloc[hdr + 1:].copy()
    df.columns = [str(c).strip() for c in raw.iloc[hdr]]
    df = df.dropna(subset=["Internal ID"])
    df["Internal ID"] = df["Internal ID"].astype(str).str.strip()
    df["is_defect"] = df["Is it a defect?"].astype(str).str.strip().str.lower().eq("yes")
    return df[["Internal ID", "Classification", "is_defect"]]


def build_labels():
    root = config.source_path(SOURCE)
    d = pd.read_excel(root / "1. GPT-4 - All Possible Defects per Screenshot.xlsx")
    d = d.dropna(subset=["Screenshot"])
    d["Internal ID"] = d["Internal ID"].astype(str).str.strip()
    d = d.merge(_consolidation(root / "2. GPT-4 - Defects Consolidation.xlsx"), on="Internal ID", how="left")
    long = []
    for _, r in d.iterrows():
        for part in re.split(r",|;|/| and (?=[A-Z0-9])", str(r["Violated Usability Heuristics"])):
            code = config.heuristic_code(part)
            if code:
                long.append(dict(shot=int(r["Screenshot"]), code=code, raw=part.strip(), sev=r["Severity"],
                                 valid=bool(r["is_defect"]) if pd.notna(r["is_defect"]) else None,
                                 text=r["Usability Problem"]))
    long = pd.DataFrame(long)
    rows = []
    for shot in sorted(d["Screenshot"].astype(int).unique()):
        sub = long[long.shot == shot]
        for etype in ("llm", "llm_expert_validated"):
            s = sub if etype == "llm" else sub[sub.valid.eq(True)]
            for i in range(1, 11):
                code = f"H{i}"
                h = s[s.code == code]
                rows.append(dict(
                    source=SOURCE, interface_id=f"{SOURCE}:screenshot_{shot:02d}", interface_name=f"Screenshot {shot}",
                    platform="web", artifact_evaluated="screenshot", fidelity="implemented",
                    evaluator_id="GPT-4" if etype == "llm" else "GPT-4+expert", evaluator_type=etype,
                    evaluation_round=1, heuristic=code, heuristic_raw=h.raw.iloc[0] if len(h) else None,
                    violation=int(len(h) > 0), negative_by_absence=len(h) == 0,
                    severity_max=float(h.sev.max()) if len(h) else None, n_issues=len(h),
                    evidence_text=" | ".join(h.text.astype(str)) if len(h) else None,
                ))
    return label_frame(rows)
