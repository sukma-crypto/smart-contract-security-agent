"""Langkah 1 & 4: proyek, kerangka, naskah, versi, dan dashboard progres."""

from __future__ import annotations

import json
import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import db
from ..core import credits
from ..core.llm.guardrails import describe_limits
from ..core.manuscript import (
    build_default_outline,
    load_manuscript,
    restore_snapshot,
    section_outline,
    snapshot,
)
from ..core.worktypes import (
    RESEARCH_NEEDS,
    RESEARCH_TYPE_LABELS,
    STEPS,
    TREATMENT,
    WORK_TYPES,
    ResearchType,
    applicable_steps,
    get_work_type,
    requires_data_step,
)
from .deps import get_conn, get_project, project_work_type

router = APIRouter(tags=["proyek"])


# --- Skema -------------------------------------------------------------------


class ProjectCreate(BaseModel):
    name: str
    work_type: str
    research_type: str = "none"
    field_of_study: str | None = None
    target_words: int | None = None
    deadline: str | None = None
    citation_style: str | None = None
    account_id: int | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    research_type: str | None = None
    field_of_study: str | None = None
    target_words: int | None = None
    deadline: str | None = None
    citation_style: str | None = None


class SectionCreate(BaseModel):
    title: str
    parent_id: int | None = None
    role: str | None = None
    target_words: int = 0
    position: int | None = None


class SectionUpdate(BaseModel):
    title: str | None = None
    role: str | None = None
    target_words: int | None = None
    status: str | None = None
    position: int | None = None
    parent_id: int | None = None


class BlockCreate(BaseModel):
    kind: str = "paragraph"
    content: str = ""
    meta: dict = Field(default_factory=dict)
    position: int | None = None


class BlockUpdate(BaseModel):
    kind: str | None = None
    content: str | None = None
    meta: dict | None = None
    position: int | None = None


class VersionCreate(BaseModel):
    label: str = "Simpan manual"


# --- Katalog -----------------------------------------------------------------


@router.get("/catalog")
def catalog() -> dict:
    """Seluruh pilihan yang menentukan bentuk sebuah proyek."""
    return {
        "work_types": [
            {
                "key": wt.key,
                "label": wt.label,
                "family": wt.family.value,
                "ciri_khas": wt.ciri_khas,
                "fitur_utama": list(wt.fitur_utama),
                "default_target_words": wt.default_target_words,
                "hard_word_limit": wt.hard_word_limit,
                "citation_style": wt.citation_style,
                "export_formats": list(wt.export_formats),
                "supervision_tracking": wt.supervision_tracking,
                "defense_mode": wt.defense_mode,
                "submission_kit": wt.submission_kit,
                "structure": [s.title for s in wt.structure],
            }
            for wt in WORK_TYPES.values()
        ],
        "research_types": [
            {
                "key": rt.value,
                "label": RESEARCH_TYPE_LABELS[rt],
                "needs": RESEARCH_NEEDS[rt],
            }
            for rt in ResearchType
        ],
        "steps": [
            {"number": s.number, "key": s.key, "title": s.title, "summary": s.summary}
            for s in STEPS
        ],
        "treatment": {family.value: values for family, values in TREATMENT.items()},
        "plans": [plan.to_dict() for plan in credits.PLANS.values()],
        "product_limits": describe_limits(),
        "credit_costs": credits.COSTS,
    }


# --- Proyek ------------------------------------------------------------------


