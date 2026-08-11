"""Pustaka proyek: kumpulan referensi satu proyek dan perakitan daftar pustaka.

Aturan yang tidak bisa dimatikan: sebuah referensi hanya berstatus terverifikasi
bila metadatanya berasal dari basis data ilmiah resmi. Referensi hasil unggahan
mandiri tetap tersimpan dan tetap bisa dikutip, tetapi ditandai jelas agar
pengguna tahu mana yang belum tertelusur ke sumber resmi.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from ... import db
from . import sources
from .styles import CSL, build_index_map, get_style, render_bibliography

REF_JSON_FIELDS = ("csl_json",)


def _unique_citekey(conn: sqlite3.Connection, project_id: int, base: str) -> str:
    existing = {
        row["citekey"]
        for row in db.fetch_all(conn, "SELECT citekey FROM refs WHERE project_id = ?", (project_id,))
    }
    if base not in existing:
        return base
    for suffix in "abcdefghijklmnopqrstuvwxyz":
        candidate = f"{base}{suffix}"
        if candidate not in existing:
            return candidate
    index = 2
    while f"{base}-{index}" in existing:
        index += 1
    return f"{base}-{index}"


def add_reference(
    conn: sqlite3.Connection,
    project_id: int,
    entry: CSL,
    source_db: str,
    external_id: str = "",
    abstract: str = "",
    pdf_path: str | None = None,
    citekey: str | None = None,
) -> dict:
    """Masukkan satu referensi ke pustaka proyek.

    Status ``verified`` tidak diterima dari pemanggil — ia diturunkan dari asal
    metadatanya, sehingga tidak ada jalur kode yang bisa menandai referensi
    karangan sebagai terverifikasi.
    """
    verified = source_db in sources.OFFICIAL_SOURCES
    base_key = citekey or entry.get("id") or sources.suggest_citekey(entry)
    key = _unique_citekey(conn, project_id, base_key)
    entry = dict(entry)
    entry["id"] = key

    ref_id = db.insert(
        conn,
        "refs",
        project_id=project_id,
        citekey=key,
        source_db=source_db,
        external_id=external_id,
        csl_json=json.dumps(entry, ensure_ascii=False),
        verified=int(verified),
        abstract=abstract or "",
        pdf_path=pdf_path,
        added_at=db.now(),
    )
    return get_reference(conn, ref_id)


def get_reference(conn: sqlite3.Connection, ref_id: int) -> dict | None:
    row = db.fetch_one(conn, "SELECT * FROM refs WHERE id = ?", (ref_id,))
    return db.row_to_dict(row, REF_JSON_FIELDS)


def list_references(conn: sqlite3.Connection, project_id: int) -> list[dict]:
    rows = db.fetch_all(
        conn, "SELECT * FROM refs WHERE project_id = ? ORDER BY citekey", (project_id,)
    )
    return db.rows_to_dicts(rows, REF_JSON_FIELDS)


def entries_for_project(conn: sqlite3.Connection, project_id: int) -> list[CSL]:
    return [ref["csl_json"] for ref in list_references(conn, project_id)]


def entries_by_citekey(conn: sqlite3.Connection, project_id: int) -> dict[str, CSL]:
    return {ref["citekey"]: ref["csl_json"] for ref in list_references(conn, project_id)}


def delete_reference(conn: sqlite3.Connection, ref_id: int) -> None:
    conn.execute("DELETE FROM refs WHERE id = ?", (ref_id,))
    conn.commit()


def verify_reference(conn: sqlite3.Connection, ref_id: int) -> dict:
    """Coba telusuri referensi unggahan ke basis data resmi.

    Bila metadatanya cocok, status naik menjadi terverifikasi dan metadata resmi
    menggantikan hasil pembacaan PDF — yang kerap salah pada tahun dan halaman.
    """
    ref = get_reference(conn, ref_id)
    if ref is None:
        raise ValueError(f"Referensi {ref_id} tidak ditemukan.")
    if ref["verified"]:
        return ref

    entry = ref["csl_json"]
    doi = str(entry.get("DOI") or "").strip()
    match: sources.SearchResult | None = None
    if doi:
        match = sources.fetch_doi(doi)
    else:
        title = entry.get("title") or ""
        if not title:
            raise ValueError("Referensi tidak memiliki judul untuk ditelusuri.")
        candidates = sources.search_crossref(str(title), rows=3)
        match = _best_title_match(str(title), candidates)

    if match is None:
        return ref

    merged = dict(match.entry)
    merged["id"] = ref["citekey"]
    db.update(
        conn,
        "refs",
        ref_id,
        csl_json=json.dumps(merged, ensure_ascii=False),
        source_db=match.source_db,
        external_id=match.external_id,
        verified=1,
        abstract=ref.get("abstract") or match.abstract,
    )
    return get_reference(conn, ref_id)


def _best_title_match(title: str, candidates: list) -> Any | None:
    import difflib

    target = title.lower().strip()
    best, best_score = None, 0.0
    for candidate in candidates:
        candidate_title = str(candidate.entry.get("title", "")).lower().strip()
        score = difflib.SequenceMatcher(None, target, candidate_title).ratio()
        if score > best_score:
            best, best_score = candidate, score
    return best if best_score >= 0.87 else None


def store_chunks(conn: sqlite3.Connection, ref_id: int, chunks: list[dict]) -> int:
    conn.execute("DELETE FROM ref_chunks WHERE ref_id = ?", (ref_id,))
    for chunk in chunks:
        conn.execute(
            "INSERT INTO ref_chunks (ref_id, page, ordinal, text) VALUES (?, ?, ?, ?)",
            (ref_id, chunk.get("page"), chunk.get("ordinal", 0), chunk["text"]),
        )
    conn.commit()
    return len(chunks)


def build_bibliography(
    conn: sqlite3.Connection,
    project_id: int,
    style_key: str,
    order: list[str] | None = None,
    ruleset: dict | None = None,
    only_cited: bool = True,
) -> dict:
    """Rakit daftar pustaka yang selalu sinkron dengan sitasi dalam teks."""
    style = get_style(style_key, ruleset)
    all_entries = entries_by_citekey(conn, project_id)
    order = order or []

    if only_cited:
        entries = [all_entries[k] for k in order if k in all_entries]
    else:
        entries = list(all_entries.values())

    return {
        "style": style.key,
        "style_label": style.label,
        "numeric": style.numeric,
        "entries": render_bibliography(style, entries, order=order),
        "index_map": build_index_map(style, order),
        "uncited": sorted(set(all_entries) - set(order)),
        # Metadata mentah seluruh pustaka, dipakai perender sitasi dalam teks.
        "csl_entries": list(all_entries.values()),
    }
