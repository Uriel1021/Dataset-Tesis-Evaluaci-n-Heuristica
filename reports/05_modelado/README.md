# Etapa 5 · Modelado (partición 70/30 por participante)

Entrenamiento: 215 sesiones de 11 participantes · prueba: 93 sesiones de 5 participantes.

Hiperparámetros, conjunto de variables y umbral se eligieron SOLO con validación cruzada agrupada en el 70 %. El 30 % se evaluó una única vez.

## Modelo seleccionado por heurística (evaluado en el 30 %)

| heuristica | modelo | variables | umbral | exactitud | exactitud_balanceada | precision | sensibilidad | especificidad | f1 | mcc | kappa | roc_auc | pr_auc | f1_ic95 | mcc_ic95 | sensibilidad_ic95 | especificidad_ic95 | roc_auc_ic95 | mcnemar_p_vs_base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| H1 | Random Forest | completo+intra_participante | 0.344 | 0.742 | 0.736 | 0.605 | 0.719 | 0.754 | 0.657 | 0.457 | 0.453 | 0.788 | 0.753 | [0.500, 0.795] | [0.245, 0.655] | [0.594, 0.857] | [0.617, 0.917] | [0.710, 0.876] | 0.256 |
| H4 | KNN | completo | 0.536 | 0.645 | 0.692 | 0.31 | 0.765 | 0.618 | 0.441 | 0.298 | 0.244 | 0.794 | 0.465 | [0.259, 0.622] | [0.108, 0.491] | [0.643, 0.909] | [0.486, 0.776] | [0.652, 0.890] | 0.02 |
| H5 | Red Neuronal (MLP) | completo+intra_participante | 0.349 | 0.778 | 0.792 | 0.889 | 0.727 | 0.857 | 0.8 | 0.57 | 0.556 | 0.935 | 0.962 | [0.667, 0.957] | [0.328, 0.878] | [0.545, 0.917] | [0.625, 1.000] | [0.828, 1.000] | 0.508 |
| H6 | Bagging (árboles) | completo+intra_participante | 0.433 | 0.785 | 0.754 | 0.7 | 0.656 | 0.852 | 0.677 | 0.517 | 0.516 | 0.874 | 0.801 | [0.563, 0.807] | [0.305, 0.745] | [0.488, 0.852] | [0.788, 0.912] | [0.780, 0.956] | 0.043 |

## H1 · todos los modelos en el 30 % de prueba

| modelo | variables | umbral | exactitud | exactitud_balanceada | precision | sensibilidad | especificidad | f1 | mcc | kappa | roc_auc | pr_auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Línea base (clase mayoritaria) | completo | 0.5 | 0.656 | 0.5 | 0 | 0 | 1 | 0 | 0 | 0 | 0.5 | 0.344 |
| Regresión Logística | sin_resultados_ISO | 0.464 | 0.71 | 0.712 | 0.561 | 0.719 | 0.705 | 0.63 | 0.405 | 0.397 | 0.773 | 0.637 |
| KNN | sin_resultados_ISO | 0.411 | 0.591 | 0.666 | 0.453 | 0.906 | 0.426 | 0.604 | 0.341 | 0.269 | 0.727 | 0.633 |
| Naive Bayes | completo+intra_participante | 0.026 | 0.495 | 0.592 | 0.397 | 0.906 | 0.279 | 0.552 | 0.214 | 0.142 | 0.702 | 0.533 |
| Árbol de Decisión | sin_resultados_ISO | 0.419 | 0.645 | 0.655 | 0.489 | 0.688 | 0.623 | 0.571 | 0.295 | 0.283 | 0.751 | 0.634 |
| Random Forest | completo+intra_participante | 0.344 | 0.742 | 0.736 | 0.605 | 0.719 | 0.754 | 0.657 | 0.457 | 0.453 | 0.788 | 0.753 |
| Bagging (árboles) | completo+intra_participante | 0.403 | 0.763 | 0.745 | 0.647 | 0.688 | 0.803 | 0.667 | 0.484 | 0.484 | 0.809 | 0.769 |
| Extra Trees (aleatorización) | completo+intra_participante | 0.444 | 0.753 | 0.759 | 0.61 | 0.781 | 0.738 | 0.685 | 0.497 | 0.486 | 0.82 | 0.811 |
| SVM sensible al costo | sin_resultados_ISO | 0.304 | 0.699 | 0.711 | 0.545 | 0.75 | 0.672 | 0.632 | 0.402 | 0.388 | 0.817 | 0.77 |
| Red Neuronal (MLP) | completo | 0.202 | 0.763 | 0.768 | 0.625 | 0.781 | 0.754 | 0.694 | 0.514 | 0.505 | 0.85 | 0.719 |
| Gradient Boosting (contraste) | completo | 0.477 | 0.71 | 0.697 | 0.568 | 0.656 | 0.738 | 0.609 | 0.382 | 0.38 | 0.757 | 0.716 |

