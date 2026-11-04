# Etapa 2 · Elegibilidad y correspondencias

## Criterios

- **C1_accessible**: Los archivos existen localmente y se pueden leer de forma programática.
- **C2_web_context**: El objeto evaluado es una interfaz web o de navegador (o un prototipo de interfaz web/app evaluado con heurísticas).
- **C3_browser_interactions**: Contiene eventos de interacción del navegador con marca de tiempo (clic, scroll, teclado, foco, navegación).
- **C4_target_heuristic_labels**: Contiene juicios explícitos de violación de al menos una heurística objetivo (H1, H4, H5, H6), con nombre Nielsen reconocible.
- **C5_disaggregated**: Los datos están a nivel de unidad (sesión, tarea, interfaz), no solo como estadísticas agregadas.
- **C6_html_available**: Dispone de HTML/DOM de las interfaces para calcular rasgos estáticos comparables.

Roles: `behavior` = C1∧C2∧C3∧C5 · `labels` = C1∧C2∧C4∧C5 · `bridge` = C1∧C2∧C6.

## Matriz de elegibilidad

| source | C1_accessible | C2_web_context | C3_browser_interactions | C4_target_heuristic_labels | C5_disaggregated | C6_html_available | roles | motivo |
|---|---|---|---|---|---|---|---|---|
| S01_web_emotions_28489601 | ✔ | ✔ | ✔ | ✘ | ✔ | ✘ | behavior | cumple todos los criterios del rol |
| S02_a11y_cua | ✔ | ✔ | ✔ | ✘ | ✔ | ✔ | behavior+bridge | cumple todos los criterios del rol |
| S03_vt_llm_prototypes_29042675 | ✔ | ✔ | ✘ | ✔ | ✔ | ✘ | labels | cumple todos los criterios del rol |
| S04_catching_ux_flaws | ✔ | ✔ | ✘ | ✔ | ✔ | ✔ | labels+bridge | cumple todos los criterios del rol |
| S04b_catching_html | ✔ | ✔ | ✘ | ✘ | ✔ | ✔ | bridge | cumple todos los criterios del rol |
| S05_serene | ✔ | ✔ | ✘ | ✘ | ✔ | ✘ | excluded | behavior: falla C3_browser_interactions; labels: falla C4_target_heuristic_labels; bridge: falla C6_html_available |
| S06_p3m | ✔ | ✔ | ✘ | ✔ | ✔ | ✘ | labels | cumple todos los criterios del rol |
| S07_phr | ✔ | ✔ | ✘ | ✘ | ✘ | ✘ | excluded | behavior: falla C3_browser_interactions, C5_disaggregated; labels: falla C4_target_heuristic_labels, C5_disaggregated; bridge: falla C6_html_available |
| S08_dashboards | ✔ | ✔ | ✔ | ✘ | ✔ | ✘ | behavior | cumple todos los criterios del rol |
| S09_cultural_heritage | ✘ | ✔ | ✘ | ✘ | ✘ | ✘ | excluded | behavior: falla C1_accessible, C3_browser_interactions, C5_disaggregated; labels: falla C1_accessible, C4_target_heuristic_labels, C5_disaggregated; bridge: falla C1_accessible, C6_html_available |
| S10_uicrit_rico | ✔ | ✘ | ✘ | ✘ | ✔ | ✘ | excluded | behavior: falla C2_web_context, C3_browser_interactions; labels: falla C2_web_context, C4_target_heuristic_labels; bridge: falla C2_web_context, C6_html_available |
| S11_zenodo_21891322 | ✔ | ✔ | ✘ | ✘ | ✘ | ✘ | excluded | behavior: falla C3_browser_interactions, C5_disaggregated; labels: falla C4_target_heuristic_labels, C5_disaggregated; bridge: falla C6_html_available |
| S12_delfi22 | ✔ | ✘ | ✘ | ✘ | ✔ | ✘ | excluded | behavior: falla C2_web_context, C3_browser_interactions; labels: falla C2_web_context, C4_target_heuristic_labels; bridge: falla C2_web_context, C6_html_available |

## Marco de correspondencia Nielsen ↔ ISO/IEC 25010 ↔ medidas

