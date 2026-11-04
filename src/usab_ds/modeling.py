"""Etapa 5 · Entrenamiento y evaluación de los modelos candidatos de la tesis.

Modelos (tesis, Tabla 1 y §2.3.3): Regresión Logística, KNN, Naive Bayes,
Árbol de Decisión, Random Forest, Bagging, Extra Trees (ensamble por
aleatorización, Dietterich 2000), SVM sensible al costo y Red Neuronal (MLP);
más un clasificador trivial (línea base) y Gradient Boosting como contraste
empírico del argumento de la tesis sobre boosting con ruido.

Protocolo (sin fuga de información):
  1. Partición 70/30 POR PARTICIPANTE (estratificada por grupo BLV/vidente):
     ninguna persona aparece en entrenamiento y prueba.
  2. En el 70 %: búsqueda de hiperparámetros con validación cruzada agrupada
     (GroupKFold por participante) maximizando ROC-AUC; el conjunto de
     variables (con / sin resultados ISO de la tarea) se trata como un
     hiperparámetro más.
  3. Umbral de decisión: el que maximiza F1 en las predicciones fuera de fold
     del 70 % (nunca se mira el 30 %).
  4. Selección del mejor modelo por heurística según la validación cruzada.
  5. Evaluación ÚNICA en el 30 %: exactitud, exactitud balanceada, precisión,
     sensibilidad, especificidad, F1, MCC, κ de Cohen, ROC-AUC, PR-AUC, Brier,
     con IC 95 % por bootstrap por participante y prueba de McNemar frente a
     la línea base.
"""

from __future__ import annotations

import itertools
import json
import warnings

import joblib
import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTE
from imblearn.pipeline import Pipeline as ImbPipeline
from scipy.stats import binomtest
from sklearn.base import clone
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import (BaggingClassifier, ExtraTreesClassifier, HistGradientBoostingClassifier,
                              RandomForestClassifier)
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, average_precision_score, balanced_accuracy_score, brier_score_loss,
                             cohen_kappa_score, confusion_matrix, f1_score, matthews_corrcoef, precision_score,
                             recall_score, roc_auc_score)
from sklearn.model_selection import GridSearchCV, GroupKFold, cross_val_predict
from sklearn.naive_bayes import GaussianNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier

from . import config

SEED = 20261103
TEST_FRACTION = 0.30
TRAINING = config.PROCESSED / "training"
OUT = config.REPORTS / "05_modelado"
MODELS_DIR = config.ROOT / "models"
TARGETS = [f"y_{h}" for h in config.TARGET_HEURISTICS]


# ----------------------------------------------------------------- partición
def participant_split(df: pd.DataFrame) -> pd.Series:
    """Elige el conjunto de participantes de prueba cuyo número de filas quede
    más cerca del 30 %, con al menos 2 participantes de cada grupo y lo más
    parecido posible en prevalencia de etiquetas al total. Determinista."""
    hum = df[df.include_main]
    parts = hum.groupby("participant_id").agg(n=("session_id", "size"), grupo=("user_group", "first"),
                                             **{t: (t, "mean") for t in TARGETS})
    total = len(hum)
    prev = hum[TARGETS].mean()
    best, best_score = None, np.inf
    pids = sorted(parts.index)
    for k in range(4, 8):
        for comb in itertools.combinations(pids, k):
            sub = parts.loc[list(comb)]
            if (sub.grupo == "BLV").sum() < 2 or (sub.grupo == "sighted").sum() < 2:
                continue
            frac = sub.n.sum() / total
            rows = hum[hum.participant_id.isin(comb)]
            dprev = (rows[TARGETS].mean() - prev).abs().mean()
            score = abs(frac - TEST_FRACTION) * 4 + dprev
            if score < best_score:
                best, best_score = comb, score
    return df.participant_id.isin(best).map({True: "test", False: "train"})


# ----------------------------------------------------------------- modelos
def _pre(scale: bool) -> list:
    steps = [("imp", SimpleImputer(strategy="median"))]
    return steps + [("sc", StandardScaler())] if scale else steps


