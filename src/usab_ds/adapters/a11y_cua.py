"""Adaptador S02 · Reduced-A11y-CUA.

Estructura de origen:  <grupo>/<participante|condición>/<tarea>/
    metadata_<tarea>.json         tarea (éxito, dificultad, familiaridad) y sesión
    <n>_<app>.exe.json            eventos de SO de cada aplicación
    web_logs/web_tab*_<ts>.json   eventos DOM de cada pestaña (no siempre presentes)
    web_logs/web_tab*_<ts>.html   snapshot DOM de la pestaña

Reglas de transformación (documentadas para la tesis):
  R1  Unidad = participante × tarea en la que se usó un navegador
      (chrome.exe / msedge.exe / firefox.exe). Tareas sin navegador se excluyen.
  R2  Acciones (click, key, scroll, mouse_move) se toman de los logs de SO del
      navegador: existen en todas las tareas con navegador y se capturan igual
      para humanos y agentes. Así no se cuentan dos veces.
  R3  Lo que solo existe a nivel DOM (page_view, focus, blur, input,
      scroll_pos) se toma de web_logs cuando existen.
  R4  nav_back = atajo Alt+Left / BrowserBack, o clic sobre un botón llamado
      "Back"/"Atrás".
  R5  Tiempo de tarea = session.ended_at − session.started_at (toda la tarea).
  R6  Grupo de usuario: BLVU→BLV, SU→sighted; carpetas de modelos → agent
      (is_human = False). Los agentes se conservan marcados, no mezclados.
  R7  Tecnología de apoyo por tarea: lector de pantalla si se ejecutó
      jfw/nvda/narrator o el baseline lo indica; magnificador si magnify.exe o
      baseline; sin evidencia → 'unknown' en BLV y 'none' en videntes. En
      agentes se toma de la condición (Default / Magnifier / Screen Reader).
  R7b assistive_tech_participant: tecnologías detectadas en cualquier tarea del
      mismo participante (es un rasgo de la persona más que de la tarea).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

from .. import config, events

SOURCE = "S02_a11y_cua"
BROWSERS = ("chrome.exe", "msedge.exe", "firefox.exe")
HUMAN_GROUPS = {"BLVU": "BLV", "SU": "sighted"}
SR_APPS = ("jfw.exe", "nvda.exe", "narrator.exe")
BACK_COMBOS = {"alt+left", "browserback", "alt+arrowleft"}

# Qué atributos del esquema canónico aporta esta fuente
CAPABILITIES = {
    "click", "key", "scroll", "mouse_move", "nav_back", "page_view", "focus", "blur", "input",
    "scroll_y", "target_tag", "target_id", "key_name",
}


def _load_json(p: Path):
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def iter_task_dirs(root: Path):
    for meta in sorted(root.glob("*/*/*/metadata_*.json")):
        yield meta.parent, meta


def _assistive_tech(group: str, condition: str, meta: dict, apps: list[str]) -> str:
    if group not in HUMAN_GROUPS:
        c = condition.lower()
        return "screen_reader" if "screen" in c else "magnifier" if "magnif" in c else "none"
    base = (meta.get("accessibility") or {}).get("baseline") or {}
    a = [x.lower() for x in apps]
    if any(s in a for s in SR_APPS) or (base.get("narrator") or {}).get("enabled"):
        return "screen_reader"
    if "magnify.exe" in a or (base.get("magnifier") or {}).get("enabled"):
        return "magnifier"
    # Sin evidencia en el log: en usuarios BLV NO se asume 'none' (un lector de
    # pantalla en segundo plano no aparece como aplicación); en videntes sí.
    return "unknown" if group == "BLVU" else "none"


def _os_events(path: Path, sid: str) -> list[dict]:
    rows = []
    for e in _load_json(path):
        if not isinstance(e, dict):
            continue
        ev = e.get("event")
        etype = ev.get("type") if isinstance(ev, dict) else ev
        ts = int(float(e["timestamp"]) * 1000)
        cur = e.get("element_under_cursor") or {}
        pos = e.get("cursor_position") or [None, None]
        tag = (cur.get("control_type") or "").lower() or None
        tid = f"{cur.get('control_type')}|{cur.get('name')}" if cur else None
        base = dict(session_id=sid, ts_ms=ts, x=pos[0], y=pos[1], target_tag=tag, target_id=tid)
        if etype == "mouse_click":
            name = (cur.get("name") or "").strip().lower()
            rows.append({**base, "event": "click"})
            if tag == "buttoncontrol" and name in {"back", "atrás", "atras"}:
                rows.append({**base, "event": "nav_back"})
        elif etype == "key_press":
            rows.append({**base, "event": "key", "key": str(ev.get("key", "")).lower()})
        elif etype == "hotkey":
            combo = str(ev.get("combo", "")).lower()
            rows.append({**base, "event": "key", "key": combo})
            if combo in BACK_COMBOS:
                rows.append({**base, "event": "nav_back"})
        elif etype == "scroll":
            rows.append({**base, "event": "scroll"})
        elif etype == "mouse_move":
            rows.append({**base, "event": "mouse_move"})
    return rows


def _web_events(web_dir: Path, sid: str) -> list[dict]:
    rows = []
    for f in sorted(web_dir.glob("web_tab*.json")):
        if f.name.endswith("_a11y_tree.json"):
            continue
        d = _load_json(f)
        url = d.get("url")
        for e in d.get("interactions", []):
            t = e.get("type")
            ts = e.get("timestamp")
            if ts is None:
                continue
            el = e.get("element") or {}
            base = dict(session_id=sid, ts_ms=int(ts), url=url,
                        target_tag=(el.get("tag") or "").lower() or None,
                        target_role=el.get("role"), target_id=e.get("selector"))
            if t == "page":
                rows.append({**base, "event": "page_view"})
            elif t in ("focus", "blur", "input"):
                rows.append({**base, "event": t})
            elif t == "scroll":
                rows.append({**base, "event": "scroll_pos", "scroll_y": e.get("scrollTop")})
    return rows


def build() -> tuple[pd.DataFrame, pd.DataFrame]:
    root = config.source_path(SOURCE)
    sess_rows, ev_rows = [], []
    for task_dir, meta_path in iter_task_dirs(root):
        group, who, task_folder = task_dir.relative_to(root).parts
        meta = _load_json(meta_path)
        t, s = meta.get("task", {}), meta.get("session", {})
        apps = [a.get("app", "") for a in s.get("applications", [])]
        browser_apps = [a for a in s.get("applications", []) if a.get("app", "").lower() in BROWSERS]
        if not browser_apps:  # R1
            continue
        is_human = group in HUMAN_GROUPS
        participant = who if is_human else group
        sid = f"{SOURCE}:{group}/{who}/{task_folder}"
        urls = [tab.get("url") for a in browser_apps for tab in a.get("tabs", []) if tab.get("url")]
        sess_rows.append(dict(
            source=SOURCE, session_id=sid, participant_id=participant,
            user_group=HUMAN_GROUPS.get(group, "agent"), is_human=is_human,
            assistive_tech=_assistive_tech(group, who, meta, apps),
            agent_condition=None if is_human else who,
            task_id=str(t.get("task_id")), task_title=t.get("task_title"), task_group=t.get("task_group"),
            familiarity=t.get("familiarity"), difficulty_before=t.get("difficulty_before"),
            difficulty_after=t.get("difficulty_after"), success=t.get("success"),
            start_ms=int(float(s["started_at"]) * 1000), end_ms=int(float(s["ended_at"]) * 1000),
            url_domain=urlparse(urls[0]).netloc if urls else None,
            browser=browser_apps[0].get("app"),
        ))
        for a in browser_apps:  # R2
            p = task_dir / a.get("log_file", "")
            if p.is_file():
                ev_rows += _os_events(p, sid)
        if (task_dir / "web_logs").is_dir():  # R3
            ev_rows += _web_events(task_dir / "web_logs", sid)
    ev = pd.DataFrame(ev_rows)
    ev["source"] = SOURCE
    sess = pd.DataFrame(sess_rows)
    # R7b: rasgo del participante = tecnología detectada en cualquiera de sus tareas
    detected = sess[sess.assistive_tech.isin(["screen_reader", "magnifier"]) & sess.is_human]
    per_p = detected.groupby("participant_id").assistive_tech.agg(lambda s: "|".join(sorted(set(s))))
    sess["assistive_tech_participant"] = sess.participant_id.map(per_p)
    sess.loc[sess.is_human & sess.assistive_tech_participant.isna(), "assistive_tech_participant"] = \
        sess.loc[sess.is_human & sess.assistive_tech_participant.isna(), "assistive_tech"]
    return events.session_frame(sess), events.frame(ev)


def html_pages() -> list[dict]:
    """Snapshots DOM ligados a su sesión (para el puente estático)."""
    root = config.source_path(SOURCE)
    out = []
    for task_dir, _ in iter_task_dirs(root):
        group, who, task_folder = task_dir.relative_to(root).parts
        sid = f"{SOURCE}:{group}/{who}/{task_folder}"
        for h in sorted((task_dir / "web_logs").glob("web_tab*.html")):
            meta_json = h.with_suffix(".json")
            url = _load_json(meta_json).get("url") if meta_json.is_file() else None
            out.append(dict(source=SOURCE, page_id=f"{sid}#{h.stem}", session_id=sid, url=url, path=h))
    return out


DIFFICULTY_EASE = {  # recodificación de difficulty_after a facilidad percibida [0,1]
    "very easy": 1.0, "easy": 0.75, "low": 0.75, "medium": 0.5, "moderate": 0.5, "neutral": 0.5,
    "hard": 0.25, "difficult": 0.25, "high": 0.25, "very hard": 0.0, "very difficult": 0.0,
}


def perceived_ease(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    return DIFFICULTY_EASE.get(re.sub(r"\s+", " ", str(value).strip().lower()))
