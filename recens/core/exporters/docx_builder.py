"""Perakit dokumen Word sesuai aturan kampus.

Pekerjaan berhari-hari menjelang penyerahan — margin, huruf, spasi, penomoran
romawi ke arab, daftar isi, daftar tabel dan gambar, serta penomoran caption —
dikerjakan di sini, dan hasilnya langsung terlihat benar atau salah
(Bagian 4.3).
"""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

from ..citations.styles import CitationStyle
from ..guidelines import RuleSet
from ..manuscript import Manuscript
from ..render import render_block

PAGE_SIZES_CM = {"A4": (21.0, 29.7), "LETTER": (21.59, 27.94)}


# --- Pembantu OOXML ----------------------------------------------------------


def _add_field(paragraph, instruction: str, placeholder: str = " ") -> None:
    """Sisipkan field Word (PAGE, TOC, dsb.) yang diperbarui saat dokumen dibuka."""
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = instruction
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    text = OxmlElement("w:t")
    text.text = placeholder
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    for element in (begin, instr, separate, text, end):
        run._r.append(element)


def _set_page_numbering(section, fmt: str, start: int | None = None) -> None:
    """Atur format penomoran halaman: angka romawi kecil atau angka arab."""
    sect_pr = section._sectPr
    page_numbers = sect_pr.find(qn("w:pgNumType"))
    if page_numbers is None:
        page_numbers = OxmlElement("w:pgNumType")
        sect_pr.append(page_numbers)
    page_numbers.set(qn("w:fmt"), fmt)
    if start is not None:
        page_numbers.set(qn("w:start"), str(start))


def _place_page_number(section, position: str) -> None:
    container = section.header if position.startswith("top") else section.footer
    container.is_linked_to_previous = False
    paragraph = container.paragraphs[0] if container.paragraphs else container.add_paragraph()
    paragraph.text = ""
    paragraph.alignment = {
        "left": WD_ALIGN_PARAGRAPH.LEFT,
        "center": WD_ALIGN_PARAGRAPH.CENTER,
        "right": WD_ALIGN_PARAGRAPH.RIGHT,
    }.get(position.split("-")[-1], WD_ALIGN_PARAGRAPH.CENTER)
    _add_field(paragraph, "PAGE", "1")


def _apply_page_setup(section, rules: RuleSet) -> None:
    width, height = PAGE_SIZES_CM.get(rules.page_size.upper(), PAGE_SIZES_CM["A4"])
    section.page_width = Cm(width)
    section.page_height = Cm(height)
    section.top_margin = Cm(rules.margins.top_cm)
    section.bottom_margin = Cm(rules.margins.bottom_cm)
    section.left_margin = Cm(rules.margins.left_cm)
    section.right_margin = Cm(rules.margins.right_cm)


def _configure_styles(document: Document, rules: RuleSet) -> None:
    normal = document.styles["Normal"]
    normal.font.name = rules.font_family
    normal.font.size = Pt(rules.font_size_pt)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), rules.font_family)
    normal.element.rPr.rFonts.set(qn("w:cs"), rules.font_family)

    paragraph_format = normal.paragraph_format
    paragraph_format.line_spacing = rules.line_spacing
    paragraph_format.space_after = Pt(0)
    paragraph_format.alignment = (
        WD_ALIGN_PARAGRAPH.JUSTIFY if rules.alignment == "justify" else WD_ALIGN_PARAGRAPH.LEFT
    )

    heading_font = rules.heading_font_family or rules.font_family
    for level in range(1, 5):
        try:
            style = document.styles[f"Heading {level}"]
        except KeyError:  # pragma: no cover
            continue
        style.font.name = heading_font
        style.font.bold = True
        style.font.color.rgb = None
        style.font.size = Pt(rules.font_size_pt + max(0, 3 - level))
        style.paragraph_format.line_spacing = rules.line_spacing
        style.paragraph_format.space_before = Pt(12)
        style.paragraph_format.space_after = Pt(6)


def _body_paragraph(document: Document, text: str, rules: RuleSet, indent: bool = True):
    paragraph = document.add_paragraph(text)
    paragraph.paragraph_format.first_line_indent = (
        Cm(rules.paragraph_indent_cm) if indent else Cm(0)
    )
    return paragraph


# --- Bagian dokumen ----------------------------------------------------------


