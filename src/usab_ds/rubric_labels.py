"""Etapa 3b · Etiquetas H1/H4/H5/H6 por inspección con rúbrica (configs/rubric.yaml).

Para cada página HTML aplica los 16 criterios de la rúbrica y produce:
  * por criterio: elegibles, afectados, proporción, severidad 0–4 y evidencia
  * por heurística: evaluable, severidad máxima, violación (severidad ≥ 2)

Se aplica igual a los snapshots de A11y-CUA (Y del dataset de entrenamiento)
y al HTML de Catching UX Flaws (validación contra sus etiquetas GPT-4o).
No usa la API ni ningún dato de comportamiento: Y depende solo del HTML.
"""

from __future__ import annotations

import re
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd
from lxml import etree
from lxml import html as lhtml

from . import config
from .adapters import a11y_cua, catching

CODES = config.TARGET_HEURISTICS
NATIVE_INTERACTIVE = {"a", "button", "input", "select", "textarea", "summary", "option", "label", "details", "area"}
INTERACTIVE_ROLES = {"button", "link", "checkbox", "radio", "tab", "menuitem", "menuitemcheckbox", "menuitemradio",
                     "option", "combobox", "textbox", "searchbox", "switch", "slider", "spinbutton", "treeitem",
                     "gridcell", "listbox", "menu", "menubar", "tablist", "tree", "grid", "dialog", "scrollbar"}
NON_TEXT_INPUTS = {"hidden", "submit", "button", "reset", "image"}
PURPOSE_TYPED = {  # patrón en nombre/id/placeholder/etiqueta → type esperado
    "email": re.compile(r"e-?mail|correo", re.I),
    "tel": re.compile(r"phone|tel[eé]fono|\btel\b|mobile|celular|m[oó]vil", re.I),
    "url": re.compile(r"\burl\b|website|sitio web|homepage", re.I),
    "number": re.compile(r"\b(qty|quantity|cantidad|amount|age|edad|zip|postal|cp)\b", re.I),
    "date": re.compile(r"\b(date|fecha|birth|nacimiento|dob)\b", re.I),
}
# Términos completos (\b) para no atrapar ids como "vector-user-links-dropdown" (corrección A2 de la auditoría)
PERSONAL = re.compile(r"\b((first|last|full|given|family)[-_ ]?name|name|nombre|apellidos?|e-?mail|correo|phone|"
                      r"tel[eé]fono|address|direcci[oó]n|postal|zip(code)?|city|ciudad|country|pa[ií]s|user[-_ ]?name|"
                      r"userid|login|usuario|password|contrase[ñn]a|card[-_ ]?number|tarjeta|cc-[a-z]+)\b", re.I)
TEXT_LIKE = {"", "text", "email", "tel", "url", "password", "number", "search", "date"}
INPUTMODE_OK = {"email": {"email"}, "tel": {"tel"}, "url": {"url"}, "number": {"numeric", "decimal"}, "date": set()}
FOCUS_ONLY_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6", "main", "section", "article", "header", "footer", "nav",
                   "aside", "form", "body", "html", "dialog", "table", "ul", "ol"}
SEARCHY = re.compile(r"search|buscar|búsqueda|^q$", re.I)


def _rcfg() -> dict:
    return config.load("rubric")


def _hidden(el) -> bool:
    for a in [el, *el.iterancestors()]:
        if a.get("aria-hidden") == "true" or a.get("hidden") is not None:
            return True
        st = (a.get("style") or "").replace(" ", "").lower()
        if "display:none" in st or "visibility:hidden" in st:
            return True
    return False


def _snip(el) -> str:
    s = etree.tostring(el, encoding="unicode", method="html", with_tail=False)
    return re.sub(r"\s+", " ", s)[:160]


def _acc_name(el, by_id: dict) -> str:
    """Nombre accesible simplificado (HTML-AAM): aria-labelledby > aria-label > texto/alt > title."""
    ids = (el.get("aria-labelledby") or "").split()
    if ids:
        t = " ".join(by_id[i].text_content() for i in ids if i in by_id).strip()
        if t:
            return t
    if (el.get("aria-label") or "").strip():
        return el.get("aria-label").strip()
    t = " ".join(el.text_content().split())
    if t:
        return t
    for img in el.xpath(".//img[@alt]|.//*[@aria-label]"):
        v = (img.get("alt") or img.get("aria-label") or "").strip()
        if v:
            return v
    if el.tag == "input" and (el.get("value") or "").strip():
        return el.get("value").strip()
    return (el.get("title") or "").strip()


