# Proyecto de tesis · evaluación heurística automática (Nielsen H1/H4/H5/H6)

## Estado (no re-explorar: ya está construido)
- Pipeline en `src/usab_ds` (CLI: `PYTHONPATH=src entornoTesis/bin/python -m usab_ds <etapa>`):
  stage1 perfil · stage2 elegibilidad · stage3 dataset · stage3b etiquetas por rúbrica · stage4 dataset de entrenamiento ·
  stage5 modelos individuales · stage6 Random Forest multi-salida (MODELO ELEGIDO) · stage7 red neuronal.
- Dataset de entrenamiento: `data/processed/usab_v2/training/` (+ `feature_spec.json`). 308 sesiones humanas, 16 participantes.
- Modelo en producción: `models/modelo_multietiqueta_H1_H4_H5_H6.joblib`.
- Backend: `backend/` (FastAPI). Arrancar: `entornoTesis/bin/uvicorn backend.app.main:app --port 8000`. Contrato: `backend/README.md`.
- Resultados resumidos: `reports/0X_*/README.md`. Reporte técnico: `reports/08_reporte/`.
- Metodología: `docs/metodologia.md`. Configs: `configs/*.yaml`.
- `archive/v1/` es trabajo viejo: no leer salvo petición explícita.

## Reglas para ahorrar tokens
- NO listar ni leer `data/` completo (21 GB). Para datos usa pandas con `head`, `shape`, `describe` y salidas cortas.
- Leer los README de `reports/` antes que los CSV; leer CSV solo con columnas/filas necesarias.
- Pruebas: `entornoTesis/bin/python -m pytest -q` (sin `-v`); mostrar solo el resumen o los fallos.
- Comandos largos: redirigir a un log y mostrar `tail`.
- No abrir imágenes ni PDF salvo que sea imprescindible.
- No re-ejecutar etapas costosas (stage5–7, ~2–8 min) si no cambió el código o los datos.
- Respuestas al usuario: en español, concisas, con tablas cuando haya métricas.

## Restricciones metodológicas (no romper)
- Partición 70/30 por participante (`reports/05_modelado/particion_70_30.csv`); decisiones solo con CV del 70 %.
- Las columnas `dom_*` no van en X (Y sale del mismo HTML).
- `tesis.pdf` no se sube al repositorio (público).