def _add_cover(document: Document, meta: dict, rules: RuleSet) -> None:
    def centered(text: str, bold: bool = False, size_delta: float = 0.0, spacing: int = 0):
        paragraph = document.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        paragraph.paragraph_format.space_after = Pt(spacing)
        run = paragraph.add_run(text)
        run.bold = bold
        run.font.size = Pt(rules.font_size_pt + size_delta)
        return paragraph

    centered(meta.get("title", "JUDUL KARYA").upper(), bold=True, size_delta=2, spacing=24)
    if meta.get("submission_statement"):
        centered(meta["submission_statement"], spacing=24)
    if meta.get("logo_note"):
        centered(f"[{meta['logo_note']}]", spacing=24)

    centered("Oleh:", spacing=6)
    centered(meta.get("author", "Nama Penulis"), bold=True, spacing=2)
    if meta.get("student_id"):
        centered(f"NIM. {meta['student_id']}", spacing=24)

    for line in (
        meta.get("program"), meta.get("department"), meta.get("faculty"),
        meta.get("institution"), str(meta.get("year", "")),
    ):
        if line:
            centered(str(line).upper(), bold=True, spacing=2)


def _add_abstract(document: Document, meta: dict, rules: RuleSet) -> None:
    heading = document.add_paragraph()
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = heading.add_run("ABSTRAK")
    run.bold = True

    body = document.add_paragraph(meta.get("abstract", ""))
    body.paragraph_format.line_spacing = 1.0
    body.paragraph_format.first_line_indent = Cm(rules.paragraph_indent_cm)
    body.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    keywords = meta.get("keywords") or []
    if keywords:
        paragraph = document.add_paragraph()
        paragraph.paragraph_format.line_spacing = 1.0
        run = paragraph.add_run("Kata kunci: ")
        run.bold = True
        paragraph.add_run(", ".join(keywords))


def _add_toc(document: Document, rules: RuleSet) -> None:
    heading = document.add_paragraph()
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
    heading.add_run("DAFTAR ISI").bold = True
    paragraph = document.add_paragraph()
    _add_field(
        paragraph,
        f'TOC \\o "1-{rules.toc_depth}" \\h \\z \\u',
        "Perbarui daftar isi di Word: klik kanan → Update Field.",
    )


def _add_table_of_captions(document: Document, title: str, label: str) -> None:
    heading = document.add_paragraph()
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
    heading.add_run(title).bold = True
    paragraph = document.add_paragraph()
    _add_field(paragraph, f'TOC \\h \\z \\c "{label}"', "Perbarui daftar di Word.")


def _add_data_table(document: Document, block, caption: dict | None, rules: RuleSet) -> None:
    meta = block.meta or {}
    columns = meta.get("columns") or []
    rows = meta.get("rows") or []

    if caption and rules.table_caption_position == "above":
        _add_caption(document, caption, rules)

    if columns:
        table = document.add_table(rows=1, cols=len(columns))
        table.style = "Table Grid"
        for index, column in enumerate(columns):
            cell = table.rows[0].cells[index]
            cell.text = str(column)
            for paragraph in cell.paragraphs:
                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                for run in paragraph.runs:
                    run.bold = True
        for row in rows:
            cells = table.add_row().cells
            for index, value in enumerate(row[: len(columns)]):
                cells[index].text = "" if value is None else str(value)
                for paragraph in cells[index].paragraphs:
                    paragraph.paragraph_format.line_spacing = 1.0

    if meta.get("note"):
        note = document.add_paragraph()
        note.paragraph_format.line_spacing = 1.0
        run = note.add_run(f"Catatan: {meta['note']}")
        run.font.size = Pt(max(rules.font_size_pt - 2, 8))

    if caption and rules.table_caption_position == "below":
        _add_caption(document, caption, rules)


def _add_caption(document: Document, caption: dict, rules: RuleSet) -> None:
    paragraph = document.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.line_spacing = 1.0
    run = paragraph.add_run(f"{caption['kind']} {caption['number']}. {caption['caption']}")
    run.bold = True
    run.font.size = Pt(max(rules.font_size_pt - 1, 9))


