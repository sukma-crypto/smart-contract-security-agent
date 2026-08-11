"""Cek konsistensi — cacat logika yang paling sering diserang penguji.

Keselarasan rumusan masalah, tujuan, hipotesis, dan kesimpulan tidak terlihat
saat membaca per bab; ia hanya muncul ketika keempatnya dijajarkan. Modul ini
menjajarkannya secara mekanis: menghitung jumlah butir tiap bagian, memasangkan
butir yang bersesuaian lewat irisan kata kunci, lalu menandai butir yang tidak
punya pasangan.
"""

from __future__ import annotations

import re

from ..manuscript import Manuscript, strip_markers
from ..retrieval import tokenize

#: Peran bagian yang harus saling bersesuaian satu lawan satu.
ALIGNED_ROLES = ("rumusan_masalah", "tujuan", "hipotesis", "simpulan")

ROLE_LABELS = {
    "rumusan_masalah": "Rumusan Masalah",
    "tujuan": "Tujuan Penelitian",
    "hipotesis": "Hipotesis",
    "simpulan": "Simpulan",
}

ITEM_PATTERN = re.compile(
    r"^\s*(?:\(?\d+[.)]|[a-h][.)]|H\d+[.:]?|[-•*])\s+(.{3,})$", re.MULTILINE
)


def extract_items(text: str) -> list[str]:
    """Ambil butir bernomor dari sebuah bagian.

    Bila bagian ditulis sebagai paragraf mengalir tanpa penomoran, tiap kalimat
    tanya atau kalimat yang memuat penanda tujuan diperlakukan sebagai butir.
    """
    clean = strip_markers(text)
    items = [match.group(1).strip() for match in ITEM_PATTERN.finditer(clean)]
    if items:
        return items

    sentences = [s.strip() for s in re.split(r"(?<=[.?!])\s+", clean) if s.strip()]
    candidates = [
        s for s in sentences
        if s.endswith("?")
        or re.search(r"\b(apakah|bagaimana|seberapa|mengapa|untuk mengetahui|"
                     r"untuk menganalisis|untuk menguji|diduga|terdapat pengaruh|"
                     r"berpengaruh)\b", s.lower())
    ]
    return candidates or ([sentences[0]] if sentences else [])


def _keywords(text: str) -> set[str]:
    return set(tokenize(text))


def _match_score(left: str, right: str) -> float:
    a, b = _keywords(left), _keywords(right)
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def align_items(
    source: list[str], target: list[str], threshold: float = 0.34
) -> list[dict]:
    """Pasangkan tiap butir sumber dengan butir target yang paling bersesuaian."""
    pairs = []
    used: set[int] = set()
    for index, item in enumerate(source):
        best_index, best_score = None, 0.0
        for candidate_index, candidate in enumerate(target):
            if candidate_index in used:
                continue
            score = _match_score(item, candidate)
            if score > best_score:
                best_index, best_score = candidate_index, score
        matched = best_index is not None and best_score >= threshold
        if matched:
            used.add(best_index)
        pairs.append(
            {
                "index": index + 1,
                "source": item,
                "target": target[best_index] if matched else None,
                "score": round(best_score, 3),
                "matched": matched,
            }
        )
    return pairs


