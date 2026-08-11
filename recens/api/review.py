"""Langkah 7 & 8: memeriksa naskah, mengelola revisi, ekspor, dan submisi."""

from __future__ import annotations

import json
import sqlite3
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .. import db
from ..config import get_settings
from ..core import annotations as annots
from ..core import checks as check_pack
from ..core.citations.library import build_bibliography
from ..core.exporters import EXPORTERS
from ..core.guidelines import active_ruleset
from ..core.llm import services
from ..core.manuscript import load_manuscript
from .deps import (
    charge_for,
    get_conn,
    get_project,
    project_rules,
    project_work_type,
    upload_path,
)

router = APIRouter(tags=["periksa"])

CHECK_KINDS = ("bahasa", "sitasi", "konsistensi", "kemiripan", "batas")


class RevisionCreate(BaseModel):
    text: str
    source: str = "pembimbing"
    author: str | None = None
    section_id: int | None = None
    block_id: int | None = None


class RevisionUpdate(BaseModel):
    status: str | None = None
    text: str | None = None
    section_id: int | None = None


class SupervisionCreate(BaseModel):
    met_on: str
    supervisor: str | None = None
    notes: str = ""
    achievements: str = ""


class ExportRequest(BaseModel):
    format: str = "docx"
    meta: dict = Field(default_factory=dict)
    style: str | None = None
    include_front_matter: bool = True


class AbstractRequest(BaseModel):
    sections: list[str] | None = None
    max_words: int = 250


class CoverLetterRequest(BaseModel):
    journal: str
    novelty: str = ""
    summary: str = ""
    scope_fit: str = ""
    author: str = ""
    affiliation: str = ""
    email: str = ""


class ReviewerResponseRequest(BaseModel):
    comments: list[dict]


# --- Langkah 7: pemeriksaan naskah ------------------------------------------


