"""Etapa 6 · Un solo modelo multi-etiqueta para H1, H4, H5 y H6.

`MultiHeuristicClassifier` recibe una sesión (X) y devuelve a la vez la
probabilidad y la decisión de violación de las cuatro heurísticas.

Estrategias comparadas (Read et al., 2011; Tsoumakas y Katakis, 2007):
  * binary_relevance  un clasificador por heurística dentro del mismo modelo
  * chain             cadena de clasificadores: cada heurística recibe además las
                      probabilidades de las anteriores (aprovecha la co-ocurrencia
                      de violaciones). En el entrenamiento se usan probabilidades
                      FUERA DE FOLD para no filtrar la etiqueta verdadera.
  * joint             un único estimador nativo multi-salida (RF, Extra Trees o
                      MLP) para las heurísticas con etiqueta completa; la que tiene
                      etiqueta parcial (H5, solo páginas con formularios) usa una
                      cabeza que recibe X + las probabilidades conjuntas.

Etiquetas faltantes: NA significa "no evaluable" (la página no tiene los
elementos), NO "sin violación". Cada salida se entrena solo con sus filas
etiquetadas y se evalúa solo donde hay etiqueta.

Protocolo: misma partición 70/30 por participante de la etapa 5; estrategia,
estimador base, hiperparámetros, conjunto de variables y umbrales por
heurística se eligen SOLO con validación cruzada agrupada en el 70 %.
"""

from __future__ import annotations

import json
import warnings

import joblib
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, ClassifierMixin, clone
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, hamming_loss, matthews_corrcoef
from sklearn.model_selection import GroupKFold
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from . import config
from .modeling import (MODELS_DIR, SEED, TARGETS, TRAINING, best_threshold, bootstrap_ci, mcnemar_p, metrics)

OUT = config.REPORTS / "06_modelo_multietiqueta"


def base_estimators() -> dict[str, Pipeline]:
    imp = ("imp", SimpleImputer(strategy="median"))
    return {
        "Random Forest": Pipeline([imp, ("m", RandomForestClassifier(n_estimators=500, min_samples_leaf=3, max_features=0.5,
                                                                    class_weight="balanced_subsample", random_state=SEED, n_jobs=-1))]),
        "Extra Trees": Pipeline([imp, ("m", ExtraTreesClassifier(n_estimators=500, min_samples_leaf=3, max_features=0.5,
                                                                class_weight="balanced_subsample", random_state=SEED, n_jobs=-1))]),
        "Red Neuronal (MLP)": Pipeline([imp, ("sc", StandardScaler()),
                                        ("m", MLPClassifier(hidden_layer_sizes=(64, 32), alpha=0.1, max_iter=3000, random_state=SEED))]),
        "Regresión Logística": Pipeline([imp, ("sc", StandardScaler()),
                                         ("m", LogisticRegression(C=0.1, class_weight="balanced", max_iter=5000))]),
    }


NATIVE_MULTIOUTPUT = {"Random Forest", "Extra Trees", "Red Neuronal (MLP)"}


def _oof(est, X, y, groups, n_splits=4) -> np.ndarray:
    """Probabilidades fuera de fold, agrupadas por participante."""
    p = np.full(len(y), np.nan)
    k = min(n_splits, len(np.unique(groups)))
    for tr, te in GroupKFold(n_splits=k).split(X, y, groups):
        if len(np.unique(y[tr])) < 2:
            p[te] = y[tr].mean()
            continue
        p[te] = clone(est).fit(X[tr], y[tr]).predict_proba(X[te])[:, 1]
    return p


