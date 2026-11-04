# Etapa 1 · Perfil de las fuentes

Generado por `python -m usab_ds stage1`. Cada cifra proviene de leer los archivos reales (ver `src/usab_ds/profiling.py`, funciones `probe_*`).

## Resumen por fuente

| source | platform | unit | n_files | size_mb | n_rows_or_units | n_participants | n_interfaces | notes |
|---|---|---|---|---|---|---|---|---|
| S01_web_emotions_28489601 | web | usuario × visita | 2 | 1.08e+04 | 1.5e+07 | 18 | 1.33e+03 | Muestreo de estado ~100 ms (no log de eventos). Sin etiquetas de usabilidad ni tareas; incluye emociones faciales. |
| S02_a11y_cua | desktop+web | participante × tarea | 13878 | 3e+03 | 1.32e+03 | 16 |  | Humanos ciegos/baja visión (BLVU) y videntes (SU) + agentes CUA (Claude Sonnet 4.5, Qwen3-VL). Tiene éxito de tarea y dificultad percibida; sin etiquetas Nielsen. |
| S03_vt_llm_prototypes_29042675 | prototype | prototipo × ronda × heurística | 47 | 2.9 | 430 |  | 25 | Evaluador: GPT-4o sobre imágenes de prototipos Figma/Behance (alta y baja fidelidad). IRR_Results.csv tiene estructura mixta y no se usa como etiqueta. |
| S04_catching_ux_flaws | web | sitio × evaluación × heurística | 92 | 1.4 | 885 |  | 30 | Tres evaluaciones GPT-4o del código de 30 plantillas web públicas. |
| S04b_catching_html | web | página HTML | 3241 | 233 | 33 |  | 13 | HTML de repositorios recuperados en la v1; match_level indica la solidez del vínculo. |
| S05_serene | web | problema de usabilidad / participante | 4 | 5.4 | 46 | 99 | 2 | Problemas con severidad y elemento de UI, pero SIN asignación a heurísticas Nielsen; M1–M8 sin diccionario en los archivos. |
| S06_p3m | web | captura × heurística | 23 | 27.2 | 400 |  | 20 | Defectos propuestos por GPT-4 con validación experta (Is it a defect?). Solo positivos explícitos. |
| S07_phr | web | portal × tarea (agregado) | 2 | 0.1 |  |  |  | Solo correlaciones y t-tests agregados; heurísticas H01–H08 adaptadas a PHR, no equivalentes a Nielsen. |
| S08_dashboards | web | sesión de navegador | 3 | 27.2 | 50 |  |  | Logs DOM completos. La tabla experimental (exactitud, tiempo, NASA-TLX) no comparte clave con los logs. |
| S09_cultural_heritage | web |  | 1 | 2.3 |  |  |  | Solo el PDF del artículo; no hay datos estructurados. |
| S10_uicrit_rico | mobile | pantalla Android × tarea | 7 | 6.5e+03 | 2.98e+03 |  | 1e+03 | Plataforma móvil (Android/RICO); ratings y críticas libres, sin heurísticas Nielsen explícitas. |
| S11_zenodo_21891322 | web | interfaz | 14 | 7.6 | 12 |  |  | Capturas, un notebook y un PDF; no hay tabla de juicios heurísticos reutilizable. |
| S12_delfi22 | lms | actividad LMS | 2 | 0 | 226 |  |  | Configuración de tareas y cuestionarios de Moodle; no evalúa una interfaz ni registra interacción. |

## Menciones textuales de las heurísticas objetivo

Conteo de apariciones del nombre de la heurística en los archivos de texto de cada fuente. Es evidencia de *presencia temática*, no una etiqueta.

| source | H1 | H4 | H5 | H6 |
|---|---|---|---|---|
| S01_web_emotions_28489601 | 0 | 0 | 0 | 0 |
| S02_a11y_cua | 0 | 0 | 0 | 0 |
| S03_vt_llm_prototypes_29042675 | 152 | 127 | 208 | 124 |
| S04_catching_ux_flaws | 98 | 95 | 130 | 96 |
| S04b_catching_html | 0 | 0 | 0 | 0 |
| S05_serene | 0 | 0 | 0 | 0 |
| S06_p3m | 34 | 19 | 10 | 14 |
| S07_phr | 0 | 0 | 0 | 0 |
| S08_dashboards | 0 | 0 | 0 | 0 |
| S09_cultural_heritage | 0 | 0 | 0 | 0 |
| S10_uicrit_rico | 0 | 0 | 0 | 0 |
| S11_zenodo_21891322 | 0 | 0 | 0 | 0 |
| S12_delfi22 | 0 | 0 | 0 | 0 |

## Tipos de evento de interacción

| source | event_type | count |
|---|---|---|
| S01_web_emotions_28489601 | click_samples | 664986 |
| S01_web_emotions_28489601 | key_samples | 935096 |
| S01_web_emotions_28489601 | emotion_samples | 3741316 |
| S02_a11y_cua | web:page | 623 |
| S02_a11y_cua | web:blur | 5069 |
| S02_a11y_cua | web:focus | 5107 |
| S02_a11y_cua | web:mouse_click | 1088 |
| S02_a11y_cua | web:key_press | 8394 |
| S02_a11y_cua | web:input | 4519 |
| S02_a11y_cua | web:scroll | 3677 |
| S02_a11y_cua | os_browser:mouse_click | 2924 |
| S02_a11y_cua | os_browser:mouse_up | 2697 |
| S02_a11y_cua | os_browser:hotkey | 5587 |
| S02_a11y_cua | os_browser:key_press | 37365 |
| S02_a11y_cua | os_browser:scroll | 3685 |
| S02_a11y_cua | os_browser:mouse_move | 13597 |
| S02_a11y_cua | os_browser:drag_drop | 56 |
| S08_dashboards | load | 50 |
| S08_dashboards | windowqueryfocus | 540 |
| S08_dashboards | mouseover | 385267 |
| S08_dashboards | mouseout | 379054 |
| S08_dashboards | scroll | 30847 |
| S08_dashboards | mousewheel | 14390 |
| S08_dashboards | mousedown | 31156 |
| S08_dashboards | mouseup | 36196 |
| S08_dashboards | keydown | 75974 |
| S08_dashboards | keypress | 55334 |
| S08_dashboards | keyup | 65983 |
| S08_dashboards | change | 34512 |
| S08_dashboards | windowqueryblur | 504 |
| S08_dashboards | dblclick | 1158 |
| S08_dashboards | select | 1981 |
| S08_dashboards | contextmenu | 180 |
| S08_dashboards | copy | 24 |
| S08_dashboards | mobileTouchStart | 763 |
| S08_dashboards | mobileTouchEnd | 826 |
| S08_dashboards | cut | 20 |
| S08_dashboards | paste | 2 |

## Archivos de detalle

- `inventario_archivos.csv`: un renglón por archivo con sha256 (base de la reproducibilidad).
- `esquema_columnas.csv`: tipo, % nulos, únicos, mín/máx/media o valores frecuentes por columna.
- `hechos_fuentes.json`: hechos booleanos que evalúa la etapa 2.