"""Ekspor PDF dengan margin, huruf, dan jarak baris sesuai aturan yang berlaku."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4, LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table as PdfTable,
    TableStyle,
)
from reportlab.lib import colors

from ..citations.styles import CitationStyle
from ..guidelines import RuleSet
from ..manuscript import Manuscript
from ..render import render_block

#: Huruf bawaan reportlab yang paling mendekati huruf pedoman kampus.
FONT_MAP = {
    "times new roman": "Times-Roman",
    "cambria": "Times-Roman",
    "garamond": "Times-Roman",
    "book antiqua": "Times-Roman",
    "georgia": "Times-Roman",
    "arial": "Helvetica",
    "helvetica": "Helvetica",
    "calibri": "Helvetica",
}


def _font(rules: RuleSet) -> tuple[str, str]:
    base = FONT_MAP.get(rules.font_family.lower(), "Times-Roman")
    bold = "Times-Bold" if base == "Times-Roman" else "Helvetica-Bold"
    return base, bold


def _escape(text: str) -> str:
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def build_pdf(
    manuscript: Manuscript,
    rules: RuleSet,
    bibliography: dict,
    meta: dict,
    output_path: Path | str,
    style: CitationStyle | None = None,
    include_front_matter: bool = True,
) -> Path:
    from ..citations.styles import get_style

    style = style or get_style(bibliography.get("style", "apa"))
    entries = {e["id"]: e for e in bibliography.get("csl_entries", []) if e.get("id")}
    index_map = bibliography.get("index_map") or {}
    captions = manuscript.numbered_captions()

    base_font, bold_font = _font(rules)
    leading = rules.font_size_pt * 1.2 * rules.line_spacing

    body_style = ParagraphStyle(
        "Body",
        fontName=base_font,
        fontSize=rules.font_size_pt,
        leading=leading,
        alignment=TA_JUSTIFY if rules.alignment == "justify" else 0,
        firstLineIndent=rules.paragraph_indent_cm * cm,
        spaceAfter=0,
    )
    chapter_style = ParagraphStyle(
        "Chapter", parent=body_style, fontName=bold_font,
        fontSize=rules.font_size_pt + 2, alignment=TA_CENTER,
        firstLineIndent=0, spaceBefore=12, spaceAfter=12,
    )
    heading_style = ParagraphStyle(
        "Heading", parent=body_style, fontName=bold_font,
        fontSize=rules.font_size_pt + 1, firstLineIndent=0, spaceBefore=10, spaceAfter=6,
    )
    caption_style = ParagraphStyle(
        "Caption", parent=body_style, fontName=bold_font,
        fontSize=max(rules.font_size_pt - 1, 8), alignment=TA_CENTER,
        firstLineIndent=0, leading=max(rules.font_size_pt - 1, 8) * 1.2, spaceAfter=4,
    )
    quote_style = ParagraphStyle(
        "Quote", parent=body_style, leftIndent=1.27 * cm,
        firstLineIndent=0, leading=rules.font_size_pt * 1.2,
    )
    biblio_style = ParagraphStyle(
        "Biblio", parent=body_style, leading=rules.font_size_pt * 1.2,
        firstLineIndent=-1.27 * cm, leftIndent=1.27 * cm, spaceAfter=6,
    )

    story: list = []

    if include_front_matter:
        story.append(Spacer(1, 4 * cm))
        story.append(Paragraph(_escape(meta.get("title", "JUDUL KARYA")).upper(), chapter_style))
        story.append(Spacer(1, 2 * cm))
        for line in ("Oleh:", meta.get("author", ""), meta.get("student_id", "")):
            if line:
                story.append(Paragraph(_escape(str(line)), chapter_style))
        story.append(Spacer(1, 2 * cm))
        for line in (meta.get("faculty"), meta.get("institution"), str(meta.get("year", ""))):
            if line:
                story.append(Paragraph(_escape(str(line)).upper(), chapter_style))
        story.append(PageBreak())

        if meta.get("abstract"):
            story.append(Paragraph("ABSTRAK", chapter_style))
            story.append(Paragraph(_escape(meta["abstract"]), body_style))
            if meta.get("keywords"):
                story.append(Spacer(1, 0.4 * cm))
                story.append(
                    Paragraph(
                        f"<b>Kata kunci:</b> {_escape(', '.join(meta['keywords']))}", body_style
                    )
                )
            story.append(PageBreak())

    def render_section(section) -> None:
        if section.level == 1:
            story.append(Paragraph(_escape(section.title).upper(), chapter_style))
        else:
            story.append(
                Paragraph(f"{section.number} {_escape(section.title)}", heading_style)
            )

        for block in section.blocks:
            caption = next((c for c in captions.values() if c["block_id"] == block.id), None)
            if block.kind == "table":
                if caption and rules.table_caption_position == "above":
                    story.append(
                        Paragraph(
                            f"{caption['kind']} {caption['number']}. "
                            f"{_escape(caption['caption'])}",
                            caption_style,
                        )
                    )
                story.append(_build_table(block, base_font, bold_font, rules))
                if caption and rules.table_caption_position == "below":
                    story.append(
                        Paragraph(
                            f"{caption['kind']} {caption['number']}. "
                            f"{_escape(caption['caption'])}",
                            caption_style,
                        )
                    )
                story.append(Spacer(1, 0.3 * cm))
                continue
            if block.kind == "figure":
                story.append(
                    Paragraph(f"[Gambar: {_escape(block.content)}]", caption_style)
                )
                if caption:
                    story.append(
                        Paragraph(
                            f"{caption['kind']} {caption['number']}. "
                            f"{_escape(caption['caption'])}",
                            caption_style,
                        )
                    )
                continue

            text = _escape(render_block(block.content, entries, style, captions, index_map))
            story.append(Paragraph(text, quote_style if block.kind == "quote" else body_style))

        for child in section.children:
            render_section(child)

    for section in manuscript.sections:
        render_section(section)

    if bibliography.get("entries"):
        story.append(PageBreak())
        story.append(Paragraph("DAFTAR PUSTAKA", chapter_style))
        for entry in bibliography["entries"]:
            story.append(Paragraph(_escape(entry["text"]), biblio_style))

    page_size = A4 if rules.page_size.upper() == "A4" else LETTER
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    document = SimpleDocTemplate(
        str(output_path),
        pagesize=page_size,
        topMargin=rules.margins.top_cm * cm,
        bottomMargin=rules.margins.bottom_cm * cm,
        leftMargin=rules.margins.left_cm * cm,
        rightMargin=rules.margins.right_cm * cm,
        title=meta.get("title", "Naskah"),
        author=meta.get("author", ""),
    )
    document.build(story, onFirstPage=_page_number, onLaterPages=_page_number)
    return output_path


def _page_number(canvas, document) -> None:
    canvas.saveState()
    canvas.setFont("Times-Roman", 10)
    canvas.drawCentredString(
        document.pagesize[0] / 2, 1.2 * cm, str(document.page)
    )
    canvas.restoreState()


def _build_table(block, base_font: str, bold_font: str, rules: RuleSet) -> PdfTable:
    meta = block.meta or {}
    columns = [str(c) for c in (meta.get("columns") or [])]
    rows = [[("" if v is None else str(v)) for v in row] for row in (meta.get("rows") or [])]
    data = [columns, *rows] if columns else rows or [[""]]

    table = PdfTable(data, repeatRows=1 if columns else 0)
    font_size = max(rules.font_size_pt - 2, 7)
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), bold_font),
                ("FONTNAME", (0, 1), (-1, -1), base_font),
                ("FONTSIZE", (0, 0), (-1, -1), font_size),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (1, 1), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table