class MultiHeuristicClassifier(BaseEstimator, ClassifierMixin):
    """Un modelo, cuatro salidas (H1, H4, H5, H6). Y puede contener NaN."""

    def __init__(self, base, strategy="chain", labels=tuple(TARGETS), order=None, base_name=""):
        self.base, self.strategy, self.labels, self.order, self.base_name = base, strategy, labels, order, base_name

    # ---- ajuste
    def fit(self, X, Y, groups=None):
        X = np.asarray(X, dtype=float)
        Y = pd.DataFrame(Y, columns=list(self.labels)).astype(float)
        groups = np.asarray(groups) if groups is not None else np.arange(len(X))
        full = [c for c in self.labels if Y[c].notna().all()]
        partial = [c for c in self.labels if c not in full]
        self.models_, self.feature_order_ = {}, []
        if self.strategy == "binary_relevance":
            for c in self.labels:
                m = Y[c].notna().to_numpy()
                self.models_[c] = clone(self.base).fit(X[m], Y[c][m].astype(int))
        elif self.strategy == "chain":
            order = list(self.order or sorted(self.labels, key=lambda c: -Y[c].notna().sum()))
            self.feature_order_ = order
            aug = X.copy()
            for c in order:
                m = Y[c].notna().to_numpy()
                y = Y[c][m].astype(int).to_numpy()
                self.models_[c] = clone(self.base).fit(aug[m], y)
                col = np.full(len(X), np.nan)
                col[m] = _oof(self.base, aug[m], y, groups[m])               # fuera de fold en las filas etiquetadas
                if (~m).any():
                    col[~m] = self.models_[c].predict_proba(aug[~m])[:, 1]   # en las no etiquetadas: predicción
                aug = np.column_stack([aug, col])
        elif self.strategy == "joint":
            if not hasattr(self.base[-1], "n_outputs_") and self.base_name not in NATIVE_MULTIOUTPUT:
                raise ValueError("joint requiere un estimador multi-salida nativo")
            self.full_, self.partial_ = full, partial
            self.models_["__joint__"] = clone(self.base).fit(X, Y[full].astype(int).to_numpy())
            oof = np.column_stack([_oof(self.base, X, Y[c].astype(int).to_numpy(), groups) for c in full])
            for c in partial:
                m = Y[c].notna().to_numpy()
                self.models_[c] = clone(self.base).fit(np.column_stack([X, oof])[m], Y[c][m].astype(int))
        else:
            raise ValueError(self.strategy)
        self.thresholds_ = {c: 0.5 for c in self.labels}
        return self

    # ---- predicción
    def predict_proba_frame(self, X) -> pd.DataFrame:
        X = np.asarray(X, dtype=float)
        out = {}
        if self.strategy == "binary_relevance":
            for c in self.labels:
                out[c] = self.models_[c].predict_proba(X)[:, 1]
        elif self.strategy == "chain":
            aug = X.copy()
            for c in self.feature_order_:
                out[c] = self.models_[c].predict_proba(aug)[:, 1]
                aug = np.column_stack([aug, out[c]])
        else:
            pj = self.models_["__joint__"].predict_proba(X)
            pj = pj if isinstance(pj, list) else [np.column_stack([1 - pj[:, i], pj[:, i]]) for i in range(pj.shape[1])]
            for i, c in enumerate(self.full_):
                out[c] = pj[i][:, 1]
            jp = np.column_stack([out[c] for c in self.full_])
            for c in self.partial_:
                out[c] = self.models_[c].predict_proba(np.column_stack([X, jp]))[:, 1]
        return pd.DataFrame(out)[list(self.labels)]

    def predict(self, X) -> pd.DataFrame:
        p = self.predict_proba_frame(X)
        return pd.DataFrame({c: (p[c] >= self.thresholds_[c]).astype(int) for c in self.labels})


# ----------------------------------------------------------------- evaluación
def _oof_multilabel(model: MultiHeuristicClassifier, X, Y, groups) -> pd.DataFrame:
    p = pd.DataFrame(np.nan, index=range(len(X)), columns=list(model.labels))
    for tr, te in GroupKFold(n_splits=4).split(X, groups=groups):
        mdl = clone(model).fit(X[tr], Y.iloc[tr], groups=groups[tr])
        p.iloc[te] = mdl.predict_proba_frame(X[te]).to_numpy()
    return p


