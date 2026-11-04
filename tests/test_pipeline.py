"""Pruebas de las definiciones operacionales (no requieren los datos crudos)."""

import numpy as np
import pandas as pd
import pytest

from usab_ds import build, config, dom_static, events, metrics
from usab_ds.adapters import vt_prototypes

ALL_CAPS = {"click", "key", "scroll", "scroll_y", "mouse_move", "page_view", "focus", "blur", "input",
            "nav_back", "hover", "target_tag", "target_id", "key_name"}


def _session(ev_rows, caps=ALL_CAPS, start=0, end=60_000, **meta):
    ev = pd.DataFrame(ev_rows)
    ev["source"] = "T"
    ev["session_id"] = "T:1"
    ev = events.frame(ev)
    s = events.session_frame([dict(source="T", session_id="T:1", is_human=True, start_ms=start, end_ms=end, **meta)])
    return metrics.compute(s, ev, caps).iloc[0]


@pytest.mark.parametrize("raw, code", [
    ("Visibility of system status", "H1"), ("4) Consistency and standards", "H4"), ("Prevention of errors", "H5"),
    ("6) Recognition rather than recall", "H6"), ("Consistency & Standards", "H4"), ("Hep and Documentation", "H10"),
    ("Something else", None),
])
def test_heuristic_code(raw, code):
    assert config.heuristic_code(raw) == code


@pytest.mark.parametrize("text, code", [
    ("4. Consistency and Standards", "H4"),
    ("Evaluation Based on Error Prevention (Heuristic Evaluation)", "H5"),
    ("Heuristic Evaluation of Recognition Rather Than Recall in Blog App (Lo-Fi Prototype)", "H6"),
    ("Heuristic Evaluation for 'Visibility of System Status' in the Low-Fidelity Prototype", "H1"),
    ("4. The heuristic principle of Consistency and Standards", None),     # plantilla
    ("Improve Consistency and Standards Across All Screens", None),        # recomendación
])
def test_vt_header_detection(text, code):
    assert vt_prototypes._header_code(text, 0) == code


def test_counts_and_rates():
    r = _session([
        dict(ts_ms=0, event="page_view", url="u1"),
        dict(ts_ms=1000, event="click", x=10, y=10, target_id="b", target_tag="button"),
        dict(ts_ms=1500, event="click", x=12, y=11, target_id="b", target_tag="button"),   # repetido (<1 s, mismo id)
        dict(ts_ms=4000, event="click", x=300, y=300, target_id="d", target_tag="div"),    # clic muerto
        dict(ts_ms=5000, event="key", key="a"),
        dict(ts_ms=5200, event="key", key="backspace"),
        dict(ts_ms=30000, event="page_view", url="u1"),                                     # revisita
    ])
    assert r.n_clicks == 3 and r.n_keys == 2
    assert r.clicks_per_min == pytest.approx(3.0)
    assert r.repeated_click_rate == pytest.approx(1 / 3)
    assert r.dead_click_rate == pytest.approx(1 / 3)
    assert r.correction_key_ratio == pytest.approx(0.5)
    assert r.page_revisit_rate == pytest.approx(0.5)
    assert r.iso_efficiency_actions == 5
    # pausas > 5 s: 30000-5200 = 24.8 s sobre 60 s
    assert r.long_pause_ratio == pytest.approx(24.8 / 60)


def test_missing_capability_is_nan_not_zero():
    r = _session([dict(ts_ms=0, event="click", x=1, y=1), dict(ts_ms=10, event="key")], caps={"click", "key"})
    assert np.isnan(r.dead_click_rate)        # sin target_tag
    assert np.isnan(r.correction_key_ratio)   # sin key_name
    assert np.isnan(r.back_nav_rate)
    assert np.isnan(r.scroll_reversal_rate)


def test_scroll_reversals():
    rows = [dict(ts_ms=i * 100, event="scroll_pos", url="u", scroll_y=y) for i, y in enumerate([0, 100, 200, 100, 300])]
    r = _session(rows)
    assert r.scroll_distance_px == 500
    assert r.scroll_reversal_rate == pytest.approx(2 / 4)


