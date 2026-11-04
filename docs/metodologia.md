# Metodología de construcción del dataset (v2)

Este documento justifica cada decisión del pipeline. Las cifras no se escriben
aquí a mano: están en los informes que genera el propio pipeline
(`reports/01_perfil_fuentes`, `reports/02_relevancia`, `reports/03_dataset`).

## 1. Marco conceptual

### 1.1 Heurísticas objetivo

Se trabaja con cuatro de las diez heurísticas de Nielsen (1994):

| Código | Heurística | Por qué es observable en el navegador |
|---|---|---|
| H1 | Visibilidad del estado del sistema | La falta de retroalimentación se manifiesta como clics repetidos, clics sin respuesta y esperas tras una acción |
| H4 | Consistencia y estándares | Elementos que parecen accionables y no lo son, y regresos de navegación, señalan expectativas no cumplidas |
| H5 | Prevención de errores | Las correcciones de entrada (Backspace/Delete) y la re-edición de campos aproximan errores de entrada |
| H6 | Reconocer antes que recordar | Las pausas largas, las reversiones de scroll y las revisitas aproximan la búsqueda o el recuerdo de información |

### 1.2 Relación con ISO/IEC 25010

* **ISO/IEC 25010** define el *modelo* de calidad. En la edición 2011, la
  característica *Usability* incluye *appropriateness recognizability*,
  *learnability*, *operability*, *user error protection*, *user interface
  aesthetics* y *accessibility*. En la edición 2023 se renombra *Interaction
  capability* (con *self-descriptiveness*, *user assistance*, *user
  engagement* e *inclusivity*), y el modelo de calidad en uso pasa a
  **ISO/IEC 25019:2023**.
* ISO/IEC 25010 **no define métricas**. Las métricas que la tesis llama
  "del estándar 25010" (tiempo, acciones, éxito, errores) son medidas de
  **ISO/IEC 25022:2016** (calidad en uso: efectividad, eficiencia,
  satisfacción) y de **ISO/IEC 25023:2016** (calidad del producto). En la
  tesis conviene citarlas así: *medidas ISO/IEC 25022 que operacionalizan
  características de ISO/IEC 25010*.
* ISO 9241-11:2018 aporta la definición de usabilidad (efectividad,
  eficiencia y satisfacción en un contexto de uso), que justifica conservar
  el **contexto de uso** (grupo de usuario, tecnología de apoyo, tarea) como
  columnas del dataset.

El mapeo completo está en `configs/crosswalk.yaml` y en
`reports/02_relevancia/crosswalk_heuristicas_iso.csv`. Cada vínculo tiene un
tipo de evidencia:

* `normative`: lo establece una norma (p. ej. H5 ↔ *user error protection*).
* `literature`: lo respaldan estudios empíricos (p. ej. clics sobre elementos
  no accionables como *usability smell*, Grigera et al., 2017).
* `operational`: es una hipótesis de este trabajo. **Debe validarse con
  juicio experto** usando `plantilla_validacion_expertos.csv` y la razón de
  validez de contenido de Lawshe (1975): CVR = (nₑ − N/2)/(N/2). Los vínculos
  con CVR por debajo del valor crítico para el número de expertos se retiran
  de `configs/indicators.yaml` y se vuelve a ejecutar el pipeline.

## 2. Selección de fuentes (etapa 2)

Las fuentes se evalúan con seis criterios automáticos
(`configs/inclusion_criteria.yaml`), calculados sobre hechos extraídos de
los datos (etapa 1), no de la documentación de los autores:

| Criterio | Descripción |
|---|---|
| C1 | Archivos disponibles y legibles |
| C2 | Contexto web o prototipo de interfaz evaluado |
| C3 | Eventos de interacción del navegador con marca de tiempo |
| C4 | Juicios explícitos de violación de H1/H4/H5/H6 |
| C5 | Datos desagregados (no solo estadísticas) |
| C6 | HTML/DOM disponible |

Roles: `behavior` = C1∧C2∧C3∧C5; `labels` = C1∧C2∧C4∧C5;
`bridge` = C1∧C2∧C6. El resultado y el motivo de cada exclusión están en
`reports/02_relevancia/matriz_elegibilidad.csv`. La tabla sigue el espíritu
del diagrama de flujo de elegibilidad de PRISMA 2020: toda fuente aparece,
incluida o excluida, con su criterio.

## 3. Nivel 1: sesiones de navegador

### 3.1 Esquema canónico de eventos