def check_consistency(manuscript: Manuscript) -> dict:
    """Jajarkan rumusan masalah, tujuan, hipotesis, dan simpulan."""
    collected: dict[str, list[str]] = {}
    present_roles: list[str] = []
    for role in ALIGNED_ROLES:
        sections = manuscript.sections_by_role(role)
        if not sections:
            continue
        present_roles.append(role)
        text = "\n".join(
            block.content for section in sections for block in section.blocks
        )
        collected[role] = extract_items(text)

    issues: list[dict] = []
    counts = {role: len(items) for role, items in collected.items()}

    missing_roles = [r for r in ALIGNED_ROLES if r not in collected]
    for role in missing_roles:
        if role == "hipotesis":
            continue  # penelitian kualitatif dan deskriptif memang tanpa hipotesis
        issues.append(
            {
                "severity": "tinggi",
                "message": f"Bagian {ROLE_LABELS[role]} belum ada atau masih kosong.",
                "role": role,
            }
        )

    if "rumusan_masalah" in collected and "tujuan" in collected:
        if counts["rumusan_masalah"] != counts["tujuan"]:
            issues.append(
                {
                    "severity": "tinggi",
                    "message": (
                        f"Jumlah rumusan masalah ({counts['rumusan_masalah']}) tidak sama "
                        f"dengan jumlah tujuan penelitian ({counts['tujuan']}). Setiap "
                        f"rumusan masalah harus punya tujuan yang menjawabnya."
                    ),
                    "role": "tujuan",
                }
            )
    if "rumusan_masalah" in collected and "simpulan" in collected:
        if counts["simpulan"] < counts["rumusan_masalah"]:
            issues.append(
                {
                    "severity": "tinggi",
                    "message": (
                        f"Terdapat {counts['rumusan_masalah']} rumusan masalah tetapi hanya "
                        f"{counts['simpulan']} butir simpulan. Setiap rumusan masalah harus "
                        f"terjawab di simpulan."
                    ),
                    "role": "simpulan",
                }
            )

    alignments = {}
    base = collected.get("rumusan_masalah", [])
    for role in ("tujuan", "hipotesis", "simpulan"):
        if not base or role not in collected:
            continue
        pairs = align_items(base, collected[role])
        alignments[role] = pairs
        unmatched = [p for p in pairs if not p["matched"]]
        for pair in unmatched:
            issues.append(
                {
                    "severity": "sedang",
                    "message": (
                        f"Rumusan masalah nomor {pair['index']} tidak menemukan pasangan yang "
                        f"jelas di bagian {ROLE_LABELS[role]}."
                    ),
                    "role": role,
                    "detail": pair["source"][:160],
                }
            )

    terms = check_term_consistency(manuscript)
    for variant in terms["inconsistent"]:
        issues.append(
            {
                "severity": "sedang",
                "message": (
                    f"Istilah '{variant['canonical']}' ditulis dalam beberapa bentuk: "
                    f"{', '.join(variant['variants'])}. Samakan penggunaannya di seluruh naskah."
                ),
                "role": "istilah",
            }
        )

    return {
        "counts": counts,
        "items": collected,
        "alignments": alignments,
        "terms": terms,
        "issues": issues,
        "passed": not any(i["severity"] == "tinggi" for i in issues),
    }


#: Pasangan istilah yang kerap dipakai bergantian dalam satu naskah.
INTERCHANGEABLE = (
    ("karyawan", "pegawai", "pekerja"),
    ("siswa", "murid", "peserta didik"),
    ("mahasiswa", "peserta didik"),
    ("kinerja", "performa"),
    ("pengaruh", "dampak", "efek"),
    ("variabel bebas", "variabel independen"),
    ("variabel terikat", "variabel dependen"),
    ("responden", "informan", "partisipan"),
    ("kuesioner", "angket"),
    ("simpulan", "kesimpulan"),
    ("daring", "online"),
    ("luring", "offline"),
)


def check_term_consistency(manuscript: Manuscript, min_count: int = 2) -> dict:
    """Deteksi istilah yang ditulis berbeda-beda untuk maksud yang sama."""
    text = manuscript.text().lower()
    inconsistent = []
    for group in INTERCHANGEABLE:
        used = []
        for term in group:
            count = len(re.findall(rf"\b{re.escape(term)}\b", text))
            if count >= min_count:
                used.append((term, count))
        if len(used) > 1:
            used.sort(key=lambda pair: -pair[1])
            inconsistent.append(
                {
                    "canonical": used[0][0],
                    "variants": [f"{term} ({count}×)" for term, count in used],
                    "recommendation": (
                        f"Pilih satu istilah — '{used[0][0]}' paling sering dipakai — lalu "
                        f"samakan seluruh kemunculannya."
                    ),
                }
            )
    return {"inconsistent": inconsistent, "checked_groups": len(INTERCHANGEABLE)}
