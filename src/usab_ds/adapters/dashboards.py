"""Adaptador S08 · Dashboards (logs de interacción).

Origen: 'Interaction Data.zip' con un archivo por sesión de navegador
(exportación de MongoDB, un objeto JSON por línea con ObjectId(...)).

Reglas de transformación:
  R1  Sesión = archivo (sessionstartms). Toda la sesión del estudio
      (consentimiento, dashboards, cuestionarios) queda en una sola sesión.
  R2  mousedown → click; dblclick → dblclick; keydown → key (nombre de tecla);
      mousewheel → scroll; scroll → scroll_pos (scrollY); mouseover → hover;
      change/select → input; load → page_view. keyup/keypress/mouseup/
      mouseout y foco de ventana se descartan (duplican acciones ya contadas).
  R3  No se guardan valores escritos por el participante (p. ej. nombre).
  Limitación: la tabla experimental 'dependent and independent variables.csv'
  (exactitud, tiempo, NASA-TLX) no tiene clave común con los logs
  (verificado en la v1: 0 coincidencias de P o sessionstart), por lo que NO se
  une; se exporta como tabla de calidad en uso independiente.
"""

from __future__ import annotations

import json
import re
import zipfile

import pandas as pd

from .. import config, events

SOURCE = "S08_dashboards"
CAPABILITIES = {"click", "key", "scroll", "scroll_y", "hover", "input", "page_view", "target_tag", "target_id",
                "key_name"}
_OID = re.compile(r'ObjectId\("([0-9a-f]+)"\)')
_MAP = {"mousedown": "click", "dblclick": "dblclick", "keydown": "key", "mousewheel": "scroll",
        "scroll": "scroll_pos", "mouseover": "hover", "change": "input", "select": "input", "load": "page_view"}


def _zip_path():
    return config.source_path(SOURCE) / "Interaction Data.zip"


def build() -> tuple[pd.DataFrame, pd.DataFrame]:
    sess_rows, ev_rows = [], []
    with zipfile.ZipFile(_zip_path()) as zf:
        for name in sorted(n for n in zf.namelist() if n.endswith(".json") and not n.startswith("__MACOSX")):
            sid = f"{SOURCE}:{name.removesuffix('.json')}"
            tss = []
            for line in zf.read(name).decode("utf-8", errors="replace").splitlines():
                line = _OID.sub(r'"\1"', line).strip()
                if not line:
                    continue
                d = json.loads(line)
                ts = d.get("timestampms")
                if ts is None:
                    continue
                tss.append(int(ts))
                ev = _MAP.get(d.get("event"))
                if ev is None:
                    continue
                node, mouse = d.get("node") or {}, d.get("mouse") or {}
                row = dict(session_id=sid, ts_ms=int(ts), event=ev, url=d.get("url"),
                           x=mouse.get("coordX"), y=mouse.get("coordY"),
                           target_tag=(node.get("type") or "").lower() or None, target_id=node.get("dom"))
                if ev == "key":
                    row["key"] = str(d.get("key", "")).lower()
                if ev == "scroll_pos":
                    row["scroll_y"] = (d.get("scroll") or {}).get("scrollY")
                if ev == "click" and mouse.get("but") not in (None, "l"):
                    continue  # solo botón izquierdo
                ev_rows.append(row)
            if tss:
                sess_rows.append(dict(source=SOURCE, session_id=sid, participant_id=sid.split(":", 1)[1],
                                      user_group="unknown", is_human=True, assistive_tech="unknown",
                                      start_ms=min(tss), end_ms=max(tss), url_domain="dashboard-study",
                                      browser="unknown"))
    ev = pd.DataFrame(ev_rows)
    ev["source"] = SOURCE
    return events.session_frame(sess_rows), events.frame(ev)


def experimental_table() -> pd.DataFrame:
    """Tabla de calidad en uso del experimento (no unida a los logs)."""
    df = pd.read_csv(config.source_path(SOURCE) / "dependent and independent variables.csv")
    df = df.rename(columns={"P": "participant_id", "DB": "dashboard", "Issue": "design_issue", "Type": "condition",
                            "Q": "question", "Answer": "iso_effectiveness_answer_correct", "Time": "iso_efficiency_task_time_raw"})  # unidad no declarada en la fuente
    tlx = ["mental", "physical", "temporal", "performance", "effort", "frustration"]
    df = df.rename(columns={c: f"nasa_tlx_{c}" for c in tlx})
    df["source"] = SOURCE
    return df