def _add_section(
    document: Document,
    section,
    manuscript: Manuscript,
    rules: RuleSet,
    entries: dict,
    style: CitationStyle,
    captions: dict,
    index_map: dict,
) -> None:
    level = min(section.level, 4)
    is_chapter = level == 1

    heading = document.add_paragraph()
    heading.style = document.styles[f"Heading {level}"]
    if is_chapter:
        heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
        heading.add_run(section.title.upper())
    else:
        heading.add_run(f"{section.number} {section.title}")

    for block in section.blocks:
        if block.kind == "table":
            caption = next(
                (c for c in captions.values() if c["block_id"] == block.id), None
            )
            _add_data_table(document, block, caption, rules)
            continue
        if block.kind == "figure":
            caption = next(
                (c for c in captions.values() if c["block_id"] == block.id), None
            )
            placeholder = document.add_paragraph()
            placeholder.alignment = WD_ALIGN_PARAGRAPH.CENTER
            placeholder.add_run(f"[Gambar: {block.content or block.meta.get('caption', '')}]")
            if caption:
                _add_caption(document, caption, rules)
            continue

        text = render_block(block.content, entries, style, captions, index_map)
        if block.kind == "quote":
            paragraph = document.add_paragraph(text)
            paragraph.paragraph_format.left_indent = Cm(1.27)
            paragraph.paragraph_format.line_spacing = 1.0
            paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        elif block.kind == "list":
            for line in text.splitlines():
                if line.strip():
                    document.add_paragraph(line.strip(), style="List Bullet")
        else:
            _body_paragraph(document, text, rules)

    for child in section.children:
        _add_section(document, child, manuscript, rules, entries, style, captions, index_map)


def _add_bibliography(document: Document, bibliography: dict, rules: RuleSet) -> None:
    document.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
    heading = document.add_paragraph()
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
    heading.style = document.styles["Heading 1"]
    heading.add_run("DAFTAR PUSTAKA")

    for entry in bibliography.get("entries", []):
        paragraph = document.add_paragraph(entry["text"])
        paragraph.paragraph_format.line_spacing = 1.0
        paragraph.paragraph_format.space_after = Pt(6)
        paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        if not bibliography.get("numeric"):
            # Gaya penulis-tahun memakai indentasi gantung.
            paragraph.paragraph_format.left_indent = Cm(1.27)
            paragraph.paragraph_format.first_line_indent = Cm(-1.27)


# --- Titik masuk -------------------------------------------------------------


def build_docx(
    manuscript: Manuscript,
    rules: RuleSet,
    bibliography: dict,
    meta: dict,
    output_path: Path | str,
    style: CitationStyle | None = None,
    include_front_matter: bool = True,
) -> Path:
    """Rakit naskah menjadi berkas Word yang sudah patuh pedoman."""
    from ..citations.styles import get_style

    style = style or get_style(bibliography.get("style", "apa"))
    entries = {e["id"]: e for e in _entries_from_bibliography(bibliography) if e.get("id")}
    index_map = bibliography.get("index_map") or {}
    captions = manuscript.numbered_captions()

    document = Document()
    _configure_styles(document, rules)
    _apply_page_setup(document.sections[0], rules)

    if include_front_matter:
        front = document.sections[0]
        _set_page_numbering(front, rules.front_matter_numbering, start=1)
        _place_page_number(front, rules.page_number_position)

        _add_cover(document, meta, rules)
        if meta.get("abstract"):
            document.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
            _add_abstract(document, meta, rules)
        if rules.include_toc:
            document.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
            _add_toc(document, rules)
        if rules.include_list_of_tables:
            document.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
            _add_table_of_captions(document, "DAFTAR TABEL", "Tabel")
        if rules.include_list_of_figures:
            document.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
            _add_table_of_captions(document, "DAFTAR GAMBAR", "Gambar")

        body = document.add_section(WD_SECTION.NEW_PAGE)
        _apply_page_setup(body, rules)
        _set_page_numbering(body, rules.body_numbering, start=1)
        _place_page_number(body, rules.body_page_number_position)
    else:
        _set_page_numbering(document.sections[0], rules.body_numbering, start=1)
        _place_page_number(document.sections[0], rules.body_page_number_position)

    for section in manuscript.sections:
        _add_section(document, section, manuscript, rules, entries, style, captions, index_map)

    if bibliography.get("entries"):
        _add_bibliography(document, bibliography, rules)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    document.save(str(output_path))
    return output_path


def _entries_from_bibliography(bibliography: dict) -> list[dict]:
    """Ambil metadata CSL dari struktur daftar pustaka."""
    return bibliography.get("csl_entries", [])
