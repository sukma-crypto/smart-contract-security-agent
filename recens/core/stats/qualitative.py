"""Bantuan analisis kualitatif: pengodean, tema, dan temuan berbasis kutipan.

Banyak skripsi bidang sosial, pendidikan, dan hukum bersifat kualitatif dan
selama ini tak terlayani alat sejenis (Bagian 4.4).

Satu aturan tidak bisa dilanggar di sini: setiap kutipan informan yang muncul di
naskah harus benar-benar ada di transkrip yang diketik pengguna. Modul ini
memverifikasinya secara harfiah, sehingga temuan kualitatif tidak bisa berisi
ucapan yang tidak pernah diucapkan.
"""

from __future__ import annotations

import re
import sqlite3
from collections import Counter
from dataclasses import dataclass, field

import pandas as pd

from ... import db
from ..retrieval import STOPWORDS, tokenize


@dataclass
class CodedSegment:
    code: str
    quote: str
    informant: str = ""
    line_ref: str = ""
    theme: str = ""

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "quote": self.quote,
            "informant": self.informant,
            "line_ref": self.line_ref,
            "theme": self.theme,
        }


class QuoteNotFound(ValueError):
    """Kutipan tidak ditemukan di transkrip — temuan ditolak."""


def normalize_quote(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def verify_quote(quote: str, transcript: str) -> bool:
    """Pastikan kutipan benar-benar ada di transkrip, bukan hasil karangan."""
    return normalize_quote(quote) in normalize_quote(transcript)


def verify_segments(segments: list[CodedSegment], transcript: str) -> tuple[list, list]:
    """Pisahkan segmen yang kutipannya terverifikasi dari yang tidak."""
    verified, rejected = [], []
    for segment in segments:
        (verified if verify_quote(segment.quote, transcript) else rejected).append(segment)
    return verified, rejected


def suggest_codes(frame: pd.DataFrame, top_k: int = 20, min_count: int = 2) -> list[dict]:
    """Usulkan kode awal dari kata dan frasa yang berulang di transkrip.

    Ini adalah pengodean terbuka tahap pertama: yang diusulkan adalah pola yang
    benar-benar muncul berulang, bukan tema yang dibayangkan. Peneliti tetap
    memutuskan kode mana yang bermakna.
    """
    if "ucapan" not in frame.columns:
        raise ValueError("Transkrip harus memiliki kolom 'ucapan'.")

    unigrams: Counter[str] = Counter()
    bigrams: Counter[str] = Counter()
    for utterance in frame["ucapan"].dropna().astype(str):
        tokens = tokenize(utterance)
        unigrams.update(set(tokens))
        bigrams.update({" ".join(pair) for pair in zip(tokens, tokens[1:])})

    candidates: list[dict] = []
    for phrase, count in bigrams.most_common(top_k * 2):
        if count >= min_count:
            candidates.append({"code": phrase, "count": count, "kind": "frasa"})
    for word, count in unigrams.most_common(top_k * 2):
        if count >= min_count and len(word) > 4:
            candidates.append({"code": word, "count": count, "kind": "kata"})

    candidates.sort(key=lambda c: (-c["count"], c["code"]))
    return candidates[:top_k]


def apply_code(frame: pd.DataFrame, code: str) -> list[CodedSegment]:
    """Tandai seluruh giliran bicara yang memuat kode tertentu."""
    segments = []
    pattern = re.compile(re.escape(code), re.IGNORECASE)
    for _, row in frame.iterrows():
        utterance = str(row.get("ucapan", ""))
        if pattern.search(utterance):
            segments.append(
                CodedSegment(
                    code=code,
                    quote=utterance.strip(),
                    informant=str(row.get("informan", "")),
                    line_ref=str(row.get("baris", "")),
                )
            )
    return segments


def build_themes(segments: list[CodedSegment], theme_map: dict[str, str]) -> dict:
    """Kelompokkan kode menjadi tema sesuai pemetaan yang ditentukan peneliti."""
    themes: dict[str, list[CodedSegment]] = {}
    for segment in segments:
        theme = theme_map.get(segment.code, "Belum dikelompokkan")
        segment.theme = theme
        themes.setdefault(theme, []).append(segment)

    return {
        "themes": [
            {
                "theme": theme,
                "codes": sorted({s.code for s in items}),
                "n_segments": len(items),
                "informants": sorted({s.informant for s in items if s.informant}),
                "quotes": [s.to_dict() for s in items],
            }
            for theme, items in sorted(themes.items(), key=lambda kv: -len(kv[1]))
        ],
        "n_codes": len({s.code for s in segments}),
        "n_segments": len(segments),
    }


def reduce_data(segments: list[CodedSegment], max_quotes_per_code: int = 3) -> dict:
    """Reduksi data: ambil kutipan paling representatif per kode.

    Representatif di sini berarti paling padat kata bermakna — bukan dipilih
    karena paling mendukung hipotesis peneliti.
    """
    by_code: dict[str, list[CodedSegment]] = {}
    for segment in segments:
        by_code.setdefault(segment.code, []).append(segment)

    reduced = {}
    for code, items in by_code.items():
        ranked = sorted(
            items,
            key=lambda s: len([t for t in tokenize(s.quote) if t not in STOPWORDS]),
            reverse=True,
        )
        reduced[code] = [s.to_dict() for s in ranked[:max_quotes_per_code]]
    return {
        "codes": reduced,
        "n_before": len(segments),
        "n_after": sum(len(v) for v in reduced.values()),
    }


def triangulation_matrix(segments: list[CodedSegment]) -> dict:
    """Matriks triangulasi sumber: kode × informan.

    Kode yang hanya muncul dari satu informan ditandai, karena itulah titik yang
    paling sering dipersoalkan penguji.
    """
    codes = sorted({s.code for s in segments})
    informants = sorted({s.informant for s in segments if s.informant})
    rows = []
    single_source = []
    for code in codes:
        line = [code]
        supporting = 0
        for informant in informants:
            count = sum(1 for s in segments if s.code == code and s.informant == informant)
            line.append(count)
            supporting += 1 if count else 0
        line.append(supporting)
        rows.append(line)
        if supporting <= 1:
            single_source.append(code)

    return {
        "columns": ["Kode", *informants, "Jumlah Informan"],
        "rows": rows,
        "single_source_codes": single_source,
        "note": (
            "Kode yang hanya didukung satu informan belum terkonfirmasi lewat "
            "triangulasi sumber."
        ),
    }


# --- Penyimpanan -------------------------------------------------------------


def save_segments(
    conn: sqlite3.Connection, project_id: int, dataset_id: int | None, segments: list[CodedSegment]
) -> int:
    for segment in segments:
        db.insert(
            conn,
            "qual_codes",
            project_id=project_id,
            dataset_id=dataset_id,
            code=segment.code,
            theme=segment.theme or None,
            quote=segment.quote,
            informant=segment.informant or None,
            line_ref=segment.line_ref or None,
            created_at=db.now(),
        )
    return len(segments)


def load_segments(conn: sqlite3.Connection, project_id: int) -> list[CodedSegment]:
    rows = db.fetch_all(
        conn, "SELECT * FROM qual_codes WHERE project_id = ? ORDER BY id", (project_id,)
    )
    return [
        CodedSegment(
            code=row["code"],
            quote=row["quote"],
            informant=row["informant"] or "",
            line_ref=row["line_ref"] or "",
            theme=row["theme"] or "",
        )
        for row in rows
    ]
