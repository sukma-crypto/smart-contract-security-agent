"""Ekspor LaTeX — bentuk yang diminta banyak konferensi dan jurnal.

Naskah dikeluarkan lengkap dengan pengaturan geometri, huruf, jarak baris, dan
berkas ``.bib`` yang dibangun dari pustaka proyek, sehingga langsung bisa
dikompilasi.
"""

from __future__ import annotations

import re
from pathlib import Path

from ..citations.styles import CitationStyle, authors, container, family_name, given_name
from ..citations.styles import title_of, year as csl_year
from ..guidelines import RuleSet
from ..manuscript import CITE_PATTERN, XREF_PATTERN, Manuscript

LATEX_SPECIALS = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}

BIBTEX_TYPES = {
    "article-journal": "article",
    "paper-conference": "inproceedings",
    "book": "book",
    "chapter": "incollection",
    "thesis": "phdthesis",
    "report": "techreport",
}


def escape(text: str) -> str:
    return "".join(LATEX_SPECIALS.get(char, char) for char in (text or ""))


def _render_markers(text: str, captions: dict) -> str:
    """Ubah penanda internal menjadi perintah LaTeX asli."""

    def cite(match: re.Match) -> str:
        citekey, locator = match.group(1), match.group(2)
        return f"\\cite[{escape(locator)}]{{{citekey}}}" if locator else f"\\cite{{{citekey}}}"

    def xref(match: re.Match) -> str:
        kind, label = match.group(1), match.group(2)
        prefix = "Tabel" if kind == "tabel" else "Gambar"
        return f"{prefix}~\\ref{{{kind}:{label}}}"

    # Penanda diproses sebelum escape agar backslash-nya tidak ikut di-escape.
    placeholder_map: dict[str, str] = {}

    def stash(value: str) -> str:
        token = f"@@LTX{len(placeholder_map)}@@"
        placeholder_map[token] = value
        return token

    staged = CITE_PATTERN.sub(lambda m: stash(cite(m)), text)
    staged = XREF_PATTERN.sub(lambda m: stash(xref(m)), staged)
    escaped = escape(staged)
    for token, value in placeholder_map.items():
        escaped = escaped.replace(token, value)
    return escaped


def build_latex(
    manuscript: Manuscript,
    rules: RuleSet,
    bibliography: dict,
    meta: dict,
    output_path: Path | str,
    style: CitationStyle | None = None,
    include_front_matter: bool = True,
) -> Path:
    captions = manuscript.numbered_captions()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    spacing_command = {1.0: "\\singlespacing", 1.5: "\\onehalfspacing", 2.0: "\\doublespacing"}.get(
        rules.line_spacing, f"\\setstretch{{{rules.line_spacing}}}"
    )
    paper = "a4paper" if rules.page_size.upper() == "A4" else "letterpaper"

    lines = [
        "% Dihasilkan oleh Recens — sudah mengikuti pedoman yang berlaku pada proyek ini.",
        f"\\documentclass[{int(rules.font_size_pt)}pt,{paper}]{{article}}",
        "\\usepackage[utf8]{inputenc}",
        "\\usepackage[T1]{fontenc}",
        "\\usepackage[bahasa]{babel}",
        "\\usepackage{setspace}",
        "\\usepackage{booktabs}",
        "\\usepackage{graphicx}",
        "\\usepackage{longtable}",
        "\\usepackage{natbib}",
        (
            f"\\usepackage[{paper},top={rules.margins.top_cm}cm,"
            f"bottom={rules.margins.bottom_cm}cm,left={rules.margins.left_cm}cm,"
            f"right={rules.margins.right_cm}cm]{{geometry}}"
        ),
        _font_package(rules.font_family),
        "",
        f"\\title{{{escape(meta.get('title', 'Judul Karya'))}}}",
        f"\\author{{{escape(meta.get('author', ''))}}}",
        f"\\date{{{escape(str(meta.get('year', '')))}}}",
        "",
        "\\begin{document}",
        spacing_command,
    ]

    if include_front_matter:
        lines.append("\\maketitle")
        if meta.get("abstract"):
            lines += [
                "\\begin{abstract}",
                escape(meta["abstract"]),
                "\\end{abstract}",
            ]
            if meta.get("keywords"):
                lines.append(
                    f"\\noindent\\textbf{{Kata kunci:}} {escape(', '.join(meta['keywords']))}"
                )
        if rules.include_toc:
            lines.append("\\tableofcontents")
        if rules.include_list_of_tables:
            lines.append("\\listoftables")
        if rules.include_list_of_figures:
            lines.append("\\listoffigures")
        lines.append("\\newpage")

    def render_section(section, depth: int = 0) -> None:
        command = ["section", "subsection", "subsubsection", "paragraph"][min(depth, 3)]
        lines.append(f"\\{command}{{{escape(section.title)}}}")
        for block in section.blocks:
            caption = next((c for c in captions.values() if c["block_id"] == block.id), None)
            if block.kind == "table":
                lines.extend(_table_env(block, caption))
                continue
            if block.kind == "figure":
                lines.extend([
                    "\\begin{figure}[htbp]",
                    "\\centering",
                    f"% Sisipkan berkas gambar: {escape(block.content)}",
                    "\\includegraphics[width=0.8\\textwidth]{"
                    + (block.meta.get("file", "gambar.png")) + "}",
                ])
                if caption:
                    lines.append(f"\\caption{{{escape(caption['caption'])}}}")
                    lines.append(f"\\label{{gambar:{caption_label(caption, block)}}}")
                lines.append("\\end{figure}")
                continue
            body = _render_markers(block.content, captions)
            if block.kind == "quote":
                lines.extend(["\\begin{quote}", body, "\\end{quote}"])
            elif block.kind == "list":
                lines.append("\\begin{itemize}")
                lines.extend(
                    f"  \\item {_render_markers(line.strip(), captions)}"
                    for line in block.content.splitlines()
                    if line.strip()
                )
                lines.append("\\end{itemize}")
            else:
                lines.extend([body, ""])
        for child in section.children:
            render_section(child, depth + 1)

    for section in manuscript.sections:
        render_section(section)

    bib_path = output_path.with_suffix(".bib")
    if bibliography.get("csl_entries"):
        bib_path.write_text(
            _build_bibtex(bibliography["csl_entries"]), encoding="utf-8"
        )
        bib_style = {"apa": "apalike", "ieee": "IEEEtran", "vancouver": "vancouver"}.get(
            bibliography.get("style", "apa"), "apalike"
        )
        lines += [
            f"\\bibliographystyle{{{bib_style}}}",
            f"\\bibliography{{{bib_path.stem}}}",
        ]

    lines.append("\\end{document}")
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def caption_label(caption: dict, block) -> str:
    return block.meta.get("label") or f"blok{block.id}"