Cada adaptador (`src/usab_ds/adapters/*.py`) traduce su fuente a un esquema
único (`events.py`): `page_view`, `click`, `key`, `scroll`, `scroll_pos`,
`input`, `focus`, `blur`, `nav_back`, `mouse_move`, `hover`. Las reglas de
traducción de cada fuente están numeradas (R1, R2, …) en el encabezado de su
adaptador, para poder citarlas.

Las métricas se calculan **una sola vez** sobre ese esquema (`metrics.py`),
así que la misma definición operacional se aplica a todas las fuentes.

### 3.2 Unidad de análisis

| Fuente | Sesión | Justificación |
|---|---|---|
| A11y-CUA | participante × tarea con navegador | La fuente está organizada por tareas con éxito y dificultad |
| 28489601 | usuario × visita a una URL; se corta tras 30 min de inactividad | Navegación libre sin tareas; umbral de sesión de Catledge y Pitkow (1995) |
| Dashboards | archivo de log | Única clave disponible; no se puede unir con la tabla experimental (0 coincidencias de clave) |

### 3.3 Datos faltantes

Si una fuente no captura lo que un indicador necesita (por ejemplo, la
identidad del elemento clicado), el indicador queda en **NaN, nunca en 0**.
Así se evita confundir "no medido" con "no ocurrió". Las capacidades de cada
fuente están declaradas en `CAPABILITIES` dentro de su adaptador, y la
cobertura real aparece en `reports/03_dataset/README.md`.

### 3.4 Control de calidad

`quality_ok` exige al menos `min_session_seconds` (5 s) y
`min_session_events` (3 eventos). La muestra principal (`include_main`)
contiene solo sesiones **humanas** con `quality_ok`. Las sesiones de agentes
(CUA) se conservan marcadas con `is_human = False` para análisis
comparativos, pero no forman parte de la muestra principal.

### 3.5 Índices proxy por heurística

`H*_proxy_z` es la media de los z robustos (mediana/MAD, calculados dentro de
cada fuente y con referencia en los humanos) de los indicadores ligados a la
heurística. Es un **índice exploratorio**, no una etiqueta de violación.
Convertirlo en etiqueta y luego entrenar un modelo con esas mismas variables
sería circular.

### 3.6 Variables de confusión documentadas

* La tecnología de apoyo cambia el patrón de interacción: los usuarios de
  lector de pantalla casi no hacen clic y navegan con teclado y foco. Los
  análisis deben estratificarse por `user_group` y
  `assistive_tech_participant`. Cuando en un usuario BLV no hay evidencia de
  la tecnología de apoyo se registra `unknown`, no `none`, porque un lector
  de pantalla que corre en segundo plano no aparece en el log de aplicaciones.
* `dead_click_rate` usa la etiqueta del elemento. En aplicaciones que
  ponen manejadores de clic en `<div>` (Shiny, React) sobreestima los clics
  muertos.
* En Dashboards, la sesión abarca todo el estudio (consentimiento,
  cuestionarios y dashboards), no una tarea.

## 4. Nivel 2: evaluaciones heurísticas

| Fuente | Evaluador | Artefacto | Negativos |
|---|---|---|---|
| Catching UX Flaws | GPT-4o × 3 evaluaciones | código de 30 sitios | explícitos (`IssueFound = false`) |
| 29042675 | GPT-4o × 2 rondas | imágenes de prototipos | sección sin severidades ≥ 1 |
| P3M | GPT-4 y GPT-4 validado por expertos | capturas | por ausencia (`negative_by_absence = True`) |

`violation = 1` si se reporta al menos un problema con severidad ≥ 1
(escala 0–4 de Nielsen). La fiabilidad entre evaluaciones se reporta con
el α de Krippendorff nominal (`reliability.csv`).

**Advertencia para el modelado:** en las fuentes evaluadas por LLM la
prevalencia de violación es casi del 100 % para H1/H4/H5/H6 (ver
`reports/03_dataset/README.md`). Con esa poca variación, la etiqueta apenas
discrimina entre interfaces. La validación experta de P3M muestra además que
parte de lo que reporta el LLM no se confirma.

## 5. Dataset único de entrenamiento (etapas 3b y 4)

Para entrenar hace falta X e Y en la misma fila. Solo A11y-CUA guarda, por
sesión, las interacciones (X) y el HTML de las páginas vistas, así que Y se
obtiene inspeccionando ese HTML.

### 5.1 Método de etiquetado: inspección por guías con rúbrica

