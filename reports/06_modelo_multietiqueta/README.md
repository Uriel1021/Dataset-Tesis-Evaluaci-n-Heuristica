# Etapa 6 · Un solo modelo multi-etiqueta (H1, H4, H5, H6)

Modelo seleccionado por validación cruzada en el 70 %: **joint · Random Forest · variables completo+intra_participante**

Entrenamiento: 215 sesiones / 11 participantes · prueba: 93 sesiones / 5 participantes (misma partición que la etapa 5).

## Resultados en el 30 % de prueba · por heurística

| heuristica | n | positivos | umbral | exactitud | exactitud_balanceada | precision | sensibilidad | especificidad | f1 | mcc | kappa | roc_auc | pr_auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| H1 | 93 | 32 | 0.481 | 0.86 | 0.849 | 0.788 | 0.812 | 0.885 | 0.8 | 0.693 | 0.693 | 0.856 | 0.855 |
| H4 | 93 | 17 | 0.4 | 0.731 | 0.721 | 0.375 | 0.706 | 0.737 | 0.49 | 0.36 | 0.33 | 0.824 | 0.666 |
| H5 | 18 | 11 | 0.341 | 0.833 | 0.786 | 0.786 | 1 | 0.571 | 0.88 | 0.67 | 0.62 | 0.87 | 0.912 |
| H6 | 93 | 32 | 0.457 | 0.742 | 0.736 | 0.605 | 0.719 | 0.754 | 0.657 | 0.457 | 0.453 | 0.847 | 0.776 |

| heuristica | f1_ic95 | mcc_ic95 | sensibilidad_ic95 | especificidad_ic95 | roc_auc_ic95 | mcnemar_p_vs_base |
|---|---|---|---|---|---|---|
| H1 | [0.727, 0.868] | [0.614, 0.801] | [0.744, 0.952] | [0.813, 0.982] | [0.804, 0.939] | 0.001 |
| H4 | [0.349, 0.690] | [0.193, 0.639] | [0.545, 1.000] | [0.493, 0.962] | [0.736, 0.968] | 0.215 |
| H5 | [0.783, 0.963] | [0.471, 0.880] | [1.000, 1.000] | [0.333, 0.833] | [0.741, 1.000] | 0.125 |
| H6 | [0.538, 0.800] | [0.195, 0.710] | [0.524, 0.931] | [0.610, 0.890] | [0.726, 0.949] | 0.256 |

## Métricas multi-etiqueta (30 % de prueba)

| f1_macro | mcc_macro | f1_micro_H1H4H6 | hamming_loss_H1H4H6 | exact_match_H1H4H6 |
|---|---|---|---|---|
| 0.707 | 0.545 | 0.663 | 0.222 | 0.548 |

`hamming_loss` = proporción de decisiones erróneas; `exact_match` = sesiones con las tres decisiones (H1, H4, H6) correctas a la vez. H5 se excluye de estas dos porque solo está etiquetada en páginas con formularios.

## Comparación de estrategias (validación cruzada en el 70 %)

