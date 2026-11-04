# Etapa 3 · Dataset final `data/processed/usab_v2`

Construido: 2026-11-03T23:06:59+00:00 · commit `aee356cd89715d55809c560792324dcb79015c21` · código sin commitear: True

## Tamaño

|  | S01_web_emotions_28489601 | S02_a11y_cua | S08_dashboards |
|---|---|---|---|
| sesiones | 22328 | 458 | 50 |
| muestra principal (humanos, quality_ok) | 11210 | 353 | 50 |

Juicios heurísticos: 1,715 (686 sobre H1/H4/H5/H6) · interfaces etiquetadas: 75 · páginas con rasgos DOM: 890

## Nivel 1 · sesiones por grupo de usuario

| source | user_group | assistive_tech | sesiones | validas | exito | tiempo_mediana_s |
|---|---|---|---|---|---|---|
| S01_web_emotions_28489601 | unknown | unknown | 22328 | 11210 |  | 5.66 |
| S02_a11y_cua | BLV | screen_reader | 15 | 15 | 0.867 | 315 |
| S02_a11y_cua | BLV | unknown | 179 | 171 | 0.866 | 173 |
| S02_a11y_cua | agent | magnifier | 34 | 30 | 0.206 | 1.18e+03 |
| S02_a11y_cua | agent | none | 40 | 37 | 0.55 | 155 |
| S02_a11y_cua | agent | screen_reader | 22 | 20 | 0.409 | 580 |
| S02_a11y_cua | sighted | none | 168 | 167 | 0.988 | 71 |
| S08_dashboards | unknown | unknown | 50 | 50 |  | 3.92e+03 |

### Cobertura (% no nulo) en la muestra principal

NaN significa que la fuente no captura lo necesario; nunca se imputa.

| column | S01_web_emotions_28489601 | S02_a11y_cua | S08_dashboards |
|---|---|---|---|
| iso_effectiveness_task_completion | 0 | 100 | 0 |
| iso_efficiency_task_time_s | 100 | 100 | 100 |
| iso_efficiency_actions | 100 | 100 | 100 |
| iso_efficiency_time_based | 0 | 100 | 0 |
| iso_satisfaction_perceived_ease | 0 | 100 | 0 |
| iso_satisfaction_affective_valence | 48 | 0 | 0 |
| repeated_click_rate | 72 | 47 | 100 |
| post_click_latency_s | 61 | 44 | 100 |
| dead_click_rate | 0 | 47 | 100 |
| back_nav_rate | 0 | 80 | 0 |
| correction_key_ratio | 0 | 95 | 100 |
| input_reentry_rate | 0 | 35 | 0 |
| long_pause_ratio | 100 | 100 | 100 |
| scroll_reversal_rate | 49 | 44 | 100 |
| page_revisit_rate | 0 | 80 | 100 |
| focus_churn | 0 | 100 | 0 |
| hover_without_click_ratio | 0 | 0 | 100 |

### Medianas en la muestra principal

| column | S01_web_emotions_28489601 | S02_a11y_cua | S08_dashboards |
|---|---|---|---|
| iso_effectiveness_task_completion |  | 1 |  |
| iso_efficiency_task_time_s | 33.7 | 133 | 3.92e+03 |
| iso_efficiency_actions | 7 | 64 | 1.8e+03 |
| iso_efficiency_time_based |  | 0.452 |  |
| iso_satisfaction_perceived_ease |  | 0.75 |  |
| iso_satisfaction_affective_valence | -0.00681 |  |  |
| repeated_click_rate | 0 | 0 | 0.156 |
| post_click_latency_s | 1.86 | 1.14 | 1.07 |
| dead_click_rate |  | 0.4 | 0.636 |
| back_nav_rate |  | 0 |  |
| correction_key_ratio |  | 0 | 0.0762 |
| input_reentry_rate |  | 0 |  |
| long_pause_ratio | 0.352 | 0.0905 | 0.366 |
| scroll_reversal_rate | 0.0726 | 0.137 | 0.266 |
| page_revisit_rate |  | 0 | 0 |
| focus_churn |  | 0.04 |  |
| hover_without_click_ratio |  |  | 0.841 |

## Nivel 2 · prevalencia de violación por fuente y evaluador

| source | evaluator_type | interfaces | H1_violation_prev | H4_violation_prev | H5_violation_prev | H6_violation_prev |
|---|---|---|---|---|---|---|
| S03_vt_llm_prototypes_29042675 | llm | 25 | 1 | 1 | 1 | 1 |
| S04_catching_ux_flaws | llm | 30 | 0.967 | 0.931 | 0.933 | 0.633 |
| S06_p3m | llm | 20 | 0.4 | 0.15 | 0 | 0.1 |
| S06_p3m | llm_expert_validated | 20 | 0.3 | 0.1 | 0 | 0.05 |

## Fiabilidad (α de Krippendorff, nominal)

NaN cuando no hay variación (todas las evaluaciones coinciden en el mismo valor): α no está definido.

| source | heuristic | evaluator_type | n_interfaces | prevalence | krippendorff_alpha |
|---|---|---|---|---|---|
| S03_vt_llm_prototypes_29042675 | H1 | llm | 13 | 1 |  |
| S03_vt_llm_prototypes_29042675 | H4 | llm | 14 | 1 |  |
| S03_vt_llm_prototypes_29042675 | H5 | llm | 14 | 1 |  |
| S03_vt_llm_prototypes_29042675 | H6 | llm | 18 | 1 |  |
| S04_catching_ux_flaws | H1 | llm | 30 | 0.966 | 0.659 |
| S04_catching_ux_flaws | H4 | llm | 30 | 0.795 | 0.102 |
| S04_catching_ux_flaws | H5 | llm | 30 | 0.876 | 0.385 |
| S04_catching_ux_flaws | H6 | llm | 30 | 0.618 | 0.153 |
| S06_p3m | H1 | llm | 0 | 0.4 |  |
| S06_p3m | H1 | llm_expert_validated | 0 | 0.3 |  |
| S06_p3m | H4 | llm | 0 | 0.15 |  |
| S06_p3m | H4 | llm_expert_validated | 0 | 0.1 |  |
| S06_p3m | H5 | llm | 0 | 0 |  |
| S06_p3m | H5 | llm_expert_validated | 0 | 0 |  |
| S06_p3m | H6 | llm | 0 | 0.1 |  |
| S06_p3m | H6 | llm_expert_validated | 0 | 0.05 |  |
| S06_p3m | all | llm vs llm_expert_validated | 200 |  | 0.872 |