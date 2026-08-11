"""Konversi Naskah: memadatkan tugas akhir menjadi artikel IMRAD.

Kewajiban publikasi tidak perlu dimulai dari halaman kosong (Bagian 4.8).
Skripsi 18.000 kata dan artikel jurnal 6.000 kata memuat penelitian yang sama;
yang berbeda hanyalah berapa banyak yang boleh diceritakan.

Yang dikerjakan modul ini adalah pemetaan struktural yang deterministik —
bagian mana masuk ke mana, berapa anggaran kata tiap bagian, tabel dan sitasi
mana yang wajib ikut. Pemadatan kalimatnya tetap pekerjaan penulis, dibantu
model per bagian. Tidak ada bab yang ditulis ulang sekali jalan.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from .. import db
from .manuscript import Manuscript, load_manuscript
from .worktypes import STRUKTUR_IMRAD, WorkType, get_work_type

#: Peta peran bagian tugas akhir ke bagian IMRAD.
ROLE_TO_IMRAD: dict[str, str] = {
    "latar_belakang": "Pendahuluan",
    "rumusan_masalah": "Pendahuluan",
    "tujuan": "Pendahuluan",
    "landasan_teori": "Pendahuluan",
    "penelitian_terdahulu": "Pendahuluan",
    "kerangka_berpikir": "Pendahuluan",
    "hipotesis": "Pendahuluan",
    "metode": "Metode",
    "populasi_sampel": "Metode",
    "instrumen": "Metode",
    "teknik_analisis": "Metode",
    "hasil": "Hasil",
    "pembahasan": "Pembahasan",
    "simpulan": "Simpulan",
    "saran": "Simpulan",
    "abstrak": "Abstrak",
}

#: Bagian yang lazimnya tidak ikut ke artikel.
DROPPED_ROLES = {"manfaat", "batasan"}

#: Anggaran kata tiap bagian artikel, sebagai bagian dari total target.
IMRAD_BUDGET: dict[str, float] = {
    "Abstrak": 0.04,
    "Pendahuluan": 0.22,
    "Metode": 0.18,
    "Hasil": 0.26,
    "Pembahasan": 0.25,
    "Simpulan": 0.05,
}


@dataclass
class SectionPlan:
    target: str
    sources: list[dict] = field(default_factory=list)
    target_words: int = 0
    source_words: int = 0

    @property
    def compression(self) -> float:
        return round(self.target_words / self.source_words, 3) if self.source_words else 0.0

    def to_dict(self) -> dict:
        return {
            "target": self.target,
            "target_words": self.target_words,
            "source_words": self.source_words,
            "compression": self.compression,
            "sources": self.sources,
        }


@dataclass
class ConversionPlan:
    source_project_id: int
    target_words: int
    sections: list[SectionPlan] = field(default_factory=list)
    dropped: list[dict] = field(default_factory=list)
    carried_tables: list[dict] = field(default_factory=list)
    citekeys: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "source_project_id": self.source_project_id,
            "target_words": self.target_words,
            "source_words": sum(s.source_words for s in self.sections),
            "overall_compression": round(
                self.target_words / max(sum(s.source_words for s in self.sections), 1), 3
            ),
            "sections": [s.to_dict() for s in self.sections],
            "dropped": self.dropped,
            "carried_tables": self.carried_tables,
            "citekeys": self.citekeys,
            "warnings": self.warnings,
        }


def plan_conversion(
    manuscript: Manuscript, target_words: int = 6000
) -> ConversionPlan:
    """Susun rencana pemadatan, tanpa mengubah apa pun.

    Rencana ditampilkan lebih dahulu supaya penulis melihat apa yang akan
    dipertahankan dan apa yang akan hilang — keputusan itu miliknya, bukan
    milik sistem.
    """
    plan = ConversionPlan(source_project_id=manuscript.project_id, target_words=target_words)
    buckets: dict[str, SectionPlan] = {
        name: SectionPlan(target=name) for name in IMRAD_BUDGET
    }

    for section in manuscript.walk():
        words = section.own_word_count
        if not words and not section.blocks:
            continue

        role = section.role or ""
        if role in DROPPED_ROLES:
            plan.dropped.append(
                {
                    "title": section.title,
                    "word_count": words,
                    "reason": (
                        "Bagian ini lazimnya tidak dimuat pada artikel jurnal; isinya "
                        "diserap ke pendahuluan bila memang penting."
                    ),
                }
            )
            continue

        target = ROLE_TO_IMRAD.get(role)
        if target is None:
            target = _guess_from_title(section.title)
        if target is None:
            plan.dropped.append(
                {
                    "title": section.title,
                    "word_count": words,
                    "reason": "Tidak ada padanan langsung di struktur IMRAD.",
                }
            )
            continue

        combined = (
            target == "Hasil"
            and "hasil" in section.title.lower()
            and "pembahasan" in section.title.lower()
        )
        buckets[target].sources.append(
            {
                "section_id": section.id,
                "number": section.number,
                "title": section.title,
                "role": role or None,
                "word_count": words,
                "combined": combined,
            }
        )
        buckets[target].source_words += words
        if combined:
            plan.warnings.append(
                f"'{section.title}' menggabungkan hasil dan pembahasan, sedangkan IMRAD "
                f"memisahkan keduanya. Isinya ditaruh di bagian Hasil; pindahkan bagian "
                f"yang menafsirkan temuan ke Pembahasan."
            )

    for name, budget in IMRAD_BUDGET.items():
        buckets[name].target_words = int(round(target_words * budget))

    plan.sections = [buckets[name] for name in IMRAD_BUDGET]

    # Tabel hasil ikut karena di situlah temuan utama berada.
    captions = manuscript.numbered_captions()
    for label, caption in captions.items():
        plan.carried_tables.append(
            {"label": label, "kind": caption["kind"], "number": caption["number"],
             "caption": caption["caption"]}
        )
    plan.citekeys = manuscript.citekeys()

    _add_warnings(plan)
    return plan


def _guess_from_title(title: str) -> str | None:
    lowered = title.lower()
    # Banyak pedoman menggabungkan hasil dan pembahasan dalam satu bab, sedangkan
    # IMRAD memisahkannya. Isinya ditaruh di Hasil dan pemisahannya diingatkan.
    if "hasil" in lowered and "pembahasan" in lowered:
        return "Hasil"
    for keyword, target in (
        ("pendahuluan", "Pendahuluan"),
        ("tinjauan", "Pendahuluan"),
        ("teori", "Pendahuluan"),
        ("metode", "Metode"),
        ("metodologi", "Metode"),
        ("hasil", "Hasil"),
        ("pembahasan", "Pembahasan"),
        ("penutup", "Simpulan"),
        ("simpulan", "Simpulan"),
        ("kesimpulan", "Simpulan"),
        ("abstrak", "Abstrak"),
    ):
        if keyword in lowered:
            return target
    return None


def _add_warnings(plan: ConversionPlan) -> None:
    source_words = sum(s.source_words for s in plan.sections)
    if source_words and source_words < plan.target_words:
        plan.warnings.append(
            f"Naskah sumber hanya {source_words} kata, lebih pendek daripada target artikel "
            f"{plan.target_words} kata. Yang dibutuhkan di sini bukan pemadatan melainkan "
            f"pengembangan — periksa apakah naskah tugas akhir memang sudah lengkap."
        )

    for section in plan.sections:
        if section.source_words and section.compression < 0.25:
            plan.warnings.append(
                f"{section.target} harus dipadatkan dari {section.source_words} menjadi "
                f"{section.target_words} kata ({int(section.compression * 100)}%). "
                f"Pemadatan sebesar ini menuntut pemilihan temuan, bukan sekadar "
                f"pemotongan kalimat."
            )
        if not section.sources and section.target != "Abstrak":
            plan.warnings.append(
                f"Tidak ada bagian naskah yang terpetakan ke {section.target}. Periksa "
                f"peran bagian pada kerangka tugas akhir Anda."
            )
    if not plan.citekeys:
        plan.warnings.append(
            "Naskah sumber belum memuat satu pun sitasi; artikel jurnal menuntut "
            "rujukan yang lengkap."
        )


def apply_conversion(
    conn: sqlite3.Connection,
    source_project: dict,
    plan: ConversionPlan,
    name: str | None = None,
    work_type_key: str = "artikel_jurnal",
) -> dict:
    """Bangun proyek artikel baru berisi bahan yang sudah dipetakan.

    Isi bagian dibawa apa adanya sebagai bahan mentah beserta penanda asalnya,
    lalu ditandai untuk dipadatkan. Yang dikerjakan sistem adalah memindahkan
    dan menganggarkan; memadatkan tetap pekerjaan penulis.
    """
    work_type: WorkType = get_work_type(work_type_key)
    project_id = db.insert(
        conn,
        "projects",
        account_id=source_project.get("account_id"),
        name=name or f"Artikel dari {source_project['name']}",
        work_type=work_type.key,
        research_type=source_project.get("research_type", "none"),
        field_of_study=source_project.get("field_of_study"),
        target_words=plan.target_words,
        deadline=None,
        citation_style=source_project.get("citation_style") or work_type.citation_style,
        created_at=db.now(),
        updated_at=db.now(),
    )

    source_manuscript = load_manuscript(conn, source_project["id"])
    blocks_by_section: dict[int, list] = {}
    for section, block in source_manuscript.all_blocks():
        blocks_by_section.setdefault(section.id, []).append(block)

    template_by_title = {t.title: t for t in STRUKTUR_IMRAD}
    for position, section_plan in enumerate(plan.sections):
        template = template_by_title.get(section_plan.target)
        section_id = db.insert(
            conn,
            "sections",
            project_id=project_id,
            parent_id=None,
            position=position,
            title=section_plan.target,
            role=template.role if template else None,
            target_words=section_plan.target_words,
            status="belum",
            created_at=db.now(),
        )

        block_position = 0
        for source in section_plan.sources:
            for block in blocks_by_section.get(source["section_id"], []):
                import json

                meta = dict(block.meta or {})
                meta.update(
                    {
                        "asal_bagian": source["title"],
                        "asal_nomor": source["number"],
                        "perlu_dipadatkan": True,
                    }
                )
                db.insert(
                    conn,
                    "blocks",
                    section_id=section_id,
                    position=block_position,
                    kind=block.kind,
                    content=block.content,
                    meta_json=json.dumps(meta, ensure_ascii=False),
                    updated_at=db.now(),
                )
                block_position += 1

    # Pustaka referensi ikut pindah agar sitasi dalam teks tetap tertaut.
    carried = _copy_references(conn, source_project["id"], project_id)

    return {
        "project_id": project_id,
        "name": name or f"Artikel dari {source_project['name']}",
        "sections_created": len(plan.sections),
        "references_copied": carried,
        "plan": plan.to_dict(),
        "note": (
            "Isi bagian dibawa apa adanya sebagai bahan mentah dan ditandai "
            "'perlu_dipadatkan', lengkap dengan asal babnya. Padatkan per bagian "
            "mengikuti anggaran kata yang sudah dihitung."
        ),
    }


def _copy_references(
    conn: sqlite3.Connection, source_project_id: int, target_project_id: int
) -> int:
    rows = db.fetch_all(
        conn, "SELECT * FROM refs WHERE project_id = ?", (source_project_id,)
    )
    for row in rows:
        db.insert(
            conn,
            "refs",
            project_id=target_project_id,
            citekey=row["citekey"],
            source_db=row["source_db"],
            external_id=row["external_id"],
            csl_json=row["csl_json"],
            # Status verifikasi ikut apa adanya; ia sifat sumbernya, bukan proyeknya.
            verified=row["verified"],
            abstract=row["abstract"],
            pdf_path=row["pdf_path"],
            added_at=db.now(),
        )
    return len(rows)
