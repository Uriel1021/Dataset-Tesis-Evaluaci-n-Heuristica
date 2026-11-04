"""Etapa 7 · Red neuronal multitarea (una red, cuatro salidas: H1, H4, H5, H6).

Arquitectura: aprendizaje multitarea con parámetros compartidos (Caruana, 1997):
un tronco MLP común aprende una representación del comportamiento y de él
salen cuatro cabezas sigmoides, una por heurística.

Detalles de entrenamiento:
  * Pérdida BCE ENMASCARADA: una etiqueta NA (heurística no evaluable, p. ej.
    H5 en páginas sin formularios) no contribuye al error.
  * Sensible al costo: pos_weight = negativos/positivos de cada heurística,
    calculado en el fold de entrenamiento (tesis §2.3.3, Johnson y
    Khoshgoftaar, 2019).
  * Preprocesamiento ajustado SOLO con el fold de entrenamiento: imputación por
    mediana + indicadores de faltante + estandarización.
  * Parada temprana con participantes apartados del propio fold de
    entrenamiento (nunca con el fold de validación ni con el 30 % de prueba).
  * Ensamble de semillas: la predicción es la media de k redes entrenadas con
    semillas distintas (reduce la varianza en muestras pequeñas).

Búsqueda: configuraciones aleatorias (semilla fija) evaluadas con validación
cruzada agrupada por participante en el 70 %; se elige por MCC macro y luego
se evalúa UNA vez en el 30 %.
"""

from __future__ import annotations

import json
import random
import time

import joblib
import numpy as np
import pandas as pd
import torch
from torch import nn

from . import config
from .modeling import MODELS_DIR, SEED, TARGETS, TRAINING, best_threshold, bootstrap_ci, mcnemar_p, metrics
from .multilabel import multilabel_summary

OUT = config.REPORTS / "07_red_neuronal_multitarea"
torch.set_num_threads(4)


# ----------------------------------------------------------------- preprocesamiento
class Prep:
    def fit(self, X: np.ndarray):
        self.med = np.nanmedian(X, axis=0)
        self.med = np.where(np.isnan(self.med), 0.0, self.med)
        self.miss_cols = np.where(np.isnan(X).any(axis=0))[0]
        Z = self._impute(X)
        self.mu, self.sd = Z.mean(0), Z.std(0) + 1e-6
        return self

    def _impute(self, X):
        Z = np.where(np.isnan(X), self.med, X)
        return np.column_stack([Z, np.isnan(X[:, self.miss_cols]).astype(float)])

    def transform(self, X):
        return ((self._impute(X) - self.mu) / self.sd).astype(np.float32)


# ----------------------------------------------------------------- red
class MultiTaskNet(nn.Module):
    def __init__(self, n_in, hidden, dropout, act, head_hidden, n_out=4):
        super().__init__()
        A = {"relu": nn.ReLU, "elu": nn.ELU}[act]
        layers, d = [], n_in
        for h in hidden:
            layers += [nn.Linear(d, h), nn.BatchNorm1d(h), A(), nn.Dropout(dropout)]
            d = h
        self.trunk = nn.Sequential(*layers)
        if head_hidden:
            self.heads = nn.ModuleList([nn.Sequential(nn.Linear(d, head_hidden), A(), nn.Linear(head_hidden, 1))
                                        for _ in range(n_out)])
        else:
            self.heads = nn.ModuleList([nn.Linear(d, 1) for _ in range(n_out)])

    def forward(self, x):
        z = self.trunk(x)
        return torch.cat([h(z) for h in self.heads], dim=1)


def _masked_bce(logits, y, mask, pos_weight):
    loss = nn.functional.binary_cross_entropy_with_logits(logits, torch.nan_to_num(y), pos_weight=pos_weight,
                                                          reduction="none")
    return (loss * mask).sum() / mask.sum().clamp(min=1)


def _seed_all(s):
    random.seed(s)
    np.random.seed(s)
    torch.manual_seed(s)


