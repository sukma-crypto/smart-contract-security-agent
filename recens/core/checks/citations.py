"""Cek silang sitasi — kesalahan sepele yang paling cepat ditemukan pembimbing.

Memastikan setiap sitasi dalam teks ada di daftar pustaka dan sebaliknya, tanpa
referensi menggantung. Pemeriksaan ini murah dijalankan dan menutup kelas
kesalahan yang biasanya baru ketahuan di menit pertama bimbingan.
"""

from __future__ import annotations

import datetime
import sqlite3

from ..citations.library import list_references
from ..citations.styles import year as csl_year
from ..manuscript import Manuscript


def check_citation_crossref(
    conn: sqlite3.Connection,
    project_id: int,
    manuscript: Manuscript,
    recency_years: int = 10,
) -> dict:
    """Periksa keselarasan sitasi dalam teks dengan pustaka proyek."""
    references = list_references(conn, project_id)
    by_key = {ref["citekey"]: ref for ref in references}
    used = manuscript.citations_with_location()
    used_keys = {item["citekey"] for item in used}

    dangling = [item for item in used if item["citekey"] not in by_key]
    uncited = [
        {
            "citekey": ref["citekey"],
            "title": _title(ref),
            "verified": bool(ref["verified"]),
        }
        for ref in references
        if ref["citekey"] not in used_keys
    ]
    unverified_in_text = [
        {
            "citekey": ref["citekey"],
            "title": _title(ref),
            "source_db": ref["source_db"],
        }
        for ref in references
        if ref["citekey"] in used_keys and not ref["verified"]
    ]

    current_year = datetime.date.today().year
    recent, old, undated = 0, 0, 0
    for ref in references:
        if ref["citekey"] not in used_keys:
            continue
        raw_year = csl_year(ref["csl_json"])
        if raw_year == "n.d." or not str(raw_year).isdigit():
            undated += 1
        elif current_year - int(raw_year) <= recency_years:
            recent += 1
        else:
            old += 1

    cited_total = recent + old + undated
    per_section: dict[str, int] = {}
    for item in used:
        per_section[item["section_title"]] = per_section.get(item["section_title"], 0) + 1

    sections_without_citation = [
        section.title
        for section in manuscript.walk()
        if section.blocks
        and section.role in ("latar_belakang", "landasan_teori", "pembahasan",
                             "penelitian_terdahulu", "kerangka_berpikir")
        and section.title not in per_section
    ]

    issues = []
    if dangling:
        keys = sorted({d["citekey"] for d in dangling})
        issues.append(
            {
                "severity": "tinggi",
                "message": (
                    f"{len(dangling)} sitasi dalam teks tidak ada di pustaka proyek: "
                    f"{', '.join(keys)}. Sitasi ini akan menjadi referensi menggantung "
                    f"di daftar pustaka."
                ),
            }
        )
    if uncited:
        issues.append(
            {
                "severity": "sedang",
                "message": (
                    f"{len(uncited)} referensi ada di pustaka tetapi tidak pernah dikutip. "
                    f"Daftar pustaka hanya memuat sumber yang benar-benar dirujuk."
                ),
            }
        )
    if unverified_in_text:
        issues.append(
            {
                "severity": "tinggi",
                "message": (
                    f"{len(unverified_in_text)} referensi yang dikutip belum tertelusur ke "
                    f"basis data ilmiah resmi. Telusuri lebih dahulu sebelum naskah "
                    f"diserahkan."
                ),
            }
        )
    if sections_without_citation:
        issues.append(
            {
                "severity": "sedang",
                "message": (
                    f"Bagian berikut belum memuat satu pun sitasi: "
                    f"{', '.join(sections_without_citation)}."
                ),
            }
        )
    if cited_total and recent / cited_total < 0.5:
        issues.append(
            {
                "severity": "sedang",
                "message": (
                    f"Hanya {recent} dari {cited_total} referensi yang dikutip terbit dalam "
                    f"{recency_years} tahun terakhir. Banyak pedoman menuntut mayoritas "
                    f"rujukan mutakhir."
                ),
            }
        )

    return {
        "n_references": len(references),
        "n_cited": len(used_keys & set(by_key)),
        "n_citations_in_text": len(used),
        "dangling": dangling,
        "uncited": uncited,
        "unverified_in_text": unverified_in_text,
        "per_section": per_section,
        "sections_without_citation": sections_without_citation,
        "recency": {
            "recent": recent,
            "old": old,
            "undated": undated,
            "window_years": recency_years,
        },
        "issues": issues,
        "passed": not dangling and not unverified_in_text,
    }


def _title(ref: dict) -> str:
    title = ref["csl_json"].get("title", "")
    if isinstance(title, list):
        return title[0] if title else ""
    return str(title)
