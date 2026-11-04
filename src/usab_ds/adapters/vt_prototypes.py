"""Adaptador S03 · Evaluaciones heurísticas GPT-4o de prototipos (29042675).

Origen: LLM_Evaluations/LLM Evaluation {1,2}/{High,Low} Fidelity/<prototipo>.docx.
Cada documento contiene primero la plantilla (preguntas) y después las
respuestas del LLM, una sección por heurística ("1. Visibility of System
Status" … "10. Help and Documentation") con problemas y "Severity: n".

Reglas de extracción:
  R1  Los párrafos de la plantilla (los que contienen "heuristic principle" o
      "given image") nunca se toman como encabezados de respuesta.
  R2  Encabezado de sección = párrafo cuyo texto, sin numeración/prefijo/
      contexto, es casi exactamente el nombre de la heurística Hn, y n es
      mayor que la última sección vista (orden Nielsen); así un problema o
      recomendación que menciona la heurística no se confunde con un encabezado.
  R3  severity_max = máximo de "Severity: k" en la sección; n_issues = número
      de severidades k ≥ 1; violation = 1 si n_issues ≥ 1, 0 si la sección
      existe y no tiene severidades ≥ 1, NA si no se encontró la sección.
  R4  IRR_Results.csv no se usa como etiqueta: sus columnas "Hn Compare"
      comparan evaluaciones y su estructura no permite separar evaluadores
      de forma inequívoca. Se documenta como metadato en la etapa 1.
"""

from __future__ import annotations

import re

import docx

from .. import config
from .labels_common import label_frame

SOURCE = "S03_vt_llm_prototypes_29042675"
# "Severity: 3 (Major)" o "(Severity: 3/4)"; excluye el rótulo "Severity Rating 0-4"
_SEV = re.compile(r"severity(?:\s*rating)?\s*[:\-–]?\s*([0-4])(?!\s*[-–]\s*\d)(?!\d)", re.I)

# Equivalencias manuales y explícitas entre nombres de archivo de ambas rondas
ALIASES = {
    "baking shop": "bakery", "e tutor": "e-tutor", "hospitalapp": "hospital app 1", "hospitalapp2": "hospital app 2",
    "running": "running app", "gaia": "gaia community app", "artwork": "artwork website", "blog": "blog app",
    "volountery pet": "voluntary pet", "vouluntary pet": "voluntary pet",
}


def _key(name: str) -> str:
    n = re.sub(r"\s+", " ", name.strip().lower())
    return ALIASES.get(n, n)


_PREFIX = re.compile(
    r"^\s*(\d{1,2}\s*[\.\)]\s*)?((heuristic )?evaluation\s*(based on|of|for|:)\s*|heuristic evaluation\s*[:\-–]?\s*)?", re.I)
_CLOSER = re.compile(r"^overall\s+(heuristic\s+)?rating\s+for\s+(.+)$", re.I)
_SUFFIX = re.compile(r"\s*\(.*?\)\s*$")
_CONTEXT = re.compile(r"\s+(in|for)\s+(the\s+)?[A-Z][\w\- ]*$")  # "... in Blog App"


def _header_code(p: str, last: int) -> str | None:
    """Devuelve Hn si el párrafo es un encabezado de sección de respuesta.

    Las tres plantillas encontradas en la fuente son:
      "4. Consistency and Standards"
      "Evaluation Based on Consistency and Standards (Heuristic Evaluation)"
      "Heuristic Evaluation of Consistency and Standards in Blog App (Lo-Fi Prototype)"
    Se exige que, quitando prefijo y contexto, el texto sea casi exactamente
    el nombre de la heurística (≤ 3 caracteres de diferencia), para no
    confundir títulos de problemas o recomendaciones con encabezados. El orden
    no se impone: algunos documentos presentan las heurísticas desordenadas o
    incompletas; si una heurística reaparece, su sección se reabre.
    """
    low = p.lower()
    if len(p) > 160 or "heuristic principle" in low or "given image" in low or "for the given" in low:
        return None
    core = _CONTEXT.sub("", _SUFFIX.sub("", _PREFIX.sub("", p))).strip(" :.-'\"‘’")
    return _exact_code(core)


def _exact_code(text: str) -> str | None:
    n = config.normalize_text(text)
    for alias, code in config.heuristic_alias_map().items():
        if n == alias or (n.startswith(alias) and len(n) - len(alias) <= 3):
            return code
    return None


def _parse_by_closers(paras: list[str]) -> dict[str, dict]:
    """Plantilla sin encabezados: cada sección TERMINA en 'Overall Rating for <H>'."""
    sections: dict[str, dict] = {}
    buf_sev: list[int] = []
    for p in paras:
        m = _CLOSER.match(p)
        if m and (code := _exact_code(m.group(2))):
            s = sections.setdefault(code, dict(raw=p, sev=[], text=[]))
            s["sev"] += buf_sev
            buf_sev = []
            continue
        if (s := _SEV.search(p)):
            buf_sev.append(int(s.group(1)))
    return sections


def parse_doc(path) -> dict[str, dict]:
    paras = [p.text.strip() for p in docx.Document(path).paragraphs if p.text.strip()]
    sections: dict[str, dict] = {}
    cur = None
    for p in paras:
        code = _header_code(p, 0)
        if code:
            cur = code
            sections.setdefault(cur, dict(raw=p, sev=[], text=[]))
            continue
        if cur is None:
            continue
        s = _SEV.search(p)
        if s:
            sections[cur]["sev"].append(int(s.group(1)))
        elif len(sections[cur]["text"]) < 3 and not p.lower().startswith(("issues found", "questions evaluated")):
            sections[cur]["text"].append(p)
    with_sev = sum(bool(s["sev"]) for s in sections.values())
    if with_sev < 3:  # plantilla de "cierre" (ver _parse_by_closers)
        alt = _parse_by_closers(paras)
        if len(alt) > with_sev:
            return alt
    return sections


def build_labels():
    root = config.source_path(SOURCE) / "LLM_Evaluations"
    rows = []
    for f in sorted(root.rglob("*.docx")):
        rnd = int(re.findall(r"\d+", f.parts[-3])[0])
        fidelity = "high" if "high" in f.parts[-2].lower() else "low"
        key = _key(f.stem)
        sections = parse_doc(f)
        for i in range(1, 11):
            code = f"H{i}"
            sec = sections.get(code)
            if sec is None:
                viol, sev, n = None, None, None
            else:
                pos = [s for s in sec["sev"] if s >= 1]
                viol, sev, n = int(bool(pos)), (max(sec["sev"]) if sec["sev"] else 0), len(pos)
            rows.append(dict(
                source=SOURCE, interface_id=f"{SOURCE}:{fidelity}/{key}", interface_name=f.stem,
                platform="prototype", artifact_evaluated="prototype_image", fidelity=fidelity,
                evaluator_id="GPT-4o", evaluator_type="llm", evaluation_round=rnd,
                heuristic=code, heuristic_raw=sec["raw"] if sec else None, violation=viol,
                negative_by_absence=False, severity_max=sev, n_issues=n,
                evidence_text=" ".join(sec["text"]) if sec else None,
            ))
    return label_frame(rows)