def multilabel_summary(Y: pd.DataFrame, P: pd.DataFrame, thr: dict) -> dict:
    yh = pd.DataFrame({c: (P[c] >= thr[c]).astype(int) for c in Y})
    full = [c for c in Y if Y[c].notna().all()]
    per = {}
    for c in Y:
        m = Y[c].notna()
        y = Y[c][m].astype(int)
        per[c] = (f1_score(y, yh[c][m]), matthews_corrcoef(y, yh[c][m]))
    yy, hh = Y[full].astype(int).to_numpy(), yh[full].to_numpy()
    return dict(
        f1_macro=np.mean([v[0] for v in per.values()]), mcc_macro=np.mean([v[1] for v in per.values()]),
        f1_micro_H1H4H6=f1_score(yy, hh, average="micro"),
        hamming_loss_H1H4H6=hamming_loss(yy, hh), exact_match_H1H4H6=float((yy == hh).all(axis=1).mean()),
    )


def run(log=print) -> pd.DataFrame:
    warnings.filterwarnings("ignore")
    OUT.mkdir(parents=True, exist_ok=True)
    df = pd.read_parquet(TRAINING / "training_dataset.parquet")
    spec = json.loads((TRAINING / "feature_spec.json").read_text())
    df = df[df.include_main].copy()
    part = pd.read_csv(config.REPORTS / "05_modelado" / "particion_70_30.csv")[["session_id", "particion"]]
    df = df.merge(part, on="session_id")
    G = spec["feature_groups"]
    num = G["behavior"] + G["iso_process"] + G["iso_outcome"]
    rank = df.groupby("participant_id")[num].rank(pct=True).add_prefix("intra_")
    df = pd.concat([df.reset_index(drop=True), rank.reset_index(drop=True)], axis=1)
    feature_sets = {"completo": spec["feature_columns"], "completo+intra_participante": spec["feature_columns"] + list(rank.columns)}

    tr, te = df[df.particion == "train"].reset_index(drop=True), df[df.particion == "test"].reset_index(drop=True)
    Ytr, Yte = tr[TARGETS].astype(float), te[TARGETS].astype(float)
    gtr = tr.participant_id.to_numpy()

    rows, best = [], None
    for fs, F in feature_sets.items():
        Xtr = tr[F].to_numpy(dtype=float)
        for bname, base in base_estimators().items():
            for strategy in ("binary_relevance", "chain", "joint"):
                if strategy == "joint" and bname not in NATIVE_MULTIOUTPUT:
                    continue
                model = MultiHeuristicClassifier(base, strategy=strategy, base_name=bname)
                P = _oof_multilabel(model, Xtr, Ytr, gtr)
                thr = {c: best_threshold(Ytr[c][Ytr[c].notna()].astype(int).to_numpy(), P[c][Ytr[c].notna()].to_numpy())
                       for c in TARGETS}
                s = multilabel_summary(Ytr, P, thr)
                rows.append(dict(estrategia=strategy, estimador=bname, variables=fs, **{f"cv_{k}": v for k, v in s.items()},
                                 umbrales=json.dumps({k[2:]: round(v, 3) for k, v in thr.items()})))
                log(f"  {strategy:17s} · {bname:20s} · {fs:28s} CV MCC macro={s['mcc_macro']:.3f} F1 macro={s['f1_macro']:.3f}")
                if best is None or s["mcc_macro"] > best[0]:
                    best = (s["mcc_macro"], strategy, bname, fs, thr)
    cv_df = pd.DataFrame(rows).sort_values("cv_mcc_macro", ascending=False)
    cv_df.to_csv(OUT / "comparacion_cv_70.csv", index=False)

    # ---- modelo final: se reentrena en todo el 70 % y se evalúa UNA vez en el 30 %
    _, strategy, bname, fs, thr = best
    F = feature_sets[fs]
    final = MultiHeuristicClassifier(base_estimators()[bname], strategy=strategy, base_name=bname)
    final.fit(tr[F].to_numpy(dtype=float), Ytr, groups=gtr)
    final.thresholds_ = thr
    P = final.predict_proba_frame(te[F].to_numpy(dtype=float))
    per = []
    gte = te.participant_id.to_numpy()
    for c in TARGETS:
        m = Yte[c].notna().to_numpy()
        y, p = Yte[c][m].astype(int).to_numpy(), P[c][m].to_numpy()
        base_pred = np.full(len(y), int(Ytr[c].dropna().mean() >= 0.5))
        per.append(dict(heuristica=c[2:], **metrics(y, p, thr[c]), **bootstrap_ci(y, p, thr[c], gte[m]),
                        mcnemar_p_vs_base=mcnemar_p(y, (p >= thr[c]).astype(int), base_pred)))
    per = pd.DataFrame(per)
    glob = multilabel_summary(Yte, P, thr)
    per.to_csv(OUT / "resultados_test_30_por_heuristica.csv", index=False)
    pd.DataFrame([dict(estrategia=strategy, estimador=bname, variables=fs, **glob)]).to_csv(OUT / "resultados_test_30_global.csv", index=False)
    pd.concat([te[["session_id", "participant_id"]], Yte.add_prefix("real_"), P.add_prefix("prob_")], axis=1).to_csv(
        OUT / "predicciones_test.csv", index=False)
    MODELS_DIR.mkdir(exist_ok=True)
    joblib.dump(dict(model=final, features=F, thresholds=thr, labels=TARGETS, strategy=strategy, base=bname,
                     usage="bundle['model'].predict_proba_frame(X[bundle['features']]) → probabilidades H1/H4/H5/H6"),
                MODELS_DIR / "modelo_multietiqueta_H1_H4_H5_H6.joblib")
    _report(cv_df, per, glob, strategy, bname, fs, tr, te)
    log(f"  seleccionado por CV → {strategy} · {bname} · {fs}")
    log(f"  test: F1 macro={glob['f1_macro']:.3f} · MCC macro={glob['mcc_macro']:.3f} · Hamming={glob['hamming_loss_H1H4H6']:.3f}")
    return per