def train_net(Xtr, Ytr, groups, cfg, seed) -> tuple[MultiTaskNet, Prep]:
    """Entrena una red. Parada temprana con ~20 % de participantes del propio entrenamiento."""
    _seed_all(seed)
    rng = np.random.default_rng(seed)
    ug = np.unique(groups)
    es_g = rng.choice(ug, max(1, int(round(0.2 * len(ug)))), replace=False)
    es = np.isin(groups, es_g)
    prep = Prep().fit(Xtr[~es])
    xa, xb = torch.tensor(prep.transform(Xtr[~es])), torch.tensor(prep.transform(Xtr[es]))
    ya, yb = torch.tensor(Ytr[~es], dtype=torch.float32), torch.tensor(Ytr[es], dtype=torch.float32)
    ma, mb = ~torch.isnan(ya), ~torch.isnan(yb)
    pos = torch.nansum(ya, 0)
    neg = ma.sum(0) - pos
    pw = (neg / pos.clamp(min=1)).clamp(0.5, 10.0)
    net = MultiTaskNet(xa.shape[1], cfg["hidden"], cfg["dropout"], cfg["act"], cfg["head_hidden"])
    opt = torch.optim.AdamW(net.parameters(), lr=cfg["lr"], weight_decay=cfg["weight_decay"])
    best, best_state, wait = np.inf, None, 0
    n = len(xa)
    for epoch in range(cfg["max_epochs"]):
        net.train()
        perm = torch.randperm(n)
        for i in range(0, n, cfg["batch"]):
            idx = perm[i:i + cfg["batch"]]
            if len(idx) < 2:
                continue
            opt.zero_grad()
            _masked_bce(net(xa[idx]), ya[idx], ma[idx].float(), pw).backward()
            opt.step()
        net.eval()
        with torch.no_grad():
            v = _masked_bce(net(xb), yb, mb.float(), pw).item()
        if v < best - 1e-4:
            best, best_state, wait = v, {k: t.clone() for k, t in net.state_dict().items()}, 0
        else:
            wait += 1
            if wait >= cfg["patience"]:
                break
    net.load_state_dict(best_state)
    net.eval()
    return net, prep


class NeuralEnsemble:
    """Ensamble de semillas de MultiTaskNet. predict_proba_frame(X) → DataFrame H1/H4/H5/H6."""

    def __init__(self, cfg, labels=tuple(TARGETS)):
        self.cfg, self.labels = cfg, list(labels)
        self.thresholds_ = {c: 0.5 for c in self.labels}

    def fit(self, X, Y, groups):
        X, Y = np.asarray(X, float), np.asarray(Y, float)
        self.members_ = [train_net(X, Y, np.asarray(groups), self.cfg, SEED + 101 * k) for k in range(self.cfg["n_seeds"])]
        return self

    def predict_proba_frame(self, X) -> pd.DataFrame:
        X = np.asarray(X, float)
        ps = []
        for net, prep in self.members_:
            with torch.no_grad():
                ps.append(torch.sigmoid(net(torch.tensor(prep.transform(X)))).numpy())
        return pd.DataFrame(np.mean(ps, 0), columns=self.labels)

    def predict(self, X) -> pd.DataFrame:
        p = self.predict_proba_frame(X)
        return pd.DataFrame({c: (p[c] >= self.thresholds_[c]).astype(int) for c in self.labels})


# ----------------------------------------------------------------- búsqueda
SPACE = dict(
    hidden=[(32,), (64,), (128,), (64, 32), (128, 64), (128, 64, 32), (256, 128)],
    dropout=[0.1, 0.3, 0.5],
    weight_decay=[1e-4, 1e-3, 1e-2, 5e-2],
    lr=[3e-4, 1e-3, 3e-3],
    act=["relu", "elu"],
    head_hidden=[0, 16],
    batch=[16, 32],
    n_seeds=[5],
    max_epochs=[300],
    patience=[25],
)


# Ronda 2: región donde estuvieron las mejores configuraciones de la ronda 1 (elegidas por CV, no por prueba)
SPACE_R2 = dict(
    hidden=[(128, 64), (256, 128), (512, 256), (256, 128, 64)],
    dropout=[0.1, 0.2, 0.3],
    weight_decay=[1e-2, 5e-2, 1e-1],
    lr=[1e-3, 3e-3],
    act=["elu"],
    head_hidden=[0, 16],
    batch=[16, 32],
    n_seeds=[10],
    max_epochs=[300],
    patience=[25],
)


def sample_configs(n: int, space: dict | None = None) -> list[dict]:
    SPACE_ = space or SPACE
    rng = random.Random(SEED)
    seen, out = set(), []
    while len(out) < n:
        c = {k: rng.choice(v) for k, v in SPACE_.items()}
        key = json.dumps(c, sort_keys=True, default=str)
        if key not in seen:
            seen.add(key)
            out.append(c)
    return out


