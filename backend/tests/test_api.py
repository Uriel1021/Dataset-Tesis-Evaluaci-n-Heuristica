"""Pruebas de la API con una base SQLite temporal (no toca backend/data/usab.db)."""

import os
import tempfile

import pytest

_TMP = tempfile.mkdtemp()
os.environ["USAB_DATABASE_URL"] = f"sqlite:///{_TMP}/test.db"
os.environ.pop("USAB_API_KEY", None)

from fastapi.testclient import TestClient  # noqa: E402

from backend.app.main import app  # noqa: E402

API = "/api/v1"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _events(t0, n=40):
    ev = [{"type": "page_view", "ts": t0, "url": "https://campus.example.edu/curso"}]
    for i in range(n):
        t = t0 + 1500 * (i + 1)
        ev.append({"type": "mouse_move", "ts": t, "x": 100 + i, "y": 200 + i})
        if i % 4 == 0:
            ev.append({"type": "click", "ts": t + 50, "x": 100 + i, "y": 200 + i, "target_tag": "BUTTON", "target_id": "#enviar"})
        if i % 5 == 0:
            ev.append({"type": "scroll_pos", "ts": t + 80, "scroll_y": 100 * (i % 3), "url": "https://campus.example.edu/curso"})
        if i % 6 == 0:
            ev += [{"type": "focus", "ts": t + 90, "target_id": "#q", "target_tag": "input"},
                   {"type": "key", "ts": t + 100, "key": "h"}, {"type": "key", "ts": t + 120, "key": "Backspace"},
                   {"type": "input", "ts": t + 130, "target_id": "#q", "target_tag": "input"}]
    return ev


def test_health_and_model(client):
    assert client.get("/health").json()["status"] == "ok"
    m = client.get(f"{API}/model").json()
    assert set(m["heuristics"]) == {"H1", "H4", "H5", "H6"} and m["n_features"] > 0
    s = client.get(f"{API}/model/schema").json()
    assert "click" in s["event_types"] and "task_group" in s["categories"]


def test_full_flow_crud_and_evaluation(client):
    r = client.post(f"{API}/participants", json={"id": "p-001", "user_group": "sighted", "assistive_tech": "none"})
    assert r.status_code == 201
    assert client.post(f"{API}/participants", json={"id": "p-001"}).status_code == 409
    assert client.put(f"{API}/participants/p-001", json={"notes": "piloto"}).json()["notes"] == "piloto"

    t0 = 1_760_000_000_000
    r = client.post(f"{API}/sessions", json={"id": "s-001", "participant_id": "p-001", "task_group": "Browsing and Web",
                                            "familiarity": "High", "difficulty_before": "Low", "started_at_ms": t0})
    assert r.status_code == 201 and r.json()["status"] == "open"

    ev = _events(t0)
    r = client.post(f"{API}/sessions/s-001/events", json={"events": ev[:50]})
    assert r.status_code == 201 and r.json()["received"] == 50
    r = client.post(f"{API}/sessions/s-001/events", json={"events": ev[50:]})
    assert r.json()["total_events"] == len(ev)

    keys = client.get(f"{API}/sessions/s-001/events", params={"type": "key"}).json()
    assert {k["key"] for k in keys} == {"char", "backspace"}            # privacidad: no se guarda la letra

    r = client.put(f"{API}/sessions/s-001", json={"ended_at_ms": t0 + 70_000, "success": True, "difficulty_after": "Easy"})
    assert r.json()["status"] == "closed"

    r = client.post(f"{API}/sessions/s-001/evaluate", params={"include_features": True})
    assert r.status_code == 200, r.text
    body = r.json()
    assert [x["heuristic"] for x in body["results"]] == ["H1", "H4", "H5", "H6"]
    assert all(0 <= x["probability"] <= 1 for x in body["results"])
    assert body["features"]["n_clicks"] == 10 and body["features"]["correction_key_ratio"] == 0.5
    assert client.get(f"{API}/sessions/s-001/evaluation").status_code == 200
    assert client.put(f"{API}/sessions/s-001/evaluation").status_code == 200
    assert client.post(f"{API}/sessions/s-001/events", json={"events": ev[:1]}).status_code == 409
    assert len(client.get(f"{API}/participants/p-001/evaluations").json()) == 1

    assert client.delete(f"{API}/sessions/s-001/evaluation").status_code == 204
    assert client.get(f"{API}/sessions/s-001/evaluation").status_code == 404
    assert client.delete(f"{API}/sessions/s-001/events").status_code == 204
    assert client.get(f"{API}/sessions/s-001").json()["n_events"] == 0
    assert client.delete(f"{API}/sessions/s-001").status_code == 204
    assert client.delete(f"{API}/participants/p-001").status_code == 204
    assert client.get(f"{API}/participants/p-001").status_code == 404


def test_stateless_predict_and_validation(client):
    t0 = 1_760_000_000_000
    r = client.post(f"{API}/predict", json={
        "participant": {"id": "anon", "user_group": "BLV", "assistive_tech": "screen_reader"},
        "session": {"participant_id": "anon", "task_group": "Curso en línea", "started_at_ms": t0},
        "session_outcome": {"ended_at_ms": t0 + 60_000, "success": False},
        "events": _events(t0)})
    assert r.status_code == 200, r.text
    assert any("no existe en el entrenamiento" in w for w in r.json()["warnings"])   # categoría nueva → advertencia
    assert client.get(f"{API}/participants/anon").status_code == 404                # no persiste
    bad = client.post(f"{API}/predict", json={"session": {"participant_id": "x", "started_at_ms": t0},
                                              "events": [{"type": "teleport", "ts": t0}]})
    assert bad.status_code == 422