def _descriptor(el, labels_for: dict) -> str:
    lab = labels_for.get(el.get("id") or "", "")
    return " ".join(filter(None, [el.get("name"), el.get("id"), el.get("placeholder"), el.get("aria-label"),
                                  el.get("autocomplete"), lab]))


def evaluate_html(text: str) -> list[dict]:
    """Aplica la rúbrica. Devuelve una fila por criterio."""
    rc = _rcfg()
    th = rc["thresholds"]
    try:
        doc = lhtml.fromstring(text)
    except Exception:
        return []
    for bad in doc.xpath("//script|//style|//noscript|//template"):
        bad.drop_tree()
    by_id = {e.get("id"): e for e in doc.xpath("//*[@id]")}
    labels_for = {lab.get("for"): " ".join(lab.text_content().split()) for lab in doc.xpath("//label[@for]")}
    inputs = [i for i in doc.xpath("//input|//select|//textarea")
              if (i.get("type") or "").lower() not in NON_TEXT_INPUTS and not _hidden(i)]
    links = [a for a in doc.xpath("//a") if not _hidden(a)]
    href_links = [a for a in links if a.get("href")]
    buttons = [b for b in doc.xpath("//button|//input[@type='button' or @type='submit' or @type='reset' or @type='image']"
                                    "|//*[@role='button']") if not _hidden(b)]
    out: list[dict] = []

    def add(cid, eligible, affected, evidence):
        out.append(dict(check=cid, eligible=eligible, affected=affected, evidence=[_snip(e) for e in evidence[:2]]))

    # ---------------- H1
    title = doc.xpath("//title")
    add("H1_page_title", 1, int(not title or not title[0].text_content().strip()), title[:1] or [doc])
    status = doc.xpath("//*[@aria-live or @role='status' or @role='alert' or @role='log' or @role='progressbar']"
                       "|//output|//progress")
    # corrección A4: solo campos donde el usuario escribe/elige datos (no checkboxes usados como interruptores CSS)
    # corrección A6: un buscador que navega a otra página no requiere mensajes de estado en la página
    data_inputs = [i for i in inputs if (i.tag in ("select", "textarea") or (i.get("type") or "").lower() in TEXT_LIKE)
                   and (i.get("type") or "").lower() != "search" and not SEARCHY.search(_descriptor(i, labels_for))
                   and i.get("size") != "1"]
    add("H1_status_messages", int(bool(data_inputs)), int(bool(data_inputs) and not status),
        data_inputs[:1] if not status else [])
    # role=tab expresa su estado con aria-selected, no aria-expanded
    disc = [e for e in doc.xpath("//*[@aria-haspopup or @aria-controls]") if not _hidden(e) and e.get("role") != "tab"]
    bad = [e for e in disc if e.get("aria-expanded") is None]
    add("H1_expanded_state", len(disc), len(bad), bad)
    navs = doc.xpath("//nav|//*[@role='navigation']")
    nav_links = [a for n in navs for a in n.xpath(".//a")]
    elig = int(len(nav_links) >= th["min_nav_links"])
    cur = [e for n in navs for e in n.xpath(".//*[@aria-current]|.//*[@class]")
           if e.get("aria-current") or re.search(r"\b(active|current|selected)\b", e.get("class") or "")]
    add("H1_current_location", elig, int(elig and not cur), navs[:1] if elig and not cur else [])

    # ---------------- H4
    by_name: dict[str, set] = {}
    ex_name: dict[str, object] = {}
    for a in href_links:
        n = _acc_name(a, by_id).lower()
        if len(n) >= 2:
            dest = re.split(r"[#?]", a.get("href"))[0]
            by_name.setdefault(n, set()).add(dest)
            ex_name.setdefault(n, a)
    amb = [n for n, d in by_name.items() if len(d) > 1]
    add("H4_ambiguous_link_names", len(by_name), len(amb), [ex_name[n] for n in amb])
    def focusable(e) -> bool:
        t = (e.get("tabindex") or "").strip()
        return t.lstrip("-").isdigit() and int(t) >= 0

    cand = [e for e in doc.xpath("//*[@onclick or @tabindex]")
            if isinstance(e.tag, str) and e.tag not in NATIVE_INTERACTIVE and not _hidden(e)
            # corrección A3: un encabezado/región enfocable sin onclick es gestión de foco, no un control
            and (e.get("onclick") is not None or (focusable(e) and e.tag not in FOCUS_ONLY_TAGS))]
    bad = [e for e in cand if not (e.get("role") or "").split() or e.get("role").split()[0] not in INTERACTIVE_ROLES]
    add("H4_nonstandard_controls", len(cand), len(bad), bad)
    bad = [a for a in links if a.get("role") != "button" and
           (a.get("href") is None or a.get("href").strip() in ("#", "") or a.get("href").strip().lower().startswith("javascript:"))]
    add("H4_links_as_buttons", len(links), len(bad), bad)
    hs = [int(h.tag[1]) for h in doc.xpath("//h1|//h2|//h3|//h4|//h5|//h6")]
    skips = sum(1 for a, b in zip(hs, hs[1:]) if b - a > 1)
    add("H4_heading_skips", max(len(hs) - 1, 0), skips, [])

    # ---------------- H5
    typed_elig, typed_bad = [], []
    for i in inputs:
        if i.tag != "input":
            continue
        d = _descriptor(i, labels_for)
        purposes = [t for t, p in PURPOSE_TYPED.items() if p.search(d)]
        exp = purposes[0] if len(purposes) == 1 else None  # corrección A5: "correo o teléfono" admite texto libre
        custom_picker = exp == "date" and (i.get("aria-haspopup") or i.get("aria-expanded") is not None)
        if exp and not custom_picker and not SEARCHY.search(d):
            typed_elig.append(i)
            # corrección A1: inputmode adecuado ya ofrece el teclado/validación del tipo esperado
            if (i.get("type") or "text").lower() == "text" and (i.get("inputmode") or "").lower() not in INPUTMODE_OK[exp]:
                typed_bad.append(i)
    add("H5_input_type_mismatch", len(typed_elig), len(typed_bad), typed_bad)
    pers = [i for i in inputs if i.tag == "input" and (i.get("type") or "").lower() in TEXT_LIKE - {"search", "number", "date"}
            and PERSONAL.search(_descriptor(i, labels_for)) and not SEARCHY.search(_descriptor(i, labels_for))]
    bad = [i for i in pers if i.get("autocomplete") is None]
    add("H5_autocomplete_missing", len(pers), len(bad), bad)
    cons = [i for i in inputs if any(i.get(a) is not None for a in ("pattern", "minlength", "min", "max"))]
    bad = [i for i in cons if not i.get("aria-describedby") and not i.get("title")]
    add("H5_constraints_not_communicated", len(cons), len(bad), bad)

    # ---------------- H6
    def labelled(i):
        return bool(i.get("aria-label") or i.get("aria-labelledby") or i.get("title")
                    or (i.get("id") and labels_for.get(i.get("id"))) or i.xpath("ancestor::label"))
    bad = [i for i in inputs if not labelled(i)]
    add("H6_unlabeled_inputs", len(inputs), len(bad), bad)
    ctrls = href_links + buttons
    bad = [c for c in ctrls if not _acc_name(c, by_id)]
    add("H6_unnamed_controls", len(ctrls), len(bad), bad)
    imgs = [i for i in doc.xpath("//img") if not _hidden(i) and i.get("role") not in ("presentation", "none")]
    bad = [i for i in imgs if i.get("alt") is None]
    add("H6_images_without_alt", len(imgs), len(bad), bad)
    body_text = len(" ".join(doc.text_content().split()))
    heads = doc.xpath("//h1|//h2|//h3|//h4|//h5|//h6|//*[@role='heading']")
    elig = int(body_text > th["min_text_chars_headings"])
    add("H6_no_headings", elig, int(elig and not heads), [])
    search = doc.xpath("//input[@type='search']|//*[@role='search']|//*[@role='searchbox']") or \
        [i for i in inputs if SEARCHY.search(_descriptor(i, labels_for))]
    elig = int(len(href_links) >= th["min_links_for_search"])
    add("H6_no_search_large_page", elig, int(elig and not search), [])
    return out