* **Tipo de método:** evaluación automatizada por *revisión de guías*
  (*guideline review*; Ivory y Hearst, 2001). Es determinista y repetible:
  la misma página siempre recibe la misma etiqueta.
* **Instrumento:** 16 criterios (`configs/rubric.yaml`). Cada uno
  operacionaliza una pregunta guía de la heurística de Nielsen (1994) y se
  ancla en un criterio de éxito de WCAG 2.2 o en una buena práctica
  documentada.
* **Severidad:** escala 0–4 de Nielsen (1994b), que combina impacto y
  frecuencia. El impacto es el nivel de conformidad WCAG (A = 3, AA = 2,
  AAA o buena práctica = 1). La frecuencia es la proporción de elementos
  afectados: ≥ 25 % conserva el impacto, 5–25 % resta 1 y < 5 % resta 2.
* **Violación:** severidad ≥ 2. Nielsen define el 1 como problema cosmético
  que no necesita arreglarse; por eso un criterio AAA o de buena práctica
  nunca produce una violación por sí solo.
* **Evaluabilidad:** si ningún criterio de una heurística tiene elementos
  elegibles en la página, la heurística queda NA. Por ejemplo, H5 en una
  página sin campos de datos.
* **Sesión:** `y_H*` = 1 si la mitad o más de las páginas evaluables de la
  sesión violan la heurística. Con "alguna página" la etiqueta crecería
  mecánicamente con el número de páginas visitadas, que también está en X.
  `y_any_H*` y `y_rate_H*` se incluyen como alternativas.

### 5.2 Auditoría del evaluador

Antes de fijar Y se revisaron muestras de evidencias de cada criterio. Se
corrigieron seis falsos positivos de implementación (A1–A6, en
`reports/04_etiquetas_rubrica/auditoria_evaluador.csv`), por ejemplo un
campo "correo o teléfono" que correctamente usa `type=text`. **No se
ajustaron los umbrales para modificar la prevalencia.** Los umbrales de
severidad y de violación se fijaron antes de ver la distribución de
etiquetas.

### 5.3 Validación (`reports/04_etiquetas_rubrica`)

1. **Validez concurrente:** comparación con la mayoría de las 3 evaluaciones
   GPT-4o de Catching UX Flaws sobre el mismo código (13 sitios). Es una
   referencia débil, porque es casi siempre positiva.
2. **Validez de criterio:** comparación entre sesiones con y sin violación
   según los resultados que reportan los propios usuarios (facilidad
   percibida, éxito y tiempo de tarea), con la prueba U de Mann-Whitney y el
   rank-biserial como tamaño de efecto.
3. **Muestra de evidencias** (`muestra_evidencias.csv`) para que un segundo
   evaluador humano verifique la rúbrica. Se recomienda calcular κ con esa
   revisión independiente.

### 5.4 Prevención de fuga de información

Y depende solo del HTML. Por eso los rasgos DOM (`dom_*`) **se excluyen de
X**: el modelo aprendería la regla de la rúbrica y no la relación con el
comportamiento. X = indicadores de interacción + medidas ISO/IEC 25022 +
contexto de uso. La pregunta de modelado queda así: *¿el comportamiento del
usuario en el navegador permite predecir los incumplimientos heurísticos
de la página?*

### 5.5 Partición

4 folds agrupados por participante y estratificados por grupo BLV/vidente
(columna `fold`). Ningún participante aparece a la vez en entrenamiento y
prueba. Los agentes (CUA) quedan con `fold = -1`.

### 5.6 Alternativa: etiquetas por LLM

`silver_labels.py` deja preparado el mismo etiquetado con Claude (con
validación contra los defectos de P3M confirmados por expertos), para quien
disponga de presupuesto de API. No se usó en el dataset definitivo.

## 6. Reproducibilidad

1. **Entradas**: el sha256 de cada archivo usado queda en `manifest.json`.
2. **Parámetros**: todos los umbrales están en `configs/indicators.yaml`, y su
   hash también queda en el manifiesto.
3. **Código**: se registra el commit y si había cambios sin commitear.
4. **Entorno**: versiones exactas en `requirements-dataset.txt` y en el manifiesto.
5. **Pruebas**: `tests/test_pipeline.py` verifica cada definición operacional
   con casos sintéticos de resultado conocido.

## Referencias

Ver `configs/crosswalk.yaml › references`. Antes de citar las fuentes de
datos, hay que completar en `configs/sources.yaml` las referencias marcadas
"completar".
