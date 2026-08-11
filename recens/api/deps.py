"""Kebergantungan bersama antar-router."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi import Depends, HTTPException

from .. import db
from ..config import get_settings
from ..core import credits
from ..core.guidelines import RuleSet, active_ruleset
from ..core.llm.guardrails import GuardrailError
from ..core.manuscript import Manuscript, load_manuscript
from ..core.worktypes import ResearchType, WorkType, get_work_type

PROJECT_JSON_FIELDS = ()


def get_conn() -> sqlite3.Connection:
    return db.connect()


def get_project(project_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    row = db.fetch_one(conn, "SELECT * FROM projects WHERE id = ?", (project_id,))
    if row is None:
        raise HTTPException(404, f"Proyek {project_id} tidak ditemukan.")
    return dict(row)


def project_work_type(project: dict) -> WorkType:
    return get_work_type(project["work_type"])


def project_research_type(project: dict) -> ResearchType:
    try:
        return ResearchType(project["research_type"])
    except ValueError:
        return ResearchType.NONE


def project_manuscript(conn: sqlite3.Connection, project_id: int) -> Manuscript:
    return load_manuscript(conn, project_id)


def project_rules(conn: sqlite3.Connection, project: dict) -> RuleSet:
    rules = active_ruleset(conn, project["id"])
    # Gaya sitasi proyek menang bila pengguna menyetelnya secara eksplisit.
    if project.get("citation_style"):
        rules.citation_style = project["citation_style"]
    return rules


def charge_for(conn: sqlite3.Connection, project: dict, action: str) -> dict:
    """Tagih kredit atas nama pemilik proyek, bila proyek memang punya akun."""
    account_id = project.get("account_id")
    if not account_id:
        return {"charged": 0, "credits_left": None, "action": action}
    try:
        return credits.charge(conn, account_id, action, project_id=project["id"])
    except credits.QuotaExceeded as exc:
        raise HTTPException(
            402,
            {
                "error": "kuota_habis",
                "message": str(exc),
                "needed": exc.needed,
                "available": exc.available,
            },
        ) from exc
    except credits.SubscriptionExpired as exc:
        raise HTTPException(402, {"error": "langganan_berakhir", "message": str(exc)}) from exc


def guard(callable_, *args, **kwargs):
    """Jalankan layanan dan terjemahkan penolakan batas produk menjadi HTTP 422.

    Penolakan tidak dikembalikan sebagai kesalahan kosong: alasan dan jalan
    keluarnya ikut dikirim agar antarmuka bisa menawarkan langkah yang sah.
    """
    try:
        return callable_(*args, **kwargs)
    except GuardrailError as exc:
        raise HTTPException(
            422,
            {
                "error": "batas_produk",
                "rule": exc.verdict.rule,
                "message": exc.verdict.reason,
                "alternative": exc.verdict.alternative,
            },
        ) from exc


def upload_path(project_id: int, filename: str, subdir: str = "") -> Path:
    settings = get_settings()
    safe = Path(filename).name.replace("/", "_")
    directory = settings.uploads_dir / str(project_id) / subdir if subdir else (
        settings.uploads_dir / str(project_id)
    )
    directory.mkdir(parents=True, exist_ok=True)
    return directory / safe
