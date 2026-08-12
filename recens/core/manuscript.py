"""Model naskah terstruktur — dasar bagi format otomatis dan pemeriksaan.

Editor Recens mengenali bab, sub-bab, kutipan, tabel, gambar, dan caption
sebagai bagian terpisah, bukan teks datar (Bagian 4.1). Seluruh fitur hilir
— auto-format, cek silang sitasi, cek batas panjang, ekspor — bekerja di atas
struktur ini.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Iterator

from .. import db
from .worktypes import SectionTemplate, WorkType

#: Penanda sitasi di dalam teks: [[cite:sugiyono2019]] atau [[cite:key|hlm. 23]]
CITE_PATTERN = re.compile(r"\[\[cite:([A-Za-z0-9_.\-]+)(?:\|([^\]]*))?\]\]")

#: Penanda silang ke tabel/gambar: [[ref:tabel:uji_validitas]]
XREF_PATTERN = re.compile(r"\[\[ref:(tabel|gambar):([A-Za-z0-9_.\-]+)\]\]")

BLOCK_KINDS = ("paragraph", "quote", "list", "table", "figure", "equation")


@dataclass
class Block:
    """Satu satuan isi di dalam sebuah bagian."""

    id: int
    section_id: int
    position: int
    kind: str
    content: str
    meta: dict = field(default_factory=dict)

    @property
    def word_count(self) -> int:
        if self.kind in ("table", "figure"):
            return 0
        return count_words(strip_markers(self.content))

    @property
    def label(self) -> str | None:
        """Label acuan silang, mis. 'uji_validitas' pada tabel."""
        return self.meta.get("label")

    @property
    def caption(self) -> str | None:
        return self.meta.get("caption")


@dataclass
class Section:
    """Bab atau sub-bab."""

    id: int
    project_id: int
    parent_id: int | None
    position: int
    title: str
    role: str | None
    target_words: int
    status: str
    blocks: list[Block] = field(default_factory=list)
    children: list["Section"] = field(default_factory=list)
    #: Nomor terhitung, mis. "1" untuk BAB I atau "1.2" untuk sub-bab kedua.
    number: str = ""
    level: int = 1

    @property
    def word_count(self) -> int:
        own = sum(b.word_count for b in self.blocks)
        return own + sum(c.word_count for c in self.children)

    @property
    def own_word_count(self) -> int:
        return sum(b.word_count for b in self.blocks)

    def walk(self) -> Iterator["Section"]:
        yield self
        for child in self.children:
            yield from child.walk()

    def text(self) -> str:
        parts = [self.title]
        parts.extend(strip_markers(b.content) for b in self.blocks if b.kind != "figure")
        for child in self.children:
            parts.append(child.text())
        return "\n\n".join(p for p in parts if p.strip())


@dataclass
class Manuscript:
    """Seluruh naskah satu proyek."""

    project_id: int
    sections: list[Section] = field(default_factory=list)

    def walk(self) -> Iterator[Section]:
        for section in self.sections:
            yield from section.walk()

    def all_blocks(self) -> Iterator[tuple[Section, Block]]:
        for section in self.walk():
            for block in section.blocks:
                yield section, block

    def find_section(self, section_id: int) -> Section | None:
        for section in self.walk():
            if section.id == section_id:
                return section
        return None

    def sections_by_role(self, role: str) -> list[Section]:
        return [s for s in self.walk() if s.role == role]

    @property
    def word_count(self) -> int:
        return sum(s.word_count for s in self.sections)

    @property
    def target_words(self) -> int:
        return sum(s.target_words for s in self.walk())

    def text(self) -> str:
        return "\n\n".join(s.text() for s in self.sections)

    def citekeys(self) -> list[str]:
        """Seluruh citekey yang dipakai dalam teks, urut kemunculan."""
        seen: list[str] = []
        for _section, block in self.all_blocks():
            for key, _locator in iter_citations(block.content):
                if key not in seen:
                    seen.append(key)
        return seen

    def citations_with_location(self) -> list[dict]:
        out = []
        for section, block in self.all_blocks():
            for key, locator in iter_citations(block.content):
                out.append(
                    {
                        "citekey": key,
                        "locator": locator,
                        "section_id": section.id,
                        "section_title": section.title,
                        "block_id": block.id,
                    }
                )
        return out

    def numbered_captions(self) -> dict[str, dict]:
        """Penomoran caption berbasis bab: Tabel 4.1, Gambar 2.3, dst."""
        counters: dict[tuple[str, str], int] = {}
        result: dict[str, dict] = {}
        for section in self.walk():
            chapter = section.number.split(".")[0] if section.number else "1"
            for block in section.blocks:
                if block.kind not in ("table", "figure"):
                    continue
                kind_id = "Tabel" if block.kind == "table" else "Gambar"
                key = (kind_id, chapter)
                counters[key] = counters.get(key, 0) + 1
                number = f"{chapter}.{counters[key]}"
                label = block.label or f"{block.kind}_{block.id}"
                result[label] = {
                    "kind": kind_id,
                    "number": number,
                    "caption": block.caption or "",
                    "full": f"{kind_id} {number}. {block.caption or ''}".strip(),
                    "block_id": block.id,
                    "section_id": section.id,
                }
        return result


# --- Utilitas teks -----------------------------------------------------------


def count_words(text: str) -> int:
    return len(re.findall(r"\b[\w'’-]+\b", text, flags=re.UNICODE))


def strip_markers(text: str) -> str:
    """Buang penanda internal agar hitungan kata dan pemeriksaan bahasa bersih."""
    text = CITE_PATTERN.sub("", text)
    text = XREF_PATTERN.sub("", text)
    return text


def iter_citations(text: str) -> Iterator[tuple[str, str | None]]:
    for match in CITE_PATTERN.finditer(text):
        yield match.group(1), match.group(2)


def make_citation_marker(citekey: str, locator: str | None = None) -> str:
    return f"[[cite:{citekey}|{locator}]]" if locator else f"[[cite:{citekey}]]"


# --- Pemuatan & penyimpanan --------------------------------------------------

ROMAN = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]


def _assign_numbers(sections: list[Section], prefix: str = "", level: int = 1) -> None:
    for index, section in enumerate(sections, start=1):
        section.number = f"{prefix}{index}" if not prefix else f"{prefix}.{index}"
        section.level = level
        _assign_numbers(section.children, prefix=section.number, level=level + 1)


def load_manuscript(conn: sqlite3.Connection, project_id: int) -> Manuscript:
    section_rows = db.fetch_all(
        conn,
        "SELECT * FROM sections WHERE project_id = ? ORDER BY parent_id IS NOT NULL, "
        "parent_id, position, id",
        (project_id,),
    )
    block_rows = db.fetch_all(
        conn,
        "SELECT b.* FROM blocks b JOIN sections s ON s.id = b.section_id "
        "WHERE s.project_id = ? ORDER BY b.section_id, b.position, b.id",
        (project_id,),
    )

    blocks_by_section: dict[int, list[Block]] = {}
    for row in block_rows:
        try:
            meta = json.loads(row["meta_json"] or "{}")
        except json.JSONDecodeError:
            meta = {}
        blocks_by_section.setdefault(row["section_id"], []).append(
            Block(
                id=row["id"],
                section_id=row["section_id"],
                position=row["position"],
                kind=row["kind"],
                content=row["content"],
                meta=meta,
            )
        )

    sections: dict[int, Section] = {}
    for row in section_rows:
        sections[row["id"]] = Section(
            id=row["id"],
            project_id=row["project_id"],
            parent_id=row["parent_id"],
            position=row["position"],
            title=row["title"],
            role=row["role"],
            target_words=row["target_words"],
            status=row["status"],
            blocks=blocks_by_section.get(row["id"], []),
        )

    roots: list[Section] = []
    for section in sections.values():
        if section.parent_id and section.parent_id in sections:
            sections[section.parent_id].children.append(section)
        else:
            roots.append(section)

    roots.sort(key=lambda s: (s.position, s.id))
    for section in sections.values():
        section.children.sort(key=lambda s: (s.position, s.id))

    _assign_numbers(roots)
    return Manuscript(project_id=project_id, sections=roots)


def create_sections_from_template(
    conn: sqlite3.Connection,
    project_id: int,
    templates: tuple[SectionTemplate, ...],
    total_target: int,
    parent_id: int | None = None,
    parent_share: float = 1.0,
) -> list[int]:
    """Bangun kerangka bab dan sub-bab beserta target jumlah kata tiap bagian."""
    created: list[int] = []
    total_weight = sum(t.weight for t in templates) or 1.0
    for position, template in enumerate(templates):
        share = parent_share * (template.weight / total_weight)
        target = int(round(total_target * share)) if not template.children else 0
        section_id = db.insert(
            conn,
            "sections",
            project_id=project_id,
            parent_id=parent_id,
            position=position,
            title=template.title,
            role=template.role,
            target_words=target,
            status="belum",
            created_at=db.now(),
        )
        created.append(section_id)
        if template.children:
            created.extend(
                create_sections_from_template(
                    conn,
                    project_id,
                    template.children,
                    total_target,
                    parent_id=section_id,
                    parent_share=share,
                )
            )
    return created


def build_default_outline(
    conn: sqlite3.Connection, project_id: int, work_type: WorkType, target_words: int
) -> list[int]:
    return create_sections_from_template(
        conn, project_id, work_type.structure, target_words or work_type.default_target_words
    )


def snapshot(manuscript: Manuscript) -> dict:
    """Bentuk serialisasi untuk riwayat versi (Bagian 4.7)."""

    def dump_section(section: Section) -> dict:
        return {
            "title": section.title,
            "role": section.role,
            "number": section.number,
            "target_words": section.target_words,
            "status": section.status,
            "blocks": [
                {"kind": b.kind, "content": b.content, "meta": b.meta, "position": b.position}
                for b in section.blocks
            ],
            "children": [dump_section(c) for c in section.children],
        }

    return {
        "project_id": manuscript.project_id,
        "word_count": manuscript.word_count,
        "sections": [dump_section(s) for s in manuscript.sections],
    }


def restore_snapshot(conn: sqlite3.Connection, project_id: int, data: dict) -> None:
    """Pulihkan versi lama — revisi bisa dikembalikan bila ternyata keliru arah."""
    conn.execute("DELETE FROM sections WHERE project_id = ?", (project_id,))
    conn.commit()

    def restore(nodes: list[dict], parent_id: int | None) -> None:
        for position, node in enumerate(nodes):
            section_id = db.insert(
                conn,
                "sections",
                project_id=project_id,
                parent_id=parent_id,
                position=position,
                title=node["title"],
                role=node.get("role"),
                target_words=node.get("target_words", 0),
                status=node.get("status", "belum"),
                created_at=db.now(),
            )
            for block_position, block in enumerate(node.get("blocks", [])):
                db.insert(
                    conn,
                    "blocks",
                    section_id=section_id,
                    position=block_position,
                    kind=block.get("kind", "paragraph"),
                    content=block.get("content", ""),
                    meta_json=json.dumps(block.get("meta", {}), ensure_ascii=False),
                    updated_at=db.now(),
                )
            restore(node.get("children", []), section_id)

    restore(data.get("sections", []), None)


def section_outline(manuscript: Manuscript) -> list[dict]:
    """Ringkasan kerangka untuk dashboard progres (Bagian 4.7)."""
    out = []
    for section in manuscript.walk():
        words = section.word_count
        target = section.target_words or sum(c.target_words for c in section.walk())
        out.append(
            {
                "id": section.id,
                "number": section.number,
                "level": section.level,
                "title": section.title,
                "role": section.role,
                "status": section.status,
                "word_count": words,
                "target_words": target,
                "progress": round(words / target, 3) if target else 0.0,
                "block_count": len(section.blocks),
            }
        )
    return out
