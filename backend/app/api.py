"""Endpoints REST. Prefijo: /api/v1 (ver main.py)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DB

from . import config, model_service as ms
from .db import Evaluation, Event, Participant, Session, get_db
from .schemas import (BatchResult, EvaluationOut, EventBatch, EventOut, HeuristicResult, ParticipantCreate,
                      ParticipantOut, ParticipantUpdate, PredictRequest, SessionCreate, SessionOut, SessionUpdate)


def require_key(x_api_key: str | None = Header(default=None)):
    if config.API_KEY and x_api_key != config.API_KEY:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "X-API-Key inválida o ausente")


router = APIRouter(dependencies=[Depends(require_key)])


def _404(what: str, id_: str):
    raise HTTPException(status.HTTP_404_NOT_FOUND, f"{what} '{id_}' no existe")


def _participant_out(db: DB, p: Participant) -> ParticipantOut:
    n = db.scalar(select(func.count()).select_from(Session).where(Session.participant_id == p.id))
    return ParticipantOut.model_validate(p).model_copy(update={"n_sessions": n})


def _session_out(db: DB, s: Session) -> SessionOut:
    n = db.scalar(select(func.count()).select_from(Event).where(Event.session_id == s.id))
    return SessionOut.model_validate(s).model_copy(update={"n_events": n})


# ================================================================ modelo
@router.get("/model", tags=["modelo"], summary="Información del modelo cargado y sus métricas de prueba")
def get_model():
    return ms.model_info()


@router.get("/model/schema", tags=["modelo"], summary="Categorías y tipos de evento que espera el modelo")
def get_schema():
    from .schemas import EventType
    return dict(event_types=[e.value for e in EventType], categories=ms.categories(),
                key_privacy="Las teclas imprimibles se almacenan como 'char'; solo se conservan teclas funcionales.",
                max_events_per_batch=config.MAX_EVENTS_PER_BATCH)


# ================================================================ participantes
@router.post("/participants", tags=["participantes"], status_code=201, response_model=ParticipantOut)
def create_participant(body: ParticipantCreate, db: DB = Depends(get_db)):
    if db.get(Participant, body.id):
        raise HTTPException(status.HTTP_409_CONFLICT, f"El participante '{body.id}' ya existe")
    p = Participant(id=body.id, user_group=body.user_group.value, assistive_tech=body.assistive_tech.value, notes=body.notes)
    db.add(p)
    db.commit()
    return _participant_out(db, p)


@router.get("/participants", tags=["participantes"], response_model=list[ParticipantOut])
def list_participants(limit: int = Query(100, le=1000), offset: int = 0, db: DB = Depends(get_db)):
    ps = db.scalars(select(Participant).order_by(Participant.created_at).limit(limit).offset(offset)).all()
    return [_participant_out(db, p) for p in ps]


@router.get("/participants/{participant_id}", tags=["participantes"], response_model=ParticipantOut)
def get_participant(participant_id: str, db: DB = Depends(get_db)):
    p = db.get(Participant, participant_id) or _404("Participante", participant_id)
    return _participant_out(db, p)


@router.put("/participants/{participant_id}", tags=["participantes"], response_model=ParticipantOut)
def update_participant(participant_id: str, body: ParticipantUpdate, db: DB = Depends(get_db)):
    p = db.get(Participant, participant_id) or _404("Participante", participant_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(p, k, v.value if hasattr(v, "value") else v)
    db.commit()
    return _participant_out(db, p)


@router.delete("/participants/{participant_id}", tags=["participantes"], status_code=204,
               summary="Elimina el participante y TODAS sus sesiones, eventos y evaluaciones")
def delete_participant(participant_id: str, db: DB = Depends(get_db)):
    p = db.get(Participant, participant_id) or _404("Participante", participant_id)
    db.delete(p)
    db.commit()
    return Response(status_code=204)


# ================================================================ sesiones
@router.post("/sessions", tags=["sesiones"], status_code=201, response_model=SessionOut)
def create_session(body: SessionCreate, db: DB = Depends(get_db)):
    db.get(Participant, body.participant_id) or _404("Participante", body.participant_id)
    sid = body.id or uuid.uuid4().hex
    if db.get(Session, sid):
        raise HTTPException(status.HTTP_409_CONFLICT, f"La sesión '{sid}' ya existe")
    data = body.model_dump(exclude={"id"})
    data = {k: (v.value if hasattr(v, "value") else v) for k, v in data.items()}
    s = Session(id=sid, **data)
    db.add(s)
    db.commit()
    return _session_out(db, s)


@router.get("/sessions", tags=["sesiones"], response_model=list[SessionOut])
def list_sessions(participant_id: str | None = None, status_: str | None = Query(None, alias="status"),
                  limit: int = Query(100, le=1000), offset: int = 0, db: DB = Depends(get_db)):
    q = select(Session).order_by(Session.started_at_ms)
    if participant_id:
        q = q.where(Session.participant_id == participant_id)
    if status_:
        q = q.where(Session.status == status_)
    return [_session_out(db, s) for s in db.scalars(q.limit(limit).offset(offset)).all()]


@router.get("/sessions/{session_id}", tags=["sesiones"], response_model=SessionOut)
def get_session(session_id: str, db: DB = Depends(get_db)):
    s = db.get(Session, session_id) or _404("Sesión", session_id)
    return _session_out(db, s)


@router.put("/sessions/{session_id}", tags=["sesiones"], response_model=SessionOut,
            summary="Actualiza contexto o cierra la sesión (ended_at_ms, success, difficulty_after)")
def update_session(session_id: str, body: SessionUpdate, db: DB = Depends(get_db)):
    s = db.get(Session, session_id) or _404("Sesión", session_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(s, k, v.value if hasattr(v, "value") else v)
    if body.ended_at_ms and body.status is None and s.status == "open":
        s.status = "closed"
    db.commit()
    return _session_out(db, s)


@router.delete("/sessions/{session_id}", tags=["sesiones"], status_code=204,
               summary="Elimina la sesión con sus eventos y su evaluación")
def delete_session(session_id: str, db: DB = Depends(get_db)):
    s = db.get(Session, session_id) or _404("Sesión", session_id)
    db.delete(s)
    db.commit()
    return Response(status_code=204)


# ================================================================ eventos
@router.post("/sessions/{session_id}/events", tags=["eventos"], status_code=201, response_model=BatchResult,
             summary="Agrega un lote de eventos (la extensión los envía cada pocos segundos)")
def add_events(session_id: str, body: EventBatch, db: DB = Depends(get_db)):
    s = db.get(Session, session_id) or _404("Sesión", session_id)
    if s.status == "evaluated":
        raise HTTPException(status.HTTP_409_CONFLICT, "La sesión ya fue evaluada; elimine la evaluación para agregar eventos")
    if len(body.events) > config.MAX_EVENTS_PER_BATCH:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"Máximo {config.MAX_EVENTS_PER_BATCH} eventos por lote")
    db.add_all([Event(session_id=session_id, ts_ms=e.ts, type=e.type.value, url=e.url, x=e.x, y=e.y, scroll_y=e.scroll_y,
                      key=e.key, target_id=e.target_id, target_tag=e.target_tag, target_role=e.target_role)
                for e in body.events])
    db.commit()
    total = db.scalar(select(func.count()).select_from(Event).where(Event.session_id == session_id))
    return BatchResult(session_id=session_id, received=len(body.events), total_events=total)


@router.get("/sessions/{session_id}/events", tags=["eventos"], response_model=list[EventOut])
def list_events(session_id: str, type: str | None = None, limit: int = Query(1000, le=50000), offset: int = 0,
                db: DB = Depends(get_db)):
    db.get(Session, session_id) or _404("Sesión", session_id)
    q = select(Event).where(Event.session_id == session_id).order_by(Event.ts_ms, Event.id)
    if type:
        q = q.where(Event.type == type)
    return db.scalars(q.limit(limit).offset(offset)).all()


@router.delete("/sessions/{session_id}/events", tags=["eventos"], status_code=204,
               summary="Borra todos los eventos de la sesión (y su evaluación, que dejaría de ser válida)")
def delete_events(session_id: str, db: DB = Depends(get_db)):
    s = db.get(Session, session_id) or _404("Sesión", session_id)
    db.query(Event).filter(Event.session_id == session_id).delete()
    if s.evaluation:
        db.delete(s.evaluation)
    s.status = "open"
    db.commit()
    return Response(status_code=204)


# ================================================================ evaluación
def _eval_out(e: Evaluation, include_features: bool) -> EvaluationOut:
    return EvaluationOut(
        session_id=e.session_id, model_version=e.model_version, created_at=e.created_at, n_events=e.n_events,
        history_sessions=e.history_sessions, warnings=e.warnings, features=e.features if include_features else None,
        results=[HeuristicResult(heuristic=h, name=ms.HEURISTICS[h], probability=round(e.probabilities[h], 4),
                                 threshold=round(e.thresholds[h], 4), violation=bool(e.predictions[h]))
                 for h in ms.HEURISTICS])


def _evaluate(db: DB, s: Session) -> Evaluation:
    events = [dict(ts_ms=e.ts_ms, type=e.type, url=e.url, x=e.x, y=e.y, scroll_y=e.scroll_y, key=e.key,
                   target_id=e.target_id, target_tag=e.target_tag, target_role=e.target_role)
              for e in sorted(s.events, key=lambda e: (e.ts_ms, e.id))]   # orden fijo: determinismo ante empates de ts
    if not events:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "La sesión no tiene eventos")
    p = s.participant
    sess = {c: getattr(s, c) for c in ("id", "task_id", "task_group", "familiarity", "difficulty_before",
                                       "difficulty_after", "success", "started_at_ms", "ended_at_ms")}
    part = dict(id=p.id, user_group=p.user_group, assistive_tech=p.assistive_tech)
    current, warnings = ms.session_features(sess, events, part)
    hist = db.scalars(select(Evaluation).join(Session).where(Session.participant_id == p.id,
                                                             Evaluation.session_id != s.id)).all()
    vec = ms.build_vector(current, [h.features for h in hist], sess, part, warnings)
    probs, preds, thr = ms.predict(vec)
    if s.evaluation:
        db.delete(s.evaluation)
        db.flush()
    ev = Evaluation(session_id=s.id, model_version=ms.bundle()["version"], features=ms.jsonable(vec), probabilities=probs,
                    predictions=preds, thresholds=thr, warnings=warnings, n_events=len(events), history_sessions=len(hist))
    db.add(ev)
    s.status = "evaluated"
    db.commit()
    return ev


@router.post("/sessions/{session_id}/evaluate", tags=["evaluación"], response_model=EvaluationOut,
             summary="Calcula métricas y evalúa H1/H4/H5/H6 con el Random Forest multi-salida")
def evaluate_session(session_id: str, include_features: bool = False, db: DB = Depends(get_db)):
    s = db.get(Session, session_id) or _404("Sesión", session_id)
    return _eval_out(_evaluate(db, s), include_features)


@router.get("/sessions/{session_id}/evaluation", tags=["evaluación"], response_model=EvaluationOut)
def get_evaluation(session_id: str, include_features: bool = False, db: DB = Depends(get_db)):
    s = db.get(Session, session_id) or _404("Sesión", session_id)
    if not s.evaluation:
        _404("Evaluación de la sesión", session_id)
    return _eval_out(s.evaluation, include_features)


@router.put("/sessions/{session_id}/evaluation", tags=["evaluación"], response_model=EvaluationOut,
            summary="Recalcula la evaluación (p. ej. tras actualizar success o difficulty_after)")
def reevaluate_session(session_id: str, include_features: bool = False, db: DB = Depends(get_db)):
    s = db.get(Session, session_id) or _404("Sesión", session_id)
    if not s.evaluation:
        _404("Evaluación de la sesión", session_id)
    return _eval_out(_evaluate(db, s), include_features)


@router.delete("/sessions/{session_id}/evaluation", tags=["evaluación"], status_code=204)
def delete_evaluation(session_id: str, db: DB = Depends(get_db)):
    s = db.get(Session, session_id) or _404("Sesión", session_id)
    if not s.evaluation:
        _404("Evaluación de la sesión", session_id)
    db.delete(s.evaluation)
    s.status = "closed" if s.ended_at_ms else "open"
    db.commit()
    return Response(status_code=204)


@router.get("/participants/{participant_id}/evaluations", tags=["evaluación"], response_model=list[EvaluationOut],
            summary="Todas las evaluaciones de un participante")
def participant_evaluations(participant_id: str, db: DB = Depends(get_db)):
    db.get(Participant, participant_id) or _404("Participante", participant_id)
    evs = db.scalars(select(Evaluation).join(Session).where(Session.participant_id == participant_id)
                     .order_by(Session.started_at_ms)).all()
    return [_eval_out(e, False) for e in evs]


@router.post("/predict", tags=["evaluación"], response_model=EvaluationOut,
             summary="Evaluación sin persistencia: envía contexto + eventos y recibe H1/H4/H5/H6")
def predict_stateless(body: PredictRequest, db: DB = Depends(get_db)):
    from datetime import datetime, timezone
    part = body.participant or ParticipantCreate(id=body.session.participant_id)
    sess = body.session.model_dump()
    sess["id"] = sess.get("id") or "stateless"
    if body.session_outcome:
        sess.update(body.session_outcome.model_dump(exclude_unset=True))
    sess = {k: (v.value if hasattr(v, "value") else v) for k, v in sess.items()}
    pdict = dict(id=part.id, user_group=part.user_group.value, assistive_tech=part.assistive_tech.value)
    events = [dict(ts_ms=e.ts, type=e.type.value, url=e.url, x=e.x, y=e.y, scroll_y=e.scroll_y, key=e.key,
                   target_id=e.target_id, target_tag=e.target_tag, target_role=e.target_role) for e in body.events]
    current, warnings = ms.session_features(sess, events, pdict)
    hist = db.scalars(select(Evaluation).join(Session).where(Session.participant_id == part.id)).all()
    vec = ms.build_vector(current, [h.features for h in hist], sess, pdict, warnings)
    probs, preds, thr = ms.predict(vec)
    e = Evaluation(session_id=sess["id"], model_version=ms.bundle()["version"], features=ms.jsonable(vec),
                   probabilities=probs, predictions=preds, thresholds=thr, warnings=warnings, n_events=len(events),
                   history_sessions=len(hist), created_at=datetime.now(timezone.utc))
    return _eval_out(e, body.include_features)