def candidates() -> dict[str, tuple]:
    """nombre → (pipeline, rejilla de hiperparámetros, referencia en la tesis)."""
    smote = ("smote", SMOTE(random_state=SEED, k_neighbors=3))
    bal = "balanced"
    return {
        "Línea base (clase mayoritaria)": (Pipeline(_pre(False) + [("m", DummyClassifier(strategy="prior"))]), {}, "comparación trivial (§3.4)"),
        "Regresión Logística": (Pipeline(_pre(True) + [("m", LogisticRegression(class_weight=bal, max_iter=5000))]),
                                {"m__C": [0.01, 0.1, 1, 10]}, "Tabla 1"),
        "KNN": (ImbPipeline(_pre(True) + [smote, ("m", KNeighborsClassifier())]),
                {"m__n_neighbors": [5, 11, 21], "m__weights": ["uniform", "distance"]}, "§2.3.3"),
        "Naive Bayes": (ImbPipeline(_pre(True) + [smote, ("m", GaussianNB())]),
                        {"m__var_smoothing": [1e-9, 1e-6, 1e-3]}, "§2.3.3"),
        "Árbol de Decisión": (Pipeline(_pre(False) + [("m", DecisionTreeClassifier(class_weight=bal, random_state=SEED))]),
                              {"m__max_depth": [3, 5, 8], "m__min_samples_leaf": [2, 5, 10]}, "§2.3.3"),
        "Random Forest": (Pipeline(_pre(False) + [("m", RandomForestClassifier(n_estimators=500, class_weight="balanced_subsample",
                                                                             random_state=SEED, n_jobs=-1))]),
                          {"m__max_depth": [None, 8], "m__min_samples_leaf": [1, 3, 5], "m__max_features": ["sqrt", 0.5]},
                          "Tabla 1 · candidato principal"),
        "Bagging (árboles)": (Pipeline(_pre(False) + [("m", BaggingClassifier(DecisionTreeClassifier(class_weight=bal),
                                                                            n_estimators=300, random_state=SEED, n_jobs=-1))]),
                              {"m__max_samples": [0.6, 1.0], "m__max_features": [0.6, 1.0]}, "§2.3.3 (Dietterich, 2000)"),
        "Extra Trees (aleatorización)": (Pipeline(_pre(False) + [("m", ExtraTreesClassifier(n_estimators=500, class_weight="balanced_subsample",
                                                                                            random_state=SEED, n_jobs=-1))]),
                                         {"m__max_depth": [None, 8], "m__min_samples_leaf": [1, 3, 5], "m__max_features": ["sqrt", 0.5]},
                                         "§2.3.3 (Dietterich, 2000)"),
        "SVM sensible al costo": (Pipeline(_pre(True) + [("m", SVC(class_weight=bal, probability=True, random_state=SEED))]),
                                  {"m__C": [0.1, 1, 10], "m__gamma": ["scale", 0.01]}, "Tabla 1 · candidato secundario"),
        "Red Neuronal (MLP)": (ImbPipeline(_pre(True) + [smote, ("m", MLPClassifier(max_iter=3000, random_state=SEED))]),
                               {"m__hidden_layer_sizes": [(32,), (64, 32)], "m__alpha": [1e-4, 1e-2, 1e-1]}, "Tabla 1 (ANN)"),
        "Gradient Boosting (contraste)": (Pipeline(_pre(False) + [("m", HistGradientBoostingClassifier(class_weight=bal, random_state=SEED))]),
                                          {"m__max_depth": [3, None], "m__learning_rate": [0.03, 0.1], "m__max_iter": [200]},
                                          "contraste con §2.3.3 (boosting y ruido)"),
    }


# ----------------------------------------------------------------- métricas
def metrics(y, p, thr) -> dict:
    yhat = (p >= thr).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, yhat, labels=[0, 1]).ravel()
    two = len(np.unique(y)) == 2
    return dict(
        n=len(y), positivos=int(y.sum()), umbral=thr, tp=int(tp), fp=int(fp), fn=int(fn), tn=int(tn),
        exactitud=accuracy_score(y, yhat), exactitud_balanceada=balanced_accuracy_score(y, yhat),
        precision=precision_score(y, yhat, zero_division=0), sensibilidad=recall_score(y, yhat, zero_division=0),
        especificidad=tn / (tn + fp) if tn + fp else np.nan, f1=f1_score(y, yhat, zero_division=0),
        mcc=matthews_corrcoef(y, yhat), kappa=cohen_kappa_score(y, yhat),
        roc_auc=roc_auc_score(y, p) if two else np.nan, pr_auc=average_precision_score(y, p) if two else np.nan,
        brier=brier_score_loss(y, p),
    )


def best_threshold(y, p) -> float:
    grid = np.unique(np.round(np.clip(p, 0.02, 0.98), 3))
    if len(grid) < 2:
        return 0.5
    scores = [(f1_score(y, (p >= t).astype(int), zero_division=0), -abs(t - 0.5), t) for t in grid]
    return float(max(scores)[2])