@router.post("/projects", status_code=201)
def create_project(payload: ProjectCreate, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    """Langkah 1 — pilihan jenis karya menentukan struktur, batas, dan langkah."""
    try:
        work_type = get_work_type(payload.work_type)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    try:
        research_type = ResearchType(payload.research_type)
    except ValueError as exc:
        raise HTTPException(400, f"Jenis penelitian '{payload.research_type}' tidak dikenal.") from exc

    if payload.account_id:
        try:
            credits.check_project_quota(conn, payload.account_id)
        except credits.QuotaExceeded as exc:
            raise HTTPException(402, str(exc)) from exc

    target = payload.target_words or work_type.default_target_words
    project_id = db.insert(
        conn,
        "projects",
        account_id=payload.account_id,
        name=payload.name,
        work_type=work_type.key,
        research_type=research_type.value,
        field_of_study=payload.field_of_study,
        target_words=target,
        deadline=payload.deadline,
        citation_style=payload.citation_style or work_type.citation_style,
        created_at=db.now(),
        updated_at=db.now(),
    )
    build_default_outline(conn, project_id, work_type, target)
    return get_project_detail(project_id, conn)


@router.get("/projects")
def list_projects(
    account_id: int | None = None, conn: sqlite3.Connection = Depends(get_conn)
) -> list[dict]:
    sql = "SELECT * FROM projects"
    params: tuple = ()
    if account_id:
        sql += " WHERE account_id = ?"
        params = (account_id,)
    sql += " ORDER BY updated_at DESC"
    projects = []
    for row in db.fetch_all(conn, sql, params):
        project = dict(row)
        manuscript = load_manuscript(conn, project["id"])
        work_type = get_work_type(project["work_type"])
        project["work_type_label"] = work_type.label
        project["word_count"] = manuscript.word_count
        project["progress"] = (
            round(manuscript.word_count / project["target_words"], 3)
            if project["target_words"]
            else 0.0
        )
        projects.append(project)
    return projects


@router.get("/projects/{project_id}")
def get_project_detail(project_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    project = get_project(project_id, conn)
    work_type = get_work_type(project["work_type"])
    research_type = ResearchType(project["research_type"])
    manuscript = load_manuscript(conn, project_id)

    counts = {
        "references": db.fetch_one(
            conn, "SELECT COUNT(*) AS n FROM refs WHERE project_id = ?", (project_id,)
        )["n"],
        "references_verified": db.fetch_one(
            conn,
            "SELECT COUNT(*) AS n FROM refs WHERE project_id = ? AND verified = 1",
            (project_id,),
        )["n"],
        "datasets": db.fetch_one(
            conn, "SELECT COUNT(*) AS n FROM datasets WHERE project_id = ?", (project_id,)
        )["n"],
        "analyses": db.fetch_one(
            conn, "SELECT COUNT(*) AS n FROM analyses WHERE project_id = ?", (project_id,)
        )["n"],
        "revisions_open": db.fetch_one(
            conn,
            "SELECT COUNT(*) AS n FROM revisions WHERE project_id = ? AND status != 'selesai'",
            (project_id,),
        )["n"],
        "versions": db.fetch_one(
            conn, "SELECT COUNT(*) AS n FROM versions WHERE project_id = ?", (project_id,)
        )["n"],
    }
    ruleset = db.fetch_one(
        conn,
        "SELECT id, name, kind, created_at FROM rulesets WHERE project_id = ? AND active = 1",
        (project_id,),
    )

    project.update(
        {
            "work_type_label": work_type.label,
            "work_type_detail": {
                "family": work_type.family.value,
                "ciri_khas": work_type.ciri_khas,
                "fitur_utama": list(work_type.fitur_utama),
                "hard_word_limit": work_type.hard_word_limit,
                "export_formats": list(work_type.export_formats),
                "supervision_tracking": work_type.supervision_tracking,
                "defense_mode": work_type.defense_mode,
                "submission_kit": work_type.submission_kit,
            },
            "research_type_label": RESEARCH_TYPE_LABELS[research_type],
            "research_needs": RESEARCH_NEEDS[research_type],
            "treatment": work_type.treatment,
            "steps": applicable_steps(work_type, research_type),
            "data_step_required": requires_data_step(work_type, research_type),
            "word_count": manuscript.word_count,
            "counts": counts,
            "active_ruleset": dict(ruleset) if ruleset else None,
        }
    )
    return project


@router.patch("/projects/{project_id}")
def update_project(
    project_id: int, payload: ProjectUpdate, conn: sqlite3.Connection = Depends(get_conn)
) -> dict:
    project = get_project(project_id, conn)
    values = {k: v for k, v in payload.model_dump(exclude_none=True).items()}
    if "research_type" in values:
        try:
            ResearchType(values["research_type"])
        except ValueError as exc:
            raise HTTPException(400, "Jenis penelitian tidak dikenal.") from exc
    if values:
        values["updated_at"] = db.now()
        db.update(conn, "projects", project["id"], **values)
    return get_project_detail(project_id, conn)


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> None:
    get_project(project_id, conn)
    conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    conn.commit()


# --- Kerangka dan naskah -----------------------------------------------------


@router.get("/projects/{project_id}/outline")
def get_outline(project_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    get_project(project_id, conn)
    manuscript = load_manuscript(conn, project_id)
    return {
        "sections": section_outline(manuscript),
        "word_count": manuscript.word_count,
        "target_words": manuscript.target_words,
    }


@router.get("/projects/{project_id}/manuscript")
def get_manuscript(project_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    get_project(project_id, conn)
    manuscript = load_manuscript(conn, project_id)

    def dump(section) -> dict:
        return {
            "id": section.id,
            "number": section.number,
            "level": section.level,
            "title": section.title,
            "role": section.role,
            "status": section.status,
            "target_words": section.target_words,
            "word_count": section.word_count,
            "blocks": [
                {
                    "id": b.id,
                    "kind": b.kind,
                    "position": b.position,
                    "content": b.content,
                    "meta": b.meta,
                    "word_count": b.word_count,
                }
                for b in section.blocks
            ],
            "children": [dump(c) for c in section.children],
        }

    return {
        "project_id": project_id,
        "sections": [dump(s) for s in manuscript.sections],
        "captions": manuscript.numbered_captions(),
        "citekeys": manuscript.citekeys(),
        "word_count": manuscript.word_count,
    }


@router.post("/projects/{project_id}/sections", status_code=201)
def create_section(
    project_id: int, payload: SectionCreate, conn: sqlite3.Connection = Depends(get_conn)
) -> dict:
    get_project(project_id, conn)
    position = payload.position
    if position is None:
        row = db.fetch_one(
            conn,
            "SELECT COALESCE(MAX(position), -1) + 1 AS p FROM sections "
            "WHERE project_id = ? AND parent_id IS ?",
            (project_id, payload.parent_id),
        )
        position = row["p"]
    section_id = db.insert(
        conn,
        "sections",
        project_id=project_id,
        parent_id=payload.parent_id,
        position=position,
        title=payload.title,
        role=payload.role,
        target_words=payload.target_words,
        status="belum",
        created_at=db.now(),
    )
    return {"id": section_id}


@router.patch("/sections/{section_id}")
def update_section(
    section_id: int, payload: SectionUpdate, conn: sqlite3.Connection = Depends(get_conn)
) -> dict:
    row = db.fetch_one(conn, "SELECT * FROM sections WHERE id = ?", (section_id,))
    if row is None:
        raise HTTPException(404, f"Bagian {section_id} tidak ditemukan.")
    values = payload.model_dump(exclude_none=True)
    if values:
        db.update(conn, "sections", section_id, **values)
    return dict(db.fetch_one(conn, "SELECT * FROM sections WHERE id = ?", (section_id,)))


@router.delete("/sections/{section_id}", status_code=204)
def delete_section(section_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> None:
    conn.execute("DELETE FROM sections WHERE id = ?", (section_id,))
    conn.commit()


@router.post("/sections/{section_id}/blocks", status_code=201)
def create_block(
    section_id: int, payload: BlockCreate, conn: sqlite3.Connection = Depends(get_conn)
) -> dict:
    section = db.fetch_one(conn, "SELECT * FROM sections WHERE id = ?", (section_id,))
    if section is None:
        raise HTTPException(404, f"Bagian {section_id} tidak ditemukan.")
    position = payload.position
    if position is None:
        row = db.fetch_one(
            conn,
            "SELECT COALESCE(MAX(position), -1) + 1 AS p FROM blocks WHERE section_id = ?",
            (section_id,),
        )
        position = row["p"]
    block_id = db.insert(
        conn,
        "blocks",
        section_id=section_id,
        position=position,
        kind=payload.kind,
        content=payload.content,
        meta_json=json.dumps(payload.meta, ensure_ascii=False),
        updated_at=db.now(),
    )
    db.update(conn, "projects", section["project_id"], updated_at=db.now())
    return {"id": block_id}


@router.patch("/blocks/{block_id}")
def update_block(
    block_id: int, payload: BlockUpdate, conn: sqlite3.Connection = Depends(get_conn)
) -> dict:
    row = db.fetch_one(conn, "SELECT * FROM blocks WHERE id = ?", (block_id,))
    if row is None:
        raise HTTPException(404, f"Blok {block_id} tidak ditemukan.")
    values = payload.model_dump(exclude_none=True)
    if "meta" in values:
        values["meta_json"] = json.dumps(values.pop("meta"), ensure_ascii=False)
    values["updated_at"] = db.now()
    db.update(conn, "blocks", block_id, **values)
    return db.row_to_dict(
        db.fetch_one(conn, "SELECT * FROM blocks WHERE id = ?", (block_id,)), ("meta_json",)
    )


@router.delete("/blocks/{block_id}", status_code=204)
def delete_block(block_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> None:
    conn.execute("DELETE FROM blocks WHERE id = ?", (block_id,))
    conn.commit()


# --- Riwayat versi & dashboard ----------------------------------------------


@router.post("/projects/{project_id}/versions", status_code=201)
def create_version(
    project_id: int, payload: VersionCreate, conn: sqlite3.Connection = Depends(get_conn)
) -> dict:
    get_project(project_id, conn)
    manuscript = load_manuscript(conn, project_id)
    data = snapshot(manuscript)
    version_id = db.insert(
        conn,
        "versions",
        project_id=project_id,
        label=payload.label,
        snapshot_json=json.dumps(data, ensure_ascii=False),
        word_count=manuscript.word_count,
        created_at=db.now(),
    )
    return {"id": version_id, "word_count": manuscript.word_count}


@router.get("/projects/{project_id}/versions")
def list_versions(project_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> list[dict]:
    rows = db.fetch_all(
        conn,
        "SELECT id, label, word_count, created_at FROM versions WHERE project_id = ? "
        "ORDER BY id DESC",
        (project_id,),
    )
    return [dict(row) for row in rows]


@router.post("/projects/{project_id}/versions/{version_id}/restore")
def restore_version(
    project_id: int, version_id: int, conn: sqlite3.Connection = Depends(get_conn)
) -> dict:
    get_project(project_id, conn)
    row = db.fetch_one(
        conn, "SELECT * FROM versions WHERE id = ? AND project_id = ?", (version_id, project_id)
    )
    if row is None:
        raise HTTPException(404, f"Versi {version_id} tidak ditemukan.")

    # Versi berjalan disimpan lebih dahulu agar pemulihan sendiri bisa dibatalkan.
    current = load_manuscript(conn, project_id)
    db.insert(
        conn,
        "versions",
        project_id=project_id,
        label=f"Otomatis sebelum pulih ke versi {version_id}",
        snapshot_json=json.dumps(snapshot(current), ensure_ascii=False),
        word_count=current.word_count,
        created_at=db.now(),
    )
    restore_snapshot(conn, project_id, json.loads(row["snapshot_json"]))
    return {"restored": version_id, "word_count": load_manuscript(conn, project_id).word_count}


@router.get("/projects/{project_id}/dashboard")
def dashboard(project_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    """Status tiap bab, jumlah kata, dan sisa waktu menuju target sidang."""
    project = get_project(project_id, conn)
    work_type = project_work_type(project)
    manuscript = load_manuscript(conn, project_id)
    sections = section_outline(manuscript)

    days_left = None
    if project.get("deadline"):
        from datetime import date

        try:
            days_left = (date.fromisoformat(project["deadline"]) - date.today()).days
        except ValueError:
            days_left = None

    open_revisions = db.fetch_all(
        conn,
        "SELECT status, COUNT(*) AS n FROM revisions WHERE project_id = ? GROUP BY status",
        (project_id,),
    )
    target = project["target_words"] or manuscript.target_words
    remaining = max(target - manuscript.word_count, 0)

    return {
        "project_id": project_id,
        "work_type": work_type.label,
        "word_count": manuscript.word_count,
        "target_words": target,
        "progress": round(manuscript.word_count / target, 3) if target else 0.0,
        "remaining_words": remaining,
        "days_left": days_left,
        "words_per_day_needed": (
            round(remaining / days_left) if days_left and days_left > 0 and remaining else None
        ),
        "chapters": [s for s in sections if s["level"] == 1],
        "sections": sections,
        "revisions": {row["status"]: row["n"] for row in open_revisions},
    }
