# Etapa 3b · Etiquetas H1/H4/H5/H6 por inspección con rúbrica

Método: revisión automatizada por guías (Ivory y Hearst, 2001) con 16 criterios (`configs/rubric.yaml`), cada uno anclado en una pregunta guía de Nielsen (1994) y un criterio WCAG 2.2. Severidad 0–4 de Nielsen (1994b) = impacto (nivel WCAG) ajustado por frecuencia; violación = severidad ≥ 2.

## Prevalencia por página (A11y-CUA)

| heuristic | paginas | evaluables | violaciones | prevalencia |
|---|---|---|---|---|
| H1 | 838 | 838 | 264 | 0.315 |
| H4 | 838 | 837 | 174 | 0.208 |
| H5 | 838 | 132 | 98 | 0.742 |
| H6 | 838 | 837 | 273 | 0.326 |

## Criterios

| check | criterio | nivel | paginas_elegibles | paginas_con_falla_sev2 | severidad_media |
|---|---|---|---|---|---|
| H1_current_location | WCAG 2.4.8 Location | AAA | 581 | 0 | 0.141 |
| H1_expanded_state | WCAG 4.1.2 Name, Role, Value (estado) | A | 682 | 240 | 0.742 |
| H1_page_title | WCAG 2.4.2 Page Titled | A | 838 | 1 | 0.00358 |
| H1_status_messages | WCAG 4.1.3 Status Messages | AA | 398 | 28 | 0.0668 |
| H4_ambiguous_link_names | WCAG 2.4.4 Link Purpose / 3.2.4 Consistent Identification | AA | 815 | 0 | 0.103 |
| H4_heading_skips | WCAG 1.3.1 Info and Relationships (buena práctica de jerarquía) | BP | 726 | 0 | 0.0155 |
| H4_links_as_buttons | Buena práctica HTML (enlace sin destino); WCAG 2.1.1 si no es enfocable | AA | 820 | 6 | 0.424 |
| H4_nonstandard_controls | WCAG 4.1.2 Name, Role, Value (rol) | A | 616 | 172 | 0.643 |
| H5_autocomplete_missing | WCAG 1.3.5 Identify Input Purpose | AA | 100 | 13 | 0.031 |
| H5_constraints_not_communicated | WCAG 3.3.2 Labels or Instructions | A | 26 | 25 | 0.0895 |
| H5_input_type_mismatch | WCAG 3.3.4 Error Prevention / 1.3.5 (buena práctica de tipos de entrada) | AA | 100 | 64 | 0.153 |
| H6_images_without_alt | WCAG 1.1.1 Non-text Content | A | 742 | 80 | 0.247 |
| H6_no_headings | WCAG 2.4.6 Headings and Labels / 1.3.1 | AA | 784 | 1 | 0.00239 |
| H6_no_search_large_page | Buena práctica (búsqueda en páginas extensas; WCAG 2.4.5 Multiple Ways, a nivel de sitio) | BP | 273 | 0 | 0.0346 |
| H6_unlabeled_inputs | WCAG 3.3.2 Labels or Instructions / 1.3.1 / 4.1.2 | A | 769 | 239 | 0.802 |
| H6_unnamed_controls | WCAG 4.1.2 Name, Role, Value / 2.4.4 Link Purpose | A | 836 | 68 | 0.703 |

## Validez concurrente frente a Catching UX Flaws

Referencia: mayoría de 3 evaluaciones GPT-4o sobre el mismo código (13 sitios con HTML recuperado). La referencia es casi siempre positiva, por lo que κ puede ser 0 o indefinido aunque la exactitud sea alta.