def bootstrap_ci(y, p, thr, groups, n=1000) -> dict:
    """IC 95 % remuestreando PARTICIPANTES (no filas), coherente con la partición."""
    rng = np.random.default_rng(SEED)
    ug = np.unique(groups)
    idx_by = {g: np.where(groups == g)[0] for g in ug}
    out = {k: [] for k in ("f1", "mcc", "sensibilidad", "especificidad", "roc_auc")}
    for _ in range(n):
        idx = np.concatenate([idx_by[g] for g in rng.choice(ug, len(ug), replace=True)])
        yy, pp = y[idx], p[idx]
        if len(np.unique(yy)) < 2:
            continue
        m = metrics(yy, pp, thr)
        for k in out:
            out[k].append(m[k])
    return {f"{k}_ic95": f"[{np.nanpercentile(v, 2.5):.3f}, {np.nanpercentile(v, 97.5):.3f}]" for k, v in out.items() if v}


def mcnemar_p(y, a, b) -> float:
    """McNemar exacto entre dos clasificadores (predicciones binarias a, b)."""
    ca, cb = a == y, b == y
    n01, n10 = int((ca & ~cb).sum()), int((~ca & cb).sum())
    return float(binomtest(n01, n01 + n10, 0.5).pvalue) if n01 + n10 else 1.0


# ----------------------------------------------------------------- entrenamiento
def run(log=print) -> pd.DataFrame:
    warnings.filterwarnings("ignore")
    OUT.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(exist_ok=True)
    df = pd.read_parquet(TRAINING / "training_dataset.parquet")
    spec = json.loads((TRAINING / "feature_spec.json").read_text())
    df = df[df.include_main].copy()
    df["particion"] = participant_split(df)
    df[["session_id", "participant_id", "user_group", "particion"]].to_csv(OUT / "particion_70_30.csv", index=False)
    log(f"  partición: train={int((df.particion == 'train').sum())} filas / "
        f"{df[df.particion == 'train'].participant_id.nunique()} participantes · "
        f"test={int((df.particion == 'test').sum())} filas / {df[df.particion == 'test'].participant_id.nunique()} participantes")

    G = spec["feature_groups"]
    # Normalización intra-participante: percentil de cada variable dentro de las sesiones de la MISMA persona.
    # Usa solo X (nunca Y) y no cruza personas, así que no filtra información entre train y test.
    # En la extensión equivale a comparar al usuario con su propia línea base.
    num = G["behavior"] + G["iso_process"] + G["iso_outcome"]
    rank = df.groupby("participant_id")[num].rank(pct=True).add_prefix("intra_")
    df = pd.concat([df, rank], axis=1)
    feature_sets = {"completo": spec["feature_columns"],
                    "sin_resultados_ISO": [c for c in spec["feature_columns"] if c not in G["iso_outcome"]],
                    "completo+intra_participante": spec["feature_columns"] + list(rank.columns)}
    rows_cv, rows_test, preds = [], [], []
    for target in TARGETS:
        d = df[df[target].notna()]
        tr, te = d[d.particion == "train"], d[d.particion == "test"]
        ytr, yte = tr[target].astype(int).to_numpy(), te[target].astype(int).to_numpy()
        if len(np.unique(ytr)) < 2 or len(np.unique(yte)) < 2 or tr.participant_id.nunique() < 4:
            log(f"  {target}: sin soporte suficiente, se omite")
            continue
        cv = GroupKFold(n_splits=min(4, tr.participant_id.nunique()))
        fitted = {}
        for name, (pipe, grid, ref) in candidates().items():
            best = None
            for fs_name, F in feature_sets.items():
                gs = GridSearchCV(clone(pipe), grid or {}, scoring="roc_auc", cv=cv, n_jobs=-1, refit=True)
                gs.fit(tr[F], ytr, groups=tr.participant_id)
                if best is None or gs.best_score_ > best[0]:
                    best = (gs.best_score_, fs_name, F, gs)
            score, fs_name, F, gs = best
            oof = cross_val_predict(clone(gs.best_estimator_), tr[F], ytr, groups=tr.participant_id, cv=cv,
                                    method="predict_proba")[:, 1]
            thr = 0.5 if name.startswith("Línea base") else best_threshold(ytr, oof)
            cvm = metrics(ytr, oof, thr)
            rows_cv.append(dict(heuristica=target[2:], modelo=name, referencia_tesis=ref, variables=fs_name,
                                hiperparametros=json.dumps(gs.best_params_), cv_roc_auc_busqueda=score,
                                **{f"cv_{k}": v for k, v in cvm.items()}))
            pte = gs.best_estimator_.predict_proba(te[F])[:, 1]
            fitted[name] = (gs.best_estimator_, F, thr, pte, cvm)
            tm = metrics(yte, pte, thr)
            rows_test.append(dict(heuristica=target[2:], modelo=name, variables=fs_name, **tm))
            log(f"  {target} · {name:32s} CV-AUC={score:.3f} · test F1={tm['f1']:.3f} MCC={tm['mcc']:.3f} AUC={tm['roc_auc']:.3f}")

        # mejor modelo según la validación cruzada (no según el test)
        cvdf = pd.DataFrame([r for r in rows_cv if r["heuristica"] == target[2:] and not r["modelo"].startswith("Línea")])
        winner = cvdf.sort_values(["cv_mcc", "cv_roc_auc"], ascending=False).iloc[0].modelo
        est, F, thr, pte, _ = fitted[winner]
        base_pred = (fitted["Línea base (clase mayoritaria)"][3] >= 0.5).astype(int)
        for r in rows_test:
            if r["heuristica"] == target[2:]:
                r["seleccionado_por_cv"] = r["modelo"] == winner
                if r["modelo"] == winner:
                    r.update(bootstrap_ci(yte, pte, thr, te.participant_id.to_numpy()))
                    r["mcnemar_p_vs_base"] = mcnemar_p(yte, (pte >= thr).astype(int), base_pred)
        joblib.dump(dict(model=est, features=F, threshold=thr, target=target, trained_on="70% participantes",
                         selected_by="CV agrupada: MCC, luego ROC-AUC"), MODELS_DIR / f"{target}_{_slug(winner)}.joblib")
        for name, (_, _, thr_, p_, _) in fitted.items():
            preds.append(pd.DataFrame(dict(heuristica=target[2:], modelo=name, session_id=te.session_id.values,
                                           participant_id=te.participant_id.values, y=yte, prob=p_, umbral=thr_)))
        log(f"  {target}: seleccionado por CV → {winner}")

    cv_df, test_df = pd.DataFrame(rows_cv), pd.DataFrame(rows_test)
    cv_df.to_csv(OUT / "resultados_cv_entrenamiento.csv", index=False)
    test_df.to_csv(OUT / "resultados_test_30.csv", index=False)
    pd.concat(preds).to_csv(OUT / "predicciones_test.csv", index=False)
    _report(cv_df, test_df, df)
    return test_df


