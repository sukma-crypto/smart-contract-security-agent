"""Langkah 1 & 4: proyek, kerangka, naskah, versi, dan dashboard progres."""

from __future__ import annotations

import json
import sqlite3

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from .. import db
from ..core import credits
from ..core.llm.guardrails import describe_limits
from ..core.ingest import UnsupportedManuscript, read_docx_manuscript
from ..core.manuscript import (
    build_default_outline,
    load_manuscript,
    restore_snapshot,
    section_outline,
    snapshot,
)
from ..core.worktypes import (
    FOCUS_PRESETS,
    RESEARCH_NEEDS,
    RESEARCH_TYPE_LABELS,
    STEPS,
    TREATMENT,
    WORK_TYPES,
    ResearchType,
    applicable_steps,
    focus_key,
    focus_label,
    get_work_type,
    normalize_focus,
    requires_data_step,
)
from .deps import (
    current_account,
    get_conn,
    get_project,
    owned_block,
    owned_section,
    project_work_type,
    upload_path,
)

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
    #: Nama preset ("olah_data") atau daftar kunci langkah. Kosong = seluruhnya.
    focus: list[str] | str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    research_type: str | None = None
    field_of_study: str | None = None
    target_words: int | None = None
    deadline: str | None = None
    citation_style: str | None = None
    focus: list[str] | str | None = None


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
        "focus_presets": [
            {
                "key": f.key,
                "label": f.label,
                "summary": f.summary,
                "steps": list(f.steps),
            }
            for f in FOCUS_PRESETS
        ],
        "treatment": {family.value: values for family, values in TREATMENT.items()},
        "plans": [plan.to_dict() for plan in credits.PLANS.values()],
        "product_limits": describe_limits(),
        "credit_costs": credits.COSTS,
    }


# --- Proyek ------------------------------------------------------------------


@router.post("/projects", status_code=201)
def create_project(
    payload: ProjectCreate,
    conn: sqlite3.Connection = Depends(get_conn),
    account: dict = Depends(current_account),
) -> dict:
    """Langkah 1 — pilihan jenis karya menentukan struktur, batas, dan langkah.

    Pemiliknya diambil dari sesi yang sedang berjalan, bukan dari kiriman.
    Selama ``account_id`` masih boleh dititipkan lewat badan permintaan, siapa
    pun bisa menaruh proyek atas nama orang lain.
    """
    try:
        work_type = get_work_type(payload.work_type)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    try:
        research_type = ResearchType(payload.research_type)
    except ValueError as exc:
        raise HTTPException(400, f"Jenis penelitian '{payload.research_type}' tidak dikenal.") from exc

    try:
        credits.check_project_quota(conn, account["id"])
    except credits.QuotaExceeded as exc:
        raise HTTPException(402, str(exc)) from exc

    target = payload.target_words or work_type.default_target_words
    project_id = db.insert(
        conn,
        "projects",
        account_id=account["id"],
        name=payload.name,
        work_type=work_type.key,
        research_type=research_type.value,
        field_of_study=payload.field_of_study,
        target_words=target,
        deadline=payload.deadline,
        citation_style=payload.citation_style or work_type.citation_style,
        focus_json=json.dumps(list(normalize_focus(payload.focus)), ensure_ascii=False),
        created_at=db.now(),
        updated_at=db.now(),
    )
    build_default_outline(conn, project_id, work_type, target)
    return _project_detail(conn, dict(db.fetch_one(conn, "SELECT * FROM projects WHERE id = ?", (project_id,))))


@router.get("/projects")
def list_projects(
    conn: sqlite3.Connection = Depends(get_conn),
    account: dict = Depends(current_account),
) -> list[dict]:
    """Hanya proyek milik akun yang sedang masuk.

    Penyaringnya bukan parameter kueri — kalau bisa disetel dari luar, ia bukan
    penyaring keamanan, melainkan saran.
    """
    projects = []
    rows = db.fetch_all(
        conn,
        "SELECT * FROM projects WHERE account_id = ? ORDER BY updated_at DESC",
        (account["id"],),
    )
    for row in rows:
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
def get_project_detail(
    conn: sqlite3.Connection = Depends(get_conn), project: dict = Depends(get_project)
) -> dict:
    return _project_detail(conn, project)