### H1 · validación cruzada en el 70 % (predicciones fuera de fold)

| modelo | cv_roc_auc | cv_f1 | cv_mcc |
|---|---|---|---|
| Línea base (clase mayoritaria) | 0.456 | 0 | 0 |
| Regresión Logística | 0.721 | 0.619 | 0.409 |
| KNN | 0.687 | 0.547 | 0.225 |
| Naive Bayes | 0.66 | 0.552 | 0.245 |
| Árbol de Decisión | 0.728 | 0.613 | 0.389 |
| Random Forest | 0.779 | 0.65 | 0.452 |
| Bagging (árboles) | 0.773 | 0.634 | 0.449 |
| Extra Trees (aleatorización) | 0.76 | 0.641 | 0.442 |
| SVM sensible al costo | 0.723 | 0.607 | 0.374 |
| Red Neuronal (MLP) | 0.721 | 0.593 | 0.386 |
| Gradient Boosting (contraste) | 0.766 | 0.65 | 0.449 |

## H4 · todos los modelos en el 30 % de prueba

| modelo | variables | umbral | exactitud | exactitud_balanceada | precision | sensibilidad | especificidad | f1 | mcc | kappa | roc_auc | pr_auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Línea base (clase mayoritaria) | completo | 0.5 | 0.817 | 0.5 | 0 | 0 | 1 | 0 | 0 | 0 | 0.5 | 0.183 |
| Regresión Logística | sin_resultados_ISO | 0.476 | 0.613 | 0.695 | 0.298 | 0.824 | 0.566 | 0.438 | 0.301 | 0.231 | 0.759 | 0.43 |
| KNN | completo | 0.536 | 0.645 | 0.692 | 0.31 | 0.765 | 0.618 | 0.441 | 0.298 | 0.244 | 0.794 | 0.465 |
| Naive Bayes | completo | 0.625 | 0.559 | 0.685 | 0.278 | 0.882 | 0.487 | 0.423 | 0.289 | 0.2 | 0.817 | 0.502 |
| Árbol de Decisión | sin_resultados_ISO | 0.783 | 0.71 | 0.617 | 0.308 | 0.471 | 0.763 | 0.372 | 0.201 | 0.194 | 0.651 | 0.357 |
| Random Forest | completo | 0.062 | 0.269 | 0.53 | 0.193 | 0.941 | 0.118 | 0.32 | 0.074 | 0.024 | 0.825 | 0.625 |
| Bagging (árboles) | completo | 0.053 | 0.215 | 0.52 | 0.189 | 1 | 0.039 | 0.318 | 0.086 | 0.015 | 0.792 | 0.589 |
| Extra Trees (aleatorización) | completo | 0.268 | 0.473 | 0.632 | 0.242 | 0.882 | 0.382 | 0.38 | 0.216 | 0.13 | 0.817 | 0.645 |
| SVM sensible al costo | completo | 0.086 | 0.183 | 0.5 | 0.183 | 1 | 0 | 0.309 | 0 | 0 | 0.839 | 0.68 |
| Red Neuronal (MLP) | sin_resultados_ISO | 0.325 | 0.774 | 0.793 | 0.438 | 0.824 | 0.763 | 0.571 | 0.477 | 0.437 | 0.858 | 0.7 |
| Gradient Boosting (contraste) | sin_resultados_ISO | 0.141 | 0.677 | 0.688 | 0.324 | 0.706 | 0.671 | 0.444 | 0.298 | 0.259 | 0.696 | 0.34 |

### H4 · validación cruzada en el 70 % (predicciones fuera de fold)