def severity(check: str, eligible: int, affected: int) -> int:
    rc = _rcfg()
    spec = rc["checks"][check]
    if not eligible or not affected:
        return 0
    imp = rc["impact_by_level"][spec["level"]]
    if spec["kind"] == "binary":
        return imp
    r = affected / eligible
    f = rc["frequency"]
    return imp if r >= f["high"] else max(imp - 1, 0) if r >= f["low"] else max(imp - 2, 0)


def _job(item: dict) -> list[dict]:
    text = Path(item["path"]).read_text(encoding="utf-8", errors="replace")
    rows = evaluate_html(text)
    meta = {k: v for k, v in item.items() if k != "path"}
    for r in rows:
        r.update(meta)
        r["ratio"] = r["affected"] / r["eligible"] if r["eligible"] else None
        r["severity"] = severity(r["check"], r["eligible"], r["affected"])
        r["heuristic"] = _rcfg()["checks"][r["check"]]["heuristic"]
        r["evidence"] = " || ".join(r["evidence"])
    return rows


def page_items() -> list[dict]:
    excl = config.load("silver_labeling")["html"]["exclude_url_patterns"]
    items = []
    for p in a11y_cua.html_pages():
        if p["url"] and any(x in p["url"] for x in excl):
            continue
        items.append(dict(kind="a11y", page_id=p["page_id"], session_id=p["session_id"], url=p["url"], path=p["path"]))
    for p in catching.html_sites():
        items.append(dict(kind="catching", page_id=p["page_id"], interface_id=p["interface_id"], url=None, path=p["path"]))
    return items