def project_focus(project: dict) -> tuple[str, ...]:
    """Langkah yang sedang difokuskan proyek ini.

    Kolomnya boleh kosong — proyek yang dibuat sebelum fokus ada, dan proyek
    yang memang ingin memakai seluruh langkah, sama-sama menyimpan NULL.
    """
    raw = project.get("focus_json")
    if not raw:
        return normalize_focus(None)
    try:
        stored = json.loads(raw)
    except (TypeError, ValueError):
        return normalize_focus(None)
    return normalize_focus(stored if isinstance(stored, list) else None)


def _project_detail(conn: sqlite3.Connection, project: dict) -> dict:
    """Rincian proyek beserta hitungan turunannya.

    Terpisah dari rutenya karena dipanggil juga setelah membuat dan mengubah
    proyek; memanggil fungsi rute secara langsung akan melewati resolusi
    kebergantungan dan justru mematikan pemeriksaan kepemilikannya.
    """
    project_id = project["id"]
    work_type = get_work_type(project["work_type"])
    research_type = ResearchType(project["research_type"])
    manuscript = load_manuscript(conn, project_id)
    focus = project_focus(project)

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
            "steps": applicable_steps(work_type, research_type, focus),
            "focus": list(focus),
            "focus_key": focus_key(focus),
            "focus_label": focus_label(focus),
            "data_step_required": requires_data_step(work_type, research_type),
            "word_count": manuscript.word_count,
            "counts": counts,
            "active_ruleset": dict(ruleset) if ruleset else None,
        }
    )
    return project


@router.patch("/projects/{project_id}")
def update_project(
    payload: ProjectUpdate,
    conn: sqlite3.Connection = Depends(get_conn),
    project: dict = Depends(get_project),
) -> dict:
    values = {k: v for k, v in payload.model_dump(exclude_none=True).items()}
    if "focus" in values:
        values["focus_json"] = json.dumps(
            list(normalize_focus(values.pop("focus"))), ensure_ascii=False
        )
    if "research_type" in values:
        try:
            ResearchType(values["research_type"])
        except ValueError as exc:
            raise HTTPException(400, "Jenis penelitian tidak dikenal.") from exc
    if values:
        values["updated_at"] = db.now()
        db.update(conn, "projects", project["id"], **values)
    fresh = db.fetch_one(conn, "SELECT * FROM projects WHERE id = ?", (project["id"],))
    return _project_detail(conn, dict(fresh))


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(
    conn: sqlite3.Connection = Depends(get_conn), project: dict = Depends(get_project)
) -> None:
    conn.execute("DELETE FROM projects WHERE id = ?", (project["id"],))
    conn.commit()


# --- Kerangka dan naskah -----------------------------------------------------


@router.get("/projects/{project_id}/outline")
def get_outline(
    conn: sqlite3.Connection = Depends(get_conn), project: dict = Depends(get_project)
) -> dict:
    manuscript = load_manuscript(conn, project["id"])
    return {
        "sections": section_outline(manuscript),
        "word_count": manuscript.word_count,
        "target_words": manuscript.target_words,
    }


@router.get("/projects/{project_id}/manuscript")
def get_manuscript(
    conn: sqlite3.Connection = Depends(get_conn), project: dict = Depends(get_project)
) -> dict:
    manuscript = load_manuscript(conn, project["id"])

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
        "project_id": project["id"],
        "sections": [dump(s) for s in manuscript.sections],
        "captions": manuscript.numbered_captions(),
        "citekeys": manuscript.citekeys(),
        "word_count": manuscript.word_count,
    }


