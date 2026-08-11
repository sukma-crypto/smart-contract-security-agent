"""Cek kemiripan mandiri — diposisikan sebagai edukasi menulis, bukan vonis.

Pemeriksaan dijalankan sebelum naskah masuk sistem kampus, disertai penjelasan
bagian mana yang bermasalah dan cara memparafrasenya (Bagian 4.5).

Cakupan pemeriksaan dinyatakan terus terang: perbandingan dilakukan terhadap
sumber yang ada di pustaka proyek — teks PDF yang diunggah dan abstrak referensi
terverifikasi — bukan terhadap seluruh internet. Angka yang dihasilkan karena
itu adalah batas bawah, dan tidak boleh dibaca sebagai pengganti hasil sistem
resmi kampus.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass

from ... import db
from ..manuscript import Manuscript, strip_markers

SHINGLE_SIZE = 8


@dataclass
class Match:
    text: str
    source_citekey: str
    source_title: str
    page: int | None
    section_id: int | None
    section_title: str
    block_id: int | None
    n_words: int


def _words(text: str) -> list[str]:
    return re.findall(r"\b[\w'’-]+\b", (text or "").lower())


def _shingles(words: list[str], size: int = SHINGLE_SIZE) -> dict[tuple, int]:
    """Peta n-gram ke posisi kemunculan pertamanya."""
    result: dict[tuple, int] = {}
    for index in range(len(words) - size + 1):
        gram = tuple(words[index : index + size])
        result.setdefault(gram, index)
    return result


def _merge_spans(positions: list[int], size: int = SHINGLE_SIZE) -> list[tuple[int, int]]:
    """Gabungkan n-gram bersambung menjadi satu rentang teks."""
    if not positions:
        return []
    positions = sorted(positions)
    spans = [(positions[0], positions[0] + size)]
    for position in positions[1:]:
        start, end = spans[-1]
        if position <= end:
            spans[-1] = (start, max(end, position + size))
        else:
            spans.append((position, position + size))
    return spans


def _load_corpus(conn: sqlite3.Connection, project_id: int) -> list[dict]:
    """Kumpulkan teks pembanding dari pustaka proyek."""
    corpus = []
    rows = db.fetch_all(
        conn,
        "SELECT c.text, c.page, r.citekey, r.csl_json FROM ref_chunks c "
        "JOIN refs r ON r.id = c.ref_id WHERE r.project_id = ?",
        (project_id,),
    )
    for row in rows:
        corpus.append(
            {
                "text": row["text"],
                "page": row["page"],
                "citekey": row["citekey"],
                "title": _title_from_json(row["csl_json"]),
            }
        )

    abstracts = db.fetch_all(
        conn,
        "SELECT citekey, abstract, csl_json FROM refs "
        "WHERE project_id = ? AND abstract IS NOT NULL AND abstract != ''",
        (project_id,),
    )
    for row in abstracts:
        corpus.append(
            {
                "text": row["abstract"],
                "page": None,
                "citekey": row["citekey"],
                "title": _title_from_json(row["csl_json"]),
            }
        )
    return corpus


def _title_from_json(raw: str) -> str:
    import json

    try:
        entry = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return ""
    title = entry.get("title", "")
    if isinstance(title, list):
        return title[0] if title else ""
    return str(title)


def check_similarity(
    conn: sqlite3.Connection,
    project_id: int,
    manuscript: Manuscript,
    shingle_size: int = SHINGLE_SIZE,
) -> dict:
    """Bandingkan naskah terhadap sumber di pustaka proyek."""
    corpus = _load_corpus(conn, project_id)

    source_index: dict[tuple, dict] = {}
    for document in corpus:
        for gram in _shingles(_words(document["text"]), shingle_size):
            source_index.setdefault(gram, document)

    matches: list[Match] = []
    total_shingles = 0
    matched_shingles = 0

    for section, block in manuscript.all_blocks():
        if block.kind in ("table", "figure", "equation"):
            continue
        words = _words(strip_markers(block.content))
        grams = _shingles(words, shingle_size)
        total_shingles += len(grams)
        if not grams:
            continue

        hits_by_source: dict[str, list[int]] = {}
        for gram, position in grams.items():
            document = source_index.get(gram)
            if document is None:
                continue
            matched_shingles += 1
            hits_by_source.setdefault(document["citekey"], []).append(position)

        for citekey, positions in hits_by_source.items():
            document = next(d for d in corpus if d["citekey"] == citekey)
            for start, end in _merge_spans(positions, shingle_size):
                matches.append(
                    Match(
                        text=" ".join(words[start:end]),
                        source_citekey=citekey,
                        source_title=document["title"],
                        page=document["page"],
                        section_id=section.id,
                        section_title=section.title,
                        block_id=block.id,
                        n_words=end - start,
                    )
                )

    percentage = round(100 * matched_shingles / total_shingles, 2) if total_shingles else 0.0
    matches.sort(key=lambda m: -m.n_words)

    quoted_ok, unquoted = _separate_quoted(manuscript, matches)

    return {
        "similarity_percent": percentage,
        "total_shingles": total_shingles,
        "matched_shingles": matched_shingles,
        "shingle_size": shingle_size,
        "n_sources_compared": len({d["citekey"] for d in corpus}),
        "matches": [
            {
                "text": m.text,
                "citekey": m.source_citekey,
                "source_title": m.source_title,
                "page": m.page,
                "section_id": m.section_id,
                "section_title": m.section_title,
                "block_id": m.block_id,
                "n_words": m.n_words,
                "guidance": _paraphrase_guidance(m),
            }
            for m in matches[:50]
        ],
        "n_matches": len(matches),
        "in_quotation": len(quoted_ok),
        "outside_quotation": len(unquoted),
        "scope_note": (
            f"Pembanding: {len({d['citekey'] for d in corpus})} sumber di pustaka proyek "
            f"ini. Pemeriksaan ini membantu menemukan bagian yang perlu diparafrase lebih "
            f"dahulu; ia bukan pengganti pemeriksaan resmi kampus, yang membandingkan "
            f"naskah terhadap basis data jauh lebih luas."
        ),
        "passed": percentage < 20,
    }


def _separate_quoted(manuscript: Manuscript, matches: list[Match]) -> tuple[list, list]:
    """Kutipan langsung yang ditandai dengan benar bukan masalah kemiripan."""
    quote_blocks = {
        block.id for _section, block in manuscript.all_blocks() if block.kind == "quote"
    }
    quoted = [m for m in matches if m.block_id in quote_blocks]
    unquoted = [m for m in matches if m.block_id not in quote_blocks]
    return quoted, unquoted


def _paraphrase_guidance(match: Match) -> str:
    if match.n_words >= 25:
        return (
            f"Rentang sepanjang {match.n_words} kata ini nyaris identik dengan "
            f"{match.source_citekey}. Bila gagasannya memang penting, jadikan kutipan "
            f"langsung lengkap dengan tanda kutip dan nomor halaman; bila tidak, tutup "
            f"sumbernya lalu tulis ulang dari ingatan dengan struktur kalimat sendiri."
        )
    return (
        f"Ubah struktur kalimat, bukan sekadar menukar kata dengan sinonim, lalu "
        f"tetap sertakan sitasi ke {match.source_citekey} karena gagasannya bukan milik "
        f"penulis."
    )