| modelo | cv_roc_auc | cv_f1 | cv_mcc |
|---|---|---|---|
| Línea base (clase mayoritaria) | 0.294 | 0 | 0 |
| Regresión Logística | 0.65 | 0.391 | 0.218 |
| KNN | 0.633 | 0.389 | 0.219 |
| Naive Bayes | 0.535 | 0.326 | 0.111 |
| Árbol de Decisión | 0.55 | 0.278 | 0.116 |
| Random Forest | 0.535 | 0.324 | 0.088 |
| Bagging (árboles) | 0.52 | 0.324 | 0.095 |
| Extra Trees (aleatorización) | 0.613 | 0.358 | 0.164 |
| SVM sensible al costo | 0.493 | 0.312 | 0.049 |
| Red Neuronal (MLP) | 0.603 | 0.364 | 0.205 |
| Gradient Boosting (contraste) | 0.404 | 0.211 | -0.041 |

## H5 · todos los modelos en el 30 % de prueba

| modelo | variables | umbral | exactitud | exactitud_balanceada | precision | sensibilidad | especificidad | f1 | mcc | kappa | roc_auc | pr_auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Línea base (clase mayoritaria) | completo | 0.5 | 0.611 | 0.5 | 0.611 | 1 | 0 | 0.759 | 0 | 0 | 0.5 | 0.611 |
| Regresión Logística | completo+intra_participante | 0.327 | 0.944 | 0.929 | 0.917 | 1 | 0.857 | 0.957 | 0.886 | 0.88 | 0.987 | 0.992 |
| KNN | completo+intra_participante | 0.214 | 0.778 | 0.74 | 0.769 | 0.909 | 0.571 | 0.833 | 0.523 | 0.507 | 0.818 | 0.864 |
| Naive Bayes | sin_resultados_ISO | 0.98 | 0.667 | 0.649 | 0.727 | 0.727 | 0.571 | 0.727 | 0.299 | 0.299 | 0.818 | 0.902 |
| Árbol de Decisión | completo | 0.37 | 0.722 | 0.669 | 0.714 | 0.909 | 0.429 | 0.8 | 0.396 | 0.366 | 0.643 | 0.684 |
| Random Forest | completo+intra_participante | 0.526 | 0.833 | 0.812 | 0.833 | 0.909 | 0.714 | 0.87 | 0.645 | 0.64 | 0.922 | 0.952 |
| Bagging (árboles) | completo | 0.537 | 0.889 | 0.857 | 0.846 | 1 | 0.714 | 0.917 | 0.777 | 0.753 | 0.909 | 0.944 |
| Extra Trees (aleatorización) | completo+intra_participante | 0.409 | 0.833 | 0.786 | 0.786 | 1 | 0.571 | 0.88 | 0.67 | 0.62 | 0.909 | 0.942 |
| SVM sensible al costo | completo+intra_participante | 0.575 | 0.778 | 0.766 | 0.818 | 0.818 | 0.714 | 0.818 | 0.532 | 0.532 | 0.883 | 0.934 |
| Red Neuronal (MLP) | completo+intra_participante | 0.349 | 0.778 | 0.792 | 0.889 | 0.727 | 0.857 | 0.8 | 0.57 | 0.556 | 0.935 | 0.962 |
| Gradient Boosting (contraste) | completo | 0.5 | 0.389 | 0.5 | 0 | 0 | 1 | 0 | 0 | 0 | 0.5 | 0.611 |

### H5 · validación cruzada en el 70 % (predicciones fuera de fold)

| modelo | cv_roc_auc | cv_f1 | cv_mcc |
|---|---|---|---|
| Línea base (clase mayoritaria) | 0.453 | 0.759 | 0 |
| Regresión Logística | 0.838 | 0.84 | 0.533 |
| KNN | 0.841 | 0.857 | 0.592 |
| Naive Bayes | 0.653 | 0.694 | 0.066 |
| Árbol de Decisión | 0.818 | 0.837 | 0.597 |
| Random Forest | 0.859 | 0.894 | 0.708 |
| Bagging (árboles) | 0.807 | 0.87 | 0.645 |
| Extra Trees (aleatorización) | 0.867 | 0.88 | 0.67 |
| SVM sensible al costo | 0.805 | 0.875 | 0.65 |
| Red Neuronal (MLP) | 0.909 | 0.884 | 0.713 |
| Gradient Boosting (contraste) | 0.5 | 0.759 | 0 |

