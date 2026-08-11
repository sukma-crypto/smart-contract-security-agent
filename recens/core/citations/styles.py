"""Perenderan gaya sitasi di atas metadata CSL-JSON.

Citation Style Language dipakai sebagai standar terbuka (Bagian 7.1). Modul ini
merender gaya yang paling sering diminta kampus dan jurnal Indonesia — APA,
IEEE, Harvard, Vancouver — serta gaya khusus kampus yang parameternya diambil
dari pedoman yang diunggah pengguna.

Satu sumber metadata, banyak bentuk keluaran: itulah sebabnya sitasi dalam teks
tidak pernah lepas sinkron dari daftar pustaka.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

CSL = dict[str, Any]


# --- Pembantu metadata -------------------------------------------------------


def authors(entry: CSL) -> list[dict]:
    return [a for a in entry.get("author", []) if isinstance(a, dict)]


def year(entry: CSL) -> str:
    issued = entry.get("issued") or {}
    parts = issued.get("date-parts") or []
    if parts and parts[0]:
        return str(parts[0][0])
    return "n.d."


def family_name(author: dict) -> str:
    if author.get("family"):
        return str(author["family"]).strip()
    literal = author.get("literal") or author.get("name") or ""
    return str(literal).strip()


def given_name(author: dict) -> str:
    return str(author.get("given", "")).strip()


def initials(author: dict, dotted: bool = True, spaced: bool = True) -> str:
    given = given_name(author)
    if not given:
        return ""
    letters = [part[0].upper() for part in given.replace("-", " ").split() if part]
    if not letters:
        return ""
    sep = " " if spaced else ""
    return sep.join(f"{ch}." for ch in letters) if dotted else sep.join(letters)


def page_range(entry: CSL) -> str:
    return str(entry.get("page", "") or "")


def container(entry: CSL) -> str:
    value = entry.get("container-title", "")
    if isinstance(value, list):
        return value[0] if value else ""
    return str(value or "")


def title_of(entry: CSL) -> str:
    value = entry.get("title", "")
    if isinstance(value, list):
        return value[0] if value else ""
    return str(value or "")


def doi_url(entry: CSL) -> str:
    doi = entry.get("DOI") or entry.get("doi")
    if doi:
        doi = str(doi).strip()
        return doi if doi.startswith("http") else f"https://doi.org/{doi}"
    return str(entry.get("URL") or entry.get("url") or "")


def sort_key(entry: CSL) -> tuple:
    author_list = authors(entry)
    first = family_name(author_list[0]) if author_list else title_of(entry)
    return (first.lower(), year(entry), title_of(entry).lower())


# --- Kerangka gaya -----------------------------------------------------------


@dataclass
class CitationStyle:
    """Satu gaya sitasi.

    ``numeric`` menentukan bentuk sitasi dalam teks (angka atau penulis-tahun),
    sekaligus urutan daftar pustaka: gaya numerik urut kemunculan, gaya
    penulis-tahun urut abjad.
    """

    key: str
    label: str
    numeric: bool = False
    et_al_term: str = "et al."
    et_al_min: int = 3
    et_al_after: int = 1

    def in_text(self, entry: CSL, locator: str | None = None, index: int | None = None) -> str:
        raise NotImplementedError

    def bibliography(self, entry: CSL, index: int | None = None) -> str:
        raise NotImplementedError

    def _authors_in_text(self, entry: CSL) -> str:
        author_list = authors(entry)
        if not author_list:
            org = entry.get("publisher") or title_of(entry)
            return str(org)[:60]
        names = [family_name(a) for a in author_list if family_name(a)]
        if not names:
            return title_of(entry)[:60]
        if len(names) == 1:
            return names[0]
        if len(names) >= self.et_al_min:
            return f"{names[0]} {self.et_al_term}"
        return f"{names[0]} & {names[1]}"


class APAStyle(CitationStyle):
    """APA edisi ke-7."""

    def in_text(self, entry, locator=None, index=None) -> str:
        base = f"({self._authors_in_text(entry)}, {year(entry)}"
        return f"{base}, {locator})" if locator else f"{base})"

    def bibliography(self, entry, index=None) -> str:
        author_list = authors(entry)
        names = []
        for author in author_list[:20]:
            fam = family_name(author)
            ini = initials(author)
            names.append(f"{fam}, {ini}".strip().rstrip(",") if ini else fam)
        if len(names) > 1:
            author_part = ", ".join(names[:-1]) + f", & {names[-1]}"
        elif names:
            author_part = names[0]
        else:
            author_part = str(entry.get("publisher") or "")

        pieces = [f"{author_part} ({year(entry)}). {title_of(entry)}."]
        journal = container(entry)
        if journal:
            locus = journal
            if entry.get("volume"):
                locus += f", {entry['volume']}"
                if entry.get("issue"):
                    locus += f"({entry['issue']})"
            if page_range(entry):
                locus += f", {page_range(entry)}"
            pieces.append(f"{locus}.")
        elif entry.get("publisher"):
            pieces.append(f"{entry['publisher']}.")
        link = doi_url(entry)
        if link:
            pieces.append(link)
        return " ".join(p for p in pieces if p).strip()


class HarvardStyle(CitationStyle):
    def in_text(self, entry, locator=None, index=None) -> str:
        base = f"({self._authors_in_text(entry)} {year(entry)}"
        return f"{base}, {locator})" if locator else f"{base})"

    def bibliography(self, entry, index=None) -> str:
        names = []
        for author in authors(entry):
            fam = family_name(author)
            ini = initials(author, spaced=False)
            names.append(f"{fam}, {ini}" if ini else fam)
        if len(names) > 1:
            author_part = ", ".join(names[:-1]) + f" and {names[-1]}"
        elif names:
            author_part = names[0]
        else:
            author_part = str(entry.get("publisher") or "")

        pieces = [f"{author_part} ({year(entry)}) '{title_of(entry)}'"]
        journal = container(entry)
        if journal:
            locus = journal
            if entry.get("volume"):
                locus += f", {entry['volume']}"
                if entry.get("issue"):
                    locus += f"({entry['issue']})"
            if page_range(entry):
                locus += f", pp. {page_range(entry)}"
            pieces.append(f", {locus}.")
        else:
            pieces.append(f". {entry.get('publisher', '')}.")
        link = doi_url(entry)
        if link:
            pieces.append(f" Tersedia pada: {link}")
        return "".join(pieces).replace(" .", ".").strip()


class IEEEStyle(CitationStyle):
    def in_text(self, entry, locator=None, index=None) -> str:
        number = index if index is not None else 1
        return f"[{number}, {locator}]" if locator else f"[{number}]"

    def bibliography(self, entry, index=None) -> str:
        names = []
        for author in authors(entry):
            fam = family_name(author)
            ini = initials(author)
            names.append(f"{ini} {fam}".strip() if ini else fam)
        if len(names) > 6:
            author_part = f"{names[0]} et al."
        elif len(names) > 1:
            author_part = ", ".join(names[:-1]) + f", and {names[-1]}"
        elif names:
            author_part = names[0]
        else:
            author_part = str(entry.get("publisher") or "")

        pieces = [f"{author_part}, \"{title_of(entry)},\""]
        journal = container(entry)
        if journal:
            pieces.append(f" {journal},")
            if entry.get("volume"):
                pieces.append(f" vol. {entry['volume']},")
            if entry.get("issue"):
                pieces.append(f" no. {entry['issue']},")
            if page_range(entry):
                pieces.append(f" pp. {page_range(entry)},")
        elif entry.get("publisher"):
            pieces.append(f" {entry['publisher']},")
        pieces.append(f" {year(entry)}.")
        prefix = f"[{index}] " if index is not None else ""
        return (prefix + "".join(pieces)).strip()


class VancouverStyle(CitationStyle):
    def in_text(self, entry, locator=None, index=None) -> str:
        number = index if index is not None else 1
        return f"({number} hlm. {locator})" if locator else f"({number})"

    def bibliography(self, entry, index=None) -> str:
        names = []
        for author in authors(entry)[:6]:
            fam = family_name(author)
            ini = initials(author, dotted=False, spaced=False)
            names.append(f"{fam} {ini}".strip() if ini else fam)
        author_part = ", ".join(names)
        if len(authors(entry)) > 6:
            author_part += ", et al"

        pieces = [f"{author_part}. {title_of(entry)}."]
        journal = container(entry)
        if journal:
            locus = f" {journal}. {year(entry)}"
            if entry.get("volume"):
                locus += f";{entry['volume']}"
                if entry.get("issue"):
                    locus += f"({entry['issue']})"
            if page_range(entry):
                locus += f":{page_range(entry)}"
            pieces.append(locus + ".")
        else:
            pieces.append(f" {entry.get('publisher', '')}. {year(entry)}.")
        prefix = f"{index}. " if index is not None else ""
        return (prefix + "".join(pieces)).replace("  ", " ").strip()


@dataclass
class CampusStyle(APAStyle):
    """Gaya khusus kampus — turunan APA dengan parameter dari pedoman.

    Banyak fakultas memakai APA dengan penyesuaian kecil: 'dkk.' menggantikan
    'et al.', ambang jumlah penulis berbeda, atau pemisah tahun memakai titik.
    Parameter itu datang dari pedoman yang diunggah, bukan ditebak.
    """

    year_separator: str = ","
    overrides: dict = field(default_factory=dict)

    def in_text(self, entry, locator=None, index=None) -> str:
        base = f"({self._authors_in_text(entry)}{self.year_separator} {year(entry)}"
        return f"{base}, {locator})" if locator else f"{base})"


STYLES: dict[str, CitationStyle] = {
    "apa": APAStyle(key="apa", label="APA (edisi ke-7)"),
    "harvard": HarvardStyle(key="harvard", label="Harvard"),
    "ieee": IEEEStyle(key="ieee", label="IEEE", numeric=True),
    "vancouver": VancouverStyle(key="vancouver", label="Vancouver", numeric=True),
}


def get_style(key: str, ruleset: dict | None = None) -> CitationStyle:
    """Ambil gaya sitasi; 'kampus' dibangun dari pedoman yang berlaku."""
    key = (key or "apa").lower()
    if key in ("kampus", "custom"):
        opts = (ruleset or {}).get("citation_options", {})
        return CampusStyle(
            key="kampus",
            label=opts.get("label", "Gaya kampus"),
            et_al_term=opts.get("et_al_term", "dkk."),
            et_al_min=int(opts.get("et_al_min", 3)),
            year_separator=opts.get("year_separator", ","),
        )
    return STYLES.get(key, STYLES["apa"])


def render_in_text(
    style: CitationStyle, entry: CSL, locator: str | None = None, index: int | None = None
) -> str:
    return style.in_text(entry, locator=locator, index=index)


def render_bibliography(
    style: CitationStyle, entries: list[CSL], order: list[str] | None = None
) -> list[dict]:
    """Susun daftar pustaka.

    Gaya numerik mengikuti urutan kemunculan sitasi dalam teks (``order``);
    gaya penulis-tahun diurutkan menurut abjad nama penulis.
    """
    by_key = {e.get("id"): e for e in entries}
    if style.numeric:
        ordered: list[CSL] = []
        for citekey in order or []:
            entry = by_key.get(citekey)
            if entry is not None and entry not in ordered:
                ordered.append(entry)
        for entry in entries:
            if entry not in ordered:
                ordered.append(entry)
    else:
        ordered = sorted(entries, key=sort_key)

    return [
        {
            "citekey": entry.get("id"),
            "index": index,
            "text": style.bibliography(entry, index=index if style.numeric else None),
        }
        for index, entry in enumerate(ordered, start=1)
    ]


def build_index_map(style: CitationStyle, order: list[str]) -> dict[str, int]:
    """Peta citekey ke nomor rujukan untuk gaya numerik."""
    if not style.numeric:
        return {}
    return {key: index for index, key in enumerate(dict.fromkeys(order), start=1)}