def run(log=print) -> tuple[pd.DataFrame, pd.DataFrame]:
    rc = _rcfg()
    with ProcessPoolExecutor() as pool:
        rows = [r for chunk in pool.map(_job, page_items(), chunksize=8) for r in chunk]
    checks = pd.DataFrame(rows)
    thr = rc["violation_min_severity"]
    g = checks.groupby(["kind", "page_id", "heuristic"], dropna=False)
    page = g.agg(session_id=("session_id", "first"), interface_id=("interface_id", "first"),
                 n_checks_eligible=("eligible", lambda s: int((s > 0).sum())),
                 severity_max=("severity", "max"),
                 failed_checks=("check", lambda s: ",".join(s[checks.loc[s.index, "severity"] >= thr]))).reset_index()
    page["assessable"] = page.n_checks_eligible > 0
    page["violation"] = (page.severity_max >= thr).astype("Int64").where(page.assessable)
    page["severity_max"] = page.severity_max.where(page.assessable)
    checks.to_parquet(config.PROCESSED / "rubric_check_results.parquet", index=False)
    page.to_parquet(config.PROCESSED / "rubric_page_labels.parquet", index=False)
    log(f"  rúbrica: {page.page_id.nunique()} páginas · {len(checks):,} comprobaciones")
    return checks, page


# ----------------------------------------------------------------- validación
AUDIT_LOG = [  # correcciones de implementación surgidas de la auditoría de evidencias (antes de fijar Y)
    ("A1", "H5_input_type_mismatch", "id=username con inputmode=email y type=text (target.com)",
     "inputmode adecuado ya ofrece el teclado del tipo esperado → no es falla"),
    ("A2", "H5_autocomplete_missing", "checkbox id=vector-user-links-dropdown-checkbox (Wikipedia)",
     "solo campos de texto y términos completos ('user' dentro de un id no es un campo de usuario)"),
    ("A3", "H4_nonstandard_controls", "<h2 tabindex=0> en target.com",
     "encabezados/regiones enfocables sin onclick son gestión de foco, no controles"),
    ("A4", "H1_status_messages", "checkbox usado como interruptor CSS del menú (neildegrassetyson.com)",
     "solo cuentan campos donde se escriben/eligen datos"),
    ("A5", "H5_input_type_mismatch", "'Email or phone number' con type=text (facebook.com); selector de fecha propio (expedia.com)",
     "campos de propósito múltiple y selectores de fecha personalizados no son falla"),
    ("A6", "H1_status_messages", "buscador de Wikipedia/YouTube",
     "un buscador que navega a otra página no requiere mensajes de estado en la página"),
]