@router.post("/projects/{project_id}/checks")
def run_checks(
    project_id: int,
    kinds: str = "all",
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
    """Jalankan pemeriksaan naskah sebelum diserahkan."""
    project = get_project(project_id, conn)
    work_type = project_work_type(project)
    rules = project_rules(conn, project)
    manuscript = load_manuscript(conn, project_id)

    selected = CHECK_KINDS if kinds == "all" else tuple(k.strip() for k in kinds.split(","))
    unknown = [k for k in selected if k not in CHECK_KINDS]
    if unknown:
        raise HTTPException(
            400, f"Pemeriksaan tidak dikenal: {', '.join(unknown)}. Pilihan: {', '.join(CHECK_KINDS)}."
        )

    results: dict = {}
    if "bahasa" in selected:
        results["bahasa"] = check_pack.check_language(manuscript)
    if "sitasi" in selected:
        results["sitasi"] = check_pack.check_citation_crossref(conn, project_id, manuscript)
    if "konsistensi" in selected:
        results["konsistensi"] = check_pack.check_consistency(manuscript)
    if "kemiripan" in selected:
        results["kemiripan"] = check_pack.check_similarity(conn, project_id, manuscript)
    if "batas" in selected:
        results["batas"] = check_pack.check_length_limits(manuscript, rules, work_type)

    for kind, result in results.items():
        db.insert(
            conn,
            "checks",
            project_id=project_id,
            kind=kind,
            result_json=json.dumps(result, ensure_ascii=False),
            created_at=db.now(),
        )
    charge_for(conn, project, "cek_naskah")

    return {
        "checks": results,
        "summary": _summarize(results),
        "ran_at": db.now(),
    }


def _summarize(results: dict) -> dict:
    problems = []
    if "bahasa" in results:
        high = results["bahasa"]["by_severity"].get("tinggi", 0)
        problems.append(
            {
                "kind": "bahasa",
                "count": results["bahasa"]["total"],
                "critical": high,
                "passed": high == 0,
            }
        )
    for kind in ("sitasi", "konsistensi", "batas"):
        if kind in results:
            issues = results[kind].get("issues", [])
            problems.append(
                {
                    "kind": kind,
                    "count": len(issues),
                    "critical": sum(1 for i in issues if i.get("severity") == "tinggi"),
                    "passed": results[kind].get("passed", False),
                }
            )
    if "kemiripan" in results:
        problems.append(
            {
                "kind": "kemiripan",
                "count": results["kemiripan"]["n_matches"],
                "critical": 0,
                "passed": results["kemiripan"]["passed"],
                "percent": results["kemiripan"]["similarity_percent"],
            }
        )
    return {
        "ready_to_submit": all(p["passed"] for p in problems) if problems else False,
        "areas": problems,
    }


@router.get("/projects/{project_id}/checks")
def check_history(
    project_id: int, kind: str | None = None, conn: sqlite3.Connection = Depends(get_conn)
) -> list[dict]:
    get_project(project_id, conn)
    sql = "SELECT * FROM checks WHERE project_id = ?"
    params: list = [project_id]
    if kind:
        sql += " AND kind = ?"
        params.append(kind)
    sql += " ORDER BY id DESC LIMIT 30"
    return db.rows_to_dicts(db.fetch_all(conn, sql, params), ("result_json",))


# --- Langkah 8: revisi & bimbingan ------------------------------------------


@router.post("/projects/{project_id}/revisions", status_code=201)
def create_revision(
    project_id: int, payload: RevisionCreate, conn: sqlite3.Connection = Depends(get_conn)
) -> dict:
    """Catatan dosen atau reviewer dicatat sebagai daftar tugas berstatus."""
    get_project(project_id, conn)
    revision_id = db.insert(
        conn,
        "revisions",
        project_id=project_id,
        section_id=payload.section_id,
        block_id=payload.block_id,
        source=payload.source,
        author=payload.author,
        text=payload.text,
        status="terbuka",
        created_at=db.now(),
    )
    return {"id": revision_id}


@router.get("/projects/{project_id}/revisions")
def list_revisions(
    project_id: int, status: str | None = None, conn: sqlite3.Connection = Depends(get_conn)
) -> dict:
    get_project(project_id, conn)
    sql = (
        "SELECT r.*, s.title AS section_title FROM revisions r "
        "LEFT JOIN sections s ON s.id = r.section_id WHERE r.project_id = ?"
    )
    params: list = [project_id]
    if status:
        sql += " AND r.status = ?"
        params.append(status)
    sql += " ORDER BY CASE r.status WHEN 'terbuka' THEN 0 WHEN 'dikerjakan' THEN 1 ELSE 2 END, r.id"
    rows = [dict(r) for r in db.fetch_all(conn, sql, params)]
    by_status: dict[str, int] = {}
    for row in rows:
        by_status[row["status"]] = by_status.get(row["status"], 0) + 1
    return {"revisions": rows, "by_status": by_status, "total": len(rows)}


@router.patch("/revisions/{revision_id}")
def update_revision(
    revision_id: int, payload: RevisionUpdate, conn: sqlite3.Connection = Depends(get_conn)
) -> dict:
    row = db.fetch_one(conn, "SELECT * FROM revisions WHERE id = ?", (revision_id,))
    if row is None:
        raise HTTPException(404, f"Revisi {revision_id} tidak ditemukan.")
    values = payload.model_dump(exclude_none=True)
    if values.get("status") == "selesai":
        values["resolved_at"] = db.now()
    db.update(conn, "revisions", revision_id, **values)
    return dict(db.fetch_one(conn, "SELECT * FROM revisions WHERE id = ?", (revision_id,)))


@router.post("/projects/{project_id}/revisions/import", status_code=201)
async def import_revisions(
    project_id: int,
    file: UploadFile = File(...),
    source: str = Form("pembimbing"),
    author: str = Form(""),
    dry_run: bool = Form(False),
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
    """Ubah coretan dosen menjadi daftar revisi berstatus.

    Menerima PDF beranotasi dan dokumen Word berkomentar. Tiap komentar
    ditautkan ke bagian naskah yang paling mungkin dimaksud; yang tidak dapat
    ditautkan tetap dicatat tanpa lokasi, karena menempelkannya ke bagian yang
    keliru lebih menyesatkan.
    """
    project = get_project(project_id, conn)
    filename = file.filename or "catatan.pdf"
    destination = upload_path(project_id, filename, "bimbingan")
    destination.write_bytes(await file.read())

    manuscript = load_manuscript(conn, project_id)
    try:
        result = annots.import_comments(destination, manuscript)
    except annots.UnsupportedAnnotationSource as exc:
        destination.unlink(missing_ok=True)
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:  # pragma: no cover - berkas rusak
        destination.unlink(missing_ok=True)
        raise HTTPException(400, f"Berkas tidak dapat dibaca: {exc}") from exc

    created: list[int] = []
    if not dry_run:
        for comment in result.comments:
            text = comment.text
            if comment.anchor:
                text = f"{text}\n\n> {comment.anchor[:300]}"
            created.append(
                db.insert(
                    conn,
                    "revisions",
                    project_id=project_id,
                    section_id=comment.section_id,
                    block_id=comment.block_id,
                    source=source,
                    author=comment.author or author or None,
                    text=text,
                    status="terbuka",
                    created_at=db.now(),
                )
            )

    charge_for(conn, project, "impor_komentar")
    return {
        **result.to_dict(),
        "created": len(created),
        "revision_ids": created,
        "dry_run": dry_run,
        "source_file": filename,
    }


@router.post("/projects/{project_id}/supervision", status_code=201)
def add_supervision(
    project_id: int, payload: SupervisionCreate, conn: sqlite3.Connection = Depends(get_conn)
) -> dict:
    """Riwayat bimbingan: catatan dan capaian tiap sesi, berurutan."""
    get_project(project_id, conn)
    session_id = db.insert(
        conn,
        "supervision",
        project_id=project_id,
        met_on=payload.met_on,
        supervisor=payload.supervisor,
        notes=payload.notes,
        achievements=payload.achievements,
        created_at=db.now(),
    )
    return {"id": session_id}


@router.get("/projects/{project_id}/supervision")
def list_supervision(project_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> list[dict]:
    get_project(project_id, conn)
    rows = db.fetch_all(
        conn, "SELECT * FROM supervision WHERE project_id = ? ORDER BY met_on DESC", (project_id,)
    )
    return [dict(row) for row in rows]


@router.post("/projects/{project_id}/defense")
def defense_mode(project_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    """Mode siap sidang: pertanyaan penguji disusun dari titik rawan naskah."""
    project = get_project(project_id, conn)
    work_type = project_work_type(project)
    if not work_type.defense_mode:
        raise HTTPException(
            400,
            f"Mode siap sidang berlaku untuk skripsi, tesis, dan disertasi. Jenis karya "
            f"proyek ini adalah {work_type.label}.",
        )

    manuscript = load_manuscript(conn, project_id)
    rules = project_rules(conn, project)
    weak_points: list[dict] = []
    weak_points += check_pack.check_consistency(manuscript)["issues"]
    weak_points += check_pack.check_citation_crossref(conn, project_id, manuscript)["issues"]
    weak_points += check_pack.check_length_limits(manuscript, rules, work_type)["issues"]

    for row in db.fetch_all(
        conn, "SELECT result_json FROM analyses WHERE project_id = ? ORDER BY id DESC LIMIT 20",
        (project_id,),
    ):
        data = json.loads(row["result_json"])
        for warning in data.get("warnings", []):
            weak_points.append({"severity": "tinggi", "message": warning})

    result = services.defense_questions(manuscript, weak_points)
    if result.source == "model":
        charge_for(conn, project, "mode_sidang")
    return {
        "questions": result.meta.get("questions", []),
        "weak_points": weak_points,
        "source": result.source,
    }


# --- Ekspor ------------------------------------------------------------------


@router.post("/projects/{project_id}/export")
def export_project(
    project_id: int, payload: ExportRequest, conn: sqlite3.Connection = Depends(get_conn)
) -> dict:
    """Keluarkan naskah dalam keadaan sudah terformat penuh."""
    project = get_project(project_id, conn)
    work_type = project_work_type(project)
    exporter = EXPORTERS.get(payload.format)
    if exporter is None:
        raise HTTPException(
            400, f"Format '{payload.format}' tidak dikenal. Pilihan: {', '.join(EXPORTERS)}."
        )
    if payload.format not in work_type.export_formats:
        raise HTTPException(
            400,
            f"Format {payload.format} tidak berlaku untuk {work_type.label}. "
            f"Format yang tersedia: {', '.join(work_type.export_formats)}.",
        )

    rules = project_rules(conn, project)
    manuscript = load_manuscript(conn, project_id)
    bibliography = build_bibliography(
        conn,
        project_id,
        style_key=payload.style or project["citation_style"] or rules.citation_style,
        order=manuscript.citekeys(),
        ruleset=rules.to_dict(),
    )

    meta = {
        "title": project["name"],
        "year": date.today().year,
        "institution": "",
        **payload.meta,
    }
    settings = get_settings()
    suffix = {"docx": ".docx", "pdf": ".pdf", "latex": ".tex"}[payload.format]
    safe_name = "".join(c if c.isalnum() or c in "-_ " else "_" for c in project["name"])[:60]
    output = settings.exports_dir / f"{project_id}_{safe_name.strip() or 'naskah'}{suffix}"

    try:
        path = exporter(
            manuscript,
            rules,
            bibliography,
            meta,
            output,
            include_front_matter=payload.include_front_matter,
        )
    except Exception as exc:  # pragma: no cover
        raise HTTPException(500, f"Perakitan dokumen gagal: {exc}") from exc

    charge_for(conn, project, "ekspor")
    return {
        "format": payload.format,
        "path": str(path),
        "download_url": f"/api/projects/{project_id}/export/download?format={payload.format}",
        "size_bytes": path.stat().st_size,
        "applied_rules": {
            "page_size": rules.page_size,
            "margins": rules.margins.__dict__,
            "font": f"{rules.font_family} {rules.font_size_pt}pt",
            "line_spacing": rules.line_spacing,
            "citation_style": bibliography["style_label"],
            "front_matter_numbering": rules.front_matter_numbering,
            "body_numbering": rules.body_numbering,
        },
        "assumed_rules": rules.assumed,
    }


@router.get("/projects/{project_id}/export/download")
def download_export(
    project_id: int, format: str = "docx", conn: sqlite3.Connection = Depends(get_conn)
) -> FileResponse:
    project = get_project(project_id, conn)
    settings = get_settings()
    suffix = {"docx": ".docx", "pdf": ".pdf", "latex": ".tex"}.get(format)
    if suffix is None:
        raise HTTPException(400, f"Format '{format}' tidak dikenal.")
    safe_name = "".join(c if c.isalnum() or c in "-_ " else "_" for c in project["name"])[:60]
    path = settings.exports_dir / f"{project_id}_{safe_name.strip() or 'naskah'}{suffix}"
    if not path.exists():
        raise HTTPException(404, "Berkas ekspor belum dibuat. Jalankan ekspor lebih dahulu.")
    return FileResponse(path, filename=path.name)


# --- Publikasi & jurnal ------------------------------------------------------


@router.post("/projects/{project_id}/abstract")
def structured_abstract(
    project_id: int, payload: AbstractRequest, conn: sqlite3.Connection = Depends(get_conn)
) -> dict:
    project = get_project(project_id, conn)
    manuscript = load_manuscript(conn, project_id)
    result = services.structured_abstract(manuscript, payload.sections, payload.max_words)
    if result.source == "model":
        charge_for(conn, project, "abstrak_terstruktur")
    return result.to_dict()


@router.post("/projects/{project_id}/cover-letter")
def cover_letter(
    project_id: int, payload: CoverLetterRequest, conn: sqlite3.Connection = Depends(get_conn)
) -> dict:
    project = get_project(project_id, conn)
    meta = {**payload.model_dump(), "title": project["name"]}
    result = services.cover_letter(meta)
    if result.source == "model":
        charge_for(conn, project, "cover_letter")
    db.insert(
        conn,
        "submissions",
        project_id=project_id,
        venue=payload.journal,
        kind="cover_letter",
        content=result.text,
        meta_json=json.dumps(meta, ensure_ascii=False),
        created_at=db.now(),
    )
    return result.to_dict()


@router.post("/projects/{project_id}/reviewer-response")
def reviewer_response(
    project_id: int,
    payload: ReviewerResponseRequest,
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
    project = get_project(project_id, conn)
    result = services.reviewer_response(payload.comments)
    if result.source == "model":
        charge_for(conn, project, "respon_reviewer")

    # Tiap komentar reviewer juga masuk daftar revisi agar tidak ada yang terlewat.
    for comment in payload.comments:
        db.insert(
            conn,
            "revisions",
            project_id=project_id,
            section_id=None,
            block_id=None,
            source="reviewer",
            author=comment.get("reviewer"),
            text=comment.get("text", ""),
            status="terbuka",
            created_at=db.now(),
        )
    db.insert(
        conn,
        "submissions",
        project_id=project_id,
        venue=None,
        kind="response",
        content=result.text,
        meta_json=json.dumps({"n_comments": len(payload.comments)}, ensure_ascii=False),
        created_at=db.now(),
    )
    return result.to_dict()


@router.get("/projects/{project_id}/submissions")
def list_submissions(project_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> list[dict]:
    get_project(project_id, conn)
    rows = db.fetch_all(
        conn, "SELECT * FROM submissions WHERE project_id = ? ORDER BY id DESC", (project_id,)
    )
    return db.rows_to_dicts(rows, ("meta_json",))