def _font_package(family: str) -> str:
    return {
        "times new roman": "\\usepackage{mathptmx}",
        "arial": "\\usepackage{helvet}\\renewcommand{\\familydefault}{\\sfdefault}",
        "helvetica": "\\usepackage{helvet}\\renewcommand{\\familydefault}{\\sfdefault}",
        "garamond": "\\usepackage{ebgaramond}",
        "book antiqua": "\\usepackage{newpxtext}",
    }.get(family.lower(), "\\usepackage{mathptmx}")


def _table_env(block, caption: dict | None) -> list[str]:
    meta = block.meta or {}
    columns = meta.get("columns") or []
    rows = meta.get("rows") or []
    if not columns and not rows:
        return []
    n_cols = len(columns) or max(len(r) for r in rows)
    spec = "l" + "c" * (n_cols - 1)

    lines = ["\\begin{table}[htbp]", "\\centering"]
    if caption:
        lines.append(f"\\caption{{{escape(caption['caption'])}}}")
        lines.append(f"\\label{{tabel:{caption_label(caption, block)}}}")
    lines += [f"\\begin{{tabular}}{{{spec}}}", "\\toprule"]
    if columns:
        lines.append(" & ".join(escape(str(c)) for c in columns) + " \\\\")
        lines.append("\\midrule")
    for row in rows:
        cells = ["" if v is None else escape(str(v)) for v in row]
        cells += [""] * (n_cols - len(cells))
        lines.append(" & ".join(cells) + " \\\\")
    lines += ["\\bottomrule", "\\end{tabular}"]
    if meta.get("note"):
        lines.append(f"\\par\\small {escape(meta['note'])}")
    lines.append("\\end{table}")
    return lines


def _build_bibtex(entries: list[dict]) -> str:
    """Bangun berkas .bib dari metadata CSL yang sudah terverifikasi."""
    blocks = []
    for entry in entries:
        entry_type = BIBTEX_TYPES.get(entry.get("type", ""), "article")
        fields = {
            "title": title_of(entry),
            "year": csl_year(entry),
            "journal" if entry_type == "article" else "booktitle": container(entry),
            "volume": entry.get("volume", ""),
            "number": entry.get("issue", ""),
            "pages": str(entry.get("page", "")).replace("-", "--"),
            "publisher": entry.get("publisher", ""),
            "doi": entry.get("DOI", ""),
        }
        author_names = " and ".join(
            f"{family_name(a)}, {given_name(a)}".strip().rstrip(",")
            for a in authors(entry)
            if family_name(a)
        )
        if author_names:
            fields["author"] = author_names

        body = ",\n".join(
            f"  {key} = {{{escape(str(value))}}}" for key, value in fields.items() if value
        )
        blocks.append(f"@{entry_type}{{{entry.get('id', 'anon')},\n{body}\n}}")
    return "\n\n".join(blocks) + "\n"