| heuristic | reference | ref_prevalence | n | tp | fp | fn | tn | accuracy | cohen_kappa | precision | recall |
|---|---|---|---|---|---|---|---|---|---|---|---|
| H1 | Catching UX Flaws · mayoría GPT-4o | 1 | 13 | 3 | 0 | 10 | 0 | 0.231 | 0 | 1 | 0.231 |
| H4 | Catching UX Flaws · mayoría GPT-4o | 0.917 | 11 | 5 | 0 | 5 | 1 | 0.545 | 0.154 | 1 | 0.5 |
| H5 | Catching UX Flaws · mayoría GPT-4o | 0.923 | 4 | 4 | 0 | 0 | 0 | 1 |  | 1 | 1 |
| H6 | Catching UX Flaws · mayoría GPT-4o | 0.231 | 12 | 3 | 5 | 0 | 4 | 0.583 | 0.286 | 0.375 | 1 |

## Validez de criterio frente a lo que reportan los usuarios

Si las violaciones detectadas afectan a las personas, las sesiones con violación deberían mostrar menor facilidad percibida o éxito, o más tiempo. `rank_biserial` > 0 = mayor en sesiones con violación (< 0 = menor). Prueba U de Mann-Whitney bilateral, sin corrección por comparaciones múltiples (exploratorio).

| heuristic | n_viol | n_no_viol | facilidad_viol | facilidad_no_viol | facilidad_p_mwu | facilidad_rank_biserial | exito_viol | exito_no_viol | exito_p_mwu | exito_rank_biserial | tiempo_s_viol | tiempo_s_no_viol | tiempo_s_p_mwu | tiempo_s_rank_biserial |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| H1 | 104 | 204 | 0.666 | 0.635 | 0.0946 | 0.0935 | 0.913 | 0.907 | 0.85 | 0.0066 | 182 | 198 | 0.415 | -0.0568 |
| H4 | 56 | 252 | 0.616 | 0.652 | 0.15 | -0.0987 | 0.875 | 0.917 | 0.328 | -0.0417 | 226 | 185 | 0.0414 | 0.174 |
| H5 | 33 | 21 | 0.674 | 0.679 | 0.825 | -0.0289 | 1 | 0.952 | 0.224 | 0.0476 | 258 | 175 | 0.264 | 0.183 |
| H6 | 101 | 207 | 0.639 | 0.649 | 0.491 | -0.0388 | 0.95 | 0.889 | 0.0782 | 0.0616 | 190 | 194 | 0.522 | 0.045 |

## Auditoría del evaluador

Antes de fijar Y se revisaron muestras de evidencias de cada criterio. Se corrigieron estos falsos positivos de implementación (no se ajustaron umbrales para cambiar la prevalencia):

| id | criterio | falso_positivo_observado | corrección |
|---|---|---|---|
| A1 | H5_input_type_mismatch | id=username con inputmode=email y type=text (target.com) | inputmode adecuado ya ofrece el teclado del tipo esperado → no es falla |
| A2 | H5_autocomplete_missing | checkbox id=vector-user-links-dropdown-checkbox (Wikipedia) | solo campos de texto y términos completos ('user' dentro de un id no es un campo de usuario) |
| A3 | H4_nonstandard_controls | <h2 tabindex=0> en target.com | encabezados/regiones enfocables sin onclick son gestión de foco, no controles |
| A4 | H1_status_messages | checkbox usado como interruptor CSS del menú (neildegrassetyson.com) | solo cuentan campos donde se escriben/eligen datos |
| A5 | H5_input_type_mismatch | 'Email or phone number' con type=text (facebook.com); selector de fecha propio (expedia.com) | campos de propósito múltiple y selectores de fecha personalizados no son falla |
| A6 | H1_status_messages | buscador de Wikipedia/YouTube | un buscador que navega a otra página no requiere mensajes de estado en la página |

`muestra_evidencias.csv` contiene 3 evidencias por criterio para revisión independiente.

## Limitaciones

- Inspección estática: no observa CSS calculado ni manejadores añadidos por JavaScript.
- La rúbrica mide incumplimientos verificables en el marcado; no sustituye una evaluación heurística experta completa (p. ej. coherencia terminológica o adecuación del contenido).
- H5 solo es evaluable en páginas con campos de datos (~16 % de las páginas).