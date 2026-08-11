"""Pedoman penulisan sebagai basis aturan yang mengikat seluruh keluaran.

Setiap fakultas punya aturan berbeda, dan inilah sumber kebingungan terbesar
mahasiswa (Bagian 4.3). Recens membaca PDF pedoman menjadi ``RuleSet`` — satu
objek yang kemudian mengikat outline, penomoran, format dokumen, gaya sitasi,
dan batas panjang.

Pembacaan dilakukan dengan pola yang eksplisit dan selalu menyertakan kutipan
kalimat asal setiap aturan, sehingga pengguna bisa memeriksa dari mana sebuah
angka datang, dan memperbaikinya bila pedoman ditulis dengan cara tak lazim.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import asdict, dataclass, field
from typing import Any

from .. import db

CM_PER_INCH = 2.54


@dataclass
class Margins:
    top_cm: float = 4.0
    right_cm: float = 3.0
    bottom_cm: float = 3.0
    left_cm: float = 4.0


@dataclass
class RuleSet:
    """Aturan yang berlaku pada satu karya.

    Nilai bawaan mengikuti pola yang paling umum pada pedoman skripsi kampus
    Indonesia: A4, Times New Roman 12, spasi ganda, margin 4-3-3-4.
    """

    name: str = "Aturan bawaan"
    kind: str = "bawaan"

    page_size: str = "A4"
    margins: Margins = field(default_factory=Margins)

    font_family: str = "Times New Roman"
    font_size_pt: float = 12.0
    heading_font_family: str | None = None
    line_spacing: float = 2.0
    paragraph_indent_cm: float = 1.25
    alignment: str = "justify"

    citation_style: str = "apa"
    citation_options: dict = field(default_factory=dict)

    #: Penomoran halaman: bagian awal angka romawi kecil, bagian isi angka arab.
    front_matter_numbering: str = "lowerRoman"
    body_numbering: str = "decimal"
    page_number_position: str = "bottom-center"
    body_page_number_position: str = "top-right"

    table_caption_position: str = "above"
    figure_caption_position: str = "below"
    caption_numbering: str = "per-bab"  # per-bab (Tabel 4.1) | berurutan (Tabel 1)

    include_toc: bool = True
    toc_depth: int = 3
    include_list_of_tables: bool = True
    include_list_of_figures: bool = True

    max_words: int | None = None
    max_pages: int | None = None
    abstract_max_words: int | None = None
    section_word_limits: dict[str, int] = field(default_factory=dict)

    required_sections: list[str] = field(default_factory=list)
    language: str = "id"

    #: Kalimat asal tiap aturan hasil pembacaan otomatis: {field: kutipan}.
    evidence: dict[str, str] = field(default_factory=dict)
    #: Aturan yang tidak ditemukan di pedoman dan karena itu memakai bawaan.
    assumed: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        data = asdict(self)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "RuleSet":
        data = dict(data or {})
        margins = data.pop("margins", None)
        ruleset = cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        if isinstance(margins, dict):
            ruleset.margins = Margins(**margins)
        return ruleset

    @property
    def font_size_half_points(self) -> int:
        return int(self.font_size_pt * 2)


# --- Pembacaan pedoman -------------------------------------------------------

_NUM = r"(\d+(?:[.,]\d+)?)"


def _to_float(raw: str) -> float:
    return float(raw.replace(",", "."))


def _snippet(text: str, match: re.Match, width: int = 90) -> str:
    start = max(0, match.start() - width // 2)
    end = min(len(text), match.end() + width // 2)
    return re.sub(r"\s+", " ", text[start:end]).strip()


FONT_NAMES = (
    "Times New Roman",
    "Arial",
    "Calibri",
    "Cambria",
    "Garamond",
    "Book Antiqua",
    "Georgia",
    "Helvetica",
)

STYLE_PATTERNS = {
    "apa": r"\bAPA\b",
    "ieee": r"\bIEEE\b",
    "vancouver": r"\bVancouver\b",
    "harvard": r"\bHarvard\b",
    "chicago": r"\bChicago\b",
    "mla": r"\bMLA\b",
}

MARGIN_LABELS = {
    "top_cm": r"(?:atas|top)",
    "bottom_cm": r"(?:bawah|bottom)",
    "left_cm": r"(?:kiri|left)",
    "right_cm": r"(?:kanan|right)",
}

SPACING_WORDS = {
    "satu": 1.0,
    "tunggal": 1.0,
    "single": 1.0,
    "satu setengah": 1.5,
    "dua": 2.0,
    "ganda": 2.0,
    "double": 2.0,
}


def parse_guidelines(text: str, name: str = "Pedoman", kind: str = "fakultas") -> RuleSet:
    """Baca teks pedoman menjadi aturan yang mengikat.

    Yang tidak ditemukan tidak ditebak: ia memakai nilai bawaan dan dicatat di
    ``assumed`` agar pengguna tahu bagian mana yang masih perlu dikonfirmasi.
    """
    rules = RuleSet(name=name, kind=kind)
    found: set[str] = set()
    flat = re.sub(r"[ \t]+", " ", text or "")
    lower = flat.lower()

    # Ukuran kertas
    if re.search(r"\bA4\b", flat, re.IGNORECASE):
        rules.page_size = "A4"
        found.add("page_size")
    elif re.search(r"\b(letter|kuarto)\b", lower):
        rules.page_size = "Letter"
        found.add("page_size")

    # Huruf
    for candidate in FONT_NAMES:
        match = re.search(re.escape(candidate), flat, re.IGNORECASE)
        if match:
            rules.font_family = candidate
            rules.evidence["font_family"] = _snippet(flat, match)
            found.add("font_family")
            break

    match = re.search(rf"(?:ukuran|size|huruf)[^.\n]{{0,30}}?{_NUM}\s*(?:pt|poin|point)", lower)
    if not match:
        match = re.search(rf"{_NUM}\s*(?:pt|poin|point)", lower)
    if match:
        size = _to_float(match.group(1))
        if 8 <= size <= 16:
            rules.font_size_pt = size
            rules.evidence["font_size_pt"] = _snippet(flat, match)
            found.add("font_size_pt")

    # Spasi
    match = re.search(rf"{_NUM}\s*spasi", lower) or re.search(rf"spasi\s*{_NUM}", lower)
    if match:
        spacing = _to_float(match.group(1))
        if 0.9 <= spacing <= 3:
            rules.line_spacing = spacing
            rules.evidence["line_spacing"] = _snippet(flat, match)
            found.add("line_spacing")
    else:
        for word, value in sorted(SPACING_WORDS.items(), key=lambda kv: -len(kv[0])):
            match = re.search(rf"\b{word}\s+spasi\b|\bspasi\s+{word}\b", lower)
            if match:
                rules.line_spacing = value
                rules.evidence["line_spacing"] = _snippet(flat, match)
                found.add("line_spacing")
                break

    # Margin
    for attr, label in MARGIN_LABELS.items():
        match = re.search(rf"{label}\s*[:=]?\s*{_NUM}\s*cm", lower)
        if not match:
            match = re.search(rf"{_NUM}\s*cm\s*(?:dari\s*)?(?:tepi\s*)?{label}", lower)
        if match:
            value = _to_float(match.group(1))
            if 0.5 <= value <= 8:
                setattr(rules.margins, attr, value)
                rules.evidence[f"margins.{attr}"] = _snippet(flat, match)
                found.add(f"margins.{attr}")

    # Pola ringkas "4-3-3-3" (kiri-atas-kanan-bawah)
    if not any(f.startswith("margins.") for f in found):
        match = re.search(rf"{_NUM}\s*[-–x]\s*{_NUM}\s*[-–x]\s*{_NUM}\s*[-–x]\s*{_NUM}\s*cm", lower)
        if match:
            left, top, right, bottom = (_to_float(match.group(i)) for i in range(1, 5))
            rules.margins = Margins(top_cm=top, right_cm=right, bottom_cm=bottom, left_cm=left)
            rules.evidence["margins"] = _snippet(flat, match)
            found.add("margins")

    # Gaya sitasi
    for style_key, pattern in STYLE_PATTERNS.items():
        match = re.search(pattern, flat)
        if match:
            rules.citation_style = style_key if style_key in ("apa", "ieee", "vancouver", "harvard") else "apa"
            rules.evidence["citation_style"] = _snippet(flat, match)
            found.add("citation_style")
            break
    if re.search(r"\bdkk\.?\b", lower):
        rules.citation_options["et_al_term"] = "dkk."

    # Batas panjang
    match = re.search(rf"abstrak[^.\n]{{0,60}}?(?:maksimal|maksimum|tidak lebih dari|paling banyak)\s*{_NUM}\s*kata", lower)
    if not match:
        match = re.search(rf"abstrak[^.\n]{{0,40}}?{_NUM}\s*kata", lower)
    if match:
        rules.abstract_max_words = int(_to_float(match.group(1)))
        rules.evidence["abstract_max_words"] = _snippet(flat, match)
        found.add("abstract_max_words")

    match = re.search(
        rf"(?:maksimal|maksimum|tidak lebih dari|paling banyak)\s*{_NUM}\s*kata", lower
    )
    if match:
        value = int(_to_float(match.group(1)))
        if value != rules.abstract_max_words and value > 500:
            rules.max_words = value
            rules.evidence["max_words"] = _snippet(flat, match)
            found.add("max_words")

    match = re.search(
        rf"(?:maksimal|maksimum|tidak lebih dari|paling banyak)\s*{_NUM}\s*halaman", lower
    )
    if match:
        rules.max_pages = int(_to_float(match.group(1)))
        rules.evidence["max_pages"] = _snippet(flat, match)
        found.add("max_pages")

    # Penomoran halaman
    if re.search(r"angka romawi|romawi kecil|huruf romawi", lower):
        rules.front_matter_numbering = "lowerRoman"
        found.add("front_matter_numbering")

    # Posisi caption
    if re.search(r"judul tabel[^.\n]{0,40}(di\s*)?atas", lower):
        rules.table_caption_position = "above"
        found.add("table_caption_position")
    if re.search(r"judul gambar[^.\n]{0,40}(di\s*)?bawah", lower):
        rules.figure_caption_position = "below"
        found.add("figure_caption_position")

    # Struktur wajib
    rules.required_sections = _extract_required_sections(flat)
    if rules.required_sections:
        found.add("required_sections")

    tracked = (
        "page_size", "font_family", "font_size_pt", "line_spacing", "citation_style",
        "margins.top_cm", "margins.bottom_cm", "margins.left_cm", "margins.right_cm",
        "abstract_max_words", "max_words", "max_pages", "required_sections",
    )
    combined_margins = "margins" in found
    rules.assumed = [
        f
        for f in tracked
        if f not in found and not (f.startswith("margins.") and combined_margins)
    ]
    return rules


CHAPTER_RE = re.compile(
    r"^\s*BAB\s+([IVXLC]+)\s*[.:\-]?\s*(.{0,80})$", re.IGNORECASE | re.MULTILINE
)


def _extract_required_sections(text: str) -> list[str]:
    """Ambil daftar bab yang disebut pedoman, urut kemunculan."""
    seen: list[str] = []
    for match in CHAPTER_RE.finditer(text):
        numeral = match.group(1).upper()
        title = re.sub(r"\s+", " ", match.group(2)).strip(" .:-")
        label = f"BAB {numeral}" + (f" {title.upper()}" if title else "")
        if label not in seen and len(seen) < 12:
            seen.append(label)
    return seen


# --- Penyimpanan -------------------------------------------------------------


def save_ruleset(
    conn: sqlite3.Connection,
    project_id: int,
    rules: RuleSet,
    source_file: str | None = None,
    make_active: bool = True,
) -> int:
    if make_active:
        conn.execute("UPDATE rulesets SET active = 0 WHERE project_id = ?", (project_id,))
    ruleset_id = db.insert(
        conn,
        "rulesets",
        project_id=project_id,
        name=rules.name,
        kind=rules.kind,
        source_file=source_file,
        rules_json=json.dumps(rules.to_dict(), ensure_ascii=False),
        active=int(make_active),
        created_at=db.now(),
    )
    return ruleset_id


def active_ruleset(conn: sqlite3.Connection, project_id: int) -> RuleSet:
    row = db.fetch_one(
        conn,
        "SELECT * FROM rulesets WHERE project_id = ? AND active = 1 ORDER BY id DESC LIMIT 1",
        (project_id,),
    )
    if row is None:
        return RuleSet()
    return RuleSet.from_dict(json.loads(row["rules_json"]))


def list_rulesets(conn: sqlite3.Connection, project_id: int) -> list[dict]:
    rows = db.fetch_all(
        conn, "SELECT * FROM rulesets WHERE project_id = ? ORDER BY id DESC", (project_id,)
    )
    return db.rows_to_dicts(rows, ("rules_json",))


def update_ruleset(conn: sqlite3.Connection, ruleset_id: int, patch: dict[str, Any]) -> RuleSet:
    """Perbaiki aturan hasil pembacaan otomatis secara manual."""
    row = db.fetch_one(conn, "SELECT * FROM rulesets WHERE id = ?", (ruleset_id,))
    if row is None:
        raise ValueError(f"Aturan {ruleset_id} tidak ditemukan.")
    data = json.loads(row["rules_json"])
    margins_patch = patch.pop("margins", None)
    data.update({k: v for k, v in patch.items() if k in RuleSet.__dataclass_fields__})
    if isinstance(margins_patch, dict):
        data.setdefault("margins", {}).update(margins_patch)
    # Aturan yang disunting manusia tidak lagi berstatus "diasumsikan".
    edited = set(patch) | ({"margins"} if margins_patch else set())
    data["assumed"] = [a for a in data.get("assumed", []) if a.split(".")[0] not in edited]
    db.update(conn, "rulesets", ruleset_id, rules_json=json.dumps(data, ensure_ascii=False))
    return RuleSet.from_dict(data)
