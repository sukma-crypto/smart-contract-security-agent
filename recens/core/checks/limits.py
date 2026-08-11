"""Cek batas panjang — dipantau sejak awal penulisan, bukan di menit terakhir.

Batas panjang datang dari pedoman yang berlaku: jumlah halaman untuk karya
pendek, target kata per bab untuk tugas akhir, dan batas kata ketat termasuk
abstrak untuk artikel publikasi (Bagian 2.2).
"""

from __future__ import annotations

from ..guidelines import RuleSet
from ..manuscript import Manuscript
from ..worktypes import WorkType


def estimate_pages(word_count: int, rules: RuleSet) -> float:
    """Perkirakan jumlah halaman dari aturan format yang berlaku.

    Perkiraan dihitung dari luas area teks, ukuran huruf, dan jarak baris —
    bukan angka tetap — sehingga ikut berubah saat pedoman diganti.
    """
    page_height_cm = 29.7 if rules.page_size.upper() == "A4" else 27.94
    page_width_cm = 21.0 if rules.page_size.upper() == "A4" else 21.59

    text_height_cm = page_height_cm - rules.margins.top_cm - rules.margins.bottom_cm
    text_width_cm = page_width_cm - rules.margins.left_cm - rules.margins.right_cm
    if text_height_cm <= 0 or text_width_cm <= 0:
        return 0.0

    line_height_cm = (rules.font_size_pt * 1.2 * rules.line_spacing) / 28.35
    lines_per_page = max(int(text_height_cm / line_height_cm), 1)

    # Lebar rata-rata karakter pada huruf berkait ≈ 0,5 × ukuran huruf.
    char_width_cm = (rules.font_size_pt * 0.5) / 28.35
    chars_per_line = max(int(text_width_cm / char_width_cm), 20)
    words_per_line = max(chars_per_line / 6.5, 1)
    words_per_page = lines_per_page * words_per_line

    return round(word_count / words_per_page, 1) if words_per_page else 0.0


def check_length_limits(
    manuscript: Manuscript, rules: RuleSet, work_type: WorkType | None = None
) -> dict:
    """Bandingkan panjang tiap bagian terhadap batas dan target yang berlaku."""
    total_words = manuscript.word_count
    estimated_pages = estimate_pages(total_words, rules)

    hard_limit = rules.max_words
    if hard_limit is None and work_type is not None:
        hard_limit = work_type.hard_word_limit

    issues: list[dict] = []
    sections = []
    for section in manuscript.walk():
        target = section.target_words or sum(c.target_words for c in section.walk())
        words = section.word_count
        limit = rules.section_word_limits.get(section.title)
        status = "sesuai"
        if limit and words > limit:
            status = "melebihi batas"
            issues.append(
                {
                    "severity": "tinggi",
                    "section": section.title,
                    "message": f"{section.title} berisi {words} kata, melebihi batas {limit} kata.",
                }
            )
        elif target:
            ratio = words / target
            if ratio < 0.5:
                status = "jauh di bawah target"
            elif ratio < 0.8:
                status = "di bawah target"
            elif ratio > 1.5:
                status = "jauh di atas target"
            elif ratio > 1.2:
                status = "di atas target"
        sections.append(
            {
                "id": section.id,
                "number": section.number,
                "title": section.title,
                "word_count": words,
                "target_words": target,
                "limit": limit,
                "status": status,
                "estimated_pages": estimate_pages(words, rules),
            }
        )

    if hard_limit and total_words > hard_limit:
        issues.append(
            {
                "severity": "tinggi",
                "section": None,
                "message": (
                    f"Naskah berisi {total_words} kata, melebihi batas {hard_limit} kata. "
                    f"Perlu dipangkas {total_words - hard_limit} kata."
                ),
            }
        )
    if rules.max_pages and estimated_pages > rules.max_pages:
        issues.append(
            {
                "severity": "tinggi",
                "section": None,
                "message": (
                    f"Perkiraan tebal naskah {estimated_pages} halaman, melebihi batas "
                    f"{rules.max_pages} halaman menurut pedoman yang berlaku."
                ),
            }
        )

    abstract_words = None
    if rules.abstract_max_words:
        abstracts = manuscript.sections_by_role("abstrak")
        if abstracts:
            abstract_words = sum(s.word_count for s in abstracts)
            if abstract_words > rules.abstract_max_words:
                issues.append(
                    {
                        "severity": "tinggi",
                        "section": "Abstrak",
                        "message": (
                            f"Abstrak berisi {abstract_words} kata, melebihi batas "
                            f"{rules.abstract_max_words} kata."
                        ),
                    }
                )

    return {
        "total_words": total_words,
        "target_words": manuscript.target_words,
        "estimated_pages": estimated_pages,
        "max_words": hard_limit,
        "max_pages": rules.max_pages,
        "abstract_words": abstract_words,
        "abstract_max_words": rules.abstract_max_words,
        "sections": sections,
        "issues": issues,
        "passed": not issues,
    }