def cv_predict(cfg, X, Y, groups, k=4) -> pd.DataFrame:
    from sklearn.model_selection import GroupKFold
    P = np.full(Y.shape, np.nan)
    for tr, te in GroupKFold(n_splits=k).split(X, groups=groups):
        m = NeuralEnsemble(cfg).fit(X[tr], Y[tr], groups[tr])
        P[te] = m.predict_proba_frame(X[te]).to_numpy()
    return pd.DataFrame(P, columns=TARGETS)


def _load():
    df = pd.read_parquet(TRAINING / "training_dataset.parquet")
    spec = json.loads((TRAINING / "feature_spec.json").read_text())
    df = df[df.include_main].copy()
    part = pd.read_csv(config.REPORTS / "05_modelado" / "particion_70_30.csv")[["session_id", "particion"]]
    df = df.merge(part, on="session_id")
    G = spec["feature_groups"]
    num = G["behavior"] + G["iso_process"] + G["iso_outcome"]
    rank = df.groupby("participant_id")[num].rank(pct=True).add_prefix("intra_")
    df = pd.concat([df.reset_index(drop=True), rank.reset_index(drop=True)], axis=1)
    sets = {"completo": spec["feature_columns"], "completo+intra_participante": spec["feature_columns"] + list(rank.columns)}
    return df, sets


def run(n_configs: int = 40, log=print, space: dict | None = None, variable_sets: list[str] | None = None,
        tag: str = "busqueda_configuraciones_cv_70") -> pd.DataFrame:
    OUT.mkdir(parents=True, exist_ok=True)
    df, sets = _load()
    tr, te = df[df.particion == "train"].reset_index(drop=True), df[df.particion == "test"].reset_index(drop=True)
    Ytr, Yte = tr[TARGETS].astype(float).to_numpy(), te[TARGETS].astype(float)
    gtr = tr.participant_id.to_numpy()
    Ytr_df = pd.DataFrame(Ytr, columns=TARGETS)

    rows, best = [], None
    use = variable_sets or list(sets)
    configs = [(fs, c) for c in sample_configs(n_configs, space) for fs in use]
    t0 = time.time()
    for i, (fs, cfg) in enumerate(configs):
        X = tr[sets[fs]].to_numpy(dtype=float)
        P = cv_predict(cfg, X, Ytr, gtr)
        thr = {c: best_threshold(Ytr_df[c][Ytr_df[c].notna()].astype(int).to_numpy(), P[c][Ytr_df[c].notna()].to_numpy())
               for c in TARGETS}
        s = multilabel_summary(Ytr_df, P, thr)
        aucs = {}
        from sklearn.metrics import roc_auc_score
        for c in TARGETS:
            msk = Ytr_df[c].notna()
            aucs[f"cv_auc_{c[2:]}"] = roc_auc_score(Ytr_df[c][msk].astype(int), P[c][msk])
        rows.append(dict(config=i // len(sets), variables=fs, **{k: str(v) for k, v in cfg.items()},
                         **{f"cv_{k}": v for k, v in s.items()}, **aucs))
        log(f"  [{i + 1}/{len(configs)} · {time.time() - t0:5.0f}s] {fs:28s} hidden={cfg['hidden']} drop={cfg['dropout']} "
            f"wd={cfg['weight_decay']} lr={cfg['lr']} head={cfg['head_hidden']} → CV MCC macro={s['mcc_macro']:.3f} "
            f"F1 macro={s['f1_macro']:.3f}")
        if best is None or s["mcc_macro"] > best[0]:
            best = (s["mcc_macro"], fs, cfg, thr)
    cv_df = pd.DataFrame(rows).sort_values("cv_mcc_macro", ascending=False)
    cv_df.to_csv(OUT / f"{tag}.csv", index=False)

    # ---- red final: reentrenada en el 70 %, evaluada UNA vez en el 30 %
    _, fs, cfg, thr = best
    F = sets[fs]
    final = NeuralEnsemble(cfg).fit(tr[F].to_numpy(dtype=float), Ytr, gtr)
    final.thresholds_ = thr
    P = final.predict_proba_frame(te[F].to_numpy(dtype=float))
    gte = te.participant_id.to_numpy()
    per = []
    for c in TARGETS:
        m = Yte[c].notna().to_numpy()
        y, p = Yte[c][m].astype(int).to_numpy(), P[c][m].to_numpy()
        base_pred = np.full(len(y), int(np.nanmean(Ytr[:, TARGETS.index(c)]) >= 0.5))
        per.append(dict(heuristica=c[2:], **metrics(y, p, thr[c]), **bootstrap_ci(y, p, thr[c], gte[m]),
                        mcnemar_p_vs_base=mcnemar_p(y, (p >= thr[c]).astype(int), base_pred)))
    per = pd.DataFrame(per)
    glob = multilabel_summary(Yte, P, thr)
    per.to_csv(OUT / "resultados_test_30_por_heuristica.csv", index=False)
    pd.DataFrame([dict(variables=fs, **{k: str(v) for k, v in cfg.items()}, **glob)]).to_csv(OUT / "resultados_test_30_global.csv", index=False)
    pd.concat([te[["session_id", "participant_id"]], Yte.add_prefix("real_"), P.add_prefix("prob_")], axis=1).to_csv(
        OUT / "predicciones_test.csv", index=False)
    MODELS_DIR.mkdir(exist_ok=True)
    joblib.dump(dict(model=final, features=F, thresholds=thr, labels=TARGETS, config=cfg,
                     usage="bundle['model'].predict_proba_frame(X[bundle['features']]) → probabilidades H1/H4/H5/H6"),
                MODELS_DIR / "red_neuronal_multitarea_H1_H4_H5_H6.joblib")
    _report(cv_df, per, glob, fs, cfg, tr, te)
    log(f"  seleccionada por CV → {fs} · {cfg}")
    log(f"  test: F1 macro={glob['f1_macro']:.3f} · MCC macro={glob['mcc_macro']:.3f} · Hamming={glob['hamming_loss_H1H4H6']:.3f}")
    return per