def _report(cv_df, per, glob, strategy, bname, fs, tr, te) -> None:
    from .report import _md
    cols = ["heuristica", "n", "positivos", "umbral", "exactitud", "exactitud_balanceada", "precision", "sensibilidad",
            "especificidad", "f1", "mcc", "kappa", "roc_auc", "pr_auc"]
    txt = ["# Etapa 6 · Un solo modelo multi-etiqueta (H1, H4, H5, H6)", "",
           f"Modelo seleccionado por validación cruzada en el 70 %: **{strategy} · {bname} · variables {fs}**", "",
           f"Entrenamiento: {len(tr)} sesiones / {tr.participant_id.nunique()} participantes · "
           f"prueba: {len(te)} sesiones / {te.participant_id.nunique()} participantes (misma partición que la etapa 5).", "",
           "## Resultados en el 30 % de prueba · por heurística", "", _md(per[cols].round(3)), "",
           _md(per[["heuristica"] + [c for c in per.columns if c.endswith("_ic95")] + ["mcnemar_p_vs_base"]].round(3)), "",
           "## Métricas multi-etiqueta (30 % de prueba)", "", _md(pd.DataFrame([glob]).round(3)), "",
           "`hamming_loss` = proporción de decisiones erróneas; `exact_match` = sesiones con las tres decisiones "
           "(H1, H4, H6) correctas a la vez. H5 se excluye de estas dos porque solo está etiquetada en páginas con formularios.", "",
           "## Comparación de estrategias (validación cruzada en el 70 %)", "",
           _md(cv_df.round(3)), ""]
    (OUT / "README.md").write_text("\n".join(txt), encoding="utf-8")