| heuristic | heuristic_name | heuristic_name_es | iso25010_2011 | iso25010_2023 | link_evidence | quality_in_use | wcag | behavioral_indicators | dom_features |
|---|---|---|---|---|---|---|---|---|---|
| H1 | Visibility of system status | Visibilidad del estado del sistema | Usability › Operability | Interaction capability › Self-descriptiveness | operational | Efficiency | 4.1.3 Status Messages | repeated_click_rate, post_click_latency_s, dead_click_rate | dom_status_regions, dom_loading_indicators |
| H1 | Visibility of system status | Visibilidad del estado del sistema | Usability › Appropriateness recognizability | Interaction capability › User assistance | operational | Efficiency | 4.1.3 Status Messages | repeated_click_rate, post_click_latency_s, dead_click_rate | dom_status_regions, dom_loading_indicators |
| H4 | Consistency and standards | Consistencia y estándares | Usability › Learnability | Interaction capability › Learnability | operational | Efficiency, Effectiveness | 3.2.3 Consistent Navigation, 3.2.4 Consistent Identification | dead_click_rate, back_nav_rate, focus_churn | dom_button_style_variety, dom_inconsistent_link_text, dom_has_nav |
| H4 | Consistency and standards | Consistencia y estándares | Usability › Operability | Interaction capability › Operability | operational | Efficiency, Effectiveness | 3.2.3 Consistent Navigation, 3.2.4 Consistent Identification | dead_click_rate, back_nav_rate, focus_churn | dom_button_style_variety, dom_inconsistent_link_text, dom_has_nav |
| H5 | Error prevention | Prevención de errores | Usability › User error protection | Interaction capability › User error protection | normative | Effectiveness, Freedom from risk | 3.3.1 Error Identification, 3.3.3 Error Suggestion, 3.3.4 Error Prevention (Legal, Financial, Data) | correction_key_ratio, input_reentry_rate | dom_input_constraint_ratio, dom_input_autocomplete_ratio |
| H6 | Recognition rather than recall | Reconocer antes que recordar | Usability › Appropriateness recognizability | Interaction capability › Appropriateness recognizability | operational | Efficiency, Satisfaction | 2.4.8 Location, 3.3.2 Labels or Instructions, 1.1.1 Non-text Content | back_nav_rate, long_pause_ratio, scroll_reversal_rate, page_revisit_rate, focus_churn, hover_without_click_ratio | dom_input_label_ratio, dom_placeholder_only_ratio, dom_img_alt_ratio, dom_has_breadcrumb, dom_has_search, dom_n_headings |
| H6 | Recognition rather than recall | Reconocer antes que recordar | Usability › Learnability | Interaction capability › Learnability | operational | Efficiency, Satisfaction | 2.4.8 Location, 3.3.2 Labels or Instructions, 1.1.1 Non-text Content | back_nav_rate, long_pause_ratio, scroll_reversal_rate, page_revisit_rate, focus_churn, hover_without_click_ratio | dom_input_label_ratio, dom_placeholder_only_ratio, dom_img_alt_ratio, dom_has_breadcrumb, dom_has_search, dom_n_headings |

`link_evidence`: *normative* = lo establece la norma; *operational* = hipótesis de este trabajo que debe validarse con la plantilla `plantilla_validacion_expertos.csv` (CVR de Lawshe).

## Fuente × heurística

