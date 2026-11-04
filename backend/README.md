# Backend · API de evaluación heurística (FastAPI)

Recibe la telemetría de la extensión web, calcula las métricas de interacción
y las medidas ISO/IEC 25022 con **el mismo código usado para entrenar**
(`src/usab_ds/metrics.py`), y evalúa H1, H4, H5 y H6 con el **Random Forest
multi-salida** (`models/modelo_multietiqueta_H1_H4_H5_H6.joblib`).

## Ejecutar en local

```bash
cd /Users/uriel/Documents/machine_learning
entornoTesis/bin/pip install -r backend/requirements.txt        # una sola vez
entornoTesis/bin/uvicorn backend.app.main:app --reload --port 8000
```

- API: `http://127.0.0.1:8000/api/v1`
- Documentación interactiva (probar endpoints desde el navegador): `http://127.0.0.1:8000/docs`
- Base de datos: `backend/data/usab.db` (SQLite; se crea sola, no se versiona)
- Pruebas: `PYTHONPATH=. entornoTesis/bin/python -m pytest backend/tests`

Variables de entorno opcionales:

| Variable | Uso | Por defecto |
|---|---|---|
| `USAB_API_KEY` | si se define, toda llamada debe enviar el encabezado `X-API-Key` | sin autenticación (local) |
| `USAB_DATABASE_URL` | p. ej. `postgresql+psycopg://…` | SQLite local |
| `USAB_MODEL_PATH` | otro modelo `.joblib` | RF multi-salida |
| `USAB_CORS_ORIGIN_REGEX` | orígenes permitidos | `chrome-extension://*`, `moz-extension://*`, `localhost` |

## Flujo esperado de la extensión

```text
1. POST   /participants                    (una vez por usuario; id = seudónimo)
2. POST   /sessions                        (al iniciar una tarea)
3. POST   /sessions/{id}/events            (cada 5–10 s, lotes de eventos)
4. PUT    /sessions/{id}                   (al terminar: ended_at_ms, success, difficulty_after)
5. POST   /sessions/{id}/evaluate          → probabilidad y decisión para H1, H4, H5, H6
```

## Endpoints

Prefijo de todos: `/api/v1` (excepto `/health`).

### Sistema y modelo

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/health` | Estado del servicio y versión del modelo |
| GET | `/model` | Heurísticas, umbrales, variables y métricas de prueba del modelo |
| GET | `/model/schema` | Tipos de evento aceptados y categorías conocidas (`task_group`, `familiarity`…) |

### Participantes

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/participants` | Crea un participante (`id`, `user_group`, `assistive_tech`) · 409 si ya existe |
| GET | `/participants` | Lista (`limit`, `offset`) |
| GET | `/participants/{id}` | Detalle, con número de sesiones |
| PUT | `/participants/{id}` | Actualiza grupo, tecnología de apoyo o notas |
| DELETE | `/participants/{id}` | Borra el participante **y todas** sus sesiones, eventos y evaluaciones |
| GET | `/participants/{id}/evaluations` | Todas las evaluaciones del participante |

### Sesiones (una tarea de un participante)

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/sessions` | Crea la sesión (`participant_id`, `started_at_ms`, contexto de la tarea) |
| GET | `/sessions` | Lista; filtros `participant_id`, `status` (open, closed, evaluated) |
| GET | `/sessions/{id}` | Detalle, con número de eventos |
| PUT | `/sessions/{id}` | Actualiza o cierra: `ended_at_ms`, `success`, `difficulty_after`… |
| DELETE | `/sessions/{id}` | Borra la sesión con sus eventos y evaluación |

### Eventos

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/sessions/{id}/events` | Agrega un lote `{"events": [...]}` (máx. 5000) · 409 si ya fue evaluada |
| GET | `/sessions/{id}/events` | Lista; filtro `type`, `limit`, `offset` |
| DELETE | `/sessions/{id}/events` | Borra los eventos (y la evaluación, que dejaría de ser válida) |

### Evaluación

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/sessions/{id}/evaluate` | Calcula métricas y evalúa H1/H4/H5/H6; `?include_features=true` devuelve el vector |
| GET | `/sessions/{id}/evaluation` | Última evaluación guardada |
| PUT | `/sessions/{id}/evaluation` | Recalcula (p. ej. tras actualizar `success`) |
| DELETE | `/sessions/{id}/evaluation` | Borra la evaluación (permite volver a agregar eventos) |
| POST | `/predict` | Evaluación **sin guardar nada**: contexto + eventos en una sola llamada |

## Formato de un evento

```json
{"type": "click", "ts": 1760000002000, "url": "https://campus.edu/curso",
 "x": 312, "y": 540, "target_tag": "button", "target_id": "#enviar", "target_role": null}
