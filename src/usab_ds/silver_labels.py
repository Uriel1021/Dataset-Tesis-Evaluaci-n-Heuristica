"""Etapa 3b · Etiquetas "silver" H1/H4/H5/H6 con Claude sobre HTML de A11y-CUA.

Flujo (cada paso es un subcomando; ver __main__.py):

  silver-prepare   limpia el HTML, deduplica por contenido y arma las solicitudes
                   (no llama a la API; estima el costo por caracteres)
  silver-count     costo exacto con /v1/messages/count_tokens (requiere credenciales)
  silver-submit    envía un Message Batch (50 % de descuento) — pide --yes
  silver-collect   descarga resultados, reintenta negativas (refusal) sin batch
                   con fallbacks, y escribe etiquetas + informe de validación

Además de las páginas de A11y-CUA se evalúan, con el mismo protocolo:
  * 33 páginas HTML de Catching UX Flaws → acuerdo con las 3 evaluaciones GPT-4o
  * 20 capturas de P3M → precisión/sensibilidad frente a los defectos
    VALIDADOS POR EXPERTOS (la única referencia humana disponible)
  * un subconjunto de A11y-CUA repetido k veces → α de Krippendorff

Todas las respuestas crudas se guardan (results_raw.jsonl) para auditoría.
"""

from __future__ import annotations

import base64
import hashlib
import json
import random
import re
import time
from pathlib import Path

import pandas as pd
from lxml import etree
from lxml import html as lhtml

from . import config
from .adapters import a11y_cua, catching, p3m

SILVER = config.INTERIM / "silver"
CODES = ("H1", "H4", "H5", "H6")
FALLBACK_BETA = "server-side-fallback-2026-07-01"


def cfg() -> dict:
    return config.load("silver_labeling")


# ----------------------------------------------------------------- HTML
def clean_html(text: str, c: dict | None = None) -> tuple[str, bool, int]:
    """Reduce el snapshot a estructura + texto + atributos relevantes.

    Devuelve (html_limpio, truncado, longitud_original). Nunca trunca en
    silencio: si supera max_chars se corta y se marca truncado=True.
    """
    c = (c or cfg())["html"]
    keep = set(c["keep_attributes"])
    try:
        doc = lhtml.fromstring(text)
    except Exception:
        return "", False, len(text)
    for bad in doc.xpath("//script|//style|//noscript|//svg|//link|//meta|//template|//iframe"):
        bad.drop_tree()
    for com in doc.xpath("//comment()"):
        com.getparent().remove(com) if com.getparent() is not None else None
    lim = c["max_text_node_chars"]
    for el in doc.iter():
        if not isinstance(el.tag, str):
            continue
        for a in list(el.attrib):
            if a not in keep:
                del el.attrib[a]
            elif a in ("class", "href", "onclick"):
                el.attrib[a] = el.attrib[a][:80]
        if el.text and len(el.text) > lim:
            el.text = el.text[:lim] + "…"
        if el.tail and len(el.tail) > lim:
            el.tail = el.tail[:lim] + "…"
    out = etree.tostring(doc, encoding="unicode", method="html")
    out = re.sub(r"\s+", " ", out)
    out = re.sub(r">\s+<", "><", out).strip()
    truncated = len(out) > c["max_chars"]
    return out[: c["max_chars"]], truncated, len(out)


# ----------------------------------------------------------------- prompt
def system_prompt() -> str:
    cw = config.load("crosswalk")["heuristics"]
    qs = cfg()["heuristic_questions"]
    parts = [
        "Eres un evaluador experto en usabilidad que realiza una evaluación heurística de Nielsen (1994) "
        "sobre UNA página web. Evalúas solo cuatro heurísticas: H1, H4, H5 y H6.",
        "",
        "Reglas:",
        "1. Juzga solo lo que se puede comprobar en el material entregado (marcado HTML estático o captura). "
        "No supongas comportamiento dinámico que no esté evidenciado.",
        "2. Cada problema debe citar en element_evidence un fragmento literal y breve del HTML (o describir el "
        "elemento visible en la captura) que lo demuestre. Si no puedes señalar evidencia concreta, no lo reportes.",
        "3. Si la página no contiene los elementos necesarios para juzgar una heurística (por ejemplo, H5 sin "
        "formularios ni acciones destructivas), marca assessable = false y no reportes problemas para ella.",
        "4. Una página sin problemas evidenciados para una heurística debe quedar con violation = false. "
        "No es necesario encontrar problemas.",
        "5. Severidad de Nielsen: 0 = no es un problema, 1 = cosmético, 2 = menor, 3 = mayor, 4 = catástrofe.",
        "6. violation = true solo si reportas al menos un problema con severidad ≥ 1.",
        "",
        "Heurísticas:",
    ]
    for h in CODES:
        parts.append(f"{h} · {cw[h]['name']} ({cw[h]['name_es']}): {cw[h]['definition']}")
        parts += [f"   - {q}" for q in qs[h]]
    parts += ["", "Responde únicamente con el JSON del esquema indicado, una entrada por heurística (H1, H4, H5, H6)."]
    return "\n".join(parts)