def _binary_agreement(pred: pd.Series, ref: pd.Series) -> dict:
    m = pd.concat([pred.rename("p"), ref.rename("r")], axis=1).dropna().astype(int)
    n = len(m)
    tp, fp = int(((m.p == 1) & (m.r == 1)).sum()), int(((m.p == 1) & (m.r == 0)).sum())
    fn, tn = int(((m.p == 0) & (m.r == 1)).sum()), int(((m.p == 0) & (m.r == 0)).sum())
    po = (tp + tn) / n if n else float("nan")
    pe = (((tp + fp) * (tp + fn) + (fn + tn) * (fp + tn)) / n ** 2) if n else float("nan")
    return dict(n=n, tp=tp, fp=fp, fn=fn, tn=tn, accuracy=po,
                cohen_kappa=(po - pe) / (1 - pe) if n and pe < 1 else float("nan"),
                precision=tp / (tp + fp) if tp + fp else float("nan"), recall=tp / (tp + fn) if tp + fn else float("nan"))


def validate(log=print) -> dict:
    from scipy import stats

    from .report import _md

    out = config.REPORTS / "04_etiquetas_rubrica"
    out.mkdir(parents=True, exist_ok=True)
    checks = pd.read_parquet(config.PROCESSED / "rubric_check_results.parquet")
    page = pd.read_parquet(config.PROCESSED / "rubric_page_labels.parquet")
    rc = _rcfg()

    # 1. distribución por criterio (A11y-CUA)
    a = checks[checks.kind == "a11y"]
    dist = a.groupby("check").agg(paginas_elegibles=("eligible", lambda x: int((x > 0).sum())),
                                  paginas_con_falla_sev2=("severity", lambda x: int((x >= 2).sum())),
                                  severidad_media=("severity", "mean")).reset_index()
    dist.insert(1, "criterio", dist.check.map(lambda c: rc["checks"][c]["criterion"]))
    dist.insert(2, "nivel", dist.check.map(lambda c: rc["checks"][c]["level"]))
    dist.to_csv(out / "distribucion_criterios.csv", index=False)
    pa = page[page.kind == "a11y"]
    prev = pa.groupby("heuristic").agg(paginas=("page_id", "nunique"), evaluables=("assessable", "sum"),
                                       violaciones=("violation", "sum"), prevalencia=("violation", "mean")).reset_index()
    prev.to_csv(out / "prevalencia_paginas.csv", index=False)

    # 2. validez concurrente: Catching (13 sitios con HTML) vs. mayoría de 3 evaluaciones GPT-4o
    ref = pd.read_parquet(config.PROCESSED / "interface_labels.parquet")
    ref = ref[ref.source == "S04_catching_ux_flaws"].set_index("interface_id")
    pc = page[page.kind == "catching"].assign(v=lambda d: pd.to_numeric(d.violation, errors="coerce"))
    site = pc.groupby(["interface_id", "heuristic"]).v.mean().ge(0.5).astype(float).where(
        pc.groupby(["interface_id", "heuristic"]).v.mean().notna()).reset_index()
    conc = []
    for h in CODES:
        s = site[site.heuristic == h].set_index("interface_id").v
        conc.append(dict(heuristic=h, reference="Catching UX Flaws · mayoría GPT-4o",
                         ref_prevalence=ref[f"{h}_violation"].reindex(s.index).mean(), **_binary_agreement(s, ref[f"{h}_violation"].reindex(s.index))))
    conc = pd.DataFrame(conc)
    conc.to_csv(out / "validez_concurrente_catching.csv", index=False)

    # 3. validez de criterio: ¿las sesiones con violación tienen peor resultado según los PROPIOS usuarios?
    from .training import OUT
    df = pd.read_parquet(OUT / "training_dataset.parquet")
    df = df[df.include_main]
    crit = []
    for h in CODES:
        d = df[df[f"y_{h}"].notna()]
        g1, g0 = d[d[f"y_{h}"] == 1], d[d[f"y_{h}"] == 0]
        row = dict(heuristic=h, n_viol=len(g1), n_no_viol=len(g0))
        for col, lab in (("iso_satisfaction_perceived_ease", "facilidad"), ("iso_effectiveness_task_completion", "exito"),
                         ("iso_efficiency_task_time_s", "tiempo_s")):
            x1, x0 = g1[col].dropna(), g0[col].dropna()
            row[f"{lab}_viol"] = x1.mean() if len(x1) else float("nan")
            row[f"{lab}_no_viol"] = x0.mean() if len(x0) else float("nan")
            if len(x1) >= 5 and len(x0) >= 5:
                u = stats.mannwhitneyu(x1, x0, alternative="two-sided")
                row[f"{lab}_p_mwu"] = u.pvalue
                row[f"{lab}_rank_biserial"] = 2 * u.statistic / (len(x1) * len(x0)) - 1  # U de x1: > 0 ⇒ mayor con violación
        crit.append(row)
    crit = pd.DataFrame(crit)
    crit.to_csv(out / "validez_criterio_usuarios.csv", index=False)

    # 4. auditoría de evidencias
    audit = pd.DataFrame(AUDIT_LOG, columns=["id", "criterio", "falso_positivo_observado", "corrección"])
    audit.to_csv(out / "auditoria_evaluador.csv", index=False)
    sample = (a[a.severity >= 2].drop_duplicates(["check", "url"]).sample(frac=1, random_state=0)
              .groupby("check").head(3).sort_values("check")[["check", "url", "affected", "eligible", "severity", "evidence"]])
    sample.to_csv(out / "muestra_evidencias.csv", index=False)

    txt = [
        "# Etapa 3b · Etiquetas H1/H4/H5/H6 por inspección con rúbrica",
        "",
        "Método: revisión automatizada por guías (Ivory y Hearst, 2001) con 16 criterios (`configs/rubric.yaml`), "
        "cada uno anclado en una pregunta guía de Nielsen (1994) y un criterio WCAG 2.2. Severidad 0–4 de Nielsen "
        "(1994b) = impacto (nivel WCAG) ajustado por frecuencia; violación = severidad ≥ 2.",
        "",
        "## Prevalencia por página (A11y-CUA)",
        "", _md(prev), "",
        "## Criterios",
        "", _md(dist), "",
        "## Validez concurrente frente a Catching UX Flaws",
        "",
        "Referencia: mayoría de 3 evaluaciones GPT-4o sobre el mismo código (13 sitios con HTML recuperado). "
        "La referencia es casi siempre positiva, por lo que κ puede ser 0 o indefinido aunque la exactitud sea alta.",
        "", _md(conc), "",
        "## Validez de criterio frente a lo que reportan los usuarios",
        "",
        "Si las violaciones detectadas afectan a las personas, las sesiones con violación deberían mostrar menor "
        "facilidad percibida o éxito, o más tiempo. `rank_biserial` > 0 = mayor en sesiones con violación (< 0 = menor). "
        "Prueba U de Mann-Whitney bilateral, sin corrección por comparaciones múltiples (exploratorio).",
        "", _md(crit), "",
        "## Auditoría del evaluador",
        "",
        "Antes de fijar Y se revisaron muestras de evidencias de cada criterio. Se corrigieron estos falsos positivos de "
        "implementación (no se ajustaron umbrales para cambiar la prevalencia):",
        "", _md(audit), "",
        "`muestra_evidencias.csv` contiene 3 evidencias por criterio para revisión independiente.",
        "",
        "## Limitaciones",
        "",
        "- Inspección estática: no observa CSS calculado ni manejadores añadidos por JavaScript.",
        "- La rúbrica mide incumplimientos verificables en el marcado; no sustituye una evaluación heurística experta "
        "completa (p. ej. coherencia terminológica o adecuación del contenido).",
        "- H5 solo es evaluable en páginas con campos de datos (~16 % de las páginas).",
    ]
    (out / "README.md").write_text("\n".join(txt), encoding="utf-8")
    log(f"  validación de la rúbrica escrita en {out.relative_to(config.ROOT)}")
    return dict(prevalence=prev, concurrent=conc, criterion=crit)
