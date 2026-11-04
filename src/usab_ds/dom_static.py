"""Rasgos estáticos del DOM (puente entre sesiones y evaluaciones etiquetadas).

Se calculan con la MISMA función sobre:
  * snapshots HTML de A11y-CUA (ligados a una sesión de comportamiento)
  * HTML recuperado de los sitios de Catching UX Flaws (ligados a etiquetas)

Cada rasgo se ancla en un criterio de éxito WCAG 2.2 y se asocia a la
heurística con la que se relaciona en configs/crosswalk.yaml. Son
indicadores de PRESENCIA de mecanismos de diseño, no juicios de violación.
"""

from __future__ import annotations

import re
from collections import Counter

from lxml import html as lhtml

# nombre -> (heurística, criterio WCAG / justificación)
FEATURES = {
    "dom_n_elements": (None, "tamaño del documento"),
    "dom_max_depth": (None, "complejidad estructural"),
    "dom_n_links": (None, "conteo"),
    "dom_n_buttons": (None, "conteo"),
    "dom_n_inputs": (None, "conteo"),
    "dom_n_forms": (None, "conteo"),
    "dom_n_images": (None, "conteo"),
    "dom_status_regions": ("H1", "WCAG 4.1.3 Status Messages: aria-live, role=status/alert/progressbar, <progress>"),
    "dom_loading_indicators": ("H1", "elementos con clase/id spinner|loader|loading|progress (retroalimentación de espera)"),
    "dom_button_style_variety": ("H4", "clases CSS distintas por botón (heterogeneidad visual; WCAG 3.2.4)"),
    "dom_inconsistent_link_text": ("H4", "WCAG 3.2.4 Consistent Identification: mismo texto de enlace → destinos distintos"),
    "dom_has_nav": ("H4", "WCAG 3.2.3 Consistent Navigation: <nav> o role=navigation"),
    "dom_input_constraint_ratio": ("H5", "WCAG 3.3.4/3.3.1: required, pattern, min/max, maxlength o type restringido"),
    "dom_input_autocomplete_ratio": ("H5", "WCAG 1.3.5 Identify Input Purpose: atributo autocomplete"),
    "dom_input_label_ratio": ("H6", "WCAG 3.3.2 Labels or Instructions: label/aria-label/aria-labelledby"),
    "dom_placeholder_only_ratio": ("H6", "placeholder sin etiqueta: la instrucción desaparece al escribir (exige recordar)"),
    "dom_img_alt_ratio": ("H6", "WCAG 1.1.1 Non-text Content: <img> con alt"),
    "dom_has_breadcrumb": ("H6", "WCAG 2.4.8 Location: migas de pan"),
    "dom_has_search": ("H6", "búsqueda disponible: reconocer en lugar de recordar la ubicación"),
    "dom_n_headings": ("H6", "WCAG 2.4.6 Headings and Labels"),
}

_CONSTRAINED_TYPES = {"email", "number", "tel", "url", "date", "datetime-local", "month", "time", "week", "range", "color"}
_LOADING = re.compile(r"spinner|loader|loading|progress|skeleton", re.I)
_IGNORED_INPUT_TYPES = {"hidden", "submit", "button", "reset", "image"}


def _ratio(num: int, den: int) -> float | None:
    return num / den if den else None


def features_from_html(text: str) -> dict:
    try:
        doc = lhtml.fromstring(text)
    except Exception:  # documento vacío o inválido
        return {k: None for k in FEATURES}
    for bad in doc.xpath("//script|//style|//noscript"):
        bad.drop_tree()
    els = list(doc.iter())
    depth = 0
    for leaf in doc.xpath("//*[not(*)]")[:20000]:
        depth = max(depth, sum(1 for _ in leaf.iterancestors()))

    buttons = doc.xpath("//button|//input[@type='button' or @type='submit']|//*[@role='button']")
    inputs = [i for i in doc.xpath("//input|//select|//textarea")
              if (i.get("type") or "").lower() not in _IGNORED_INPUT_TYPES]
    label_for = {lab.get("for") for lab in doc.xpath("//label[@for]")}

    def labelled(i) -> bool:
        return bool(i.get("aria-label") or i.get("aria-labelledby") or (i.get("id") and i.get("id") in label_for)
                    or i.xpath("ancestor::label") or i.get("title"))

    def constrained(i) -> bool:
        return any(i.get(a) is not None for a in ("required", "pattern", "min", "max", "maxlength", "minlength")) \
            or (i.get("type") or "").lower() in _CONSTRAINED_TYPES or i.tag == "select"

    links = doc.xpath("//a[@href]")
    by_text: dict[str, set] = {}
    for a in links:
        t = " ".join(a.text_content().split()).lower()
        if t:
            by_text.setdefault(t, set()).add(a.get("href").split("#")[0])
    texts_multi = [t for t, hrefs in by_text.items() if len(hrefs) > 1]
    btn_classes = Counter(" ".join(sorted((b.get("class") or "").split())) for b in buttons)
    imgs = doc.xpath("//img")
    attr_text = lambda e: f"{e.get('class', '')} {e.get('id', '')}"  # noqa: E731

    return {
        "dom_n_elements": len(els),
        "dom_max_depth": depth,
        "dom_n_links": len(links),
        "dom_n_buttons": len(buttons),
        "dom_n_inputs": len(inputs),
        "dom_n_forms": len(doc.xpath("//form")),
        "dom_n_images": len(imgs),
        "dom_status_regions": len(doc.xpath("//*[@aria-live or @role='status' or @role='alert' or @role='progressbar']|//progress")),
        "dom_loading_indicators": sum(1 for e in els if isinstance(e.tag, str) and _LOADING.search(attr_text(e))),
        "dom_button_style_variety": _ratio(len(btn_classes), len(buttons)),
        "dom_inconsistent_link_text": _ratio(len(texts_multi), len(by_text)),
        "dom_has_nav": int(bool(doc.xpath("//nav|//*[@role='navigation']"))),
        "dom_input_constraint_ratio": _ratio(sum(constrained(i) for i in inputs), len(inputs)),
        "dom_input_autocomplete_ratio": _ratio(sum(i.get("autocomplete") is not None for i in inputs), len(inputs)),
        "dom_input_label_ratio": _ratio(sum(labelled(i) for i in inputs), len(inputs)),
        "dom_placeholder_only_ratio": _ratio(sum(bool(i.get("placeholder")) and not labelled(i) for i in inputs), len(inputs)),
        "dom_img_alt_ratio": _ratio(sum(i.get("alt") is not None for i in imgs), len(imgs)),
        "dom_has_breadcrumb": int(bool(doc.xpath(
            "//*[contains(translate(@aria-label,'BREADCRUMB','breadcrumb'),'breadcrumb') or contains(@class,'breadcrumb')]"))),
        "dom_has_search": int(bool(doc.xpath("//input[@type='search']|//*[@role='search']|//*[@role='searchbox']"))),
        "dom_n_headings": len(doc.xpath("//h1|//h2|//h3|//h4|//h5|//h6")),
    }


def features_from_file(path) -> dict:
    with open(path, encoding="utf-8", errors="replace") as fh:
        return features_from_html(fh.read())
