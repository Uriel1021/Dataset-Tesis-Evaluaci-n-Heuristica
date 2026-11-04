"""Esquema canónico de eventos de interacción.

Cada adaptador de comportamiento traduce los eventos de su fuente a este
esquema único. Las métricas (metrics.py) se calculan SOLO sobre él, de modo
que la misma definición operacional se aplica idénticamente a todas las
fuentes. Las diferencias de captura se registran en CAPABILITIES de cada
adaptador y se propagan como NaN (nunca como 0).

Tipos de evento canónicos
-------------------------
page_view   carga/visita de una URL
click       pulsación de botón del ratón (un evento por clic)
dblclick    doble clic
scroll      acción discreta de desplazamiento (rueda, teclado de scroll)
scroll_pos  posición de scroll reportada por la página (no es una acción;
            se usa para distancia y reversiones de scroll)
key         pulsación de tecla (incluye combinaciones como 'Ctrl+L')
input       cambio de valor en un campo
focus/blur  foco de elemento
nav_back    navegación hacia atrás (Alt+Left, botón Atrás, history back)
mouse_move  muestra de posición del cursor
hover       entrada del cursor en un elemento (mouseover)
"""

from __future__ import annotations

import pandas as pd

EVENT_TYPES = (
    "page_view", "click", "dblclick", "scroll", "scroll_pos", "key", "input",
    "focus", "blur", "nav_back", "mouse_move", "hover",
)

ACTION_TYPES = ("click", "dblclick", "key", "scroll")

COLUMNS = {
    "source": "string",
    "session_id": "string",
    "ts_ms": "int64",
    "event": "string",
    "x": "float64",
    "y": "float64",
    "scroll_y": "float64",
    "key": "string",
    "target_id": "string",
    "target_tag": "string",
    "target_role": "string",
    "url": "string",
}


def frame(rows: list[dict] | pd.DataFrame) -> pd.DataFrame:
    """Construye un DataFrame con el esquema canónico (columnas y tipos)."""
    df = rows if isinstance(rows, pd.DataFrame) else pd.DataFrame(rows)
    for col, dtype in COLUMNS.items():
        if col not in df.columns:
            df[col] = pd.Series(index=df.index, dtype=dtype)
    df = df[list(COLUMNS)]
    df = df.astype(COLUMNS)
    bad = set(df["event"].dropna().unique()) - set(EVENT_TYPES)
    if bad:
        raise ValueError(f"Tipos de evento no canónicos: {bad}")
    return df.sort_values(["session_id", "ts_ms"], kind="stable").reset_index(drop=True)


# Esquema de metadatos de sesión (una fila por sesión)
SESSION_COLUMNS = {
    "source": "string",
    "session_id": "string",
    "participant_id": "string",
    "user_group": "string",        # BLV | sighted | agent | unknown
    "is_human": "boolean",
    "assistive_tech": "string",     # none | screen_reader | magnifier | unknown
    "task_id": "string",
    "task_title": "string",
    "task_group": "string",
    "familiarity": "string",
    "difficulty_before": "string",
    "difficulty_after": "string",
    "success": "boolean",
    "start_ms": "int64",
    "end_ms": "int64",
    "url_domain": "string",
    "browser": "string",
}


def session_frame(rows: list[dict] | pd.DataFrame) -> pd.DataFrame:
    df = rows if isinstance(rows, pd.DataFrame) else pd.DataFrame(rows)
    for col, dtype in SESSION_COLUMNS.items():
        if col not in df.columns:
            df[col] = pd.Series(index=df.index, dtype=dtype if dtype != "int64" else "Int64")
    extra = [c for c in df.columns if c not in SESSION_COLUMNS]
    df = df[list(SESSION_COLUMNS) + extra]
    return df.astype(SESSION_COLUMNS)
