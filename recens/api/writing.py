"""Langkah 4 & 5: menyusun kerangka dan menulis di editor."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .. import db
from ..core.citations.library import entries_by_citekey
from ..core.llm import services
from ..core.llm.guardrails import describe_limits
from ..core.manuscript import (
    create_sections_from_template,
    load_manuscript,
    make_citation_marker,
)
from ..core.worktypes import SectionTemplate
from .deps import charge_for, get_conn, get_project, guard, project_work_type

router = APIRouter(tags=["penulisan"])


class ContinueRequest(BaseModel):
    context: str
    section_id: int | None = None


class ParaphraseRequest(BaseModel):
    text: str
    instruction: str = ""


class LanguageRequest(BaseModel):
    text: str


class OutlineRequest(BaseModel):
    reset: bool = False
    target_words: int | None = None


class CiteRequest(BaseModel):
    citekey: str
    locator: str | None = None


@router.post("/projects/{project_id}/continue")
def continue_sentence(
    project_id: int, payload: ContinueRequest, conn: sqlite3.Connection = Depends(get_conn)
) -> dict:
    """Lanjutan kalimat — menghapus kebuntuan halaman kosong."""
    project = get_project(project_id, conn)
    work_type = project_work_type(project)

    section_title = ""
    if payload.section_id:
        row = db.fetch_one(
            conn, "SELECT title FROM sections WHERE id = ?", (payload.section_id,)
        )
        section_title = row["title"] if row else ""

    citekeys = set(entries_by_citekey(conn, project_id))
    result = guard(
        services.continue_sentence,
        payload.context,
        section_title=section_title,
        work_type_label=work_type.label,
        citekeys=citekeys,
    )
    if result.text:
        charge_for(conn, project, "lanjutan_kalimat")
    return result.to_dict()


@router.post("/projects/{project_id}/paraphrase")
def paraphrase(
    project_id: int, payload: ParaphraseRequest, conn: sqlite3.Connection = Depends(get_conn)
) -> dict:
    """Parafrase disertai penjelasan alasan perubahan."""
    project = get_project(project_id, conn)
    result = guard(services.paraphrase, payload.text, payload.instruction)
    if result.source == "model":
        charge_for(conn, project, "parafrase")
    return result.to_dict()


@router.post("/projects/{project_id}/language")
def academic_language(
    project_id: int, payload: LanguageRequest, conn: sqlite3.Connection = Depends(get_conn)
) -> dict:
    """Penyuntingan sesuai kaidah PUEBI/EYD."""
    project = get_project(project_id, conn)
    result = services.academic_language(payload.text)
    if result.source == "model":
        charge_for(conn, project, "bahasa_akademik")
    return result.to_dict()


@router.get("/templates")
def list_templates() -> dict:
    """Template siap pakai untuk bagian standar."""
    return {
        "templates": [
            {"role": role, "label": value["label"], "outline": value["outline"]}
            for role, value in services.SECTION_TEMPLATES.items()
        ]
    }


@router.get("/templates/{role}")
def get_template(role: str) -> dict:
    try:
        return services.section_template(role)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/projects/{project_id}/outline/generate")
def generate_outline(
    project_id: int, payload: OutlineRequest, conn: sqlite3.Connection = Depends(get_conn)
) -> dict:
    """Bangun kerangka mengikuti struktur yang berlaku pada jenis karya ini."""
    project = get_project(project_id, conn)
    work_type = project_work_type(project)
    target = payload.target_words or project["target_words"] or work_type.default_target_words

    existing = db.fetch_one(
        conn, "SELECT COUNT(*) AS n FROM sections WHERE project_id = ?", (project_id,)
    )["n"]
    if existing and not payload.reset:
        raise HTTPException(
            409,
            "Kerangka sudah ada. Kirim reset=true untuk membangun ulang — seluruh isi "
            "bagian yang sudah ditulis akan ikut terhapus, jadi simpan versi lebih dahulu.",
        )
    if payload.reset:
        conn.execute("DELETE FROM sections WHERE project_id = ?", (project_id,))
        conn.commit()

    created = create_sections_from_template(conn, project_id, work_type.structure, target)
    db.update(conn, "projects", project_id, target_words=target, updated_at=db.now())
    manuscript = load_manuscript(conn, project_id)
    return {
        "created": len(created),
        "target_words": target,
        "sections": [
            {
                "id": s.id,
                "number": s.number,
                "title": s.title,
                "role": s.role,
                "target_words": s.target_words,
                "level": s.level,
            }
            for s in manuscript.walk()
        ],
    }


@router.post("/projects/{project_id}/cite-marker")
def build_cite_marker(
    project_id: int, payload: CiteRequest, conn: sqlite3.Connection = Depends(get_conn)
) -> dict:
    """Bentuk penanda sitasi yang siap disisipkan ke naskah.

    Penanda hanya dibuat untuk citekey yang benar-benar ada di pustaka proyek,
    sehingga sitasi dalam teks tidak pernah menunjuk sumber yang tidak ada.
    """
    get_project(project_id, conn)
    entries = entries_by_citekey(conn, project_id)
    if payload.citekey not in entries:
        raise HTTPException(
            404,
            f"Citekey '{payload.citekey}' tidak ada di pustaka proyek. Tambahkan "
            f"referensinya lebih dahulu lewat pencarian literatur atau DOI.",
        )
    return {
        "marker": make_citation_marker(payload.citekey, payload.locator),
        "citekey": payload.citekey,
    }


@router.get("/limits")
def product_limits() -> dict:
    """Batas produk yang melekat dan tidak dapat dimatikan."""
    return {
        "limits": describe_limits(),
        "note": "Batasan berikut melekat pada produk dan tidak dapat dimatikan.",
    }