| source | heuristic | roles | explicit_labels | indicators_computable | indicators_linked | indicators | dom_features |
|---|---|---|---|---|---|---|---|
| S01_web_emotions_28489601 | H1 | behavior | 0 | 2 | 3 | repeated_click_rate, post_click_latency_s | 0 |
| S01_web_emotions_28489601 | H4 | behavior | 0 | 0 | 3 |  | 0 |
| S01_web_emotions_28489601 | H5 | behavior | 0 | 0 | 2 |  | 0 |
| S01_web_emotions_28489601 | H6 | behavior | 0 | 2 | 6 | long_pause_ratio, scroll_reversal_rate | 0 |
| S02_a11y_cua | H1 | behavior+bridge | 0 | 3 | 3 | repeated_click_rate, post_click_latency_s, dead_click_rate | 2 |
| S02_a11y_cua | H4 | behavior+bridge | 0 | 3 | 3 | dead_click_rate, back_nav_rate, focus_churn | 3 |
| S02_a11y_cua | H5 | behavior+bridge | 0 | 2 | 2 | correction_key_ratio, input_reentry_rate | 2 |
| S02_a11y_cua | H6 | behavior+bridge | 0 | 5 | 6 | back_nav_rate, long_pause_ratio, scroll_reversal_rate, page_revisit_rate, focus_churn | 6 |
| S03_vt_llm_prototypes_29042675 | H1 | labels | 37 | 0 | 3 |  | 0 |
| S03_vt_llm_prototypes_29042675 | H4 | labels | 38 | 0 | 3 |  | 0 |
| S03_vt_llm_prototypes_29042675 | H5 | labels | 38 | 0 | 2 |  | 0 |
| S03_vt_llm_prototypes_29042675 | H6 | labels | 43 | 0 | 6 |  | 0 |
| S04_catching_ux_flaws | H1 | labels+bridge | 88 | 0 | 3 |  | 2 |
| S04_catching_ux_flaws | H4 | labels+bridge | 88 | 0 | 3 |  | 3 |
| S04_catching_ux_flaws | H5 | labels+bridge | 89 | 0 | 2 |  | 2 |
| S04_catching_ux_flaws | H6 | labels+bridge | 89 | 0 | 6 |  | 6 |
| S04b_catching_html | H1 | bridge | 0 | 0 | 3 |  | 2 |
| S04b_catching_html | H4 | bridge | 0 | 0 | 3 |  | 3 |
| S04b_catching_html | H5 | bridge | 0 | 0 | 2 |  | 2 |
| S04b_catching_html | H6 | bridge | 0 | 0 | 6 |  | 6 |
| S06_p3m | H1 | labels | 40 | 0 | 3 |  | 0 |
| S06_p3m | H4 | labels | 40 | 0 | 3 |  | 0 |
| S06_p3m | H5 | labels | 40 | 0 | 2 |  | 0 |
| S06_p3m | H6 | labels | 40 | 0 | 6 |  | 0 |
| S08_dashboards | H1 | behavior | 0 | 3 | 3 | repeated_click_rate, post_click_latency_s, dead_click_rate | 0 |
| S08_dashboards | H4 | behavior | 0 | 1 | 3 | dead_click_rate | 0 |
| S08_dashboards | H5 | behavior | 0 | 1 | 2 | correction_key_ratio | 0 |
| S08_dashboards | H6 | behavior | 0 | 4 | 6 | long_pause_ratio, scroll_reversal_rate, page_revisit_rate, hover_without_click_ratio | 0 |

## Fuente × medida ISO/IEC 25022

| source | iso_measure | iso_characteristic | standard | computable | requires |
|---|---|---|---|---|---|
| S01_web_emotions_28489601 | iso_effectiveness_task_completion | Effectiveness | iso25022 | False | success |
| S01_web_emotions_28489601 | iso_efficiency_task_time_s | Efficiency | iso25022 | True | duration |
| S01_web_emotions_28489601 | iso_efficiency_actions | Efficiency | iso25022 | True | actions |
| S01_web_emotions_28489601 | iso_efficiency_time_based | Efficiency | iso25022 | False | success |
| S01_web_emotions_28489601 | iso_satisfaction_perceived_ease | Satisfaction | iso25022 | False | difficulty_after |
| S01_web_emotions_28489601 | iso_satisfaction_affective_valence | Satisfaction | iso25022 | True | emotion |
| S02_a11y_cua | iso_effectiveness_task_completion | Effectiveness | iso25022 | True | success |
| S02_a11y_cua | iso_efficiency_task_time_s | Efficiency | iso25022 | True | duration |
| S02_a11y_cua | iso_efficiency_actions | Efficiency | iso25022 | True | actions |
| S02_a11y_cua | iso_efficiency_time_based | Efficiency | iso25022 | True | success |
| S02_a11y_cua | iso_satisfaction_perceived_ease | Satisfaction | iso25022 | True | difficulty_after |
| S02_a11y_cua | iso_satisfaction_affective_valence | Satisfaction | iso25022 | False | emotion |
| S08_dashboards | iso_effectiveness_task_completion | Effectiveness | iso25022 | False | success |
| S08_dashboards | iso_efficiency_task_time_s | Efficiency | iso25022 | True | duration |
| S08_dashboards | iso_efficiency_actions | Efficiency | iso25022 | True | actions |
| S08_dashboards | iso_efficiency_time_based | Efficiency | iso25022 | False | success |
| S08_dashboards | iso_satisfaction_perceived_ease | Satisfaction | iso25022 | False | difficulty_after |
| S08_dashboards | iso_satisfaction_affective_valence | Satisfaction | iso25022 | False | emotion |
| S08_dashboards | iso_effectiveness_answer_correct / NASA-TLX | Effectiveness / Satisfaction | iso25022 | True | tabla experimental separada (sin clave con los logs) |