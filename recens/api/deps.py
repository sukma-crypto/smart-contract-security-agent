"""Kebergantungan bersama antar-router.

Di sinilah kepemilikan ditegakkan. Aturannya satu kalimat: **tidak ada sumber
daya yang boleh dibaca atau diubah tanpa ditelusuri lebih dahulu ke proyek, dan
proyek ke akun yang sedang masuk.**

Sumber daya seperti blok dan analisis diakses lewat ID-nya sendiri
(``PATCH /api/blocks/7``), bukan lewat alamat proyek. Karena itu tiap pembantu
``owned_*`` di bawah melakukan gabungan balik ke ``projects`` — bukan sekadar
memeriksa keberadaan barisnya. Milik orang lain dijawab 404, bukan 403, supaya
nomor ID tidak bisa dipakai memetakan isi basis data.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi import Cookie, Depends, HTTPException, Request

from .. import db
from ..config import get_settings
from ..core import auth, credits
from ..core.guidelines import RuleSet, active_ruleset
from ..core.llm.guardrails import GuardrailError
from ..core.manuscript import Manuscript, load_manuscript
from ..core.worktypes import ResearchType, WorkType, get_work_type

PROJECT_JSON_FIELDS = ()

#: Nama kuki sesi. Dipakai bersama oleh router auth dan pembacaan di bawah.
SESSION_COOKIE = "recens_sesi"


def get_conn() -> sqlite3.Connection:
    return db.connect()


# --- Identitas ---------------------------------------------------------------


def current_session(
    request: Request,
    conn: sqlite3.Connection = Depends(get_conn),
    recens_sesi: str | None = Cookie(default=None),
) -> dict:
    """Sesi yang sedang berjalan, atau 401.

    Token juga diterima lewat ``Authorization: Bearer`` agar klien non-peramban
    — skrip, pengujian, perkakas baris perintah — tidak perlu mengurus kuki.
    """
    token = recens_sesi
    header = request.headers.get("authorization", "")
    if not token and header.lower().startswith("bearer "):
        token = header[7:].strip()

    session = auth.resolve_session(conn, token)
    if session is None:
        raise HTTPException(401, "Sesi tidak ditemukan atau sudah berakhir. Silakan masuk.")
    auth.touch_session(conn, session["id"])
    return session


def current_account(
    session: dict = Depends(current_session), conn: sqlite3.Connection = Depends(get_conn)
) -> dict:
    account = credits.get_account(conn, session["account_id"])
    if account is None:
        # Akun terhapus tetapi kuki masih tertinggal di peramban.
        raise HTTPException(401, "Akun tidak ditemukan. Silakan masuk kembali.")
    account.pop("password_hash", None)
    account["session_id"] = session["id"]
    return account


# --- Kepemilikan -------------------------------------------------------------


def get_project(
    project_id: int,
    conn: sqlite3.Connection = Depends(get_conn),
    account: dict = Depends(current_account),
) -> dict:
    row = db.fetch_one(
        conn,
        "SELECT * FROM projects WHERE id = ? AND account_id = ?",
        (project_id, account["id"]),
    )
    if row is None:
        raise HTTPException(404, f"Proyek {project_id} tidak ditemukan.")
    return dict(row)


def owned_row(
    conn: sqlite3.Connection,
    account_id: int,
    table: str,
    row_id: int,
    label: str,
    *,
    join: str = "",
    project_column: str = "t.project_id",
) -> dict:
    """Ambil satu baris hanya bila ia menelusuri ke proyek milik ``account_id``.

    ``join`` dipakai untuk tabel yang tidak menyimpan ``project_id`` sendiri —
    ``blocks`` misalnya, yang hanya tahu ``section_id``.
    """
    sql = (
        f"SELECT t.* FROM {table} t {join} "
        f"JOIN projects p ON p.id = {project_column} "
        f"WHERE t.id = ? AND p.account_id = ?"
    )
    row = db.fetch_one(conn, sql, (row_id, account_id))
    if row is None:
        raise HTTPException(404, f"{label} {row_id} tidak ditemukan.")
    return dict(row)


def owned_section(conn: sqlite3.Connection, account_id: int, section_id: int) -> dict:
    return owned_row(conn, account_id, "sections", section_id, "Bagian", project_column="t.project_id")


def owned_block(conn: sqlite3.Connection, account_id: int, block_id: int) -> dict:
    return owned_row(
        conn,
        account_id,
        "blocks",
        block_id,
        "Blok",
        join="JOIN sections s ON s.id = t.section_id",
        project_column="s.project_id",
    )


def owned_ref(conn: sqlite3.Connection, account_id: int, ref_id: int) -> dict:
    return owned_row(conn, account_id, "refs", ref_id, "Referensi", project_column="t.project_id")


def owned_dataset(conn: sqlite3.Connection, account_id: int, dataset_id: int) -> dict:
    return owned_row(
        conn, account_id, "datasets", dataset_id, "Data", project_column="t.project_id"
    )


def owned_analysis(conn: sqlite3.Connection, account_id: int, analysis_id: int) -> dict:
    return owned_row(
        conn, account_id, "analyses", analysis_id, "Analisis", project_column="t.project_id"
    )


def owned_revision(conn: sqlite3.Connection, account_id: int, revision_id: int) -> dict:
    return owned_row(
        conn, account_id, "revisions", revision_id, "Catatan revisi", project_column="t.project_id"
    )


def owned_ruleset(conn: sqlite3.Connection, account_id: int, ruleset_id: int) -> dict:
    return owned_row(
        conn, account_id, "rulesets", ruleset_id, "Pedoman", project_column="t.project_id"
    )


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