@router.post("/projects/{project_id}/sections", status_code=201)
def create_section(
    payload: SectionCreate,
    conn: sqlite3.Connection = Depends(get_conn),
    project: dict = Depends(get_project),
) -> dict:
    project_id = project["id"]
    if payload.parent_id is not None:
        # Induk harus berada di proyek yang sama, bukan sekadar ada.
        parent = db.fetch_one(
            conn,
            "SELECT id FROM sections WHERE id = ? AND project_id = ?",
            (payload.parent_id, project_id),
        )
        if parent is None:
            raise HTTPException(404, f"Bagian induk {payload.parent_id} tidak ditemukan.")
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
    section_id: int,
    payload: SectionUpdate,
    conn: sqlite3.Connection = Depends(get_conn),
    account: dict = Depends(current_account),
) -> dict:
    section = owned_section(conn, account["id"], section_id)
    values = payload.model_dump(exclude_none=True)
    if "parent_id" in values:
        parent = db.fetch_one(
            conn,
            "SELECT id FROM sections WHERE id = ? AND project_id = ?",
            (values["parent_id"], section["project_id"]),
        )
        if parent is None:
            raise HTTPException(404, f"Bagian induk {values['parent_id']} tidak ditemukan.")
    if values:
        db.update(conn, "sections", section_id, **values)
    return dict(db.fetch_one(conn, "SELECT * FROM sections WHERE id = ?", (section_id,)))


@router.delete("/sections/{section_id}", status_code=204)
def delete_section(
    section_id: int,
    conn: sqlite3.Connection = Depends(get_conn),
    account: dict = Depends(current_account),
) -> None:
    owned_section(conn, account["id"], section_id)
    conn.execute("DELETE FROM sections WHERE id = ?", (section_id,))
    conn.commit()


@router.post("/sections/{section_id}/blocks", status_code=201)
def create_block(
    section_id: int,
    payload: BlockCreate,
    conn: sqlite3.Connection = Depends(get_conn),
    account: dict = Depends(current_account),
) -> dict:
    section = owned_section(conn, account["id"], section_id)
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
    block_id: int,
    payload: BlockUpdate,
    conn: sqlite3.Connection = Depends(get_conn),
    account: dict = Depends(current_account),
) -> dict:
    owned_block(conn, account["id"], block_id)
    values = payload.model_dump(exclude_none=True)
    if "meta" in values:
        values["meta_json"] = json.dumps(values.pop("meta"), ensure_ascii=False)
    values["updated_at"] = db.now()
    db.update(conn, "blocks", block_id, **values)
    return db.row_to_dict(
        db.fetch_one(conn, "SELECT * FROM blocks WHERE id = ?", (block_id,)), ("meta_json",)
    )


@router.delete("/blocks/{block_id}", status_code=204)
def delete_block(
    block_id: int,
    conn: sqlite3.Connection = Depends(get_conn),
    account: dict = Depends(current_account),
) -> None:
    owned_block(conn, account["id"], block_id)
    conn.execute("DELETE FROM blocks WHERE id = ?", (block_id,))
    conn.commit()


# --- Riwayat versi & dashboard ----------------------------------------------


@router.post("/projects/{project_id}/versions", status_code=201)
def create_version(
    payload: VersionCreate,
    conn: sqlite3.Connection = Depends(get_conn),
    project: dict = Depends(get_project),
) -> dict:
    project_id = project["id"]
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
def list_versions(
    conn: sqlite3.Connection = Depends(get_conn), project: dict = Depends(get_project)
) -> list[dict]:
    rows = db.fetch_all(
        conn,
        "SELECT id, label, word_count, created_at FROM versions WHERE project_id = ? "
        "ORDER BY id DESC",
        (project["id"],),
    )
    return [dict(row) for row in rows]


@router.post("/projects/{project_id}/versions/{version_id}/restore")
def restore_version(
    version_id: int,
    conn: sqlite3.Connection = Depends(get_conn),
    project: dict = Depends(get_project),
) -> dict:
    project_id = project["id"]
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


