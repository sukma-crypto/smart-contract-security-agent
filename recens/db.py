"""Penyimpanan Recens di atas SQLite.

Satu proyek berisi bab, pustaka referensi, data penelitian, dan riwayat versi
(Bagian 4.7 — Manajemen Proyek).
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import get_settings

SCHEMA = """
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS accounts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT UNIQUE,
    display_name  TEXT,
    password_hash TEXT,
    plan          TEXT NOT NULL DEFAULT 'coba',
    credits       INTEGER NOT NULL DEFAULT 0,
    valid_until   TEXT,
    created_at    TEXT NOT NULL
);

-- Sesi masuk. Yang tersimpan hanyalah SHA-256 dari token; token aslinya hanya
-- pernah ada di kuki peramban, sehingga salinan basis data yang bocor tidak
-- bisa langsung dipakai masuk.
CREATE TABLE IF NOT EXISTS sessions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id   INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    token_hash   TEXT NOT NULL UNIQUE,
    user_agent   TEXT NOT NULL DEFAULT '',
    ip           TEXT NOT NULL DEFAULT '',
    created_at   TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    expires_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id     INTEGER REFERENCES accounts(id) ON DELETE CASCADE,
    name           TEXT NOT NULL,
    work_type      TEXT NOT NULL,
    research_type  TEXT NOT NULL DEFAULT 'none',
    field_of_study TEXT,
    target_words   INTEGER NOT NULL DEFAULT 0,
    deadline       TEXT,
    citation_style TEXT NOT NULL DEFAULT 'apa',
    -- Langkah yang benar-benar ingin dikerjakan pengguna. NULL berarti seluruh
    -- langkah; itulah bawaan, dan itu pula arti proyek yang dibuat sebelum
    -- kolom ini ada.
    focus_json     TEXT,
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL
);

-- Langkah 2: pedoman yang dibaca menjadi aturan yang mengikat seluruh keluaran.
CREATE TABLE IF NOT EXISTS rulesets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    kind        TEXT NOT NULL,           -- fakultas | dosen | panitia | jurnal | bawaan
    source_file TEXT,
    rules_json  TEXT NOT NULL,
    active      INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL
);

-- Langkah 3: pustaka proyek. Metadata hanya diterima dari basis data resmi.
CREATE TABLE IF NOT EXISTS refs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    citekey     TEXT NOT NULL,
    source_db   TEXT NOT NULL,           -- crossref | openalex | semantic_scholar | garuda | unggahan
    external_id TEXT,
    csl_json    TEXT NOT NULL,
    verified    INTEGER NOT NULL DEFAULT 0,
    abstract    TEXT,
    pdf_path    TEXT,
    added_at    TEXT NOT NULL,
    UNIQUE(project_id, citekey)
);

CREATE TABLE IF NOT EXISTS ref_chunks (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    ref_id  INTEGER NOT NULL REFERENCES refs(id) ON DELETE CASCADE,
    page    INTEGER,
    ordinal INTEGER NOT NULL DEFAULT 0,
    text    TEXT NOT NULL
);

-- Langkah 4 & 5: naskah terstruktur (bukan teks datar).
CREATE TABLE IF NOT EXISTS sections (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id   INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    parent_id    INTEGER REFERENCES sections(id) ON DELETE CASCADE,
    position     INTEGER NOT NULL DEFAULT 0,
    title        TEXT NOT NULL,
    role         TEXT,
    target_words INTEGER NOT NULL DEFAULT 0,
    status       TEXT NOT NULL DEFAULT 'belum',   -- belum | draf | selesai
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS blocks (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    section_id INTEGER NOT NULL REFERENCES sections(id) ON DELETE CASCADE,
    position   INTEGER NOT NULL DEFAULT 0,
    kind       TEXT NOT NULL DEFAULT 'paragraph', -- paragraph|quote|list|table|figure|equation
    content    TEXT NOT NULL DEFAULT '',
    meta_json  TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS versions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id    INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    label         TEXT NOT NULL,
    snapshot_json TEXT NOT NULL,
    word_count    INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL
);

-- Langkah 6: data penelitian dan jejak analisis.
CREATE TABLE IF NOT EXISTS datasets (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    filename   TEXT NOT NULL,
    path       TEXT NOT NULL,
    kind       TEXT NOT NULL,            -- csv | xlsx | sav | transcript | pls_output
    meta_json  TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS analyses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    dataset_id  INTEGER REFERENCES datasets(id) ON DELETE SET NULL,
    method      TEXT NOT NULL,
    params_json TEXT NOT NULL,
    result_json TEXT NOT NULL,
    narrative   TEXT,
    engine      TEXT NOT NULL DEFAULT 'python',
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS qual_codes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    dataset_id INTEGER REFERENCES datasets(id) ON DELETE CASCADE,
    code       TEXT NOT NULL,
    theme      TEXT,
    quote      TEXT NOT NULL,
    informant  TEXT,
    line_ref   TEXT,
    created_at TEXT NOT NULL
);

-- Langkah 7: hasil pemeriksaan naskah.
CREATE TABLE IF NOT EXISTS checks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    kind        TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

-- Langkah 8: revisi, bimbingan, sidang, submisi.
CREATE TABLE IF NOT EXISTS revisions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    section_id  INTEGER REFERENCES sections(id) ON DELETE SET NULL,
    block_id    INTEGER REFERENCES blocks(id) ON DELETE SET NULL,
    source      TEXT NOT NULL DEFAULT 'pembimbing', -- pembimbing | penguji | reviewer | mandiri
    author      TEXT,
    text        TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'terbuka',    -- terbuka | dikerjakan | selesai | ditolak
    created_at  TEXT NOT NULL,
    resolved_at TEXT
);

