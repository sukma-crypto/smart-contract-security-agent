"""Template Jurnal Tujuan: menyesuaikan naskah dengan pedoman penulis jurnal.

Naskah tidak ditolak di meja editor hanya karena salah format (Bagian 4.8).
Penolakan desk-reject hampir selalu bersumber dari hal yang bisa diperiksa
mesin: struktur bagian yang tidak sesuai, gaya sitasi yang keliru, batas kata
yang terlampaui, atau abstrak yang melebihi ketentuan.

Profil jurnal di sini adalah ``RuleSet`` yang sama dengan pedoman kampus,
ditambah struktur bagian wajib. Dengan begitu satu mesin format melayani
skripsi maupun artikel, dan pengecekan kesiapan submisi memakai perhitungan
yang sama dengan pengecekan naskah kampus.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .guidelines import Margins, RuleSet
from .manuscript import Manuscript


@dataclass
class JournalProfile:
    """Ketentuan satu jurnal atau konferensi tujuan."""

    key: str
    name: str
    #: Struktur bagian wajib, urut.
    sections: tuple[str, ...]
    citation_style: str = "apa"
    max_words: int | None = None
    abstract_max_words: int | None = None
    max_keywords: int | None = None
    #: Pola abstrak terstruktur bila diminta jurnal.
    structured_abstract: tuple[str, ...] = ()
    language: str = "id"
    requires_english_abstract: bool = True
    table_format: str = "Tabel tanpa garis vertikal, hanya garis horizontal (booktabs)."
    font_family: str = "Times New Roman"
    font_size_pt: float = 12.0
    line_spacing: float = 1.0
    notes: tuple[str, ...] = ()

    def to_ruleset(self) -> RuleSet:
        """Ubah profil jurnal menjadi aturan yang mengikat seluruh keluaran."""
        return RuleSet(
            name=f"Pedoman penulis {self.name}",
            kind="jurnal",
            font_family=self.font_family,
            font_size_pt=self.font_size_pt,
            line_spacing=self.line_spacing,
            citation_style=self.citation_style,
            max_words=self.max_words,
            abstract_max_words=self.abstract_max_words,
            required_sections=list(self.sections),
            margins=Margins(top_cm=2.5, right_cm=2.5, bottom_cm=2.5, left_cm=2.5),
            include_toc=False,
            include_list_of_tables=False,
            include_list_of_figures=False,
            front_matter_numbering="decimal",
            caption_numbering="berurutan",
            paragraph_indent_cm=0.5,
        )

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "name": self.name,
            "sections": list(self.sections),
            "citation_style": self.citation_style,
            "max_words": self.max_words,
            "abstract_max_words": self.abstract_max_words,
            "max_keywords": self.max_keywords,
            "structured_abstract": list(self.structured_abstract),
            "language": self.language,
            "requires_english_abstract": self.requires_english_abstract,
            "table_format": self.table_format,
            "notes": list(self.notes),
        }


#: Profil bawaan yang mewakili pola paling umum. Jurnal sesungguhnya
#: ditambahkan pengguna lewat unggahan pedoman penulisnya.
BUILTIN_PROFILES: dict[str, JournalProfile] = {
    "sinta_umum": JournalProfile(
        key="sinta_umum",
        name="Jurnal nasional terakreditasi (pola umum SINTA)",
        sections=("Abstrak", "Pendahuluan", "Metode", "Hasil dan Pembahasan", "Simpulan"),
        citation_style="apa",
        max_words=7000,
        abstract_max_words=250,
        max_keywords=5,
        language="id",
        notes=(
            "Sebagian besar jurnal SINTA menggabungkan hasil dan pembahasan dalam satu "
            "bagian.",
            "Abstrak wajib dwibahasa: Indonesia dan Inggris.",
        ),
    ),
    "internasional_imrad": JournalProfile(
        key="internasional_imrad",
        name="Jurnal internasional (IMRAD, gaya APA)",
        sections=("Abstract", "Introduction", "Methods", "Results", "Discussion", "Conclusion"),
        citation_style="apa",
        max_words=8000,
        abstract_max_words=250,
        max_keywords=6,
        structured_abstract=("Purpose", "Design/methodology", "Findings", "Originality"),
        language="en",
        requires_english_abstract=False,
        notes=("Rujukan sebaiknya didominasi terbitan sepuluh tahun terakhir.",),
    ),
    "konferensi_ieee": JournalProfile(
        key="konferensi_ieee",
        name="Prosiding konferensi (template IEEE)",
        sections=("Abstract", "Introduction", "Method", "Result and Discussion", "Conclusion"),
        citation_style="ieee",
        max_words=5000,
        abstract_max_words=200,
        max_keywords=5,
        language="en",
        requires_english_abstract=False,
        font_family="Times New Roman",
        font_size_pt=10.0,
        table_format="Tabel dua kolom, judul di atas, penomoran angka Romawi.",
        notes=(
            "Batas panjang konferensi lazimnya dihitung per halaman, bukan per kata; "
            "periksa ketentuan penyelenggara.",
        ),
    ),
}


@dataclass
class ReadinessReport:
    profile: str
    issues: list[dict] = field(default_factory=list)
    matched_sections: list[str] = field(default_factory=list)
    missing_sections: list[str] = field(default_factory=list)
    extra_sections: list[str] = field(default_factory=list)
    word_count: int = 0

    @property
    def ready(self) -> bool:
        return not any(i["severity"] == "tinggi" for i in self.issues)

    def to_dict(self) -> dict:
        return {
            "profile": self.profile,
            "ready": self.ready,
            "word_count": self.word_count,
            "matched_sections": self.matched_sections,
            "missing_sections": self.missing_sections,
            "extra_sections": self.extra_sections,
            "issues": self.issues,
        }


def _normalize(title: str) -> str:
    return re.sub(r"[^a-z]", "", title.lower())


#: Padanan judul bagian lintas bahasa, agar naskah Indonesia tetap terbaca
#: sebagai memenuhi struktur jurnal berbahasa Inggris.
EQUIVALENTS: dict[str, set[str]] = {
    "abstract": {"abstrak", "abstract"},
    "introduction": {"pendahuluan", "introduction", "latarbelakang"},
    "methods": {"metode", "metodologi", "methods", "method", "metodepenelitian"},
    "results": {"hasil", "results", "result", "hasilpenelitian"},
    "discussion": {"pembahasan", "discussion"},
    "resultsanddiscussion": {"hasildanpembahasan", "resultanddiscussion",
                             "resultsanddiscussion"},
    "conclusion": {"simpulan", "kesimpulan", "conclusion", "penutup"},
}


def _canonical(title: str) -> str:
    normalized = _normalize(title)
    for canonical, variants in EQUIVALENTS.items():
        if normalized in variants:
            return canonical
    return normalized


def check_readiness(
    manuscript: Manuscript, profile: JournalProfile, keywords: list[str] | None = None
) -> ReadinessReport:
    """Periksa kesiapan naskah terhadap ketentuan jurnal tujuan."""
    report = ReadinessReport(profile=profile.name, word_count=manuscript.word_count)

    present = {_canonical(s.title): s for s in manuscript.sections}
    required = {_canonical(name): name for name in profile.sections}

    for canonical, original in required.items():
        if canonical in present:
            report.matched_sections.append(original)
            continue
        # "Hasil dan Pembahasan" boleh terpenuhi oleh dua bagian terpisah.
        if canonical == "resultsanddiscussion" and {"results", "discussion"} <= set(present):
            report.matched_sections.append(original)
            continue
        if canonical in ("results", "discussion") and "resultsanddiscussion" in present:
            report.matched_sections.append(original)
            continue
        report.missing_sections.append(original)

    for canonical, section in present.items():
        if canonical not in required and canonical not in (
            "results", "discussion", "resultsanddiscussion"
        ):
            report.extra_sections.append(section.title)

    if report.missing_sections:
        report.issues.append(
            {
                "severity": "tinggi",
                "message": (
                    f"Bagian wajib belum ada: {', '.join(report.missing_sections)}. "
                    f"Editor lazimnya menolak naskah yang strukturnya tidak sesuai "
                    f"sebelum dikirim ke reviewer."
                ),
            }
        )
    if report.extra_sections:
        report.issues.append(
            {
                "severity": "sedang",
                "message": (
                    f"Bagian berikut tidak ada pada struktur jurnal ini: "
                    f"{', '.join(report.extra_sections)}. Serap isinya ke bagian yang "
                    f"sesuai atau hapus."
                ),
            }
        )

    if profile.max_words and manuscript.word_count > profile.max_words:
        report.issues.append(
            {
                "severity": "tinggi",
                "message": (
                    f"Naskah berisi {manuscript.word_count} kata, melebihi batas "
                    f"{profile.max_words} kata. Perlu dipangkas "
                    f"{manuscript.word_count - profile.max_words} kata."
                ),
            }
        )

    if profile.abstract_max_words:
        abstracts = manuscript.sections_by_role("abstrak") or [
            s for s in manuscript.sections if _canonical(s.title) == "abstract"
        ]
        if abstracts:
            abstract_words = sum(s.word_count for s in abstracts)
            if abstract_words > profile.abstract_max_words:
                report.issues.append(
                    {
                        "severity": "tinggi",
                        "message": (
                            f"Abstrak berisi {abstract_words} kata, melebihi batas "
                            f"{profile.abstract_max_words} kata."
                        ),
                    }
                )

    if keywords is not None and profile.max_keywords and len(keywords) > profile.max_keywords:
        report.issues.append(
            {
                "severity": "sedang",
                "message": (
                    f"Kata kunci berjumlah {len(keywords)}, melebihi batas "
                    f"{profile.max_keywords}."
                ),
            }
        )

    if profile.requires_english_abstract:
        report.issues.append(
            {
                "severity": "rendah",
                "message": (
                    "Jurnal ini menuntut abstrak dwibahasa. Susun versi bahasa Inggris "
                    "lewat fitur Dua Bahasa agar istilah teknisnya konsisten."
                ),
            }
        )

    return report


def get_profile(key: str) -> JournalProfile:
    try:
        return BUILTIN_PROFILES[key]
    except KeyError:
        raise ValueError(
            f"Profil jurnal '{key}' tidak dikenal. Pilihan bawaan: "
            f"{', '.join(BUILTIN_PROFILES)}. Untuk jurnal lain, unggah pedoman "
            f"penulisnya lewat langkah 2."
        ) from None