```

| `type` | Cuándo enviarlo (listener en la extensión) | Campos útiles |
|---|---|---|
| `page_view` | carga de página o cambio de URL (`load`, `popstate`, `pushState`) | `url` |
| `click` / `dblclick` | `click` / `dblclick` | `x`, `y`, `target_*` |
| `key` | `keydown` | `key` (`event.key`) |
| `scroll` | `wheel` | — |
| `scroll_pos` | `scroll` (con *throttle* de ~200 ms) | `scroll_y` (`window.scrollY`), `url` |
| `input` | `input` / `change` (**sin** el valor) | `target_id`, `target_tag` |
| `focus` / `blur` | `focusin` / `focusout` | `target_*` |
| `nav_back` | `popstate` hacia atrás, botón Atrás | — |
| `mouse_move` | `mousemove` (con *throttle* de ~100 ms) | `x`, `y` |
| `hover` | `mouseover` sobre elementos interactivos | `target_*` |

**Privacidad:** el backend nunca guarda texto escrito. Toda tecla imprimible
se almacena como `char`; solo se conservan teclas funcionales (Backspace,
Delete, Enter, Tab, flechas…) porque son las que usa el modelo. La extensión
tampoco debe enviar valores de campos.

## Ejemplo con curl

```bash
A=http://127.0.0.1:8000/api/v1
curl -X POST $A/participants -H 'Content-Type: application/json' \
     -d '{"id":"p-001","user_group":"sighted","assistive_tech":"none"}'
curl -X POST $A/sessions -H 'Content-Type: application/json' \
     -d '{"id":"s-001","participant_id":"p-001","task_group":"Browsing and Web","started_at_ms":1760000000000}'
curl -X POST $A/sessions/s-001/events -H 'Content-Type: application/json' \
     -d '{"events":[{"type":"page_view","ts":1760000000000,"url":"https://campus.edu"},
                    {"type":"click","ts":1760000002000,"x":10,"y":20,"target_tag":"a","target_id":"#menu"}]}'
curl -X PUT  $A/sessions/s-001 -H 'Content-Type: application/json' \
     -d '{"ended_at_ms":1760000030000,"success":true,"difficulty_after":"Easy"}'
curl -X POST $A/sessions/s-001/evaluate
```

Respuesta de `/evaluate`:

```json
{"session_id": "s-001", "model_version": "modelo_multietiqueta_H1_H4_H5_H6", "n_events": 8, "history_sessions": 0,
 "results": [
   {"heuristic": "H1", "name": "Visibilidad del estado del sistema", "probability": 0.53, "threshold": 0.48, "violation": true},
   {"heuristic": "H4", "name": "Consistencia y estándares",          "probability": 0.36, "threshold": 0.40, "violation": false},
   {"heuristic": "H5", "name": "Prevención de errores",              "probability": 0.62, "threshold": 0.34, "violation": true},
   {"heuristic": "H6", "name": "Reconocer antes que recordar",       "probability": 0.37, "threshold": 0.46, "violation": false}],
 "warnings": ["El participante tiene 0 sesiones previas evaluadas; …"]}
```

## Ejemplo desde la extensión (JavaScript)

```js
const API = "http://127.0.0.1:8000/api/v1";
let buffer = [];
const push = (e) => buffer.push({ ts: Date.now(), url: location.href, ...e });

document.addEventListener("click", (ev) => push({
  type: "click", x: ev.clientX, y: ev.clientY,
  target_tag: ev.target.tagName.toLowerCase(), target_id: ev.target.id ? `#${ev.target.id}` : null,
  target_role: ev.target.getAttribute("role") }), true);
document.addEventListener("keydown", (ev) => push({ type: "key", key: ev.key }), true);

setInterval(async () => {                       // envío por lotes
  if (!buffer.length) return;
  const events = buffer.splice(0);
  await fetch(`${API}/sessions/${sessionId}/events`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ events }) });
}, 5000);
```

## Advertencias que puede devolver `/evaluate`

- **Categorías nuevas:** un `task_group` que no estaba en el entrenamiento (p. ej. tareas educativas) se
  codifica como desconocido. Hay que reentrenar con datos de la extensión.
- **Sesiones cortas:** menos de 5 s o menos de 3 eventos.
- **Pocas sesiones previas:** con menos de 5 sesiones evaluadas del mismo participante, la normalización
  intra-participante es menos fiable.
- **Sin `success` o `difficulty_after`:** se imputan con la mediana del entrenamiento.