CREATE TABLE IF NOT EXISTS supervision (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id   INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    met_on       TEXT NOT NULL,
    supervisor   TEXT,
    notes        TEXT NOT NULL DEFAULT '',
    achievements TEXT NOT NULL DEFAULT '',
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS submissions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    venue      TEXT,
    kind       TEXT NOT NULL,            -- cover_letter | response | abstract | template
    content    TEXT NOT NULL,
    meta_json  TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS credit_ledger (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    delta      INTEGER NOT NULL,
    reason     TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sessions_account ON sessions(account_id);
CREATE INDEX IF NOT EXISTS idx_projects_account ON projects(account_id, updated_at);
CREATE INDEX IF NOT EXISTS idx_sections_project ON sections(project_id, parent_id, position);
CREATE INDEX IF NOT EXISTS idx_blocks_section ON blocks(section_id, position);
CREATE INDEX IF NOT EXISTS idx_refs_project ON refs(project_id);
CREATE INDEX IF NOT EXISTS idx_revisions_project ON revisions(project_id, status);
CREATE INDEX IF NOT EXISTS idx_analyses_project ON analyses(project_id);
CREATE INDEX IF NOT EXISTS idx_chunks_ref ON ref_chunks(ref_id);
"""

_local = threading.local()


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Koneksi per-thread; SQLite dipakai satu koneksi per utas."""
    path = str(db_path or get_settings().db_path)
    cached = getattr(_local, "conns", None)
    if cached is None:
        cached = {}
        _local.conns = cached
    conn = cached.get(path)
    if conn is None:
        conn = sqlite3.connect(path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        cached[path] = conn
    return conn


#: Kolom yang ditambahkan setelah basis data pertama kali dipakai orang.
#: ``CREATE TABLE IF NOT EXISTS`` tidak menyentuh tabel yang sudah ada, jadi
#: kolom baru harus ditambal sendiri. Ini bukan pengganti sistem migrasi —
#: hanya cukup untuk penambahan kolom yang boleh kosong. Begitu ada perubahan
#: yang menuntut penulisan ulang data, pasang Alembic.
_ADDED_COLUMNS: dict[str, dict[str, str]] = {
    "accounts": {"password_hash": "TEXT"},
    "projects": {"focus_json": "TEXT"},
}


def _patch_columns(conn: sqlite3.Connection) -> None:
    for table, columns in _ADDED_COLUMNS.items():
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        if not existing:
            continue
        for name, decl in columns.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")


def init_db(db_path: Path | str | None = None) -> sqlite3.Connection:
    conn = connect(db_path)
    conn.executescript(SCHEMA)
    _patch_columns(conn)
    conn.commit()
    return conn


def close_all() -> None:
    for conn in getattr(_local, "conns", {}).values():
        conn.close()
    _local.conns = {}


# --- Pembantu kueri ----------------------------------------------------------


def insert(conn: sqlite3.Connection, table: str, **values: Any) -> int:
    cols = ", ".join(values)
    marks = ", ".join("?" for _ in values)
    cur = conn.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", tuple(values.values()))
    conn.commit()
    return int(cur.lastrowid)


def update(conn: sqlite3.Connection, table: str, row_id: int, **values: Any) -> None:
    if not values:
        return
    assigns = ", ".join(f"{k} = ?" for k in values)
    conn.execute(f"UPDATE {table} SET {assigns} WHERE id = ?", (*values.values(), row_id))
    conn.commit()


def fetch_one(conn: sqlite3.Connection, sql: str, params: Iterable = ()) -> sqlite3.Row | None:
    return conn.execute(sql, tuple(params)).fetchone()


def fetch_all(conn: sqlite3.Connection, sql: str, params: Iterable = ()) -> list[sqlite3.Row]:
    return conn.execute(sql, tuple(params)).fetchall()


def row_to_dict(row: sqlite3.Row | None, json_fields: Iterable[str] = ()) -> dict | None:
    if row is None:
        return None
    data = dict(row)
    for fieldname in json_fields:
        if fieldname in data and isinstance(data[fieldname], str):
            try:
                data[fieldname] = json.loads(data[fieldname])
            except json.JSONDecodeError:
                pass
    return data


def rows_to_dicts(rows: Iterable[sqlite3.Row], json_fields: Iterable[str] = ()) -> list[dict]:
    return [row_to_dict(r, json_fields) for r in rows]