@router.post("/projects/{project_id}/manuscript/import", status_code=201)
async def import_manuscript(
    file: UploadFile = File(...),
    replace: bool = Form(False),
    conn: sqlite3.Connection = Depends(get_conn),
    project: dict = Depends(get_project),
) -> dict:
    """Impor naskah .docx yang sudah ditulis sendiri menjadi kerangka bernaskah.

    Yang sudah menggarap BAB I sampai III berbulan-bulan lalu mentok di BAB IV
    tidak boleh diminta mengetik ulang tiga bab hanya untuk memakai satu fitur.
    Naskahnya masuk apa adanya, dengan strukturnya sendiri — struktur bawaan
    Recens memang cuma tebakan, sedangkan yang ia bawa sudah disetujui
    pembimbingnya.
    """
    project_id = project["id"]
    filename = file.filename or "naskah.docx"
    if not filename.lower().endswith(".docx"):
        raise HTTPException(
            400,
            "Format naskah harus .docx. Bila berkas Anda .doc lama atau PDF, buka di Word "
            "lalu simpan ulang sebagai .docx.",
        )

    destination = upload_path(project_id, filename, "naskah")
    destination.write_bytes(await file.read())
    try:
        imported = read_docx_manuscript(destination)
    except UnsupportedManuscript as exc:
        destination.unlink(missing_ok=True)
        raise HTTPException(400, str(exc)) from exc

    current = load_manuscript(conn, project_id)
    # Naskah yang sudah berisi tidak ditimpa diam-diam. Kerangka bawaan yang
    # masih kosong boleh diganti tanpa bertanya — tidak ada yang hilang — tetapi
    # tulisan yang sudah ada adalah pekerjaan orang.
    if current.word_count and not replace:
        raise HTTPException(
            409,
            "Naskah proyek ini sudah berisi tulisan. Impor akan menggantinya. Ulangi "
            "dengan pilihan 'ganti naskah yang ada' bila memang itu yang Anda maksud.",
        )

    versi_id = None
    if current.word_count:
        # Titik pulih dibuat lebih dulu, sehingga impor yang ternyata keliru
        # arah bisa dibatalkan lewat riwayat versi.
        versi_id = db.insert(
            conn,
            "versions",
            project_id=project_id,
            label="Sebelum impor naskah",
            snapshot_json=json.dumps(snapshot(current), ensure_ascii=False),
            word_count=current.word_count,
            created_at=db.now(),
        )

    conn.execute("DELETE FROM sections WHERE project_id = ?", (project_id,))
    conn.commit()

    dibuat = 0

    def tanam(nodes, parent_id: int | None) -> None:
        nonlocal dibuat
        for position, node in enumerate(nodes):
            section_id = db.insert(
                conn,
                "sections",
                project_id=project_id,
                parent_id=parent_id,
                position=position,
                title=node.title,
                role=None,
                target_words=0,
                status="draf" if node.blocks else "belum",
                created_at=db.now(),
            )
            dibuat += 1
            for block_position, block in enumerate(node.blocks):
                db.insert(
                    conn,
                    "blocks",
                    section_id=section_id,
                    position=block_position,
                    kind=block.get("kind", "paragraph"),
                    content=block.get("content", ""),
                    meta_json=json.dumps(block.get("meta", {}), ensure_ascii=False),
                    updated_at=db.now(),
                )
            tanam(node.children, section_id)

    tanam(imported.sections, None)
    conn.commit()

    fresh = load_manuscript(conn, project_id)
    catatan = list(imported.notes)
    catatan.append(
        "Bagian hasil analisis akan dibuatkan sendiri saat Anda menyisipkan hasil olah "
        "data, jadi tidak perlu menyiapkannya lebih dulu."
    )
    if versi_id:
        catatan.append("Naskah sebelumnya disimpan sebagai versi dan bisa dipulihkan.")

    return {
        "sections_created": dibuat,
        "word_count": fresh.word_count,
        "notes": catatan,
        "restore_version_id": versi_id,
    }


@router.get("/projects/{project_id}/dashboard")
def dashboard(
    conn: sqlite3.Connection = Depends(get_conn), project: dict = Depends(get_project)
) -> dict:
    """Status tiap bab, jumlah kata, dan sisa waktu menuju target sidang."""
    project_id = project["id"]
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
    focus = project_focus(project)

    return {
        "project_id": project_id,
        "work_type": work_type.label,
        "focus": list(focus),
        "focus_key": focus_key(focus),
        "focus_label": focus_label(focus),
        # Menulis bukan bagian dari tiap pekerjaan. Bagi yang datang hanya untuk
        # merapikan format, editor tidak pernah dibuka sama sekali.
        "writing_in_focus": "menulis" in focus,
        # Target kata seluruh naskah hanya berlaku bagi yang memang bertanggung
        # jawab atas seluruh naskah, dan penandanya adalah menyusun kerangka:
        # orang yang hanya menggarap BAB IV tetap menulis, tetapi 18.000 kata
        # bukan ukurannya — melaporkan ia baru 3% selesai adalah kabar buruk
        # tentang pekerjaan yang tidak pernah ia ambil.
        "tracks_word_target": "menulis" in focus and "susun_outline" in focus,
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
        "work_done": _work_done(conn, project, focus, sections),
    }


