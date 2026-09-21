#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DatasetRule:
    dataset_id: str
    source_names: tuple[str, ...]
    dest_name: str
    priority: str
    similarity: str
    mode: str
    note: str = ""


RULES = [
    DatasetRule("AMUSED", ("AMUSED",), "01_amused", "P1", "ALTA", "all",
                "Pendiente de acceso; si después aparece en la carpeta fuente, este mismo script lo copiará."),
    DatasetRule("ZENODO_21891322", ("Zenodo 21891322", "21891322"), "02_zenodo_21891322", "P1", "ALTA", "all"),
    DatasetRule("VT_29042675", ("29042675",), "03_29042675", "P1", "ALTA", "all"),
    DatasetRule("CATCHING_UX_FLAWS", ("Catching UX Flaws",), "04_catching_ux_flaws", "P1", "ALTA", "catching",
                "Conserva README, notebook y results/*.json; omite graphs/ y static/."),
    DatasetRule("SERENE", ("SERENE",), "05_serene", "P1", "ALTA", "all"),
    DatasetRule("P3M", ("P3M",), "06_p3m", "P2", "ALTA", "all"),
    DatasetRule("PHR", ("PHR",), "07_phr", "P2", "ALTA", "all"),
    DatasetRule("DASHBOARDS", ("Dashboards",), "08_dashboards", "P2", "ALTA", "all",
                "Interaction Data.zip se mantiene comprimido en raw."),
    DatasetRule("CULTURAL_HERITAGE", ("Cultural Heritage", "Cultural_Heritage"), "09_cultural_heritage", "P2", "ALTA", "all",
                "Si no existe la carpeta del dataset y solo está el PDF de Hoang, se marca como referencia."),
    DatasetRule("UICRIT_RICO", ("RICO + uicrit", "RICO + UICrit", "UICrit + RICO"), "10_uicrit_rico", "P2", "ALTA", "rico",
                "Por defecto no copia traces.tar.gz; usa --include-rico-traces para incluirlo."),
]


def sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def find_source_folder(root: Path, names: tuple[str, ...]) -> Path | None:
    for name in names:
        p = root / name
        if p.is_dir():
            return p
    return None


def selected_files(rule: DatasetRule, folder: Path, include_rico_traces: bool) -> list[Path]:
    if rule.mode == "all":
        return sorted(p for p in folder.rglob("*") if p.is_file())

    if rule.mode == "catching":
        files = []
        for name in ("README.md", "analysis.ipynb"):
            p = folder / name
            if p.is_file():
                files.append(p)
        results = folder / "results"
        if results.is_dir():
            files.extend(p for p in results.rglob("*.json") if p.is_file())
        return sorted(set(files))

    if rule.mode == "rico":
        files = []
        for name in ("uicrit_public.csv", "ui_details.csv", "app_details.csv", "unique_uis.tar.gz"):
            p = folder / name
            if p.is_file():
                files.append(p)

        vec_dir = folder / "ui_layout_vectors"
        if vec_dir.is_dir():
            files.extend(p for p in vec_dir.rglob("*") if p.is_file())

        dup = folder / "app_details (1).csv"
        canonical = folder / "app_details.csv"
        if dup.is_file():
            if canonical.is_file():
                same = dup.stat().st_size == canonical.stat().st_size and sha256(dup) == sha256(canonical)
                if not same:
                    files.append(dup)
            else:
                files.append(dup)

        if include_rico_traces:
            traces = folder / "traces.tar.gz"
            if traces.is_file():
                files.append(traces)

        return sorted(set(files))

    raise ValueError(rule.mode)


def human_size(n: int) -> str:
    size = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{n} B"


def copy_file(src: Path, dst: Path, apply: bool) -> str:
    if dst.exists() and dst.stat().st_size == src.stat().st_size:
        return "SKIP_EXISTS_SAME_SIZE"
    if not apply:
        return "WOULD_COPY"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return "COPIED"