def _report(cv_df, per, glob, fs, cfg, tr, te) -> None:
    from .report import _md
    rf = config.REPORTS / "06_modelo_multietiqueta" / "resultados_test_30_por_heuristica.csv"
    cols = ["heuristica", "n", "positivos", "umbral", "exactitud", "exactitud_balanceada", "precision", "sensibilidad",
            "especificidad", "f1", "mcc", "kappa", "roc_auc", "pr_auc"]
    txt = ["# Etapa 7 · Red neuronal multitarea (una red, salidas H1/H4/H5/H6)", "",
           f"Configuración seleccionada por validación cruzada en el 70 % (de {cv_df.config.nunique()} configuraciones × "
           f"{cv_df.variables.nunique()} conjuntos de variables):", "", "```", json.dumps({"variables": fs, **cfg}, indent=2, default=str), "```", "",
           f"Entrenamiento: {len(tr)} sesiones / {tr.participant_id.nunique()} participantes · prueba: {len(te)} sesiones / "
           f"{te.participant_id.nunique()} participantes.", "",
           "## Resultados en el 30 % de prueba", "", _md(per[cols].round(3)), "",
           _md(per[["heuristica"] + [c for c in per.columns if c.endswith("_ic95")] + ["mcnemar_p_vs_base"]].round(3)), "",
           "## Métricas multi-etiqueta", "", _md(pd.DataFrame([glob]).round(3)), ""]
    if rf.exists():
        r = pd.read_csv(rf)[["heuristica", "f1", "mcc", "roc_auc"]].rename(columns=lambda c: c if c == "heuristica" else f"RF_{c}")
        cmp = per[["heuristica", "f1", "mcc", "roc_auc"]].rename(columns=lambda c: c if c == "heuristica" else f"RN_{c}").merge(r, on="heuristica")
        txt += ["## Comparación con el Random Forest multi-salida (etapa 6, mismo 30 %)", "", _md(cmp.round(3)), ""]
    txt += ["## 10 mejores configuraciones (validación cruzada en el 70 %)", "",
            _md(cv_df.head(10)[["variables", "hidden", "dropout", "weight_decay", "lr", "act", "head_hidden", "batch",
                                "cv_f1_macro", "cv_mcc_macro", "cv_auc_H1", "cv_auc_H4", "cv_auc_H5", "cv_auc_H6"]].round(3))]
    (OUT / "README.md").write_text("\n".join(txt), encoding="utf-8")