SCHEMA = {
    "type": "object",
    "properties": {
        "heuristics": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "enum": list(CODES)},
                    "assessable": {"type": "boolean"},
                    "violation": {"type": "boolean"},
                    "severity_max": {"type": "integer", "enum": [0, 1, 2, 3, 4]},
                    "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
                    "issues": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "description": {"type": "string"},
                                "element_evidence": {"type": "string"},
                                "severity": {"type": "integer", "enum": [0, 1, 2, 3, 4]},
                            },
                            "required": ["description", "element_evidence", "severity"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["code", "assessable", "violation", "severity_max", "confidence", "issues"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["heuristics"],
    "additionalProperties": False,
}


def _params(content: list[dict]) -> dict:
    c = cfg()
    return dict(
        model=c["model"], max_tokens=c["max_tokens"], system=system_prompt(),
        output_config={"effort": c["effort"], "format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{"role": "user", "content": content}],
    )


def _html_content(url: str | None, html: str, truncated: bool) -> list[dict]:
    note = " (el HTML fue recortado por longitud; evalúa lo disponible)" if truncated else ""
    return [{"type": "text", "text": f"URL: {url or 'desconocida'}{note}\n\nHTML de la página:\n{html}"}]


def _image_content(path: Path) -> list[dict]:
    data = base64.standard_b64encode(path.read_bytes()).decode("utf-8")
    return [{"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": data}},
            {"type": "text", "text": "Captura de pantalla de la página web a evaluar (no hay HTML disponible)."}]


# ----------------------------------------------------------------- ítems
def build_items() -> tuple[pd.DataFrame, dict[str, dict], pd.DataFrame]:
    """Devuelve (páginas, {custom_id: params}, metadatos por solicitud)."""
    c = cfg()
    excl = c["html"]["exclude_url_patterns"]
    pages, uniq = [], {}

    def add_html(kind, page_meta, path):
        raw = Path(path).read_text(encoding="utf-8", errors="replace")
        html, trunc, n = clean_html(raw, c)
        url = page_meta.get("url")
        status = "ok"
        if url and any(p in url for p in excl):
            status = "excluded_url"
        elif len(html) < c["html"]["min_chars"]:
            status = "too_small"
        h = hashlib.sha256(html.encode()).hexdigest()[:16]
        pages.append({**page_meta, "kind": kind, "content_hash": h if status == "ok" else None, "status": status,
                      "clean_chars": n, "html_truncated": trunc})
        if status == "ok" and (kind, h) not in uniq:
            uniq[(kind, h)] = _html_content(url, html, trunc)

    for p in a11y_cua.html_pages():
        add_html("a11y", {k: p[k] for k in ("page_id", "session_id", "url")}, p["path"])
    for p in catching.html_sites():
        add_html("catching", {"page_id": p["page_id"], "interface_id": p["interface_id"], "url": None}, p["path"])
    shots = sorted((config.source_path(p3m.SOURCE) / "Screenshots").glob("Screenshot *.png"))
    for s in shots:
        n = int(re.findall(r"\d+", s.stem)[0])
        h = hashlib.sha256(s.read_bytes()).hexdigest()[:16]
        pages.append(dict(page_id=f"{p3m.SOURCE}:screenshot_{n:02d}", interface_id=f"{p3m.SOURCE}:screenshot_{n:02d}",
                          kind="p3m", content_hash=h, status="ok", clean_chars=None, html_truncated=False))
        uniq[("p3m", h)] = _image_content(s)

    # repeticiones: todas 1 vez; validación (catching, p3m, muestra A11y) k veces
    rng = random.Random(c["seed"])
    a11y_hashes = sorted(h for (k, h) in uniq if k == "a11y")
    rel = set(rng.sample(a11y_hashes, min(c["reliability_sample"], len(a11y_hashes))))
    reqs, meta = {}, []
    for (kind, h), content in uniq.items():
        reps = c["validation_repeats"] if kind in ("catching", "p3m") or h in rel else c["repeats"]
        for r in range(reps):
            cid = f"{kind}-{h}-r{r}"
            reqs[cid] = _params(content)
            meta.append(dict(custom_id=cid, kind=kind, content_hash=h, rep=r, reliability_item=h in rel or kind != "a11y",
                             approx_input_chars=sum(len(b.get("text", "")) for b in content),
                             has_image=any(b["type"] == "image" for b in content)))
    return pd.DataFrame(pages), reqs, pd.DataFrame(meta)


# ----------------------------------------------------------------- costo
def estimate(meta: pd.DataFrame, input_tokens: int | None = None) -> dict:
    c = cfg()
    pr = c["pricing_usd_per_mtok"]
    sys_tok = len(system_prompt()) / 3.5
    if input_tokens is None:  # aproximación: ~3.5 caracteres/token para HTML; ~1600 tokens por imagen
        input_tokens = int(meta.approx_input_chars.sum() / 3.5 + len(meta) * sys_tok + meta.has_image.sum() * 1600)
    out_tok = len(meta) * c["assumed_output_tokens"]
    d = pr["batch_discount"]
    usd = (input_tokens * pr["input"] + out_tok * pr["output"]) / 1e6 * d
    return dict(requests=len(meta), input_tokens=input_tokens, assumed_output_tokens=out_tok,
                usd_batch=round(usd, 2), usd_standard=round(usd / d, 2), model=c["model"])


def prepare(log=print) -> dict:
    SILVER.mkdir(parents=True, exist_ok=True)
    pages, reqs, meta = build_items()
    pages.to_csv(SILVER / "pages.csv", index=False)
    meta.to_csv(SILVER / "requests_meta.csv", index=False)
    with open(SILVER / "requests.jsonl", "w", encoding="utf-8") as fh:
        for cid, p in reqs.items():
            fh.write(json.dumps({"custom_id": cid, "params": p}, ensure_ascii=False) + "\n")
    est = estimate(meta)
    log(f"  páginas: {len(pages)} · por estado: {pages.status.value_counts().to_dict()}")
    log(f"  truncadas: {int(pages.html_truncated.sum())} · solicitudes: {len(reqs)} "
        f"({meta.kind.value_counts().to_dict()})")
    log(f"  costo estimado (aprox. por caracteres): ${est['usd_batch']} con Batches · ${est['usd_standard']} sin batch")
    (SILVER / "estimate.json").write_text(json.dumps(est, indent=2))
    return est


def _load_requests() -> dict[str, dict]:
    with open(SILVER / "requests.jsonl", encoding="utf-8") as fh:
        return {d["custom_id"]: d["params"] for d in map(json.loads, fh)}


def count(log=print) -> dict:
    import anthropic
    client = anthropic.Anthropic()
    total = 0
    for i, (cid, p) in enumerate(_load_requests().items()):
        r = client.messages.count_tokens(model=p["model"], system=p["system"], messages=p["messages"],
                                         output_config={"format": p["output_config"]["format"]})
        total += r.input_tokens
        if i % 50 == 0:
            log(f"  {i} solicitudes contadas…")
    est = estimate(pd.read_csv(SILVER / "requests_meta.csv"), input_tokens=total)
    (SILVER / "estimate.json").write_text(json.dumps(est, indent=2))
    log(f"  tokens de entrada exactos: {total:,} → ${est['usd_batch']} con Batches")
    return est


# ----------------------------------------------------------------- envío
def submit(yes: bool, log=print) -> str | None:
    import anthropic
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request

    est = json.loads((SILVER / "estimate.json").read_text())
    if not yes:
        log(f"  Se enviarían {est['requests']} solicitudes a {est['model']} por ~${est['usd_batch']}. "
            "Repite con --yes para confirmar.")
        return None
    client = anthropic.Anthropic()
    reqs = [Request(custom_id=cid, params=MessageCreateParamsNonStreaming(**p)) for cid, p in _load_requests().items()]
    batch = client.messages.batches.create(requests=reqs)
    rec = dict(batch_id=batch.id, submitted=time.strftime("%Y-%m-%dT%H:%M:%S"), n=len(reqs))
    (SILVER / "batch.json").write_text(json.dumps(rec, indent=2))
    log(f"  batch {batch.id} enviado ({len(reqs)} solicitudes). Ejecuta silver-collect cuando termine (≤ 24 h).")
    return batch.id


def _text_of(msg) -> str:
    return next((b.text for b in msg.content if getattr(b, "type", None) == "text"), "")


def collect(retry: bool = True, log=print) -> pd.DataFrame | None:
    import anthropic
    client = anthropic.Anthropic()
    rec = json.loads((SILVER / "batch.json").read_text())
    b = client.messages.batches.retrieve(rec["batch_id"])
    if b.processing_status != "ended":
        log(f"  batch {b.id}: {b.processing_status} · {b.request_counts}")
        return None
    raw_path = SILVER / "results_raw.jsonl"
    done = {}
    if raw_path.exists():
        done = {d["custom_id"]: d for d in map(json.loads, raw_path.open(encoding="utf-8"))}
    with open(raw_path, "a", encoding="utf-8") as fh:
        for r in client.messages.batches.results(b.id):
            if r.custom_id in done and done[r.custom_id].get("ok"):
                continue
            row = dict(custom_id=r.custom_id, result_type=r.result.type, ok=False, via="batch")
            if r.result.type == "succeeded":
                m = r.result.message
                row.update(model=m.model, stop_reason=m.stop_reason, text=_text_of(m),
                           input_tokens=m.usage.input_tokens, output_tokens=m.usage.output_tokens,
                           ok=m.stop_reason == "end_turn")
            else:
                row["error"] = str(getattr(r.result, "error", ""))
            done[r.custom_id] = row
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

        # negativas o errores: reintento directo (fallbacks no existen en Batches)
        pending = [cid for cid, d in done.items() if not d.get("ok")]
        if retry and pending:
            log(f"  reintentando {len(pending)} solicitudes sin batch (fallbacks='default')")
            reqs = _load_requests()
            for cid in pending:
                p = reqs[cid]
                try:
                    m = client.beta.messages.create(**p, betas=[FALLBACK_BETA], fallbacks="default")
                except anthropic.BadRequestError as e:
                    row = dict(custom_id=cid, ok=False, via="direct", error=e.message)
                except (anthropic.RateLimitError, anthropic.APIStatusError, anthropic.APIConnectionError) as e:
                    row = dict(custom_id=cid, ok=False, via="direct", error=str(e))
                else:
                    row = dict(custom_id=cid, result_type="succeeded", via="direct", model=m.model,
                               stop_reason=m.stop_reason, text=_text_of(m), input_tokens=m.usage.input_tokens,
                               output_tokens=m.usage.output_tokens, ok=m.stop_reason == "end_turn")
                done[cid] = row
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return finalize(log)


# ----------------------------------------------------------------- resultados
def parse_results() -> pd.DataFrame:
    thr = cfg()["violation_min_severity"]
    meta = pd.read_csv(SILVER / "requests_meta.csv").set_index("custom_id")
    last = {}
    for d in map(json.loads, (SILVER / "results_raw.jsonl").open(encoding="utf-8")):
        last[d["custom_id"]] = d
    rows = []
    for cid, d in last.items():
        base = dict(custom_id=cid, **meta.loc[cid].to_dict(), model=d.get("model"), via=d.get("via"),
                    stop_reason=d.get("stop_reason"), input_tokens=d.get("input_tokens"), output_tokens=d.get("output_tokens"))
        try:
            obj = json.loads(d["text"]) if d.get("ok") else None
        except (json.JSONDecodeError, TypeError):
            obj = None
        if obj is None:
            rows += [dict(base, heuristic=h, parse_ok=False) for h in CODES]
            continue
        seen = {e["code"]: e for e in obj["heuristics"]}
        for h in CODES:
            e = seen.get(h)
            if e is None:
                rows.append(dict(base, heuristic=h, parse_ok=False))
                continue
            sev = [i["severity"] for i in e["issues"]]
            pos = [s for s in sev if s >= thr]
            rows.append(dict(
                base, heuristic=h, parse_ok=True, assessable=e["assessable"],
                violation=(int(bool(pos)) if e["assessable"] else None),
                violation_model_flag=e["violation"], severity_max=max(sev) if sev else 0,
                n_issues=len(pos), confidence=e["confidence"],
                evidence=" | ".join(f"[{i['severity']}] {i['description']} :: {i['element_evidence']}" for i in e["issues"])[:1000],
            ))
    return pd.DataFrame(rows)


def finalize(log=print) -> pd.DataFrame:
    from .build import krippendorff_alpha_nominal

    lab = parse_results()
    lab.to_parquet(SILVER / "labels_long.parquet", index=False)
    pages = pd.read_csv(SILVER / "pages.csv")

    # ---- etiqueta por contenido (mayoría de repeticiones) → página → sesión
    ok = lab[lab.parse_ok.fillna(False)]
    by_hash = ok.groupby(["kind", "content_hash", "heuristic"]).agg(
        n_evals=("violation", "size"), assessable_rate=("assessable", "mean"),
        violation_rate=("violation", "mean"), severity_max=("severity_max", "max")).reset_index()
    by_hash["violation"] = (by_hash.violation_rate > 0.5).astype("Int64").where(by_hash.violation_rate.notna())
    page_lab = pages.merge(by_hash, on=["kind", "content_hash"], how="left")
    page_lab.to_parquet(config.PROCESSED / "silver_page_labels.parquet", index=False)

    # ---- fiabilidad (ítems repetidos)
    rel = []
    for (kind, h), g in ok[ok.reliability_item].groupby(["kind", "heuristic"]):
        units = [list(s.dropna().astype(int)) for _, s in g.groupby("content_hash").violation]
        rel.append(dict(kind=kind, heuristic=h, items=sum(len(u) >= 2 for u in units),
                        prevalence=round(float(g.violation.mean()), 3), krippendorff_alpha=krippendorff_alpha_nominal(units)))
    rel = pd.DataFrame(rel)

    # ---- validación externa
    ref = pd.read_parquet(config.PROCESSED / "interface_labels.parquet")
    val = []
    site = page_lab[page_lab.kind.isin(["catching", "p3m"])].groupby(["kind", "interface_id", "heuristic"]).violation.max().reset_index()
    for kind, src, et in (("p3m", p3m.SOURCE, "llm_expert_validated"), ("catching", catching.SOURCE, "llm")):
        r = ref[(ref.source == src) & (ref.evaluator_type == et)].set_index("interface_id")
        for h in CODES:
            s = site[(site.kind == kind) & (site.heuristic == h)].set_index("interface_id").violation
            y = r[f"{h}_violation"].reindex(s.index)
            m = pd.concat([s.rename("pred"), y.rename("ref")], axis=1).dropna().astype(int)
            tp, fp = int(((m.pred == 1) & (m.ref == 1)).sum()), int(((m.pred == 1) & (m.ref == 0)).sum())
            fn, tn = int(((m.pred == 0) & (m.ref == 1)).sum()), int(((m.pred == 0) & (m.ref == 0)).sum())
            po = (tp + tn) / len(m) if len(m) else float("nan")
            pe = (((tp + fp) * (tp + fn) + (fn + tn) * (fp + tn)) / len(m) ** 2) if len(m) else float("nan")
            val.append(dict(reference=f"{src} · {et}", heuristic=h, n=len(m), tp=tp, fp=fp, fn=fn, tn=tn,
                            accuracy=po, cohen_kappa=(po - pe) / (1 - pe) if len(m) and pe < 1 else float("nan"),
                            precision=tp / (tp + fp) if tp + fp else float("nan"),
                            recall=tp / (tp + fn) if tp + fn else float("nan")))
    val = pd.DataFrame(val)

    usage = lab.drop_duplicates("custom_id")
    pr = cfg()["pricing_usd_per_mtok"]
    cost = ((usage.input_tokens.fillna(0).sum() * pr["input"] + usage.output_tokens.fillna(0).sum() * pr["output"]) / 1e6
            * pr["batch_discount"])
    out = config.REPORTS / "04_etiquetas_silver"
    out.mkdir(parents=True, exist_ok=True)
    rel.to_csv(out / "fiabilidad.csv", index=False)
    val.to_csv(out / "validacion_externa.csv", index=False)
    prev = page_lab[page_lab.kind == "a11y"].groupby("heuristic").agg(
        paginas=("violation", "count"), prevalencia=("violation", "mean"), evaluable=("assessable_rate", "mean")).reset_index()
    prev.to_csv(out / "prevalencia_a11y.csv", index=False)
    summary = dict(requests=int(usage.custom_id.nunique()), parse_failures=int((~lab.parse_ok.fillna(False)).sum() // 4),
                   input_tokens=int(usage.input_tokens.fillna(0).sum()), output_tokens=int(usage.output_tokens.fillna(0).sum()),
                   cost_usd_batch_approx=round(cost, 2), model=cfg()["model"])
    (out / "resumen.json").write_text(json.dumps(summary, indent=2))
    log(f"  etiquetas: {summary} ")
    return page_lab