def write_csv(path: Path, rows: list[dict], fields: list[str], apply: bool):
    if not apply:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--dest", required=True, type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--include-rico-traces", action="store_true")
    args = parser.parse_args()

    source = args.source.expanduser().resolve()
    dest = args.dest.expanduser().resolve()

    if not source.is_dir():
        raise SystemExit(f"No existe la carpeta fuente: {source}")

    print(f"Modo: {'APPLY' if args.apply else 'DRY-RUN'}")
    print(f"Fuente: {source}")
    print(f"Destino: {dest}")
    print("Este script NO elimina ni modifica los originales.\n")

    manifest, summary = [], []

    for rule in RULES:
        src_folder = find_source_folder(source, rule.source_names)
        if src_folder is None:
            status = "PENDING_ACCESS" if rule.dataset_id == "AMUSED" else "MISSING"
            if rule.dataset_id == "CULTURAL_HERITAGE":
                status = "MISSING_DATASET_FOLDER"
            summary.append({
                "dataset_id": rule.dataset_id, "priority": rule.priority, "similarity": rule.similarity,
                "source_folder": "", "dest_folder": str(dest / rule.dest_name), "status": status,
                "selected_files": 0, "selected_bytes": 0, "selected_size": "0 B", "note": rule.note
            })
            print(f"[{status}] {rule.dataset_id}")
            continue

        files = selected_files(rule, src_folder, args.include_rico_traces)
        total = sum(p.stat().st_size for p in files)
        print(f"[FOUND] {rule.dataset_id}: {len(files)} archivos, {human_size(total)}")

        for src in files:
            rel = src.relative_to(src_folder)
            dst = dest / rule.dest_name / rel
            action = copy_file(src, dst, args.apply)
            manifest.append({
                "dataset_id": rule.dataset_id, "priority": rule.priority, "similarity": rule.similarity,
                "source_file": str(src), "relative_file": str(rel), "dest_file": str(dst),
                "size_bytes": src.stat().st_size, "action": action
            })

        summary.append({
            "dataset_id": rule.dataset_id, "priority": rule.priority, "similarity": rule.similarity,
            "source_folder": str(src_folder), "dest_folder": str(dest / rule.dest_name),
            "status": "COPIED_OR_PRESENT" if args.apply else "READY_TO_COPY",
            "selected_files": len(files), "selected_bytes": total, "selected_size": human_size(total), "note": rule.note
        })

    hoang = source / "hoang-identificationofusability-2021.pdf"
    if hoang.is_file():
        dst = dest / "_references" / "cultural_heritage" / hoang.name
        action = copy_file(hoang, dst, args.apply)
        manifest.append({
            "dataset_id": "CULTURAL_HERITAGE_REFERENCE", "priority": "P2", "similarity": "ALTA_REFERENCIA",
            "source_file": str(hoang), "relative_file": hoang.name, "dest_file": str(dst),
            "size_bytes": hoang.stat().st_size, "action": action
        })
        print("[REFERENCE] hoang-identificationofusability-2021.pdf")

    manifest_dir = dest / "_manifests"
    write_csv(manifest_dir / "dataset_copy_manifest.csv", manifest,
              ["dataset_id","priority","similarity","source_file","relative_file","dest_file","size_bytes","action"], args.apply)
    write_csv(manifest_dir / "dataset_copy_summary.csv", summary,
              ["dataset_id","priority","similarity","source_folder","dest_folder","status","selected_files","selected_bytes","selected_size","note"], args.apply)

    print("\nResumen")
    print("-------")
    print("Datasets definidos:", len(RULES))
    print("Archivos seleccionados:", sum(r["selected_files"] for r in summary))
    print("Tamaño seleccionado:", human_size(sum(r["selected_bytes"] for r in summary)))
    if not args.apply:
        print("\nNo se copió nada. Revisa y ejecuta otra vez con --apply.")
    else:
        print("\nCopia terminada.")
        print("Manifiestos:", manifest_dir)


if __name__ == "__main__":
    main()
