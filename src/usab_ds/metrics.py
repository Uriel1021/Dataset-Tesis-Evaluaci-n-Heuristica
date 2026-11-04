"""Cálculo de medidas ISO e indicadores conductuales por sesión.

Entrada: eventos canónicos (events.py) + metadatos de sesión + CAPABILITIES
de la fuente. Salida: una fila por sesión.

Principios:
  * Una única implementación para todas las fuentes.
  * Si la fuente no captura lo que un indicador requiere → NaN (no 0).
  * Denominador 0 → NaN.
  * Los parámetros se leen de configs/indicators.yaml.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config
from .events import ACTION_TYPES

USER_EVENTS = set(ACTION_TYPES) | {"input", "focus", "nav_back"}


def _div(a, b):
    return a / b if b else np.nan


def _session_indicators(ev: pd.DataFrame, dur_s: float, p: dict, caps: set) -> dict:
    has = lambda *req: all(r in caps for r in req)  # noqa: E731
    e = ev["event"].to_numpy()
    ts = ev["ts_ms"].to_numpy(dtype="int64")
    clicks = ev[np.isin(e, ["click", "dblclick"])]
    keys = ev[e == "key"]
    n_click, n_key, n_scroll = len(clicks), len(keys), int((e == "scroll").sum())
    pages = ev.loc[e == "page_view", "url"]
    n_pages = pages.nunique() if has("page_view") and len(pages) else np.nan
    mins = dur_s / 60 if dur_s and dur_s > 0 else np.nan
    out = {
        "n_events": len(ev),
        "n_clicks": n_click if has("click") else np.nan,
        "n_keys": n_key if has("key") else np.nan,
        "n_scrolls": n_scroll if has("scroll") else np.nan,
        "n_pages": n_pages,
        "clicks_per_min": n_click / mins if has("click") else np.nan,
        "keys_per_min": n_key / mins if has("key") else np.nan,
        "scrolls_per_min": n_scroll / mins if has("scroll") else np.nan,
    }

    # cursor
    mv = ev.loc[e == "mouse_move", ["x", "y"]].dropna()
    out["mouse_distance_px"] = float(np.hypot(np.diff(mv.x), np.diff(mv.y)).sum()) if has("mouse_move") and len(mv) > 1 else np.nan

    # scroll (posición por URL)
    sp = ev.loc[e == "scroll_pos", ["url", "scroll_y"]].dropna(subset=["scroll_y"])
    if has("scroll_y") and len(sp) > 1:
        dist, rev, steps = 0.0, 0, 0
        for _, g in sp.groupby(sp["url"].fillna(""), sort=False):
            d = np.diff(g["scroll_y"].to_numpy(dtype=float))
            d = d[d != 0]
            dist += np.abs(d).sum()
            steps += len(d)
            rev += int((np.sign(d[1:]) != np.sign(d[:-1])).sum()) if len(d) > 1 else 0
        out["scroll_distance_px"] = dist
        out["scroll_reversal_rate"] = _div(rev, steps)
    else:
        out["scroll_distance_px"] = np.nan if not has("scroll_y") else 0.0
        out["scroll_reversal_rate"] = np.nan

    # H1: clics repetidos y latencia tras clic
    if has("click") and n_click:
        c_ts = clicks["ts_ms"].to_numpy(dtype="int64")
        c_id = clicks["target_id"].to_numpy(dtype=object)
        cx, cy = clicks["x"].to_numpy(dtype=float), clicks["y"].to_numpy(dtype=float)
        rep = 0
        for i in range(1, n_click):
            if (c_ts[i] - c_ts[i - 1]) / 1000 > p["repeated_click_window_s"]:
                continue
            same_id = c_id[i] is not None and c_id[i] is not pd.NA and c_id[i] == c_id[i - 1]
            near = np.hypot(cx[i] - cx[i - 1], cy[i] - cy[i - 1]) <= p["repeated_click_radius_px"]
            rep += bool(same_id or near)
        out["repeated_click_rate"] = rep / n_click
        user_ts = ts[np.isin(e, list(USER_EVENTS))]
        lat = []
        for t in c_ts:
            j = np.searchsorted(user_ts, t, side="right")
            if j < len(user_ts):
                dt = (user_ts[j] - t) / 1000
                if dt <= p["post_click_max_s"]:
                    lat.append(dt)
        out["post_click_latency_s"] = float(np.median(lat)) if lat else np.nan
    else:
        out["repeated_click_rate"] = out["post_click_latency_s"] = np.nan

    if has("click", "target_tag"):
        tags = clicks["target_tag"].str.lower()
        roles = clicks["target_role"].str.lower()
        known = tags.notna()
        inter = tags.isin(p["interactive_tags"]) | roles.isin(p["interactive_roles"])
        out["dead_click_rate"] = _div(int((known & ~inter).sum()), int(known.sum()))
    else:
        out["dead_click_rate"] = np.nan

    # H4/H6: navegación hacia atrás y revisitas
    n_back = int((e == "nav_back").sum())
    out["back_nav_rate"] = _div(n_back, n_pages) if has("nav_back") and not np.isnan(n_pages) else np.nan
    if has("page_view") and len(pages):
        out["page_revisit_rate"] = _div(int(pages.duplicated().sum()), len(pages))
    else:
        out["page_revisit_rate"] = np.nan

    # H5: correcciones y re-edición de campos
    if has("key", "key_name") and n_key:
        k = keys["key"].fillna("").str.lower()
        corr = k.isin(p["correction_keys"]) | k.str.contains("backspace|delete", regex=True)
        out["correction_key_ratio"] = corr.sum() / n_key
    else:
        out["correction_key_ratio"] = np.nan
    if has("focus", "input", "target_id"):
        # visita a un campo = racha consecutiva de focus/input sobre el mismo target;
        # campo re-editado = recibe input en ≥ 2 visitas distintas
        fi = ev[np.isin(e, ["focus", "input"])][["event", "target_id"]].dropna()
        if len(fi):
            fi = fi.assign(run=(fi["target_id"] != fi["target_id"].shift()).fillna(True).astype("int64").cumsum())
            per_field = fi[fi.event == "input"].groupby("target_id")["run"].nunique()
            out["input_reentry_rate"] = _div(int((per_field >= 2).sum()), len(per_field))
        else:
            out["input_reentry_rate"] = np.nan
    else:
        out["input_reentry_rate"] = np.nan

    # H6: pausas, churn de foco, exploración sin clic
    if len(ts) > 1 and dur_s and dur_s > 0:
        gaps = np.diff(np.sort(ts)) / 1000
        out["long_pause_ratio"] = min(1.0, gaps[gaps > p["long_pause_s"]].sum() / dur_s)
    else:
        out["long_pause_ratio"] = np.nan
    out["focus_churn"] = _div(int((e == "focus").sum()), n_click + n_key) if has("focus", "click") else np.nan
    if has("hover"):
        hov = set(ev.loc[e == "hover", "target_id"].dropna())
        clk = set(clicks["target_id"].dropna())
        out["hover_without_click_ratio"] = _div(len(hov - clk), len(hov))
    else:
        out["hover_without_click_ratio"] = np.nan
    return out


def compute(sessions: pd.DataFrame, ev: pd.DataFrame, caps: set) -> pd.DataFrame:
    p = config.params()
    groups = dict(tuple(ev.groupby("session_id", sort=False)))
    rows = []
    empty = ev.iloc[0:0]
    for s in sessions.itertuples(index=False):
        g = groups.get(s.session_id, empty)
        dur_s = (s.end_ms - s.start_ms) / 1000 if pd.notna(s.end_ms) and pd.notna(s.start_ms) else np.nan
        row = {"session_id": s.session_id, "iso_efficiency_task_time_s": dur_s}
        row.update(_session_indicators(g, dur_s, p, caps))
        rows.append(row)
    m = pd.DataFrame(rows)
    out = sessions.merge(m, on="session_id", how="left")
    acts = out[["n_clicks", "n_keys", "n_scrolls"]]
    out["iso_efficiency_actions"] = acts.sum(axis=1, min_count=1)
    succ = out["success"].astype("Float64")
    out["iso_effectiveness_task_completion"] = succ
    out["iso_efficiency_time_based"] = succ / (out["iso_efficiency_task_time_s"] / 60)
    out["quality_ok"] = (out["iso_efficiency_task_time_s"] >= p["min_session_seconds"]) & (out["n_events"] >= p["min_session_events"])
    return out


def add_proxy_scores(df: pd.DataFrame) -> pd.DataFrame:
    """z robusto dentro de cada fuente y puntaje proxy por heurística.

    z = (x − mediana) / (1.4826 · MAD), con mediana y MAD calculadas sobre las
    sesiones humanas válidas de la MISMA fuente (los agentes se escalan contra
    la referencia humana). H*_proxy_z = media de los z disponibles de los
    indicadores ligados a la heurística (multiplicados por su `direction`).
    Es un índice exploratorio, NO una etiqueta de violación.
    """
    ind = config.load("indicators")["indicators"]
    df = df.copy()
    zcols: dict[str, list[tuple[str, int]]] = {h: [] for h in config.TARGET_HEURISTICS}
    for name, spec in ind.items():
        if not spec.get("heuristics") or name not in df:
            continue
        z = pd.Series(np.nan, index=df.index)
        for _, idx in df.groupby("source").groups.items():
            sub = df.loc[idx]
            ref = sub.loc[sub["is_human"].fillna(False).astype(bool) & sub["quality_ok"], name].astype(float)
            med = ref.median()
            mad = 1.4826 * (ref - med).abs().median()
            if pd.notna(mad) and mad > 0:
                z.loc[idx] = (sub[name].astype(float) - med) / mad
        df[f"z_{name}"] = z.clip(-5, 5)
        for h in spec["heuristics"]:
            zcols[h].append((f"z_{name}", spec.get("direction", 1)))
    for h, cols in zcols.items():
        mat = pd.concat([df[c] * d for c, d in cols], axis=1) if cols else pd.DataFrame(index=df.index)
        df[f"{h}_proxy_z"] = mat.mean(axis=1, skipna=True)
        df[f"{h}_proxy_n_indicators"] = mat.notna().sum(axis=1)
    return df
