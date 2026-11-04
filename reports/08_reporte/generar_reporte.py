"""Genera reports/08_reporte/Reporte_modelos_y_backend.docx.

Todas las cifras se leen de los CSV producidos por el pipeline (etapas 4–7);
no hay números escritos a mano. Ejecutar desde la raíz del proyecto:
    entornoTesis/bin/python reports/08_reporte/generar_reporte.py
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import matplotlib
import pandas as pd
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
R = ROOT / "reports"
HERE = R / "08_reporte"
CAP = HERE / "capturas"
FIG = HERE / "figuras"
FIG.mkdir(exist_ok=True)
H = ["H1", "H4", "H5", "H6"]
HN = {"H1": "Visibilidad del estado del sistema", "H4": "Consistencia y estándares",
      "H5": "Prevención de errores", "H6": "Reconocer antes que recordar"}

# ----------------------------------------------------------------- datos
train = pd.read_parquet(ROOT / "data/processed/usab_v2/training/training_dataset.parquet")
spec = json.loads((ROOT / "data/processed/usab_v2/training/feature_spec.json").read_text())
part = pd.read_csv(R / "05_modelado/particion_70_30.csv")
s5 = pd.read_csv(R / "05_modelado/resultados_test_30.csv")
s5cv = pd.read_csv(R / "05_modelado/resultados_cv_entrenamiento.csv")
s6 = pd.read_csv(R / "06_modelo_multietiqueta/resultados_test_30_por_heuristica.csv")
s6g = pd.read_csv(R / "06_modelo_multietiqueta/resultados_test_30_global.csv").iloc[0]
s6cv = pd.read_csv(R / "06_modelo_multietiqueta/comparacion_cv_70.csv")
s7 = pd.read_csv(R / "07_red_neuronal_multitarea/resultados_test_30_por_heuristica.csv")
s7g = pd.read_csv(R / "07_red_neuronal_multitarea/resultados_test_30_global.csv").iloc[0]
s7r1 = pd.read_csv(R / "07_red_neuronal_multitarea/busqueda_ronda1_cv_70.csv")
s7r2 = pd.read_csv(R / "07_red_neuronal_multitarea/busqueda_ronda2_cv_70.csv")
rub = pd.read_csv(R / "04_etiquetas_rubrica/prevalencia_paginas.csv")
main = train[train.include_main]

f = lambda v, d=2: "—" if pd.isna(v) else f"{v:.{d}f}"  # noqa: E731


# ----------------------------------------------------------------- figuras
def fig_comparacion():
    w = s5[s5.seleccionado_por_cv == True].set_index("heuristica")  # noqa: E712
    d = pd.DataFrame({"Modelos individuales (mejor por heurística)": w.f1, "Random Forest multi-salida": s6.set_index("heuristica").f1,
                      "Red neuronal multitarea": s7.set_index("heuristica").f1}).loc[H]
    ax = d.plot.bar(figsize=(8, 3.4), color=["#9aa5b1", "#2b6cb0", "#dd6b20"], width=0.78, rot=0)
    ax.axhline(0.85, ls="--", lw=1, c="k"); ax.text(3.45, 0.86, "meta 0.85", ha="right", fontsize=8)
    ax.set_ylim(0, 1); ax.set_ylabel("F1 (30 % de prueba)"); ax.legend(fontsize=8, loc="upper left", frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    for c in ax.containers:
        ax.bar_label(c, fmt="%.2f", fontsize=7, padding=1)
    plt.tight_layout(); plt.savefig(FIG / "f1_comparacion.png", dpi=200); plt.close()


def fig_flujo():
    fig, ax = plt.subplots(figsize=(9, 1.9)); ax.axis("off")
    steps = ["Extensión web\n(eventos DOM)", "POST /sessions\n/events (lotes)", "Métricas de\ninteracción e ISO", "Random Forest\nmulti-salida",
             "H1 · H4 · H5 · H6\nprobabilidad + decisión"]
    for i, s in enumerate(steps):
        x = i * 2.05
        ax.add_patch(plt.Rectangle((x, 0.2), 1.75, 0.9, fc="#ebf4ff" if i not in (3,) else "#2b6cb0", ec="#2b6cb0", lw=1.2))
        ax.text(x + 0.875, 0.65, s, ha="center", va="center", fontsize=8.5, color="white" if i == 3 else "#1a202c")
        if i < len(steps) - 1:
            ax.annotate("", xy=(x + 2.03, 0.65), xytext=(x + 1.77, 0.65), arrowprops=dict(arrowstyle="->", lw=1.3))
    ax.set_xlim(-0.05, 10.0); ax.set_ylim(0, 1.3)
    plt.tight_layout(); plt.savefig(FIG / "flujo_backend.png", dpi=200); plt.close()


fig_comparacion(); fig_flujo()

# ----------------------------------------------------------------- documento
doc = Document()
sec = doc.sections[0]
sec.page_width, sec.page_height = Cm(21), Cm(29.7)
for m in ("left_margin", "right_margin"):
    setattr(sec, m, Cm(2.2))
sec.top_margin = sec.bottom_margin = Cm(2)
st = doc.styles["Normal"]; st.font.name = "Calibri"; st.font.size = Pt(10.5)
st.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
for name, size in (("Heading 1", 15), ("Heading 2", 12.5), ("Heading 3", 11)):
    doc.styles[name].font.size = Pt(size); doc.styles[name].font.color.rgb = RGBColor(0x1F, 0x3A, 0x68)

_fig, _tab = [0], [0]


def p(text, bold_prefix=None, size=None, italic=False, align=None, space_after=4):
    para = doc.add_paragraph()
    if bold_prefix:
        r = para.add_run(bold_prefix); r.bold = True
    r = para.add_run(text); r.italic = italic
    if size:
        r.font.size = Pt(size)
    if align:
        para.alignment = align
    para.paragraph_format.space_after = Pt(space_after)
    return para


def bullet(text, bold_prefix=None):
    para = doc.add_paragraph(style="List Bullet")
    if bold_prefix:
        para.add_run(bold_prefix).bold = True
    para.add_run(text)
    para.paragraph_format.space_after = Pt(2)


def caption(kind, text):
    if kind == "Tabla":
        _tab[0] += 1; n = _tab[0]
    else:
        _fig[0] += 1; n = _fig[0]
    c = p(f" {text}", bold_prefix=f"{kind} {n}.", size=9, align=WD_ALIGN_PARAGRAPH.CENTER if kind == "Figura" else None,
          space_after=8 if kind == "Figura" else 3)
    for r in c.runs[1:]:
        r.italic = True
    return n


def shade(cell, hex_):
    tcPr = cell._tc.get_or_add_tcPr(); shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear"); shd.set(qn("w:color"), "auto"); shd.set(qn("w:fill"), hex_); tcPr.append(shd)


def _tight(cell):
    pf = cell.paragraphs[0].paragraph_format
    pf.space_after = Pt(1); pf.space_before = Pt(1); pf.line_spacing = 1.0


def table(df: pd.DataFrame, title: str, widths=None, highlight_col=None, note=None, fsize=8.5):
    caption("Tabla", title)
    t = doc.add_table(rows=1, cols=len(df.columns)); t.style = "Table Grid"; t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, c in enumerate(df.columns):
        cell = t.rows[0].cells[i]; cell.text = ""; _tight(cell); run = cell.paragraphs[0].add_run(str(c)); run.bold = True
        run.font.size = Pt(fsize); run.font.color.rgb = RGBColor(255, 255, 255); shade(cell, "1F3A68")
    for _, row in df.iterrows():
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""; _tight(cells[i]); run = cells[i].paragraphs[0].add_run(str(v)); run.font.size = Pt(fsize)
            if highlight_col is not None and i == highlight_col:
                run.bold = True
            if isinstance(v, str) and v.endswith("✔"):
                shade(cells[i], "E6F4EA")
    if widths:
        for row in t.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Cm(w)
    if note:
        p(note, size=8, italic=True, space_after=8)
    else:
        doc.add_paragraph().paragraph_format.space_after = Pt(2)


def image(path, width_cm, text):
    doc.add_picture(str(path), width=Cm(width_cm)); doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    caption("Figura", text)


def metric_table(df):
    return pd.DataFrame({"Heurística": df.heuristica, "Precisión": df.precision.map(ok), "Sensibilidad": df.sensibilidad.map(ok),
                         "Especificidad": df.especificidad.map(ok), "F1": df.f1.map(ok), "MCC": df.mcc.map(ok),
                         "Kappa": df.kappa.map(ok), "ROC-AUC": df.roc_auc.map(ok), "PR-AUC": df.pr_auc.map(ok),
                         "IC 95 % F1": df.f1_ic95})


def ok(v):  # marca valores ≥ 0.85; si el redondeo a 2 decimales ocultaría que no llega (p. ej. 0.847), usa 3
    if pd.notna(v) and v >= 0.85:
        return f"{v:.2f} ✔"
    return f(v, 3) if pd.notna(v) and round(v, 2) >= 0.85 else f(v)



# ================================================================ portada
t = doc.add_paragraph(); t.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = t.add_run("Reporte técnico\nEntrenamiento de modelos y backend de evaluación heurística"); r.bold = True; r.font.size = Pt(18)
r.font.color.rgb = RGBColor(0x1F, 0x3A, 0x68)
p("Evaluación automática de las heurísticas de Nielsen H1, H4, H5 y H6 a partir de la interacción del usuario en el navegador",
  align=WD_ALIGN_PARAGRAPH.CENTER, italic=True)
p(f"Uriel Aguilar Mauricio · {date.today().strftime('%d/%m/%Y')}", align=WD_ALIGN_PARAGRAPH.CENTER, size=10, space_after=14)

# ================================================================ 1 resumen
doc.add_heading("1. Resumen", level=1)
w5 = s5[s5.seleccionado_por_cv == True].set_index("heuristica")  # noqa: E712
p(f"Se entrenaron y compararon tres enfoques para detectar violaciones de cuatro heurísticas de Nielsen a partir de la "
  f"interacción de usuarios con páginas web: (a) un modelo por heurística ({s5.modelo.nunique()} algoritmos de la tesis), "
  f"(b) un Random Forest multi-salida que evalúa las cuatro heurísticas a la vez y (c) una red neuronal multitarea "
  f"({len(s7r1) + len(s7r2)} configuraciones). Con una partición 70/30 por participante, el modelo con mejor desempeño fue el "
  f"Random Forest multi-salida (F1 macro {s6g.f1_macro:.2f}, MCC macro {s6g.mcc_macro:.2f}), que se integró en un backend "
  f"FastAPI preparado para recibir la telemetría de la extensión web.")
mejor = s6.set_index("heuristica")
for h in H:
    m_ = mejor.loc[h]
    bullet(f"F1 {ok(m_.f1)} · sensibilidad {ok(m_.sensibilidad)} · especificidad {ok(m_.especificidad)} · "
           f"ROC-AUC {ok(m_.roc_auc)}", bold_prefix=f"{h} ({HN[h]}): ")

# ================================================================ 2 dataset
doc.add_heading("2. Dataset de entrenamiento", level=1)
G = spec["feature_groups"]
p(f"El dataset único (training_dataset) proviene de Reduced-A11y-CUA, la única fuente pública que registra, en la misma "
  f"sesión, la interacción del usuario en el navegador y el HTML de las páginas visitadas, condición necesaria para tener "
  f"variables (X) y etiquetas (Y) en la misma fila. Cada fila es una tarea realizada por un participante.")
tr, te = part[part.particion == "train"], part[part.particion == "test"]
d = pd.DataFrame([
    ["Unidad de análisis", "participante × tarea (sesión de navegador)"],
    ["Sesiones (muestra principal: personas)", f"{len(main)} de {main.participant_id.nunique()} participantes "
                                               f"({(main.user_group == 'BLV').sum()} sesiones de usuarios ciegos/baja visión, "
                                               f"{(main.user_group == 'sighted').sum()} de videntes)"],
    ["Variables X", f"{len(spec['feature_columns'])}: {len(G['behavior'])} de interacción, "
                    f"{len(G['iso_process']) + len(G['iso_outcome'])} medidas ISO/IEC 25022, {len(G['context'])} de contexto"],
    ["Variables Y", "y_H1, y_H4, y_H5, y_H6 (violación 0/1; NA = no evaluable)"],
    ["Excluidas de X", f"{len(spec['excluded_from_X_leakage'])} rasgos del HTML (dom_*): Y se obtiene del mismo HTML"],
    ["Partición entrenamiento", f"{len(tr)} sesiones · {tr.participant_id.nunique()} participantes ({len(tr) / len(part):.0%})"],
    ["Partición prueba", f"{len(te)} sesiones · {te.participant_id.nunique()} participantes ({len(te) / len(part):.0%})"],
], columns=["Característica", "Valor"])
table(d, "Características del dataset de entrenamiento.", widths=[5, 11.5])

p("Variables X (ejemplos): ", bold_prefix=None, space_after=2)
bullet("clics/min, teclas/min, scroll/min, distancia del cursor, clics repetidos, latencia tras clic, clics sobre elementos "
       "no interactivos, navegación hacia atrás, teclas de corrección, re-edición de campos, pausas largas, reversiones de "
       "scroll, revisitas de página, cambios de foco.", bold_prefix="Interacción: ")
bullet("tiempo de tarea, número de acciones, éxito de la tarea, eficiencia basada en tiempo, facilidad percibida.",
       bold_prefix="ISO/IEC 25022: ")
bullet("grupo de usuario, tecnología de apoyo, tipo de tarea, familiaridad y dificultad esperada.", bold_prefix="Contexto: ")

p("Las violaciones se obtuvieron por inspección del HTML de cada página con una rúbrica de 16 criterios: "
  "cada criterio operacionaliza una pregunta guía de Nielsen y se ancla en un criterio de WCAG 2.2; la severidad sigue la "
  "escala 0–4 de Nielsen (impacto × frecuencia) y se considera violación una severidad ≥ 2. La rúbrica es determinista "
  "(misma página → misma etiqueta) y fue auditada antes de fijar las etiquetas.", bold_prefix="Etiquetado (Y). ", space_after=6)
prev = pd.DataFrame({"Heurística": [f"{h} · {HN[h]}" for h in H],
                     "Sesiones etiquetadas": [int(main[f"y_{h}"].notna().sum()) for h in H],
                     "Prevalencia de violación": [f"{main[f'y_{h}'].astype('Float64').mean():.0%}" for h in H]})
table(prev, "Variables objetivo en la muestra principal.", widths=[8, 4, 4.5],
      note="H5 solo es evaluable en sesiones con páginas que contienen formularios.")

# ================================================================ 3 metodología
doc.add_heading("3. Protocolo de entrenamiento y evaluación", level=1)
for txt, b in [
    ("70 % entrenamiento / 30 % prueba, dividido por participante (ninguna persona aparece en ambos conjuntos) y "
     "estratificado por grupo de usuario.", "Partición: "),
    ("hiperparámetros, conjunto de variables y umbral de decisión se eligieron solo con validación cruzada agrupada "
     "por participante (4 folds) dentro del 70 %.", "Selección: "),
    ("el 30 % se evaluó una única vez con el modelo elegido por la validación cruzada.", "Evaluación: "),
    ("precisión, sensibilidad, especificidad, F1, MCC, Kappa de Cohen, ROC-AUC y PR-AUC; IC 95 % por bootstrap de "
     "participantes y prueba de McNemar frente a una línea base trivial.", "Métricas: "),
    ("pesos por clase y SMOTE dentro de cada fold (aprendizaje sensible al costo).", "Desbalance: "),
]:
    bullet(txt, bold_prefix=b)

# ================================================================ 4 resultados
doc.add_heading("4. Resultados", level=1)
doc.add_heading("4.1 Modelos individuales (un modelo por heurística)", level=2)
p("Se compararon los algoritmos propuestos en la tesis: Regresión Logística, KNN, Naive Bayes, Árbol de Decisión, Random "
  "Forest, Bagging, Extra Trees, SVM sensible al costo y Red Neuronal (MLP), más Gradient Boosting como contraste y un "
  "clasificador trivial como línea base.")
models = [m for m in s5.modelo.unique()]
piv = s5.pivot(index="modelo", columns="heuristica", values="f1").loc[models, H]
pm = s5.pivot(index="modelo", columns="heuristica", values="mcc").loc[models, H]
comb = pd.DataFrame({"Modelo": piv.index})
for h in H:
    comb[f"{h} F1"] = [f(v) for v in piv[h]]
    comb[f"{h} MCC"] = [f(v) for v in pm[h]]
for h in H:
    win = w5.loc[h, "modelo"]
    comb.loc[comb.Modelo == win, f"{h} F1"] = comb.loc[comb.Modelo == win, f"{h} F1"] + " ●"
table(comb, "F1 y MCC de cada modelo en el 30 % de prueba (● = modelo elegido por validación cruzada).", fsize=7.5,
      widths=[4.2] + [1.55] * 8)
table(metric_table(w5.reset_index()), "Métricas completas del modelo elegido para cada heurística (30 % de prueba).",
      fsize=7.5, note="✔ = valor ≥ 0.85. " + " · ".join(f"{h}: {w5.loc[h, 'modelo']}" for h in H))

doc.add_heading("4.2 Random Forest multi-salida (un modelo para las 4 heurísticas)", level=2)
top = s6cv.iloc[0]
p(f"Se compararon {len(s6cv)} combinaciones (estrategia multi-etiqueta × algoritmo × conjunto de variables). La validación "
  f"cruzada eligió un Random Forest con salida conjunta ({top.estrategia}) y normalización intra-participante (percentil de "
  f"cada variable dentro de las sesiones del mismo usuario). H5 se aprende solo con las sesiones donde es evaluable.")
table(metric_table(s6), "Random Forest multi-salida: resultados en el 30 % de prueba.", fsize=7.5,
      note=f"Métricas globales: F1 macro {s6g.f1_macro:.2f} · MCC macro {s6g.mcc_macro:.2f} · Hamming loss "
           f"{s6g.hamming_loss_H1H4H6:.2f} · coincidencia exacta H1/H4/H6 {s6g.exact_match_H1H4H6:.0%}. ✔ = valor ≥ 0.85.")
cvt = s6cv.head(5)[["estrategia", "estimador", "variables", "cv_mcc_macro", "cv_f1_macro"]].copy()
cvt.columns = ["Estrategia", "Algoritmo", "Variables", "MCC macro (CV)", "F1 macro (CV)"]
cvt["MCC macro (CV)"] = cvt["MCC macro (CV)"].map(f); cvt["F1 macro (CV)"] = cvt["F1 macro (CV)"].map(f)
table(cvt, "Cinco mejores configuraciones multi-etiqueta en validación cruzada (70 %).", fsize=8)

doc.add_heading("4.3 Red neuronal multitarea", level=2)
cfg = {k: s7g[k] for k in ("hidden", "dropout", "weight_decay", "lr", "act", "head_hidden", "batch", "n_seeds")}
p(f"Red con tronco compartido y cuatro salidas, pérdida BCE enmascarada (ignora H5 cuando no es evaluable) y ponderada por "
  f"clase, parada temprana y ensamble de semillas. Se exploraron {len(s7r1)} configuraciones en una primera ronda y "
  f"{len(s7r2)} en una segunda centrada en la región más prometedora. Configuración elegida: capas {cfg['hidden']}, "
  f"activación {cfg['act'].upper()}, dropout {cfg['dropout']}, weight decay {cfg['weight_decay']}, tasa de aprendizaje "
  f"{cfg['lr']}, ensamble de {cfg['n_seeds']} redes.")
table(metric_table(s7), "Red neuronal multitarea: resultados en el 30 % de prueba.", fsize=7.5,
      note=f"Métricas globales: F1 macro {s7g.f1_macro:.2f} · MCC macro {s7g.mcc_macro:.2f} · Hamming loss "
           f"{s7g.hamming_loss_H1H4H6:.2f}. ✔ = valor ≥ 0.85.")

doc.add_heading("4.4 Comparación y modelo seleccionado", level=2)
cmp = pd.DataFrame({
    "Enfoque": ["Modelos individuales (mejor por heurística)", "Random Forest multi-salida", "Red neuronal multitarea"],
    "F1 macro": [f(w5.f1.mean()), f(s6g.f1_macro), f(s7g.f1_macro)],
    "MCC macro": [f(w5.mcc.mean()), f(s6g.mcc_macro), f(s7g.mcc_macro)],
    "ROC-AUC medio": [f(w5.roc_auc.mean()), f(s6.roc_auc.mean()), f(s7.roc_auc.mean())],
    "Modelos a mantener": ["4", "1", "1"]})
table(cmp, "Comparación de enfoques en el 30 % de prueba.", highlight_col=None, fsize=8.5, widths=[6.5, 2.4, 2.4, 2.6, 2.6])
image(FIG / "f1_comparacion.png", 15.5, "F1 por heurística de los tres enfoques en el 30 % de prueba.")
p("Se selecciona el Random Forest multi-salida: obtiene el mejor F1 y MCC macro, es un solo modelo para las cuatro "
  "heurísticas y ofrece importancia de variables, como se anticipó en el marco teórico. La red neuronal no lo supera con este "
  "tamaño de muestra, resultado consistente con la literatura sobre datos tabulares pequeños.")

# ================================================================ 5 backend
doc.add_heading("5. Desarrollo del backend", level=1)
p("El backend (FastAPI + SQLAlchemy/SQLite) recibe la telemetría de la extensión, calcula las métricas con el mismo código "
  "usado en el entrenamiento y aplica el Random Forest multi-salida.")
image(FIG / "flujo_backend.png", 16, "Flujo de datos de la extensión al resultado de la evaluación.")
ep = pd.DataFrame([
    ["GET", "/health · /model · /model/schema", "Estado, modelo cargado y contrato de datos"],
    ["POST / GET / PUT / DELETE", "/participants[/{id}]", "Alta, consulta, actualización y baja de participantes"],
    ["POST / GET / PUT / DELETE", "/sessions[/{id}]", "Inicio, consulta, cierre (éxito, dificultad) y baja de sesiones"],
    ["POST / GET / DELETE", "/sessions/{id}/events", "Recepción de eventos por lotes desde la extensión"],
    ["POST", "/sessions/{id}/evaluate", "Evalúa H1, H4, H5 y H6"],
    ["GET / PUT / DELETE", "/sessions/{id}/evaluation", "Consultar, recalcular o borrar la evaluación"],
    ["GET", "/participants/{id}/evaluations", "Historial de evaluaciones del participante"],
    ["POST", "/predict", "Evaluación en una sola llamada, sin almacenar datos"],
], columns=["Método", "Ruta (prefijo /api/v1)", "Función"])
table(ep, "Endpoints del backend.", widths=[3.6, 5.6, 7.3], fsize=8)
for txt, b in [
    ("las teclas imprimibles se almacenan como 'char'; solo se conservan teclas funcionales (Backspace, Enter…). "
     "La extensión no envía valores de campos.", "Privacidad: "),
    ("validación de tipos con Pydantic (422), recursos inexistentes (404), duplicados (409) y lotes de hasta 5000 eventos.",
     "Validación: "),
    ("CORS para extensiones de Chrome, Firefox y Edge; autenticación opcional por encabezado X-API-Key.", "Integración: "),
    ("advierte cuando la sesión es corta, faltan datos de resultado o la categoría de tarea no existía en el entrenamiento.",
     "Advertencias: "),
]:
    bullet(txt, bold_prefix=b)

doc.add_heading("5.1 Evidencias de funcionamiento", level=2)
p("Las siguientes capturas corresponden al servidor ejecutándose en local (http://127.0.0.1:8000). Para las evaluaciones "
  "se reenviaron por la API las sesiones reales de un participante del conjunto de prueba (BLVU3), con sus eventos "
  "originales, siguiendo el mismo flujo que usará la extensión.", space_after=6)
for fname, w, txt in [
    ("01_swagger_docs.png", 15.5, "Documentación interactiva generada por FastAPI (Swagger UI, /docs) con todos los endpoints."),
    ("08_servidor.png", 16, "Registro del servidor Uvicorn con las solicitudes atendidas y sus códigos de estado."),
    ("02_health_modelo.png", 14, "GET /health y GET /model: estado del servicio, umbrales y métricas del modelo cargado."),
    ("03_eventos_privacidad.png", 12, "Alta de participante y sesión, envío de un lote de eventos y almacenamiento de teclas como 'char'."),
    ("04_evaluacion.png", 13, "Cierre de una sesión real (PUT) y evaluación de H1, H4, H5 y H6 (POST /evaluate)."),
    ("05_historial.png", 13, "Historial de evaluaciones de un participante (6 sesiones reales)."),
    ("06_validacion_errores.png", 13, "Validación de entrada y manejo de errores (422, 404, 409)."),
    ("07_pruebas.png", 16, "Pruebas automatizadas del pipeline y del backend (pytest)."),
]:
    image(CAP / fname, w, txt)

# ================================================================ 6 limitaciones
doc.add_heading("6. Limitaciones y siguientes pasos", level=1)
for txt in [
    f"El entrenamiento usa {tr.participant_id.nunique()} participantes; los intervalos de confianza son amplios. La principal "
    "mejora esperada vendrá de recolectar más sesiones con la extensión.",
    "Las etiquetas provienen de una rúbrica de inspección (Nielsen + WCAG 2.2), no de una evaluación experta completa; se "
    "recomienda validar una muestra con evaluadores humanos (κ de Cohen).",
    "H5 tiene pocas sesiones evaluables; sus métricas son las menos estables.",
    "Las categorías de tarea del entrenamiento no son educativas; al reunir datos de la extensión en plataformas educativas "
    "debe reentrenarse el modelo (el backend ya advierte las categorías desconocidas).",
    "Siguiente paso: desarrollar la extensión web conforme al contrato de eventos documentado en backend/README.md.",
]:
    bullet(txt)

doc.add_heading("Anexo · Reproducibilidad", level=2)
for c in ["PYTHONPATH=src python -m usab_ds all       # dataset + etiquetas", "PYTHONPATH=src python -m usab_ds stage5    # modelos individuales",
          "PYTHONPATH=src python -m usab_ds stage6    # Random Forest multi-salida", "PYTHONPATH=src python -m usab_ds stage7    # red neuronal",
          "uvicorn backend.app.main:app --port 8000   # backend local"]:
    para = doc.add_paragraph(); r = para.add_run(c); r.font.name = "Consolas"; r.font.size = Pt(8.5)
    para.paragraph_format.space_after = Pt(0)

out = HERE / "Reporte_modelos_y_backend.docx"
doc.save(out)
print(out, f"tablas={_tab[0]} figuras={_fig[0]}")
