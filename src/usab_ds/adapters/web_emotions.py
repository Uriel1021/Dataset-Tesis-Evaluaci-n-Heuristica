"""Adaptador S01 · Interacciones web + emociones (Figshare 28489601).

La fuente NO es un log de eventos: es un muestreo de estado cada ~100 ms
(mediana medida = 97 ms) con banderas booleanas (clic, teclado) y
posiciones (ratón, scroll). Reglas de transformación:

  R1  Visita = racha consecutiva de muestras del mismo usuario en la misma
      URL; una pausa > session_gap_minutes abre una visita nueva
      (Catledge y Pitkow, 1995). Cada visita es una sesión.
  R2  click  = flanco de subida de mouse.clicks (false→true).
      key    = flanco de subida de keyboard.
      Un clic/tecla mantenido durante varias muestras cuenta una vez.
  R3  scroll = inicio de una racha de muestras con cambio en scroll.absolute.y;
      además cada cambio se guarda como scroll_pos (posición).
  R4  mouse_move = muestra con posición del cursor distinta de la anterior.
  R5  Emociones: media de valence y engagement sobre muestras con
      emotions.exist = true (indicador afectivo, no autoinforme).
  R6  Se usa interactions.csv (crudo). aggregates.csv son ventanas ya
      agregadas por los autores con otra lógica y se describen en la etapa 1
      pero no se mezclan.
  Limitaciones: no hay identidad del elemento clicado (sin target_tag) ni
  nombre de tecla, por lo que dead_click_rate y correction_key_ratio quedan NaN.
"""

from __future__ import annotations

from urllib.parse import urlparse

import pandas as pd
import polars as pl

from .. import config, events

SOURCE = "S01_web_emotions_28489601"
# page_view se emite (inicio de visita) pero NO se declara: como cada sesión es
# una sola URL por construcción (R1), n_pages y page_revisit_rate serían
# constantes (1 y 0) y no informativas; se dejan en NaN.
CAPABILITIES = {"click", "key", "scroll", "scroll_y", "mouse_move"}

_OVERRIDES = {c: pl.Float64 for c in ("emotions.joy", "emotions.sadness", "emotions.anger", "emotions.fear",
                                      "emotions.disgust", "emotions.surprise", "emotions.contempt",
                                      "emotions.valence", "emotions.engagement")}


def _scan() -> pl.LazyFrame:
    path = config.source_path(SOURCE) / "interactions.csv"
    return pl.scan_csv(path, schema_overrides=_OVERRIDES).select(
        "user_id", "timestamp", "url", "mouse.position.x", "mouse.position.y", "mouse.clicks",
        "keyboard", "scroll.absolute.y", "emotions.exist", "emotions.valence", "emotions.engagement",
    )


def build() -> tuple[pd.DataFrame, pd.DataFrame]:
    gap_ms = config.params()["session_gap_minutes"] * 60_000
    lf = _scan().sort(["user_id", "timestamp"])
    prev = lambda c: pl.col(c).shift(1).over("user_id")  # noqa: E731
    lf = lf.with_columns(
        new_visit=(pl.col("url") != prev("url")).fill_null(True)
        | ((pl.col("timestamp") - prev("timestamp")) > gap_ms).fill_null(True),
    ).with_columns(visit=pl.col("new_visit").cast(pl.Int32).cum_sum().over("user_id"))
    lf = lf.with_columns(
        session_id=pl.lit(SOURCE + ":") + pl.col("user_id") + pl.lit("/") + pl.col("visit").cast(pl.Utf8),
    )
    sp = lambda c: pl.col(c).shift(1).over("session_id")  # noqa: E731
    lf = lf.with_columns(
        click_on=pl.col("mouse.clicks") & ~sp("mouse.clicks").fill_null(False),
        key_on=pl.col("keyboard") & ~sp("keyboard").fill_null(False),
        sc_change=(pl.col("scroll.absolute.y") != sp("scroll.absolute.y")).fill_null(False),
        mv=((pl.col("mouse.position.x") != sp("mouse.position.x"))
            | (pl.col("mouse.position.y") != sp("mouse.position.y"))).fill_null(False),
        first=pl.col("new_visit"),
    ).with_columns(sc_on=pl.col("sc_change") & ~pl.col("sc_change").shift(1).over("session_id").fill_null(False))
    df = lf.collect(engine="streaming")

    # ---- sesiones ----
    emo = pl.col("emotions.exist").fill_null(False)
    sess = df.group_by("session_id").agg(
        participant_id=pl.col("user_id").first(), url=pl.col("url").first(),
        start_ms=pl.col("timestamp").min(), end_ms=pl.col("timestamp").max(),
        emotion_valence_mean=pl.col("emotions.valence").filter(emo).mean(),
        emotion_engagement_mean=pl.col("emotions.engagement").filter(emo).mean(),
        emotion_samples=emo.sum(),
    ).to_pandas()
    sess["source"] = SOURCE
    sess["url_domain"] = sess.pop("url").map(lambda u: urlparse(u).netloc if isinstance(u, str) else None)
    sess = sess.assign(user_group="unknown", is_human=True, assistive_tech="unknown", browser="unknown")

    # ---- eventos canónicos ----
    base = ["session_id", "timestamp", "url"]
    parts = [
        df.filter(pl.col("first")).select(base).with_columns(event=pl.lit("page_view")),
        df.filter(pl.col("click_on")).select(base + ["mouse.position.x", "mouse.position.y"]).with_columns(event=pl.lit("click")),
        df.filter(pl.col("key_on")).select(base).with_columns(event=pl.lit("key")),
        df.filter(pl.col("sc_on")).select(base).with_columns(event=pl.lit("scroll")),
        df.filter(pl.col("sc_change")).select(base + ["scroll.absolute.y"]).with_columns(event=pl.lit("scroll_pos")),
        df.filter(pl.col("mv")).select(base + ["mouse.position.x", "mouse.position.y"]).with_columns(event=pl.lit("mouse_move")),
    ]
    ev = pl.concat(parts, how="diagonal").rename({
        "timestamp": "ts_ms", "mouse.position.x": "x", "mouse.position.y": "y", "scroll.absolute.y": "scroll_y",
    }).with_columns(source=pl.lit(SOURCE)).to_pandas()
    return events.session_frame(sess), events.frame(ev)
