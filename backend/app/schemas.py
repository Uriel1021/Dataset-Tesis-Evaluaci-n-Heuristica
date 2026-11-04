"""Contrato de datos entre la extensión web y el backend (Pydantic v2).

Los tipos de evento son exactamente los del esquema canónico usado para
entrenar el modelo (src/usab_ds/events.py), de modo que las métricas se
calculan igual en producción que en el entrenamiento.
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EventType(str, Enum):
    page_view = "page_view"     # carga o cambio de URL
    click = "click"
    dblclick = "dblclick"
    scroll = "scroll"           # acción de desplazamiento (rueda / teclado)
    scroll_pos = "scroll_pos"   # posición vertical reportada por la página (scrollY)
    key = "key"
    input = "input"             # cambio de valor de un campo (sin el valor)
    focus = "focus"
    blur = "blur"
    nav_back = "nav_back"       # botón Atrás / history.back / Alt+←
    mouse_move = "mouse_move"
    hover = "hover"


class UserGroup(str, Enum):
    BLV = "BLV"
    sighted = "sighted"
    unknown = "unknown"


class AssistiveTech(str, Enum):
    none = "none"
    screen_reader = "screen_reader"
    magnifier = "magnifier"
    unknown = "unknown"


class Level(str, Enum):
    Low = "Low"
    Medium = "Medium"
    High = "High"
    Easy = "Easy"
    Hard = "Hard"


# Teclas que se conservan por nombre; cualquier carácter imprimible se reduce a "char".
FUNCTIONAL_KEYS = {"backspace", "delete", "enter", "tab", "escape", "esc", "arrowup", "arrowdown", "arrowleft",
                   "arrowright", "up", "down", "left", "right", "home", "end", "pageup", "pagedown", "shift", "control",
                   "ctrl", "alt", "meta", "capslock", "space", "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9",
                   "f10", "f11", "f12"}


def sanitize_key(k: str | None) -> str | None:
    """Privacidad: nunca se almacena el texto escrito. Atajos como 'ctrl+backspace' se conservan."""
    if k is None:
        return None
    k = k.strip().lower()
    parts = re.split(r"\s*\+\s*", k)
    if all(p in FUNCTIONAL_KEYS for p in parts):
        return k[:32]
    if len(parts) > 1 and any(p in {"ctrl", "control", "alt", "meta"} for p in parts[:-1]):
        return "+".join(parts[:-1] + ["char"])            # p. ej. ctrl+c → ctrl+char
    return "char"


# ----------------------------------------------------------------- participantes
class ParticipantCreate(BaseModel):
    id: Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_\-.:]+$",
                             description="Seudónimo estable generado por la extensión (no use nombres ni correos).")]
    user_group: UserGroup = UserGroup.unknown
    assistive_tech: AssistiveTech = AssistiveTech.unknown
    notes: str | None = None


class ParticipantUpdate(BaseModel):
    user_group: UserGroup | None = None
    assistive_tech: AssistiveTech | None = None
    notes: str | None = None


class ParticipantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_group: str
    assistive_tech: str
    notes: str | None
    created_at: datetime
    updated_at: datetime
    n_sessions: int = 0


# ----------------------------------------------------------------- sesiones
class SessionCreate(BaseModel):
    id: Annotated[str | None, Field(default=None, max_length=64, pattern=r"^[A-Za-z0-9_\-.:]+$",
                                    description="Opcional; si se omite el backend genera un UUID.")] = None
    participant_id: str
    task_id: str | None = None
    task_title: str | None = None
    task_group: str | None = Field(None, description="Ver GET /model/schema → categorías conocidas por el modelo.")
    familiarity: Level | None = None
    difficulty_before: Level | None = None
    url_start: str | None = None
    browser: str | None = None
    extension_version: str | None = None
    started_at_ms: int = Field(..., description="Epoch en milisegundos (Date.now() en la extensión).")


class SessionUpdate(BaseModel):
    task_id: str | None = None
    task_title: str | None = None
    task_group: str | None = None
    familiarity: Level | None = None
    difficulty_before: Level | None = None
    difficulty_after: Level | None = Field(None, description="Dificultad percibida al terminar la tarea.")
    success: bool | None = Field(None, description="¿El usuario completó la tarea? (efectividad ISO/IEC 25022)")
    ended_at_ms: int | None = None
    status: str | None = Field(None, pattern="^(open|closed)$")


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    participant_id: str
    task_id: str | None
    task_title: str | None
    task_group: str | None
    familiarity: str | None
    difficulty_before: str | None
    difficulty_after: str | None
    success: bool | None
    url_start: str | None
    browser: str | None
    extension_version: str | None
    started_at_ms: int
    ended_at_ms: int | None
    status: str
    created_at: datetime
    updated_at: datetime
    n_events: int = 0


# ----------------------------------------------------------------- eventos
class EventIn(BaseModel):
    type: EventType
    ts: int = Field(..., description="Epoch en milisegundos.")
    url: str | None = None
    x: float | None = None
    y: float | None = None
    scroll_y: float | None = None
    key: str | None = Field(None, description="Nombre de tecla; los caracteres imprimibles se guardan como 'char'.")
    target_id: str | None = Field(None, max_length=512, description="Selector CSS o id del elemento.")
    target_tag: str | None = Field(None, max_length=64, description="Etiqueta HTML en minúsculas (button, a, input…).")
    target_role: str | None = Field(None, max_length=64, description="Atributo role ARIA.")

    @field_validator("key")
    @classmethod
    def _privacy(cls, v):
        return sanitize_key(v)

    @field_validator("target_tag", "target_role")
    @classmethod
    def _lower(cls, v):
        return v.lower() if isinstance(v, str) else v


class EventBatch(BaseModel):
    events: list[EventIn] = Field(..., min_length=1)


class EventOut(EventIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    ts: int = Field(validation_alias="ts_ms")


class BatchResult(BaseModel):
    session_id: str
    received: int
    total_events: int


# ----------------------------------------------------------------- evaluación
class HeuristicResult(BaseModel):
    heuristic: str
    name: str
    probability: float
    threshold: float
    violation: bool


class EvaluationOut(BaseModel):
    session_id: str
    model_version: str
    created_at: datetime
    n_events: int
    history_sessions: int
    results: list[HeuristicResult]
    warnings: list[str]
    features: dict | None = None


class PredictRequest(BaseModel):
    """Evaluación sin guardar nada: eventos + contexto en una sola llamada."""
    participant: ParticipantCreate | None = None
    session: SessionCreate
    session_outcome: SessionUpdate | None = None
    events: list[EventIn] = Field(..., min_length=1)
    include_features: bool = False
