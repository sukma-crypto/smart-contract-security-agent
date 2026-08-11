"""Langkah 2 & 3: memuat aturan penulisan dan mengumpulkan referensi."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from .. import db
from ..core import documents, retrieval
from ..core.citations import library as reflib
from ..core.citations import sources
from ..core.guidelines import (
    RuleSet,
    active_ruleset,
    list_rulesets,
    parse_guidelines,
    save_ruleset,
    update_ruleset,
)
from ..core.llm import services
from ..core.manuscript import load_manuscript
from .deps import charge_for, get_conn, get_project, upload_path

router = APIRouter(tags=["pustaka"])


class GuidelineText(BaseModel):
    text: str
    name: str = "Pedoman"
    kind: str = "fakultas"


class ReferenceAdd(BaseModel):
    entry: dict
    source_db: str
    external_id: str = ""
    abstract: str = ""
    citekey: str | None = None


class DoiAdd(BaseModel):
    doi: str


class AskRequest(BaseModel):
    question: str
    ref_ids: list[int] | None = None
    top_k: int = 5


class SynthesisRequest(BaseModel):
    ref_ids: list[int] | None = None


# --- Langkah 2: aturan penulisan --------------------------------------------


@router.post("/projects/{project_id}/guidelines/upload", status_code=201)
async def upload_guidelines(
    project_id: int,
    file: UploadFile = File(...),
    name: str = Form("Pedoman penulisan"),
    kind: str = Form("fakultas"),
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
    """Baca PDF pedoman menjadi aturan yang mengikat seluruh keluaran."""
    get_project(project_id, conn)
    destination = upload_path(project_id, file.filename or "pedoman.pdf", "pedoman")
    destination.write_bytes(await file.read())

    try:
        parsed = documents.parse_document(destination)
    except (ValueError, documents.PdfSupportMissing) as exc:
        raise HTTPException(400, str(exc)) from exc

    rules = parse_guidelines(parsed.text, name=name, kind=kind)
    ruleset_id = save_ruleset(conn, project_id, rules, source_file=str(destination))
    return {
        "id": ruleset_id,
        "rules": rules.to_dict(),
        "pages_read": parsed.page_count,
        "assumed": rules.assumed,
        "note": (
            "Aturan yang tidak ditemukan di pedoman memakai nilai bawaan dan tercantum "
            "pada 'assumed'. Periksa dan perbaiki sebelum naskah dirakit."
        ),
    }


@router.post("/projects/{project_id}/guidelines/text", status_code=201)
def add_guidelines_text(
    project_id: int, payload: GuidelineText, conn: sqlite3.Connection = Depends(get_conn)
) -> dict:
    """Untuk instruksi dosen atau ketentuan panitia yang datang sebagai teks."""
    get_project(project_id, conn)
    rules = parse_guidelines(payload.text, name=payload.name, kind=payload.kind)
    ruleset_id = save_ruleset(conn, project_id, rules)
    return {"id": ruleset_id, "rules": rules.to_dict(), "assumed": rules.assumed}


@router.get("/projects/{project_id}/guidelines")
def get_guidelines(project_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    get_project(project_id, conn)
    return {
        "active": active_ruleset(conn, project_id).to_dict(),
        "history": list_rulesets(conn, project_id),
    }


@router.patch("/guidelines/{ruleset_id}")
def patch_guidelines(
    ruleset_id: int, patch: dict, conn: sqlite3.Connection = Depends(get_conn)
) -> dict:
    """Perbaiki aturan hasil pembacaan otomatis."""
    try:
        rules = update_ruleset(conn, ruleset_id, patch)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    return rules.to_dict()


# --- Langkah 3: referensi ----------------------------------------------------


@router.get("/references/search")
def search_references(
    q: str,
    rows: int = 10,
    providers: str | None = None,
    project_id: int | None = None,
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
    """Penelusuran serentak ke sumber nasional dan internasional."""
    chosen = providers.split(",") if providers else None
    if project_id:
        project = get_project(project_id, conn)
        charge_for(conn, project, "pencarian_literatur")
    return sources.search_all(q, rows=rows, providers=chosen)


@router.post("/projects/{project_id}/references", status_code=201)
def add_reference(
    project_id: int, payload: ReferenceAdd, conn: sqlite3.Connection = Depends(get_conn)
) -> dict:
    """Masukkan hasil pencarian ke pustaka proyek."""
    get_project(project_id, conn)
    reference = reflib.add_reference(
        conn,
        project_id,
        entry=payload.entry,
        source_db=payload.source_db,
        external_id=payload.external_id,
        abstract=payload.abstract,
        citekey=payload.citekey,
    )
    return reference


@router.post("/projects/{project_id}/references/doi", status_code=201)
def add_reference_by_doi(
    project_id: int, payload: DoiAdd, conn: sqlite3.Connection = Depends(get_conn)
) -> dict:
    """Tambah referensi lewat DOI — metadata ditarik langsung dari Crossref."""
    get_project(project_id, conn)
    try:
        result = sources.fetch_doi(payload.doi)
    except sources.SourceUnavailable as exc:
        raise HTTPException(404, str(exc)) from exc
    return reflib.add_reference(
        conn,
        project_id,
        entry=result.entry,
        source_db=result.source_db,
        external_id=result.external_id,
        abstract=result.abstract,
    )


@router.post("/projects/{project_id}/references/upload", status_code=201)
async def upload_reference_pdf(
    project_id: int,
    file: UploadFile = File(...),
    title: str = Form(""),
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
    """Unggah PDF sendiri; isinya diindeks agar bisa ditanyai.

    Metadata hasil pembacaan PDF ditandai belum terverifikasi sampai berhasil
    ditelusuri ke basis data resmi lewat endpoint verifikasi.
    """
    get_project(project_id, conn)
    destination = upload_path(project_id, file.filename or "referensi.pdf", "referensi")
    destination.write_bytes(await file.read())

    try:
        parsed = documents.parse_document(destination)
    except (ValueError, documents.PdfSupportMissing) as exc:
        raise HTTPException(400, str(exc)) from exc

    guessed_title = title or parsed.title or destination.stem
    entry = {
        "id": "",
        "type": "article-journal",
        "title": guessed_title,
        "author": [],
        "issued": {"date-parts": [[0]]},
    }
    doi = _find_doi(parsed.text)
    if doi:
        entry["DOI"] = doi

    reference = reflib.add_reference(
        conn,
        project_id,
        entry=entry,
        source_db="unggahan",
        external_id="",
        abstract=_first_abstract(parsed.text),
        pdf_path=str(destination),
    )
    chunks = documents.chunk_pages(parsed.pages)
    reflib.store_chunks(conn, reference["id"], chunks)

    return {
        **reference,
        "chunks": len(chunks),
        "pages": parsed.page_count,
        "doi_detected": doi,
        "note": (
            "Referensi ini belum terverifikasi. Jalankan verifikasi agar metadatanya "
            "ditarik dari basis data resmi — pembacaan PDF sering salah pada tahun dan "
            "halaman."
        ),
    }


def _find_doi(text: str) -> str:
    import re

    match = re.search(r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+\b", text or "")
    return match.group(0).rstrip(".") if match else ""


def _first_abstract(text: str) -> str:
    sections = documents.split_sections(text or "")
    for key in ("abstract", "abstrak"):
        if sections.get(key):
            return sections[key][:2000]
    return ""


@router.post("/references/{ref_id}/verify")
def verify_reference(ref_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    """Telusuri referensi unggahan ke basis data ilmiah resmi."""
    try:
        reference = reflib.verify_reference(conn, ref_id)
    except (ValueError, sources.SourceUnavailable) as exc:
        raise HTTPException(400, str(exc)) from exc
    if not reference["verified"]:
        return {
            **reference,
            "note": (
                "Metadata belum cocok dengan basis data resmi. Periksa ejaan judul, atau "
                "isi DOI-nya secara manual lalu ulangi verifikasi."
            ),
        }
    return reference


@router.get("/projects/{project_id}/references")
def get_references(project_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    get_project(project_id, conn)
    references = reflib.list_references(conn, project_id)
    return {
        "count": len(references),
        "verified": sum(1 for r in references if r["verified"]),
        "references": references,
    }


@router.delete("/references/{ref_id}", status_code=204)
def delete_reference(ref_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> None:
    reflib.delete_reference(conn, ref_id)


# --- Tanya Jurnal & Matriks Sintesis ----------------------------------------


@router.post("/projects/{project_id}/ask")
def ask_journal(
    project_id: int, payload: AskRequest, conn: sqlite3.Connection = Depends(get_conn)
) -> dict:
    """Bertanya atas isi jurnal di pustaka; jawaban disertai penunjuk halaman."""
    project = get_project(project_id, conn)
    hits = retrieval.search_chunks(
        conn, project_id, payload.question, top_k=payload.top_k, ref_ids=payload.ref_ids
    )
    if hits:
        charge_for(conn, project, "tanya_jurnal")
    result = services.ask_journal(payload.question, hits)
    return result.to_dict()


@router.post("/projects/{project_id}/synthesis")
def synthesis_matrix(
    project_id: int, payload: SynthesisRequest, conn: sqlite3.Connection = Depends(get_conn)
) -> dict:
    """Matriks sintesis: penulis, tahun, teori, metode, temuan, dan celah penelitian."""
    project = get_project(project_id, conn)
    references = reflib.list_references(conn, project_id)
    if payload.ref_ids:
        references = [r for r in references if r["id"] in payload.ref_ids]

    rows = []
    for reference in references:
        hits = retrieval.search_chunks(
            conn,
            project_id,
            "metode penelitian hasil temuan teori sampel",
            top_k=4,
            ref_ids=[reference["id"]],
        )
        if hits:
            charge_for(conn, project, "matriks_sintesis")
        rows.append(services.synthesis_row(reference, hits))

    return {
        "columns": ["penulis", "tahun", "judul", "teori", "metode", "sampel", "temuan", "celah"],
        "rows": rows,
        "count": len(rows),
    }


@router.get("/projects/{project_id}/bibliography")
def bibliography(
    project_id: int,
    style: str | None = None,
    only_cited: bool = True,
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
    """Daftar pustaka yang selalu sinkron dengan sitasi dalam teks."""
    project = get_project(project_id, conn)
    rules = active_ruleset(conn, project_id)
    manuscript = load_manuscript(conn, project_id)
    style_key = style or project["citation_style"] or rules.citation_style
    result = reflib.build_bibliography(
        conn,
        project_id,
        style_key=style_key,
        order=manuscript.citekeys(),
        ruleset=rules.to_dict(),
        only_cited=only_cited,
    )
    result.pop("csl_entries", None)
    return result