def _work_done(
    conn: sqlite3.Connection,
    project: dict,
    focus: tuple[str, ...],
    sections: list[dict],
) -> list[dict]:
    """Pekerjaan yang sudah benar-benar dikerjakan, disaring menurut fokus.

    Jumlah kata adalah ukuran kemajuan yang buruk untuk sebagian besar
    pekerjaan di sini, dan ukuran yang menyesatkan untuk seluruhnya: ia
    memberi nilai pada volume, padahal Bagian 8.1 justru menolak menuliskan bab
    utuh. Yang layak dihitung adalah pekerjaan yang punya wujud — uji yang
    dijalankan, referensi yang terverifikasi, coretan pembimbing yang ditutup.
    """
    project_id = project["id"]

    def hitung(sql: str, *args) -> int:
        return int(db.fetch_one(conn, sql, (project_id, *args))["n"])

    ruleset = hitung(
        "SELECT COUNT(*) AS n FROM rulesets WHERE project_id = ? AND active = 1"
    )
    kandidat = [
        {
            "step": "muat_aturan",
            "key": "ruleset",
            "label": "Pedoman aktif",
            "count": ruleset,
            "hint": "Aturan struktur, margin, dan penomoran yang mengikat seluruh keluaran.",
        },
        {
            "step": "kumpulkan_referensi",
            "key": "references",
            "label": "Referensi terverifikasi",
            "count": hitung(
                "SELECT COUNT(*) AS n FROM refs WHERE project_id = ? AND verified = 1"
            ),
            "total": hitung("SELECT COUNT(*) AS n FROM refs WHERE project_id = ?"),
            "hint": "Hanya yang terlacak ke basis data resmi yang boleh masuk daftar pustaka.",
        },
        {
            "step": "susun_outline",
            "key": "sections",
            "label": "Bagian tersusun",
            "count": len(sections),
            "hint": "Kerangka bagian dan sub-bagian beserta target katanya.",
        },
        {
            "step": "menulis",
            "key": "sections_written",
            "label": "Bagian sudah terisi",
            "count": sum(1 for s in sections if s.get("word_count")),
            "total": len(sections),
            "hint": "Bagian yang sudah memuat tulisan, bukan sekadar judul.",
        },
        {
            "step": "olah_data",
            "key": "analyses",
            "label": "Analisis dijalankan",
            "count": hitung("SELECT COUNT(*) AS n FROM analyses WHERE project_id = ?"),
            "hint": "Tiap uji tersimpan lengkap dengan data, parameter, dan hasilnya.",
        },
        {
            "step": "olah_data",
            "key": "datasets",
            "label": "Berkas data terbaca",
            "count": hitung("SELECT COUNT(*) AS n FROM datasets WHERE project_id = ?"),
            "hint": "SPSS, Excel, CSV, atau transkrip wawancara.",
        },
        {
            "step": "ekspor_revisi",
            "key": "revisions_done",
            "label": "Revisi ditutup",
            "count": hitung(
                "SELECT COUNT(*) AS n FROM revisions WHERE project_id = ? AND status = 'selesai'"
            ),
            "total": hitung("SELECT COUNT(*) AS n FROM revisions WHERE project_id = ?"),
            "hint": "Coretan pembimbing yang sudah ditindaklanjuti di naskah.",
        },
        {
            "step": "ekspor_revisi",
            "key": "versions",
            "label": "Versi tersimpan",
            "count": hitung("SELECT COUNT(*) AS n FROM versions WHERE project_id = ?"),
            "hint": "Titik pulih naskah sebelum perubahan besar.",
        },
    ]
    return [item for item in kandidat if item["step"] in focus]
