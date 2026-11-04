"""Adaptador S04 · Catching UX Flaws (etiquetas) y S04b (HTML recuperado).

Origen: results/<sitio>/eval{1,2,3}.json — tres evaluaciones GPT-4o
independientes sobre el código del sitio; una entrada por heurística con
IssueFound (bool) y SeverityRating (0–4).

Reglas:
  R1  violation = IssueFound (negativo explícito cuando es false).
  R2  Si una heurística aparece varias veces en la misma evaluación se toma
      OR de IssueFound y el máximo de severidad.
  R3  Para el puente HTML: se usan solo repositorios recuperados localmente.
      match_level = CONFIRMED (carpeta catching_confirmed) o NAME_MATCH
      (catching_negative_candidates: coincidencia por nombre de repositorio,
      evidencia más débil). Se conserva como columna para filtrar.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .. import config
from .labels_common import label_frame

SOURCE = "S04_catching_ux_flaws"
BRIDGE = "S04b_catching_html"


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def build_labels():
    root = config.source_path(SOURCE) / "results"
    rows = []
    for site_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        for f in sorted(site_dir.glob("eval*.json")):
            rnd = int(re.findall(r"\d+", f.stem)[0])
            agg: dict[str, dict] = {}
            for e in json.loads(f.read_text(encoding="utf-8")):
                code = config.heuristic_code(e.get("Heuristic"))
                if code is None:
                    continue
                a = agg.setdefault(code, dict(raw=e.get("Heuristic"), found=False, sev=None, n=0, text=[]))
                found = bool(e.get("IssueFound"))
                a["found"] |= found
                sev = e.get("SeverityRating")
                if isinstance(sev, (int, float)):
                    a["sev"] = max(a["sev"] or 0, sev)
                if found:
                    a["n"] += 1
                    a["text"].append(str(e.get("IssueDescription") or ""))
            for code, a in agg.items():
                rows.append(dict(
                    source=SOURCE, interface_id=f"{SOURCE}:{site_dir.name}", interface_name=site_dir.name,
                    platform="web", artifact_evaluated="code", fidelity="implemented",
                    evaluator_id="GPT-4o", evaluator_type="llm", evaluation_round=rnd,
                    heuristic=code, heuristic_raw=a["raw"], violation=int(a["found"]), negative_by_absence=False,
                    severity_max=a["sev"], n_issues=a["n"], evidence_text=" | ".join(a["text"]),
                ))
    return label_frame(rows)


def html_sites() -> list[dict]:
    """Páginas HTML recuperadas, enlazadas al sitio etiquetado."""
    rec = config.source_path(BRIDGE)
    sites = {_norm(p.name): p.name for p in (config.source_path(SOURCE) / "results").iterdir() if p.is_dir()}
    out = []
    for level, folder in (("CONFIRMED", "catching_confirmed"), ("NAME_MATCH", "catching_negative_candidates")):
        for repo in sorted(p for p in (rec / folder).iterdir() if p.is_dir()):
            repo_name = repo.name.split("__")[-1]
            site = sites.get(_norm(repo_name))
            if site is None:
                continue
            for h in sorted(repo.rglob("*.html")):
                if any(part in {"node_modules", "vendor", ".git"} for part in h.parts):
                    continue
                out.append(dict(source=BRIDGE, page_id=f"{BRIDGE}:{site}/{h.relative_to(repo)}",
                                interface_id=f"{SOURCE}:{site}", match_level=level, repo=repo.name, path=Path(h)))
    return out
