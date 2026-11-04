# Etapa 7 · Red neuronal multitarea (una red, salidas H1/H4/H5/H6)

Configuración seleccionada por validación cruzada en el 70 % (de 15 configuraciones × 1 conjuntos de variables):

```
{
  "variables": "completo",
  "hidden": [
    512,
    256
  ],
  "dropout": 0.2,
  "weight_decay": 0.1,
  "lr": 0.003,
  "act": "elu",
  "head_hidden": 0,
  "batch": 16,
  "n_seeds": 10,
  "max_epochs": 300,
  "patience": 25
}
```

Entrenamiento: 215 sesiones / 11 participantes · prueba: 93 sesiones / 5 participantes.

## Resultados en el 30 % de prueba

| heuristica | n | positivos | umbral | exactitud | exactitud_balanceada | precision | sensibilidad | especificidad | f1 | mcc | kappa | roc_auc | pr_auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| H1 | 93 | 32 | 0.535 | 0.785 | 0.777 | 0.667 | 0.75 | 0.803 | 0.706 | 0.54 | 0.537 | 0.815 | 0.775 |
| H4 | 93 | 17 | 0.628 | 0.785 | 0.709 | 0.435 | 0.588 | 0.829 | 0.5 | 0.374 | 0.367 | 0.733 | 0.586 |
| H5 | 18 | 11 | 0.414 | 0.833 | 0.838 | 0.9 | 0.818 | 0.857 | 0.857 | 0.663 | 0.658 | 0.922 | 0.953 |
| H6 | 93 | 32 | 0.551 | 0.763 | 0.716 | 0.692 | 0.562 | 0.869 | 0.621 | 0.457 | 0.451 | 0.797 | 0.757 |

| heuristica | f1_ic95 | mcc_ic95 | sensibilidad_ic95 | especificidad_ic95 | roc_auc_ic95 | mcnemar_p_vs_base |
|---|---|---|---|---|---|---|
| H1 | [0.596, 0.785] | [0.439, 0.619] | [0.718, 0.786] | [0.700, 0.870] | [0.754, 0.895] | 0.065 |
| H4 | [0.312, 0.625] | [0.191, 0.535] | [0.417, 0.750] | [0.706, 0.924] | [0.606, 0.830] | 0.678 |
| H5 | [0.625, 1.000] | [0.258, 1.000] | [0.556, 1.000] | [0.625, 1.000] | [0.792, 1.000] | 0.289 |
| H6 | [0.416, 0.787] | [0.216, 0.695] | [0.345, 0.778] | [0.818, 0.918] | [0.680, 0.930] | 0.076 |

## Métricas multi-etiqueta

| f1_macro | mcc_macro | f1_micro_H1H4H6 | hamming_loss_H1H4H6 | exact_match_H1H4H6 |
|---|---|---|---|---|
| 0.671 | 0.508 | 0.627 | 0.222 | 0.495 |

## Comparación con el Random Forest multi-salida (etapa 6, mismo 30 %)

| heuristica | RN_f1 | RN_mcc | RN_roc_auc | RF_f1 | RF_mcc | RF_roc_auc |
|---|---|---|---|---|---|---|
| H1 | 0.706 | 0.54 | 0.815 | 0.8 | 0.693 | 0.856 |
| H4 | 0.5 | 0.374 | 0.733 | 0.49 | 0.36 | 0.824 |
| H5 | 0.857 | 0.663 | 0.922 | 0.88 | 0.67 | 0.87 |
| H6 | 0.621 | 0.457 | 0.797 | 0.657 | 0.457 | 0.847 |

## 10 mejores configuraciones (validación cruzada en el 70 %)

| variables | hidden | dropout | weight_decay | lr | act | head_hidden | batch | cv_f1_macro | cv_mcc_macro | cv_auc_H1 | cv_auc_H4 | cv_auc_H5 | cv_auc_H6 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| completo | (512, 256) | 0.2 | 0.1 | 0.003 | elu | 0 | 16 | 0.603 | 0.374 | 0.713 | 0.587 | 0.705 | 0.679 |
| completo | (256, 128) | 0.3 | 0.01 | 0.003 | elu | 0 | 32 | 0.581 | 0.34 | 0.703 | 0.621 | 0.662 | 0.639 |
| completo | (512, 256) | 0.3 | 0.05 | 0.001 | elu | 0 | 32 | 0.578 | 0.328 | 0.679 | 0.611 | 0.61 | 0.651 |
| completo | (512, 256) | 0.1 | 0.1 | 0.003 | elu | 16 | 16 | 0.582 | 0.322 | 0.705 | 0.622 | 0.688 | 0.653 |
| completo | (256, 128, 64) | 0.1 | 0.1 | 0.003 | elu | 16 | 16 | 0.578 | 0.314 | 0.669 | 0.583 | 0.692 | 0.648 |
| completo | (256, 128, 64) | 0.1 | 0.05 | 0.001 | elu | 16 | 32 | 0.579 | 0.311 | 0.669 | 0.565 | 0.669 | 0.657 |
| completo | (256, 128, 64) | 0.2 | 0.01 | 0.001 | elu | 16 | 16 | 0.563 | 0.303 | 0.655 | 0.554 | 0.662 | 0.636 |
| completo | (512, 256) | 0.3 | 0.05 | 0.001 | elu | 0 | 16 | 0.571 | 0.3 | 0.697 | 0.597 | 0.656 | 0.647 |
| completo | (512, 256) | 0.2 | 0.1 | 0.001 | elu | 16 | 32 | 0.573 | 0.297 | 0.697 | 0.619 | 0.62 | 0.62 |
| completo | (256, 128, 64) | 0.3 | 0.05 | 0.003 | elu | 0 | 32 | 0.575 | 0.296 | 0.689 | 0.6 | 0.666 | 0.622 |