| estrategia | estimador | variables | cv_f1_macro | cv_mcc_macro | cv_f1_micro_H1H4H6 | cv_hamming_loss_H1H4H6 | cv_exact_match_H1H4H6 | umbrales |
|---|---|---|---|---|---|---|---|---|
| joint | Random Forest | completo+intra_participante | 0.629 | 0.454 | 0.585 | 0.236 | 0.553 | {"H1": 0.481, "H4": 0.4, "H5": 0.341, "H6": 0.457} |
| binary_relevance | Extra Trees | completo+intra_participante | 0.617 | 0.441 | 0.568 | 0.245 | 0.488 | {"H1": 0.382, "H4": 0.365, "H5": 0.354, "H6": 0.425} |
| joint | Red Neuronal (MLP) | completo+intra_participante | 0.616 | 0.433 | 0.535 | 0.278 | 0.474 | {"H1": 0.048, "H4": 0.025, "H5": 0.435, "H6": 0.383} |
| chain | Extra Trees | completo+intra_participante | 0.625 | 0.433 | 0.522 | 0.349 | 0.265 | {"H1": 0.382, "H4": 0.144, "H5": 0.333, "H6": 0.439} |
| joint | Extra Trees | completo+intra_participante | 0.615 | 0.42 | 0.5 | 0.394 | 0.186 | {"H1": 0.443, "H4": 0.124, "H5": 0.339, "H6": 0.55} |
| binary_relevance | Regresión Logística | completo+intra_participante | 0.613 | 0.414 | 0.543 | 0.282 | 0.414 | {"H1": 0.451, "H4": 0.515, "H5": 0.355, "H6": 0.595} |
| chain | Random Forest | completo+intra_participante | 0.621 | 0.412 | 0.51 | 0.42 | 0.13 | {"H1": 0.354, "H4": 0.07, "H5": 0.34, "H6": 0.377} |
| binary_relevance | Random Forest | completo+intra_participante | 0.619 | 0.408 | 0.508 | 0.423 | 0.121 | {"H1": 0.354, "H4": 0.073, "H5": 0.345, "H6": 0.383} |
| binary_relevance | Random Forest | completo | 0.614 | 0.404 | 0.504 | 0.412 | 0.135 | {"H1": 0.378, "H4": 0.068, "H5": 0.429, "H6": 0.409} |
| chain | Regresión Logística | completo+intra_participante | 0.613 | 0.404 | 0.543 | 0.295 | 0.377 | {"H1": 0.451, "H4": 0.469, "H5": 0.238, "H6": 0.489} |
| binary_relevance | Extra Trees | completo | 0.605 | 0.4 | 0.523 | 0.295 | 0.367 | {"H1": 0.488, "H4": 0.268, "H5": 0.409, "H6": 0.501} |
| chain | Red Neuronal (MLP) | completo+intra_participante | 0.587 | 0.395 | 0.491 | 0.315 | 0.381 | {"H1": 0.027, "H4": 0.021, "H5": 0.252, "H6": 0.771} |
| chain | Regresión Logística | completo | 0.61 | 0.391 | 0.549 | 0.278 | 0.423 | {"H1": 0.473, "H4": 0.684, "H5": 0.322, "H6": 0.408} |
| chain | Extra Trees | completo | 0.604 | 0.386 | 0.522 | 0.31 | 0.34 | {"H1": 0.488, "H4": 0.234, "H5": 0.422, "H6": 0.445} |
| joint | Random Forest | completo | 0.609 | 0.382 | 0.516 | 0.411 | 0.186 | {"H1": 0.452, "H4": 0.126, "H5": 0.424, "H6": 0.35} |
| binary_relevance | Regresión Logística | completo | 0.611 | 0.382 | 0.554 | 0.282 | 0.414 | {"H1": 0.473, "H4": 0.623, "H5": 0.321, "H6": 0.413} |
| chain | Random Forest | completo | 0.602 | 0.374 | 0.5 | 0.431 | 0.112 | {"H1": 0.378, "H4": 0.062, "H5": 0.469, "H6": 0.335} |
| binary_relevance | Red Neuronal (MLP) | completo | 0.578 | 0.361 | 0.52 | 0.284 | 0.437 | {"H1": 0.058, "H4": 0.248, "H5": 0.265, "H6": 0.094} |
| binary_relevance | Red Neuronal (MLP) | completo+intra_participante | 0.588 | 0.36 | 0.51 | 0.333 | 0.381 | {"H1": 0.027, "H4": 0.024, "H5": 0.082, "H6": 0.042} |
| chain | Red Neuronal (MLP) | completo | 0.586 | 0.36 | 0.506 | 0.318 | 0.358 | {"H1": 0.058, "H4": 0.021, "H5": 0.02, "H6": 0.228} |
| joint | Extra Trees | completo | 0.587 | 0.357 | 0.509 | 0.344 | 0.326 | {"H1": 0.354, "H4": 0.409, "H5": 0.409, "H6": 0.561} |
| joint | Red Neuronal (MLP) | completo | 0.572 | 0.328 | 0.499 | 0.321 | 0.391 | {"H1": 0.07, "H4": 0.02, "H5": 0.036, "H6": 0.023} |
