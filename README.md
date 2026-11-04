# Dataset de usabilidad web · Nielsen (H1, H4, H5, H6) × ISO/IEC 25010/25022

Pipeline reproducible que construye, a partir de 12 fuentes públicas, un
dataset de usabilidad web en **dos niveles enlazados**:

| Nivel | Unidad | Qué contiene |
|---|---|---|
| **1 · Sesiones** (`sessions`) | sesión de navegador (participante × tarea o visita) | contexto de uso, medidas ISO/IEC 25022 (efectividad, eficiencia, satisfacción), indicadores conductuales (clics, scroll, teclado, foco, navegación) ligados a H1/H4/H5/H6, índices proxy y rasgos DOM de las páginas vistas |
| **2 · Evaluaciones** (`heuristic_evaluations`, `interface_labels`) | interfaz × evaluador × heurística | juicios explícitos de violación Nielsen con severidad 0–4 (LLM, LLM validado por expertos) |
| **Puente** (`pages_static`) | página HTML | los mismos rasgos DOM (anclados en WCAG 2.2) calculados en ambos niveles |

Ninguna fuente pública tiene a la vez interacciones de navegador y etiquetas
Nielsen sobre la misma sesión; por eso los niveles **no se unen fila a fila**.
Los une un espacio común de rasgos DOM y un marco de correspondencia explícito
(`configs/crosswalk.yaml`). La justificación completa está en
[`docs/metodologia.md`](docs/metodologia.md).

## Cómo reproducirlo

```bash
python3.13 -m venv entornoTesis && source entornoTesis/bin/activate
pip install -r requirements-dataset.txt   # versiones exactas usadas por el pipeline
# colocar los datos crudos en las rutas de configs/sources.yaml
PYTHONPATH=src python -m usab_ds all      # etapas 1 → 2 → 3 (~5 min)
PYTHONPATH=src python -m pytest           # pruebas de las definiciones
```

Cada ejecución escribe `data/processed/usab_v2/manifest.json` con el sha256 de
cada archivo de entrada y salida, las versiones de los paquetes, los
parámetros y el commit de git. Dos ejecuciones con las mismas entradas y el
mismo commit producen las mismas tablas.

## Etapas

| Etapa | Comando | Salida | Pregunta que responde |
|---|---|---|---|
| 1 | `stage1` | `reports/01_perfil_fuentes/` | ¿Qué características tiene cada dataset? |
| 2 | `stage2` | `reports/02_relevancia/` | ¿Qué fuentes se relacionan con H1/H4/H5/H6 y con las medidas ISO, y con qué evidencia? |
| 3 | `stage3` | `data/processed/usab_v2/`, `reports/03_dataset/` | El dataset final, su diccionario y su manifiesto |
| 3b | `stage3b` | `data/processed/usab_v2/rubric_*.parquet`, `reports/04_etiquetas_rubrica/` | Etiquetas H1/H4/H5/H6 por inspección con rúbrica (Nielsen + WCAG 2.2), con auditoría y validación |
| (opcional) | `silver-prepare` → `silver-count` → `silver-submit --yes` → `silver-collect` | `reports/04_etiquetas_silver/` | Alternativa: el mismo etiquetado con Claude por API (con costo) |
| 4 | `stage4` | `data/processed/usab_v2/training/` | **El dataset único listo para entrenar** (X e Y en la misma fila, folds por participante) |

## Estructura

```text
configs/
  sources.yaml             registro de las 12 fuentes (ruta, cita, licencia, unidad)
  crosswalk.yaml           Nielsen ↔ ISO/IEC 25010 (2011/2023) ↔ ISO/IEC 25022 ↔ WCAG, con referencias
  indicators.yaml          definición y umbrales de cada indicador conductual
  inclusion_criteria.yaml  criterios C1–C6 de elegibilidad de fuentes
src/usab_ds/
  profiling.py             etapa 1
  relevance.py             etapa 2
  build.py                 etapa 3
  events.py                esquema canónico de eventos (común a todas las fuentes)
  metrics.py               medidas ISO e indicadores (una sola implementación)
  dom_static.py            rasgos DOM anclados en WCAG 2.2
  report.py                informes Markdown generados desde los CSV
  adapters/                un adaptador por fuente, con sus reglas de transformación documentadas
notebooks/                 notebooks de consulta (no contienen lógica)
reports/                   salidas de las etapas 1–3
tests/                     pruebas de las definiciones operacionales
archive/v1/                trabajo de la versión anterior (solo consulta)
```

`data/` no se versiona (ver `.gitignore`); la versión anterior de los datos
derivados quedó en `data/_archive_v1/`.
