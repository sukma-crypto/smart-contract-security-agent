"""Konversi naskah, template jurnal tujuan, dan penerjemahan dwibahasa.

Bagian 4.8 dan bagian Dua Bahasa pada 4.1.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .. import db
from ..core import conversion, glossary, journals
from ..core.llm import services
from ..core.manuscript import load_manuscript
from .deps import charge_for, get_conn, get_project, guard, project_work_type

router = APIRouter(tags=["publikasi"])


class ConversionRequest(BaseModel):
    target_words: int = 6000


class ApplyConversionRequest(BaseModel):
    target_words: int = 6000
    name: str | None = None
    work_type: str = "artikel_jurnal"


class CondenseRequest(BaseModel):
    text: str
    section_name: str
    budget_words: int
    source_section: str = ""


class ReadinessRequest(BaseModel):
    profile: str = "sinta_umum"
    keywords: list[str] | None = None


class ApplyProfileRequest(BaseModel):
    profile: str


class TranslateRequest(BaseModel):
    text: str
    direction: str = "id-en"


class TerminologyRequest(BaseModel):
    indonesian: str
    english: str


# --- Konversi naskah ---------------------------------------------------------


@router.post("/projects/{project_id}/conversion/plan")
def plan_conversion(
    payload: ConversionRequest,
    conn: sqlite3.Connection = Depends(get_conn),
    project: dict = Depends(get_project),
) -> dict:
    """Rencana pemadatan tugas akhir menjadi artikel, sebelum apa pun diubah."""
    project_id = project["id"]
    work_type = project_work_type(project)
    if work_type.family.value == "artikel_publikasi":
        raise HTTPException(
            400,
            f"Proyek ini sudah berupa {work_type.label}. Konversi naskah berlaku untuk "
            f"tugas akhir atau proposal yang akan dijadikan artikel.",
        )

    manuscript = load_manuscript(conn, project_id)
    if not manuscript.word_count:
        raise HTTPException(
            400, "Naskah sumber masih kosong; belum ada yang bisa dipadatkan."
        )
    plan = conversion.plan_conversion(manuscript, target_words=payload.target_words)
    charge_for(conn, project, "rencana_konversi")
    return plan.to_dict()


@router.post("/projects/{project_id}/conversion/apply", status_code=201)
def apply_conversion(
    payload: ApplyConversionRequest,
    conn: sqlite3.Connection = Depends(get_conn),
    project: dict = Depends(get_project),
) -> dict:
    """Bangun proyek artikel baru dari rencana konversi."""
    manuscript = load_manuscript(conn, project["id"])
    if not manuscript.word_count:
        raise HTTPException(400, "Naskah sumber masih kosong.")

    plan = conversion.plan_conversion(manuscript, target_words=payload.target_words)
    result = conversion.apply_conversion(
        conn, project, plan, name=payload.name, work_type_key=payload.work_type
    )
    charge_for(conn, project, "rencana_konversi")
    return result


@router.post("/projects/{project_id}/conversion/condense")
def condense(
    payload: CondenseRequest,
    conn: sqlite3.Connection = Depends(get_conn),
    project: dict = Depends(get_project),
) -> dict:
    """Padatkan satu bagian saja — bukan seluruh artikel sekali jalan."""
    result = guard(
        services.condense_section,
        payload.text,
        payload.section_name,
        payload.budget_words,
        payload.source_section,
    )
    if result.source == "model":
        charge_for(conn, project, "konversi_naskah")
    return result.to_dict()


# --- Template jurnal tujuan --------------------------------------------------


@router.get("/journals")
def list_journal_profiles() -> dict:
    return {
        "profiles": [p.to_dict() for p in journals.BUILTIN_PROFILES.values()],
        "note": (
            "Profil bawaan mewakili pola yang paling umum. Untuk jurnal tertentu, "
            "unggah pedoman penulisnya lewat langkah 2 agar aturannya terbaca persis."
        ),
    }


@router.post("/projects/{project_id}/journal/readiness")
def journal_readiness(
    payload: ReadinessRequest,
    conn: sqlite3.Connection = Depends(get_conn),
    project: dict = Depends(get_project),
) -> dict:
    """Periksa kesiapan naskah terhadap ketentuan jurnal tujuan."""
    project_id = project["id"]
    try:
        profile = journals.get_profile(payload.profile)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc

    manuscript = load_manuscript(conn, project_id)
    report = journals.check_readiness(manuscript, profile, keywords=payload.keywords)
    charge_for(conn, project, "cek_jurnal")
    return {**report.to_dict(), "profile_detail": profile.to_dict()}


@router.post("/projects/{project_id}/journal/apply")
def apply_journal_profile(
    payload: ApplyProfileRequest,
    conn: sqlite3.Connection = Depends(get_conn),
    project: dict = Depends(get_project),
) -> dict:
    """Jadikan ketentuan jurnal sebagai aturan yang mengikat seluruh keluaran."""
    from ..core.guidelines import save_ruleset

    project_id = project["id"]
    try:
        profile = journals.get_profile(payload.profile)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc

    rules = profile.to_ruleset()
    ruleset_id = save_ruleset(conn, project_id, rules)
    db.update(
        conn, "projects", project_id, citation_style=profile.citation_style, updated_at=db.now()
    )
    return {
        "ruleset_id": ruleset_id,
        "rules": rules.to_dict(),
        "profile": profile.to_dict(),
        "note": (
            f"Naskah kini dirakit mengikuti ketentuan {profile.name}: struktur bagian, "
            f"gaya sitasi {profile.citation_style.upper()}, dan batas panjangnya."
        ),
    }


# --- Dua bahasa --------------------------------------------------------------


@router.post("/projects/{project_id}/translate")
def translate(
    payload: TranslateRequest,
    conn: sqlite3.Connection = Depends(get_conn),
    project: dict = Depends(get_project),
) -> dict:
    """Terjemahkan dengan padanan istilah teknis yang dijaga glosarium."""
    if payload.direction not in ("id-en", "en-id"):
        raise HTTPException(400, "Arah terjemahan harus 'id-en' atau 'en-id'.")
    result = services.translate(
        payload.text, direction=payload.direction, field_of_study=project.get("field_of_study")
    )
    if result.source == "model":
        charge_for(conn, project, "terjemahan")
    return result.to_dict()


@router.post("/projects/{project_id}/terminology")
def check_terminology(
    payload: TerminologyRequest,
    conn: sqlite3.Connection = Depends(get_conn),
    project: dict = Depends(get_project),
) -> dict:
    """Periksa konsistensi istilah teknis antara abstrak Indonesia dan Inggris."""
    charge_for(conn, project, "glosarium")
    return glossary.check_translation(
        payload.indonesian, payload.english, field_of_study=project.get("field_of_study")
    )


@router.get("/glossary")
def get_glossary(field_of_study: str | None = None) -> dict:
    terms = glossary.build_glossary(field_of_study)
    return {
        "field_of_study": field_of_study,
        "count": len(terms),
        "fields_available": sorted(glossary.BIDANG),
        "terms": terms,
    }