## H6 · todos los modelos en el 30 % de prueba

| modelo | variables | umbral | exactitud | exactitud_balanceada | precision | sensibilidad | especificidad | f1 | mcc | kappa | roc_auc | pr_auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Línea base (clase mayoritaria) | completo | 0.5 | 0.656 | 0.5 | 0 | 0 | 1 | 0 | 0 | 0 | 0.5 | 0.344 |
| Regresión Logística | sin_resultados_ISO | 0.443 | 0.699 | 0.711 | 0.545 | 0.75 | 0.672 | 0.632 | 0.402 | 0.388 | 0.752 | 0.7 |
| KNN | sin_resultados_ISO | 0.405 | 0.72 | 0.683 | 0.6 | 0.562 | 0.803 | 0.581 | 0.372 | 0.371 | 0.728 | 0.636 |
| Naive Bayes | completo+intra_participante | 0.028 | 0.559 | 0.605 | 0.421 | 0.75 | 0.459 | 0.539 | 0.204 | 0.176 | 0.701 | 0.575 |
| Árbol de Decisión | sin_resultados_ISO | 0.585 | 0.796 | 0.725 | 0.842 | 0.5 | 0.951 | 0.627 | 0.531 | 0.499 | 0.8 | 0.672 |
| Random Forest | completo+intra_participante | 0.378 | 0.774 | 0.791 | 0.628 | 0.844 | 0.738 | 0.72 | 0.554 | 0.538 | 0.879 | 0.816 |
| Bagging (árboles) | completo+intra_participante | 0.433 | 0.785 | 0.754 | 0.7 | 0.656 | 0.852 | 0.677 | 0.517 | 0.516 | 0.874 | 0.801 |
| Extra Trees (aleatorización) | sin_resultados_ISO | 0.394 | 0.742 | 0.714 | 0.625 | 0.625 | 0.803 | 0.625 | 0.428 | 0.428 | 0.81 | 0.713 |
| SVM sensible al costo | completo+intra_participante | 0.378 | 0.753 | 0.715 | 0.655 | 0.594 | 0.836 | 0.623 | 0.441 | 0.44 | 0.833 | 0.716 |
| Red Neuronal (MLP) | sin_resultados_ISO | 0.332 | 0.71 | 0.697 | 0.568 | 0.656 | 0.738 | 0.609 | 0.382 | 0.38 | 0.707 | 0.639 |
| Gradient Boosting (contraste) | sin_resultados_ISO | 0.297 | 0.731 | 0.758 | 0.574 | 0.844 | 0.672 | 0.684 | 0.49 | 0.464 | 0.863 | 0.79 |

### H6 · validación cruzada en el 70 % (predicciones fuera de fold)

| modelo | cv_roc_auc | cv_f1 | cv_mcc |
|---|---|---|---|
| Línea base (clase mayoritaria) | 0.355 | 0 | 0 |
| Regresión Logística | 0.67 | 0.583 | 0.375 |
| KNN | 0.696 | 0.566 | 0.318 |
| Naive Bayes | 0.599 | 0.471 | 0.151 |
| Árbol de Decisión | 0.733 | 0.596 | 0.399 |
| Random Forest | 0.764 | 0.615 | 0.408 |
| Bagging (árboles) | 0.76 | 0.645 | 0.519 |
| Extra Trees (aleatorización) | 0.75 | 0.646 | 0.503 |
| SVM sensible al costo | 0.658 | 0.574 | 0.394 |
| Red Neuronal (MLP) | 0.667 | 0.584 | 0.389 |
| Gradient Boosting (contraste) | 0.732 | 0.612 | 0.399 |

## Notas

- El modelo de cada heurística se elige por MCC en validación cruzada (no por el resultado de prueba), para que la cifra de prueba no esté sesgada por la selección.
- IC 95 %: bootstrap de 1000 remuestreos de participantes del conjunto de prueba.
- McNemar exacto frente a la línea base (clase mayoritaria).
- Con pocos participantes en prueba los intervalos son amplios; interprételos junto con la CV.