def test_input_reentry():
    rows = [dict(ts_ms=0, event="focus", target_id="f1"), dict(ts_ms=1, event="input", target_id="f1"),
            dict(ts_ms=2, event="focus", target_id="f2"), dict(ts_ms=3, event="input", target_id="f2"),
            dict(ts_ms=4, event="focus", target_id="f1"), dict(ts_ms=5, event="input", target_id="f1")]
    assert _session(rows).input_reentry_rate == pytest.approx(0.5)


def test_success_time_based_efficiency():
    r = _session([dict(ts_ms=0, event="click", x=0, y=0)], end=120_000, success=True)
    assert r.iso_effectiveness_task_completion == 1
    assert r.iso_efficiency_time_based == pytest.approx(0.5)  # 1 tarea / 2 min


def test_krippendorff_alpha():
    assert build.krippendorff_alpha_nominal([[1, 1], [0, 0], [1, 1]]) == pytest.approx(1.0)
    assert np.isnan(build.krippendorff_alpha_nominal([[1, 1, 1], [1, 1]]))  # sin variación
    # ejemplo con desacuerdo total en 2 de 4 unidades
    a = build.krippendorff_alpha_nominal([[1, 1], [0, 0], [1, 0], [0, 1]])
    assert a < 0.5


def test_dom_features():
    html = """<html><body><nav><a href="/a">Inicio</a><a href="/b">Inicio</a></nav>
      <div aria-live="polite"></div><div class="spinner"></div>
      <form><label for="e">Email</label><input id="e" type="email" autocomplete="email">
      <input name="q" placeholder="Buscar"><button class="btn">Enviar</button></form>
      <img src="x.png" alt="x"><img src="y.png"><h1>T</h1></body></html>"""
    f = dom_static.features_from_html(html)
    assert f["dom_status_regions"] == 1 and f["dom_loading_indicators"] == 1
    assert f["dom_has_nav"] == 1 and f["dom_inconsistent_link_text"] == 1.0
    assert f["dom_input_label_ratio"] == 0.5 and f["dom_placeholder_only_ratio"] == 0.5
    assert f["dom_input_constraint_ratio"] == 0.5 and f["dom_img_alt_ratio"] == 0.5


def test_clean_html_strips_and_flags_truncation():
    from usab_ds import silver_labels as sl
    c = sl.cfg()
    html = "<html><head><script>x()</script><style>.a{}</style></head><body>" \
           "<div class='very-long-css' data-x='1' aria-label='Menú'><input type='email' required placeholder='E-mail'></div>" \
           + "<p>texto</p>" * 10 + "</body></html>"
    out, trunc, n = sl.clean_html(html, c)
    assert "script" not in out and "style" not in out and "data-x" not in out and "class=" not in out
    assert 'aria-label="Menú"' in out and "required" in out and not trunc
    c2 = {**c, "html": {**c["html"], "max_chars": 50}}
    out2, trunc2, n2 = sl.clean_html(html, c2)
    assert trunc2 and len(out2) == 50 and n2 > 50


def test_silver_schema_has_target_codes():
    from usab_ds import silver_labels as sl
    item = sl.SCHEMA["properties"]["heuristics"]["items"]
    assert item["properties"]["code"]["enum"] == ["H1", "H4", "H5", "H6"]
    assert "task" not in sl.system_prompt().lower()  # el evaluador no ve la tarea ni el comportamiento


def _rub(html):
    from usab_ds import rubric_labels as rl
    return {r["check"]: r for r in rl.evaluate_html(html)}


