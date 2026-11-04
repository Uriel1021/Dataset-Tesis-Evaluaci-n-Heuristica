"""Punto de entrada del pipeline.

    python -m usab_ds all        # etapas 1 → 2 → 3
    python -m usab_ds stage1     # perfil de fuentes
    python -m usab_ds stage2     # elegibilidad y correspondencias
    python -m usab_ds stage3     # dataset final (requiere 1 y 2)
    python -m usab_ds stage3b    # etiquetas H1/H4/H5/H6 por rúbrica + dataset de entrenamiento + validación
    python -m usab_ds stage4     # solo reconstruye el dataset de entrenamiento
    python -m usab_ds stage5     # entrena y evalúa los modelos de la tesis (70/30 por participante)
    python -m usab_ds stage6     # un solo modelo multi-etiqueta para H1/H4/H5/H6
    python -m usab_ds stage7     # red neuronal multitarea (búsqueda de configuraciones)
    python -m usab_ds stage1 --no-hash   # omite sha256 (más rápido, no reproducible)
"""

from __future__ import annotations

import argparse
import time

from . import build, config, profiling, relevance, report, rubric_labels, training


def main() -> None:
    ap = argparse.ArgumentParser(prog="usab_ds")
    ap.add_argument("stage", choices=["all", "stage1", "stage2", "stage3", "stage3b", "stage4", "stage5", "stage6", "stage7",
                                      "silver-prepare", "silver-count", "silver-submit", "silver-collect"])
    ap.add_argument("--no-hash", action="store_true")
    ap.add_argument("--yes", action="store_true", help="confirma el envío (y el gasto) en silver-submit")
    a = ap.parse_args()
    t0 = time.time()
    log = lambda m: print(f"[{time.time() - t0:7.1f}s] {m}", flush=True)  # noqa: E731
    config.ensure_dirs()
    if a.stage.startswith("silver"):
        from . import silver_labels as sl
        {"silver-prepare": lambda: sl.prepare(log), "silver-count": lambda: sl.count(log),
         "silver-submit": lambda: sl.submit(a.yes, log), "silver-collect": lambda: sl.collect(True, log)}[a.stage]()
        if a.stage == "silver-collect" and (config.PROCESSED / "silver_page_labels.parquet").exists():
            training.build(log)
        return
    if a.stage == "stage3b":
        rubric_labels.run(log)
        training.build(log)
        rubric_labels.validate(log)
        return
    if a.stage == "stage7":
        from . import neural
        neural.run(n_configs=60, log=log, tag="busqueda_ronda1_cv_70")                      # ronda 1: espacio amplio
        neural.run(n_configs=30, log=log, space=neural.SPACE_R2, variable_sets=["completo"],  # ronda 2: región prometedora
                   tag="busqueda_ronda2_cv_70")
        return
    if a.stage == "stage6":
        from . import multilabel
        multilabel.run(log)
        return
    if a.stage == "stage5":
        from . import modeling
        modeling.run(log)
        return
    if a.stage == "stage4":
        training.build(log)
        return
    if a.stage in ("all", "stage1"):
        log("[1/5] Perfil de fuentes")
        profiling.run(with_hash=not a.no_hash)
    if a.stage in ("all", "stage2"):
        log("[2/5] Elegibilidad y correspondencias")
        relevance.run()
    if a.stage in ("all", "stage3"):
        build.run(log)
    if a.stage == "all":
        log("[3b] Etiquetas por inspección con rúbrica")
        rubric_labels.run(log)
        log("[4] Dataset de entrenamiento")
        training.build(log)
        rubric_labels.validate(log)
    report.write_all()
    log("Listo.")


if __name__ == "__main__":
    main()