def _slug(s: str) -> str:
    import re
    import unicodedata
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def _report(cv_df: pd.DataFrame, test_df: pd.DataFrame, df: pd.DataFrame) -> None:
    from .report import _md
    cols = ["modelo", "variables", "umbral", "exactitud", "exactitud_balanceada", "precision", "sensibilidad",
            "especificidad", "f1", "mcc", "kappa", "roc_auc", "pr_auc"]
    win = test_df[test_df.seleccionado_por_cv.fillna(False).astype(bool)]
    txt = ["# Etapa 5 · Modelado (partición 70/30 por participante)", "",
           f"Entrenamiento: {int((df.particion == 'train').sum())} sesiones de "
           f"{df[df.particion == 'train'].participant_id.nunique()} participantes · prueba: "
           f"{int((df.particion == 'test').sum())} sesiones de {df[df.particion == 'test'].participant_id.nunique()} participantes.",
           "", "Hiperparámetros, conjunto de variables y umbral se eligieron SOLO con validación cruzada agrupada en el 70 %. "
           "El 30 % se evaluó una única vez.", "",
           "## Modelo seleccionado por heurística (evaluado en el 30 %)", "",
           _md(win[["heuristica"] + cols + [c for c in win.columns if c.endswith("_ic95")] + ["mcnemar_p_vs_base"]].round(3)), ""]
    for h in test_df.heuristica.unique():
        t = test_df[test_df.heuristica == h][cols].round(3)
        c = cv_df[cv_df.heuristica == h][["modelo", "cv_roc_auc", "cv_f1", "cv_mcc"]].round(3)
        txt += [f"## {h} · todos los modelos en el 30 % de prueba", "", _md(t), "",
                f"### {h} · validación cruzada en el 70 % (predicciones fuera de fold)", "", _md(c), ""]
    txt += ["## Notas", "",
            "- El modelo de cada heurística se elige por MCC en validación cruzada (no por el resultado de prueba), "
            "para que la cifra de prueba no esté sesgada por la selección.",
            "- IC 95 %: bootstrap de 1000 remuestreos de participantes del conjunto de prueba.",
            "- McNemar exacto frente a la línea base (clase mayoritaria).",
            "- Con pocos participantes en prueba los intervalos son amplios; interprételos junto con la CV."]
    (OUT / "README.md").write_text("\n".join(txt), encoding="utf-8")