def test_rubric_detects_and_respects_corrections():
    from usab_ds import rubric_labels as rl
    bad = """<html><head></head><body><nav><a href="/a">A</a><a href="/b">B</a><a href="/c">C</a></nav>
      <form><input name="email" type="text"><input name="q" type="search"><button></button></form>
      <img src="x.png"><div tabindex="0">Más</div><h2 tabindex="0">Título</h2></body></html>"""
    r = _rub(bad)
    assert r["H1_page_title"]["affected"] == 1
    assert r["H1_current_location"]["affected"] == 1
    assert r["H5_input_type_mismatch"]["affected"] == 1          # email con type=text
    assert r["H5_autocomplete_missing"]["affected"] == 1
    assert r["H6_unlabeled_inputs"]["affected"] == 2
    assert r["H6_unnamed_controls"]["affected"] == 1             # <button></button>
    assert r["H6_images_without_alt"]["affected"] == 1
    assert r["H4_nonstandard_controls"]["eligible"] == 1         # A3: el <h2 tabindex> no cuenta
    good = """<html lang="es"><head><title>Ok</title></head><body>
      <nav><a href="/a" aria-current="page">A</a><a href="/b">B</a><a href="/c">C</a></nav>
      <form><label for="e">Correo o teléfono</label><input id="e" name="email_or_phone" type="text" autocomplete="username">
      <div role="status" aria-live="polite"></div></form><img src="x.png" alt=""></body></html>"""
    g = _rub(good)
    assert all(rl.severity(c, v["eligible"], v["affected"]) == 0 for c, v in g.items())


def test_severity_follows_impact_and_frequency():
    from usab_ds import rubric_labels as rl
    assert rl.severity("H6_unlabeled_inputs", 10, 5) == 3   # A, 50 %
    assert rl.severity("H6_unlabeled_inputs", 10, 1) == 2   # A, 10 %
    assert rl.severity("H6_unlabeled_inputs", 100, 1) == 1  # A, 1 % → cosmético, no es violación
    assert rl.severity("H1_status_messages", 1, 1) == 2     # AA binario
    assert rl.severity("H1_current_location", 1, 1) == 1   # AAA → nunca alcanza violación por sí sola


@pytest.mark.parametrize("strategy", ["binary_relevance", "chain", "joint"])
def test_multilabel_handles_missing_labels(strategy):
    from usab_ds.multilabel import MultiHeuristicClassifier, base_estimators
    rng = np.random.default_rng(0)
    X = rng.normal(size=(80, 5))
    Y = pd.DataFrame({"y_H1": (X[:, 0] > 0).astype(float), "y_H4": (X[:, 1] > 0).astype(float),
                      "y_H5": np.where(np.arange(80) < 30, (X[:, 2] > 0).astype(float), np.nan),
                      "y_H6": (X[:, 3] > 0).astype(float)})
    m = MultiHeuristicClassifier(base_estimators()["Random Forest"], strategy=strategy, base_name="Random Forest")
    m.fit(X, Y, groups=np.repeat(np.arange(8), 10))
    P = m.predict_proba_frame(X)
    assert list(P.columns) == ["y_H1", "y_H4", "y_H5", "y_H6"] and P.notna().all().all()
    assert m.predict(X).isin([0, 1]).all().all()


def test_neural_masked_loss_ignores_missing_labels():
    import torch
    from usab_ds.neural import _masked_bce
    logits = torch.tensor([[0.0, 5.0], [0.0, -5.0]])
    y = torch.tensor([[1.0, float("nan")], [0.0, float("nan")]])
    mask = (~torch.isnan(y)).float()
    a = _masked_bce(logits, y, mask, torch.ones(2))
    logits2 = logits.clone(); logits2[:, 1] = 100.0          # cambiar la salida enmascarada no debe alterar la pérdida
    assert torch.isclose(a, _masked_bce(logits2, y, mask, torch.ones(2)))


def test_neural_ensemble_outputs_four_heuristics():
    from usab_ds.neural import NeuralEnsemble
    rng = np.random.default_rng(0)
    X = rng.normal(size=(60, 6)); X[::7, 2] = np.nan
    Y = np.column_stack([(X[:, 0] > 0), (X[:, 1] > 0), np.where(np.arange(60) < 25, X[:, 3] > 0, np.nan), (X[:, 4] > 0)]).astype(float)
    cfg = dict(hidden=(16,), dropout=0.1, weight_decay=1e-3, lr=3e-3, act="relu", head_hidden=0, batch=16,
               n_seeds=2, max_epochs=20, patience=5)
    m = NeuralEnsemble(cfg).fit(X, Y, np.repeat(np.arange(6), 10))
    P = m.predict_proba_frame(X)
    assert P.shape == (60, 4) and P.notna().all().all() and ((P >= 0) & (P <= 1)).all().all()
